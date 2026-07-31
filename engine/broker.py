
from typing import Dict, Any, List, Tuple
from enum import Enum
import re
import json

from utils.json_logger import RuleEngineLogger
from .pattern_matchers import ISTVONPatternMatcher
from .context_analyzers import ContextAnalyzer
from .llm_mapper import LLMISTVONMapper
from .completion_rules import ISTVONCompletionEngine
from .istvon_schema import ISTVONSchema


class BrokerDecision(Enum):
    """Broker decision types"""
    ALLOW = "ALLOW"           # Safe to proceed with LLM enhancement
    NEEDS_FIX = "NEEDS_FIX"   # Contains potentially risky content, needs sanitization or clarification
    BLOCK = "BLOCK"           # Too dangerous, block completely


class ISTVONBroker:

    def __init__(self):
        self.pattern_matcher = ISTVONPatternMatcher()
        self.context_analyzer = ContextAnalyzer()
        self.llm_mapper = LLMISTVONMapper()
        self.completion_engine = ISTVONCompletionEngine()
        self.schema_validator = ISTVONSchema()
        self.json_logger = RuleEngineLogger()

        # Build precompiled unsafe pattern lists (single words use word boundaries)
        self.unsafe_patterns = {
            "malicious": [
                r"hack\b", r"exploit\b", r"attack\b", r"malware\b", r"virus\b", r"trojan\b",
                r"phish(?:ing)?\b", r"phishing\b", r"inject(?:ion)?\b", r"brute\s*force\b",
                r"ransomware\b", r"keylogger\b", r"spyware\b", r"rootkit\b",
                r"steal(?:ing)?\b", r"data\s*theft\b", r"credential\s*harvest(?:ing)?\b",
                r"data\s*breach\b", r"unauthorized\s*access\b"
            ],
            "inappropriate": [
                r"explicit\b", r"pornographic\b", r"adult content", r"hate speech", r"discrimination",
                r"racist\b", r"harassment\b", r"bully(?:ing|ied)?\b"
            ],
            "sensitive": [
                r"personal data\b", r"private information\b", r"confidential\b",
                r"financial\b", r"bank(?:ing)?\b", r"credit card\b", r"\bssn\b",
                r"medical\b", r"health records\b", r"patient data\b"
            ],
            "dangerous": [
                r"make(?: an)? explosive\b", r"create(?: an)? bomb\b", r"build(?: a)? weapon\b",
                r"how to kill\b", r"how to harm\b", r"how to hurt\b", r"suicide\b",
                r"attack(?: people)?\b", r"illegal\b", r"drug manufacture\b", r"poison recipe\b"
            ]
        }
        # Compile patterns for performance and case-insensitivity
        self.compiled_unsafe = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in self.unsafe_patterns.items()
        }

        # Numeric severity scoring per category (tunable)
        self.severity_score_map = {
            "malicious": 5,
            "dangerous": 5,
            "sensitive": 3,
            "inappropriate": 2
        }

        # Allowlist patterns (benign collocations that would otherwise match)
        self.allowlist_patterns = [
            re.compile(r"\bhackathon\b", re.IGNORECASE),
            re.compile(r"\bethical hacking\b", re.IGNORECASE),
            re.compile(r"\bpenetration testing\b", re.IGNORECASE),
            re.compile(r"\bhow to prevent phishing\b", re.IGNORECASE),
            re.compile(r"\bprevent phishing\b", re.IGNORECASE),
            re.compile(r"\banti[- ]phishing\b", re.IGNORECASE),
        ]

        # Mitigation/intent words that indicate a benign/defensive intent nearby
        self.mitigation_indicators = [
            r"prevent", r"avoid", r"stop", r"protect", r"secure", r"defend", r"mitigate",
            r"how to prevent", r"how to avoid", r"how to stop"
        ]
        self.mitigation_res = [re.compile(r'\b' + w + r'\b', re.IGNORECASE) for w in self.mitigation_indicators]

        # COSTAR gap patterns (unchanged semantics but compiled)
        self.costar_gaps = {
            "context": [re.compile(r"\b(context|background|situation|about|regarding)\b", re.I)],
            "objective": [re.compile(r"\b(goal|objective|purpose|aim|to\s+(?:write|create|make|build))\b", re.I)],
            "success": [re.compile(r"\b(success|completion|done|finished|means|should)\b", re.I)],
            "timeline": [re.compile(r"\b(when|time|deadline|schedule|by|before)\b", re.I)],
            "audience": [re.compile(r"\b(for|target|audience|recipient|customers|users|people)\b", re.I)],
            "resources": [re.compile(r"\b(using|with|tools|resources|via|through)\b", re.I)]
        }

        # Tunable thresholds (kept in-class to avoid changing other files)
        self._high_risk_threshold = 5   # score >= this -> high risk
        self._medium_risk_threshold = 2  # score >= this -> medium risk
        self._completeness_threshold = 0.3  # below this -> needs enhancement

    def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt and make broker decision"""
        # Step 1: Safety analysis
        safety_result = self._analyze_safety(prompt)

        # Step 2: COSTAR gap analysis
        costar_gaps = self._analyze_costar_gaps(prompt)

        # Step 3: Context analysis
        context = self.context_analyzer.analyze_prompt_context(prompt)

        # Step 4: Make broker decision
        decision = self._make_broker_decision(safety_result, costar_gaps, context)

        return {
            "decision": decision,
            "safety_analysis": safety_result,
            "costar_gaps": costar_gaps,
            "context": context,
            "recommendations": self._get_recommendations(decision, safety_result, costar_gaps)
        }

    def _analyze_safety(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt for unsafe content with context-aware filtering"""
        prompt_lower = prompt.lower()
        issues = []
        total_score = 0

        # Quick allowlist short-circuit: if any allowlist full-pattern matches the prompt, treat as safe
        for allow_re in self.allowlist_patterns:
            if allow_re.search(prompt):
                return {
                    "risk_level": "low",
                    "issues": [],
                    "is_safe": True,
                    "score": 0,
                    "matches": []
                }

        # For every compiled pattern, find matches but skip them if context indicates mitigation intent
        for category, patterns in self.compiled_unsafe.items():
            for cre in patterns:
                for m in cre.finditer(prompt):
                    match_text = m.group(0)
                    span = m.span()

                    # Check for allowlist in a small window (20 chars before/after)
                    window_start = max(0, span[0] - 40)
                    window_end = min(len(prompt), span[1] + 40)
                    window = prompt[window_start:window_end]

                    # If mitigation indicators are present in the window, treat as a benign context
                    if any(r.search(window) for r in self.mitigation_res):
                        # lower severity: record but with reduced score
                        issue_score = max(1, int(self.severity_score_map.get(category, 1) / 2))
                        issues.append({
                            "category": category,
                            "pattern": cre.pattern,
                            "match": match_text,
                            "span": span,
                            "severity": "low_context",
                            "score": issue_score,
                            "context_window": window.strip()
                        })
                        total_score += issue_score
                        continue

                    # Otherwise, normal handling
                    issue_score = self.severity_score_map.get(category, 1)
                    issues.append({
                        "category": category,
                        "pattern": cre.pattern,
                        "match": match_text,
                        "span": span,
                        "severity": "normal",
                        "score": issue_score
                    })
                    total_score += issue_score

        # Apply multi-category bonus: if matches span 2+ distinct categories, add bonus
        matched_categories = set(i.get("category") for i in issues if i.get("severity") == "normal")
        if len(matched_categories) >= 2:
            total_score += len(matched_categories)  # bonus per distinct category

        # Determine overall risk level using numeric thresholds
        if total_score >= self._high_risk_threshold:
            risk_level = "high"
        elif total_score >= self._medium_risk_threshold:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "issues": issues,
            "is_safe": risk_level == "low",
            "score": total_score,
            "matches": issues  # keep same field name for compatibility
        }

    def _analyze_costar_gaps(self, prompt: str) -> Dict[str, Any]:
        """Analyze for COSTAR gaps (missing critical elements) using compiled patterns"""
        prompt_lower = prompt.lower()
        gaps = []

        for element, pattern_list in self.costar_gaps.items():
            if not any(p.search(prompt_lower) for p in pattern_list):
                gaps.append(element)

        completeness_score = (len(self.costar_gaps) - len(gaps)) / len(self.costar_gaps)
        return {
            "missing_elements": gaps,
            "completeness_score": completeness_score,
            "needs_enhancement": len(gaps) > 0
        }

    def _make_broker_decision(self, safety_result: Dict, costar_gaps: Dict, context: Dict) -> BrokerDecision:
        """Make broker decision based on safety analysis only.
        
        COSTAR gaps are informational and affect recommendations but do NOT
        change the safety verdict. A safe prompt with missing COSTAR elements
        is still ALLOW — the gaps are surfaced as suggestions.
        """
        # Block if high risk
        if safety_result["risk_level"] == "high":
            return BrokerDecision.BLOCK

        # Needs fix if medium risk (safety concern)
        if safety_result["risk_level"] == "medium":
            return BrokerDecision.NEEDS_FIX

        # Allow if safe — COSTAR gaps are informational only
        return BrokerDecision.ALLOW

    def _get_recommendations(self, decision: BrokerDecision, safety_result: Dict, costar_gaps: Dict) -> List[str]:
        """Get recommendations based on broker decision; returns both human and structured recommendations"""
        recommendations = []

        if decision == BrokerDecision.BLOCK:
            recommendations.append("BLOCKED: Content contains high-risk elements.")
            recommendations.append("Revise your prompt to remove instructions for harmful or illegal activities.")
            # provide structured suggestion for UI or API consumers
            recommendations.append(json.dumps({"action": "remove_high_risk_content"}))

        elif decision == BrokerDecision.NEEDS_FIX:
            if safety_result["risk_level"] != "low":
                recommendations.append("Contains potentially unsafe content; consider rephrasing or redacting sensitive terms.")
                recommendations.append(json.dumps({"action": "sanitize_or_rephrase"}))

            if costar_gaps["missing_elements"]:
                rec = "Missing critical elements: " + ", ".join(costar_gaps["missing_elements"])
                recommendations.append(rec)
                recommendations.append(json.dumps({"action": "add_context", "missing": costar_gaps["missing_elements"]}))
            else:
                recommendations.append("Consider clarifying objectives or audience for better results.")
        else:  # ALLOW
            recommendations.append("Safe to proceed with ISTVON enhancement.")
            if costar_gaps["completeness_score"] < 0.8:
                recommendations.append("Consider adding more details for better results.")
                recommendations.append(json.dumps({"action": "consider_more_details"}))

        return recommendations

    def process_with_broker(self, prompt: str) -> Dict[str, Any]:
        """Process prompt through broker with appropriate action"""
        analysis = self.analyze_prompt(prompt)
        decision = analysis["decision"]

        # Get decision reason
        reason = self._get_decision_reason(decision, analysis)

        # Log to JSON file
        try:
            self.json_logger.log_decision(prompt, decision.value, reason)
        except Exception:
            # Logging must not block processing
            pass

        broker_result = {
            "verdict": decision.value,
            "reason": reason,
            "prompt": prompt,
            "analysis": analysis
        }

        if decision == BrokerDecision.BLOCK:
            broker_result.update({
                "success": False,
                "decision": "BLOCK"
            })
            return broker_result

        elif decision == BrokerDecision.NEEDS_FIX:
            # Sanitize and enhance but keep original prompt for audit
            sanitized_info = self._sanitize_prompt(prompt, analysis)
            sanitized_prompt = sanitized_info.get("sanitized_prompt")
            redactions = sanitized_info.get("redactions")
            suggested_rewrite = sanitized_info.get("suggested_rewrite")

            enhanced_prompt = self._enhance_prompt(sanitized_prompt, analysis)

            broker_result.update({
                "success": True,
                "decision": "NEEDS_FIX",
                "original_prompt": prompt,
                "sanitized_prompt": sanitized_prompt,
                "redactions": redactions,
                "suggested_rewrite": suggested_rewrite,
                "enhanced_prompt": enhanced_prompt
            })
            return broker_result

        else:  # ALLOW
            # Proceed with normal ISTVON processing
            broker_result.update({
                "success": True,
                "decision": "ALLOW",
                "prompt": prompt
            })
            return broker_result

    def _sanitize_prompt(self, prompt: str, analysis: Dict = None) -> Dict[str, Any]:
        """Sanitize prompt by redacting risky tokens and returning a suggested rewrite.

        Returns a dict with:
        - sanitized_prompt: str
        - redactions: list of dict(original, replacement, category, span)
        - suggested_rewrite: str (a simple human-friendly suggestion)
        """
        if not prompt:
            return {"sanitized_prompt": "", "redactions": [], "suggested_rewrite": ""}

        sanitized = prompt
        redactions = []

        # Use the safety analysis matches if provided (more precise spans), else compute matches
        matches = []
        if analysis and "safety_analysis" in analysis:
            matches = analysis["safety_analysis"].get("matches") or analysis["safety_analysis"].get("issues") or []
        else:
            # fallback: run analysis to get matches
            matches = self._analyze_safety(prompt).get("matches", [])

        # Perform redaction using spans from matches; handle overlapping spans carefully
        # Build list of (start, end, replacement, original, category)
        spans = []
        for m in matches:
            try:
                span = m.get("span")
                if not span:
                    # try to find text occurrence
                    idx = sanitized.lower().find(m.get("match", "").lower())
                    if idx >= 0:
                        span = (idx, idx + len(m.get("match", "")))
                    else:
                        continue
                spans.append((span[0], span[1], "[REDACTED]", m.get("match", ""), m.get("category")))
            except Exception:
                continue

        # Merge overlapping spans and redact from end to start to preserve indices
        spans = sorted(spans, key=lambda x: (x[0], -x[1]))
        merged = []
        for s in spans:
            if not merged:
                merged.append(list(s))
            else:
                last = merged[-1]
                if s[0] <= last[1]:  # overlap
                    last[1] = max(last[1], s[1])
                    # keep category list
                    if isinstance(last[4], list):
                        last[4].append(s[4])
                    else:
                        last[4] = [last[4], s[4]]
                else:
                    merged.append(list(s))

        # Apply redactions
        out = []
        last_idx = 0
        for s in merged:
            start, end, replacement, original, category = s
            out.append(sanitized[last_idx:start])
            out.append(replacement)
            redactions.append({"original": original, "replacement": replacement, "category": category, "span": (start, end)})
            last_idx = end
        out.append(sanitized[last_idx:])
        sanitized_prompt = "".join(out).strip()

        # Build a very conservative suggested rewrite: replace REDACTED with a descriptive placeholder
        suggested_rewrite = sanitized_prompt.replace("[REDACTED]", "(sensitive term redacted)")
        # Add guidance for user to rephrase and include required COSTAR elements if missing
        missing = []
        if analysis and "costar_gaps" in analysis:
            missing = analysis["costar_gaps"].get("missing_elements", [])
        if missing:
            suggested_rewrite += " Please provide additional details: " + ", ".join(missing) + "."

        return {
            "sanitized_prompt": sanitized_prompt,
            "redactions": redactions,
            "suggested_rewrite": suggested_rewrite
        }

    def _enhance_prompt(self, prompt: str, analysis: Dict) -> str:
        """Enhance prompt by adding missing COSTAR elements (same behaviour as before but safe to call with sanitized prompt)."""
        enhanced = prompt or ""
        gaps = analysis.get("costar_gaps", {}).get("missing_elements", [])

        enhancements = []

        if "context" in gaps:
            enhancements.append("Please provide context and background information.")

        if "objective" in gaps:
            enhancements.append("Please specify your goal or objective.")

        if "success" in gaps:
            enhancements.append("Please define what success looks like.")

        if "timeline" in gaps:
            enhancements.append("Please specify any time constraints or deadlines.")

        if "audience" in gaps:
            enhancements.append("Please specify your target audience.")

        if "resources" in gaps:
            enhancements.append("Please specify any tools or resources to use.")

        if enhancements:
            enhanced += "\n\nAdditional guidance: " + " ".join(enhancements)

        return enhanced

    def _get_decision_reason(self, decision: BrokerDecision, analysis: Dict) -> str:
        """Get human-readable reason for broker decision"""
        if decision == BrokerDecision.BLOCK:
            safety_issues = analysis.get("safety_analysis", {}).get("issues", [])
            if safety_issues:
                # find highest severity issue if present
                highest = sorted(safety_issues, key=lambda x: x.get("score", 0), reverse=True)[0]
                return f"Blocked due to: pattern:{highest.get('category')} match:{highest.get('match')}"
            return "Blocked due to: safety pattern match"
        elif decision == BrokerDecision.NEEDS_FIX:
            safety_level = analysis.get("safety_analysis", {}).get("risk_level")
            gaps = analysis.get("costar_gaps", {}).get("missing_elements", [])
            if safety_level and safety_level != "low":
                return "Content needs sanitization due to safety concerns"
            elif gaps:
                return "Content needs enhancement - missing: " + ", ".join(gaps)
            else:
                return "Content needs improvement"
        else:
            # ALLOW
            return "Safe to proceed"
