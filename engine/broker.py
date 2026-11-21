
from typing import Dict, Any, List
from enum import Enum
import re

from utils.json_logger import RuleEngineLogger
from .context_analyzers import ContextAnalyzer

# Safety rule levels. A prompt's verdict is set by its single worst match (no summing):
# one BLOCK-level match blocks; otherwise one REVIEW-level match gives NEEDS_FIX, which
# still proceeds but shows a warning. Summing scores let two harmless topic words
# ("bank", "financial") add up to a block.
BLOCK_LEVEL = 5
REVIEW_LEVEL = 2

_ACTION = r"(?:write|writing|create|creating|build|building|make|making|develop|developing|code|coding|craft|crafting|design|designing|generate|generating|draft|drafting|deploy|deploying|spread|spreading|send|sending)"
# Person targets. "'s" is excluded so "hurt someone's feelings" is not a threat;
# "child" excludes software senses ("kill a child process").
_PERSON = (r"(?:someone|somebody|people|(?:a|the)\s+person|him|her|them|"
           r"(?:my|his|her|their|your|a|the)\s+(?:wife|husband|partner|girlfriend|boyfriend|ex|boss|co-?workers?|"
           r"neighbou?rs?|teachers?|friends?|mom|mother|dad|father|brother|sister|son|daughter|"
           r"child(?!\s+(?:process|thread|node|element|component|task|widget))|kids?|family|roommates?|classmates?))\b(?!'s)")
_SYSTEM = r"(?:systems?|servers?|networks?|websites?|sites?|computers?|accounts?|databases?|infrastructure|phones?|wi-?fi|cameras?|emails?)"
_ATTACK_TARGET = r"(?:systems?|servers?|networks?|websites?|computers?|databases?|infrastructure)"
_DET = r"(?:a|an|the|their|his|her|someone's|my|our)"
_DRUGS = r"(?:meth|methamphetamine|cocaine|crack\s+cocaine|heroin|fentanyl|lsd|mdma|dmt|ghb|ketamine)"
_MINOR = r"(?:child|children|minors?|underage|kids?|preteens?)"
_SEXUAL = r"(?:porn\w*|nude|naked|erotic|sexually\s+explicit)"

