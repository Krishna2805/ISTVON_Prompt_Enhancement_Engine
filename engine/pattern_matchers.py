# engine/pattern_matchers.py
import re
from typing import Dict, List, Any

class ISTVONPatternMatcher:
    """Extract ISTVON elements using pattern matching"""
    
    def __init__(self):
        # Instructions (I) patterns
        self.instruction_patterns = {
            "action_verbs": [
                # the article must be a whole word, or "Write about X" became "Write a bout X"
                r"\b(write|create|generate|build|make|develop)\s+(?:(a|an|the)\s+)?((?:[^.!?\n]|\.(?=\S))+)",
                r"\b(explain|describe|summarize|analyze)\s+((?:[^.!?\n]|\.(?=\S))+)",
                r"\b(how to|steps to|way to)\s+((?:[^.!?\n]|\.(?=\S))+)",
                r"\b(list|provide|give me)\s+((?:[^.!?\n]|\.(?=\S))+)"
            ],
            "quality_indicators": [
                r"(professional|creative|technical|simple|detailed)\s+",
                r"(in\s+\d+\s+words|in\s+\d+\s+points|briefly|comprehensively)",
                r"(high quality|well written|properly formatted)"
            ]
        }
        
        # Source Data (S): document references (URLs use an inline pattern)
        self.source_patterns = {
            "documents": [r"(based on|using|from)\s+(the\s+)?document", r"file:\s*\w+", r"document\s+provided"],
        }

        # Tools (T) patterns
        # Matched against the lowercased prompt, so patterns are lowercase too
        self.tool_patterns = {
            "frameworks": [r"\b(swot|pestle|smart|okr|raci|moscow|five whys|5 whys|porter's five forces)\b"],
            "styles": [r"\bin\s+(?:the\s+)?(\w+)\s+style\b"],
        }

        # Notification (N) patterns (tone, length, audience and format use inline patterns below)
        self.notification_patterns = {
            "updates": [r"notify\s+me", r"send\s+updates", r"progress\s+report", r"keep me informed"],
        }
    
    def extract_istvon_elements(self, prompt: str) -> Dict[str, Any]:
        """Extract ISTVON elements using pattern matching"""
        prompt_lower = prompt.lower()
        
        return {
            "I": self._extract_instructions(prompt),  # original case, matched case-insensitively
            "S": self._extract_source_data(prompt),  # original case: URLs are case-sensitive
            "T": self._extract_tools(prompt_lower),
            "V": self._extract_variables(prompt_lower),
            "O": self._extract_outcome(prompt_lower),
            "N": self._extract_notification(prompt_lower)
        }
    
    def _extract_instructions(self, prompt: str) -> List[str]:
        """Extract instructions from prompt"""
        # Action verbs and their objects, in prompt order
        found = []
        for pattern in self.instruction_patterns["action_verbs"]:
            for m in re.finditer(pattern, prompt, re.I):
                text = " ".join(g for g in m.groups() if g).strip(" ,;:")
                if len(text) > 3:
                    found.append((m.start(), text))
        texts = [t for _, t in found]
        # drop fragments contained in a longer match ("make x" inside "explain how to make x")
        instructions = list(dict.fromkeys(
            t[0].upper() + t[1:] for _, t in sorted(found)
            if not any(t != other and t in other for other in texts)
        ))

        # Add quality indicators to instructions
        for pattern in self.instruction_patterns["quality_indicators"]:
            for match in re.findall(pattern, prompt, re.I):
                if match:
                    instructions.append(f"Quality requirement: {match.strip()}")

        return instructions if instructions else [f"Respond to the request: {prompt.strip()}"]
    
    def _extract_source_data(self, prompt: str) -> Dict[str, Any]:
        """Extract source data information"""
        sources = {}
        
        # Check for document references
        doc_matches = [m.group(0) for p in self.source_patterns["documents"] for m in re.finditer(p, prompt, re.I)]
        if doc_matches:
            sources["documents"] = list(dict.fromkeys(doc_matches))

        # Check for URLs (drop trailing sentence punctuation)
        url_matches = [u.rstrip('.,;:!?)') for u in re.findall(r'https?://[^\s]+', prompt)]
        if url_matches:
            sources["urls"] = list(dict.fromkeys(url_matches))
        
        return sources if sources else {}
    
    def _extract_tools(self, prompt: str) -> List[str]:
        """Extract tools and methodologies"""
        tools = []
        
        for pattern in self.tool_patterns["frameworks"]:
            tools.extend(f"{m.upper() if len(m) <= 6 else m.title()} framework" for m in re.findall(pattern, prompt))
        
        for pattern in self.tool_patterns["styles"]:
            matches = re.findall(pattern, prompt)
            tools.extend([f"Use {match} style" for match in matches if match])
        
        return list(dict.fromkeys(tools))
    
    def _extract_variables(self, prompt: str) -> Dict[str, str]:
        """Extract variable parameters"""
        variables = {}
        
        # Extract tone (the stated tone word, e.g. "casual tone" or "tone: friendly")
        tone_match = re.search(r'tone:\s*(\w+)|\b(formal|casual|professional|friendly)\s+tone', prompt)
        if tone_match:
            variables["tone"] = tone_match.group(1) or tone_match.group(2)

        # Extract length, keeping qualifiers such as "under 200 words"
        length_match = re.search(r'(?:(?:under|less than|at most|max(?:imum)?|about|around|up to)\s+)?\d+\s+(?:words|pages|sentences|paragraphs|lines)', prompt)
        if length_match:
            variables["length"] = length_match.group()

        audience_match = re.search(r'\bfor\s+(beginners|experts|students|executives|kids|children|developers|investors|customers|clients)\b', prompt)
        if audience_match:
            variables["audience"] = audience_match.group(1)

        return variables
    
    def _extract_outcome(self, prompt: str) -> Dict[str, Any]:
        """Extract outcome specifications"""
        outcome = {}
        
        format_matches = re.findall(r'as\s+a\s+(\w+)', prompt)
        if format_matches:
            outcome["format"] = format_matches[0].capitalize()
        
        return outcome if outcome else {}
    
    def _extract_notification(self, prompt: str) -> Dict[str, Any]:
        """Extract notification preferences"""
        notification = {}
        
        if any(re.search(pattern, prompt) for pattern in self.notification_patterns["updates"]):
            notification["completion_notice"] = True
        
        return notification