# (category, level, pattern). Intent phrases block; bare topic words only flag for review.
SAFETY_RULES = [
    # dangerous: weapons, violence, drugs
    ("dangerous", BLOCK_LEVEL, r"\b(?:make|making|build|building|create|creating|assemble|assembling)\s+(?:an?\s+)?(?:\w+\s+){0,2}(?:explosives|explosive\s+(?:devices?|vests?|charges?)|bombs?|weapons?)\b"),
    ("dangerous", BLOCK_LEVEL, rf"\b(?:kill|murder|poison|stab|shoot|attack|harm|hurt|beat\s+up)(?:s|ed|ing)?\s+{_PERSON}"),
    ("dangerous", BLOCK_LEVEL, r"\bunalive\b"),
    ("dangerous", BLOCK_LEVEL, rf"\b(?:make|making|cook|cooking|synthesi[sz]e|synthesi[sz]ing|manufactur(?:e|ing)|produce|producing)\s+(?:\w+\s+){{0,2}}{_DRUGS}\b"),
    ("dangerous", BLOCK_LEVEL, rf"\b(?:recipe|instructions|steps|guide)\s+(?:for|to\s+make)\s+(?:\w+\s+)?{_DRUGS}\b|\b{_DRUGS}\s+recipe\b"),
    ("dangerous", BLOCK_LEVEL, r"\b(?:drug\s+manufactur(?:e|ing)|poison\s+recipe)\b"),
    ("dangerous", REVIEW_LEVEL, r"\b(?:explosives|bombs?|illegal)\b"),
    # self-harm
    ("self_harm", BLOCK_LEVEL, r"\b(?:commit(?:ting)?\s+suicide|(?:kill|hang|cut|harm|hurt|starve|poison|drown)(?:ing)?\s+myself|slit(?:ting)?\s+my\s+wrists?|(?:end|take)(?:ing)?\s+my\s+(?:own\s+)?life)\b"),
    ("self_harm", REVIEW_LEVEL, r"\b(?:suicid\w*|self[- ]harm)\b"),
    # malicious: offensive cyber
    ("malicious", BLOCK_LEVEL, rf"\bhack(?:s|ed|ing)?\s+(?:into\b|{_PERSON}|(?:{_DET}\s+)?(?:\w+\s+)?{_SYSTEM}\b)"),
    ("malicious", BLOCK_LEVEL, rf"\b(?:attack|ddos|breach|compromis)(?:e|es|s|ed|ing)?\s+(?:{_DET}\s+)?(?:\w+\s+)?{_ATTACK_TARGET}\b"),
    ("malicious", BLOCK_LEVEL, rf"\b{_ACTION}\s+(?:(?:a|an|some|the)\s+)?(?:\w+\s+){{0,2}}(?:malware|ransomware|keyloggers?|spyware|rootkits?|trojans?|botnets?|backdoors?|computer\s+virus(?:es)?|phishing)\b"),
    ("malicious", BLOCK_LEVEL, r"\b(?:write|writing|code|coding|program|programming|develop|developing|deploy|deploying)\s+(?:(?:a|an|some|the)\s+)?(?:\w+\s+){0,2}virus(?:es)?\b"),
    ("malicious", BLOCK_LEVEL, r"\bmalicious\s+(?:code|software|scripts?|payloads?|programs?)\b"),
    ("malicious", BLOCK_LEVEL, r"\b(?:steal|steals|stealing|stole|stolen)\s+(?:\S+\s+){0,2}(?:data|passwords?|credentials?|identit(?:y|ies)|money|credit\s+cards?|accounts?|(?:browser|session|auth|http)\s+cookies|tokens?|information|info)\b"),
    ("malicious", BLOCK_LEVEL, r"\b(?:bypass(?:es|ed|ing)?|crack(?:s|ed|ing)?|brute[\s-]*forc(?:e|es|ed|ing))\s+(?:\S+\s+){0,2}(?:passwords?|logins?|authentication|2fa|mfa|accounts?)\b"),
    ("malicious", REVIEW_LEVEL, r"\b(?:hack(?:s|ed|ing|er|ers)?|malware|ransomware|keyloggers?|spyware|rootkits?|trojans?|botnets?|phish(?:ing)?|zero[- ]day|exploit\s+(?:code|kits?)|(?:sql|code|command|prompt)\s+injection|data\s+(?:breach|theft)|identity\s+theft|credential\s+harvest(?:ing)?|unauthori[sz]ed\s+access|exfiltrat\w*)\b"),
    # inappropriate
    ("inappropriate", BLOCK_LEVEL, rf"\b{_MINOR}\b(?:\W+\w+){{0,3}}?\W+{_SEXUAL}\b(?!\s+eye)|\b{_SEXUAL}\b(?!\s+eye)(?:\W+\w+){{0,3}}?\W+{_MINOR}\b"),
    # the generated thing must BE the content: "write racist jokes", not "write an essay on hate speech"
    ("inappropriate", BLOCK_LEVEL, rf"\b{_ACTION}\s+(?:(?:a|an|some|more)\s+)?(?:(?!on\b|about\b|regarding\b|against\b)\w+\s+)?(?:hate\s+speech|racist\s+(?:jokes?|content|propaganda)|porn(?:ography|ographic)?|sexually\s+explicit)"),
    ("inappropriate", REVIEW_LEVEL, r"\b(?:explicit\s+content|pornographic|porn|hate\s+speech|racist|harassment|bully(?:ing|ied)?)\b"),
    # sensitive: personal data, not topic words like "bank" or "medical"
    ("sensitive", REVIEW_LEVEL, r"\b(?:personal\s+(?:data|information|info|details|financial|medical|health)|private\s+information|confidential|credit\s+card\s+(?:numbers?|details|info)|bank\s+(?:account|login|credentials|details)|ssn|social\s+security\s+number|(?:health|medical)\s+records|patient\s+data)\b"),
    ("sensitive", REVIEW_LEVEL, r"\b\d{3}-\d{2}-\d{4}\b|\b(?:\d[ -]?){12,15}\d\b"),  # SSN / card-number shaped values
]

# Benign collocations that would otherwise match; only overlapping matches are suppressed.
ALLOWLIST = [
    r"\bethical\s+hacking\b",
    r"\b(?:how\s+to\s+)?prevent\s+phishing\b", r"\banti[- ]phishing\b",
    r"\blife\s*hacks?\b", r"\bgrowth\s+hack(?:ing|er|ers)?\b", r"\bhack\s+together\b",
    r"\bbath\s+bombs?\b", r"\bphoto\s*bomb\w*\b",
]

# Defensive or test framing near a cyber match downgrades BLOCK to NEEDS_FIX ("protect my account
# from someone trying to hack into it", "bypass authentication in Cypress tests"). It needs a verb
# with an object, so nouns like "security defenses" don't count. Never applied to violence,
# self-harm or sexual content.
DEFENSIVE = re.compile(
    r"\b(?:prevent|protect|defend|detect|mitigat|secur|harden|guard)\w*\s+(?:my|our|your|the|against|from|it|them|us)\b"
    r"|\bhow\s+to\s+(?:avoid|stop)\b|\b(?:unit|integration|e2e|cypress|playwright|selenium|jest|pytest)\s+tests?\b"
    r"|\bin\s+(?:my\s+|our\s+)?(?:tests?|test\s+suite|staging|local\s+dev\w*)\b", re.I)


# Shown when a self-harm rule matches. findahelpline.com (run by ThroughLine; the directory the
# International Association for Suicide Prevention links to) lists free, confidential helplines by country.
SUPPORT_MESSAGE = ("If you are thinking about harming yourself, you don't have to go through it alone. "
                   "If you are in immediate danger, call your local emergency number. "
                   "To find a free, confidential helpline in your country, visit https://findahelpline.com. "
                   "This tool is not a crisis service.")


class BrokerDecision(Enum):
    """Broker decision types"""
    ALLOW = "ALLOW"           # No rule matched
    NEEDS_FIX = "NEEDS_FIX"   # Sensitive/ambiguous term: warn, then process the prompt unchanged
    BLOCK = "BLOCK"           # Harmful-intent phrase: stop


class ISTVONBroker:

    def __init__(self):
        self.context_analyzer = ContextAnalyzer()
        self.json_logger = RuleEngineLogger()
        self.safety_rules = [(cat, level, re.compile(p, re.IGNORECASE)) for cat, level, p in SAFETY_RULES]
        self.allowlist_patterns = [re.compile(p, re.IGNORECASE) for p in ALLOWLIST]

        # COSTAR gap patterns (unchanged semantics but compiled)
        self.costar_gaps = {
            "context": [re.compile(r"\b(context|background|situation|about|regarding)\b", re.I)],
            "objective": [re.compile(r"\b(goal|objective|purpose|aim|to\s+(?:write|create|make|build))\b", re.I)],
            "success": [re.compile(r"\b(success|completion|done|finished|means|should)\b", re.I)],
            "timeline": [re.compile(r"\b(when|time|deadline|schedule|by|before)\b", re.I)],
            "audience": [re.compile(r"\b(for|target|audience|recipient|customers|users|people)\b", re.I)],
            "resources": [re.compile(r"\b(using|with|tools|resources|via|through)\b", re.I)]
        }

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
        """Match the safety rules; the worst single match sets the risk level."""
        allow_spans = [m.span() for allow_re in self.allowlist_patterns for m in allow_re.finditer(prompt)]
        issues = []
        for category, level, cre in self.safety_rules:
            for m in cre.finditer(prompt):
                start, end = m.span()
                if any(start < a_end and end > a_start for a_start, a_end in allow_spans):
                    continue
                score = level
                if level == BLOCK_LEVEL and category == "malicious" and \
                        DEFENSIVE.search(prompt[max(0, start - 60):end + 60]):
                    score = REVIEW_LEVEL  # defensive framing: flag, don't block
                issues.append({
                    "category": category,
                    "pattern": cre.pattern,
                    "match": m.group(0),
                    "span": (start, end),
                    "severity": "block" if score == BLOCK_LEVEL else "review",
                    "score": score,
                })

        score = max((i["score"] for i in issues), default=0)
        risk_level = "high" if score >= BLOCK_LEVEL else "medium" if score >= REVIEW_LEVEL else "low"
        return {
            "risk_level": risk_level,
            "issues": issues,
            "is_safe": risk_level == "low",
            "score": score,
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

        if any(i.get("category") == "self_harm" for i in safety_result.get("issues", [])):
            # Region-neutral on purpose: no country-specific numbers to go stale or be wrong abroad.
            # Only the support message: "revise your prompt" boilerplate reads badly here.
            return [SUPPORT_MESSAGE]

        if decision == BrokerDecision.BLOCK:
            recommendations.append("BLOCKED: Content contains high-risk elements.")
            recommendations.append("Revise your prompt to remove instructions for harmful or illegal activities.")

        elif decision == BrokerDecision.NEEDS_FIX:
            if safety_result["risk_level"] != "low":
                recommendations.append("Contains potentially unsafe content or sensitive data; consider rephrasing. "
                                       "The prompt is processed as written (and sent to the LLM if one is configured), "
                                       "so leave out real personal data such as names, account or card numbers.")

            if costar_gaps["missing_elements"]:
                recommendations.append("Missing critical elements: " + ", ".join(costar_gaps["missing_elements"]))
            else:
                recommendations.append("Consider clarifying objectives or audience for better results.")
        else:  # ALLOW
            recommendations.append("Safe to proceed with ISTVON enhancement.")
            if costar_gaps["completeness_score"] < 0.8:
                missing = costar_gaps.get("missing_elements") or []
                recommendations.append("Consider adding more details for better results"
                                       + (f" (missing: {', '.join(missing)})." if missing else "."))

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
            # Build a redacted copy for the audit log only. The caller still processes the
            # original prompt unchanged; nothing here keeps text away from the LLM provider.
            audit_info = self._redact_for_audit(prompt, analysis)
            sanitized_prompt = audit_info.get("sanitized_prompt")
            redactions = audit_info.get("redactions")
            suggested_rewrite = audit_info.get("suggested_rewrite")

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

    def _redact_for_audit(self, prompt: str, analysis: Dict = None) -> Dict[str, Any]:
        """Replace the matched rule spans with [REDACTED] for the audit-log copy.

        Only rule matches are replaced; names, addresses and other personal data that no
        rule matches stay in the text. Returns a dict with:
        - sanitized_prompt: str (key named after the prompt_log column)
        - redactions: list of dict(original, replacement, category, span)
        - suggested_rewrite: str (a simple human-friendly suggestion)
        """
        if not prompt:
            return {"sanitized_prompt": "", "redactions": [], "suggested_rewrite": ""}

        text = prompt
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
                    idx = text.lower().find(m.get("match", "").lower())
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
            out.append(text[last_idx:start])
            out.append(replacement)
            redactions.append({"original": original, "replacement": replacement, "category": category, "span": (start, end)})
            last_idx = end
        out.append(text[last_idx:])
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
        """Append guidance for missing COSTAR elements (result is returned but not used by the app)."""
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
                return "Sensitive or risky wording flagged for review"
            elif gaps:
                return "Content needs enhancement - missing: " + ", ".join(gaps)
            else:
                return "Content needs improvement"
        else:
            # ALLOW
            return "Safe to proceed"
