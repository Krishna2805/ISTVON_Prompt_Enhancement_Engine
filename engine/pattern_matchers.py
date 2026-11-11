# engine/pattern_matchers.py
import re
from typing import Dict, List, Any

class ISTVONPatternMatcher:
    """Extract ISTVON elements using pattern matching"""
    
    def __init__(self):
        # Instructions (I) patterns
        self.instruction_patterns = {
            "action_verbs": [
                r"(write|create|generate|build|make|develop)\s+(a|an|the)?\s*([\w\s]+)",
                r"(explain|describe|summarize|analyze)\s+([\w\s]+)",
                r"(how to|steps to|way to)\s+([\w\s]+)",
                r"(list|provide|give me)\s+([\w\s]+)"
            ],
            "quality_indicators": [
                r"(professional|creative|technical|simple|detailed)\s+",
                r"(in\s+\d+\s+words|in\s+\d+\s+points|briefly|comprehensively)",
                r"(high quality|well written|properly formatted)"
            ]
        }
        
        # Source Data (S) patterns
        self.source_patterns = {
            "documents": [r"(based on|using|from)\s+(the\s+)?document", r"file:\s*\w+", r"document\s+provided"],
            "urls": [r"https?://[^\s]+", r"website|URL|link", r"webpage|site"],
            "data": [r"data\s+points?", r"statistics?", r"numbers?", r"figures?"]
        }
        
        # Tools (T) patterns
        self.tool_patterns = {
            "frameworks": [r"using\s+(SWOT|PESTLE|SMART)", r"framework|methodology", r"template"],
            "styles": [r"in\s+(\w+)\s+style", r"like\s+(\w+)", r"similar to"],
            "formats": [r"in\s+(JSON|XML|HTML|Markdown)", r"format|template", r"structure"]
        }
        
        # Variable (V) patterns
        self.variable_patterns = {
            "tone": [r"(formal|casual|professional|friendly)\s+tone", r"tone:\s*(\w+)", r"sound\s+(\w+)"],
            "length": [r"\d+\s+words", r"\d+\s+pages", r"short|long|brief|detailed", r"length:\s*(\w+)"],
            "audience": [r"for\s+(beginners|experts|students|executives)", r"targeting\s+(\w+)"],
            "complexity": [r"simple|complex|detailed|basic|advanced"]
        }
        
        # Outcome (O) patterns
        self.outcome_patterns = {
            "format": [r"as\s+a\s+(report|email|blog|presentation)", r"in\s+(\w+)\s+format", r"output as"],
            "delivery": [r"save\s+to\s+(\w+)", r"export\s+as", r"downloadable", r"send to"]
        }
        
        # Notification (N) patterns
        self.notification_patterns = {
            "updates": [r"notify\s+me", r"send\s+updates", r"progress\s+report", r"keep me informed"],
            "milestones": [r"when\s+done", r"after\s+each\s+step", r"milestone", r"upon completion"]
        }
    
    def extract_istvon_elements(self, prompt: str) -> Dict[str, Any]:
        """Extract ISTVON elements using pattern matching"""
        prompt_lower = prompt.lower()
        
        return {
            "I": self._extract_instructions(prompt_lower),
            "S": self._extract_source_data(prompt_lower),
            "T": self._extract_tools(prompt_lower),
            "V": self._extract_variables(prompt_lower),
            "O": self._extract_outcome(prompt_lower),
            "N": self._extract_notification(prompt_lower)
        }
    
    def _extract_instructions(self, prompt: str) -> List[str]:
        """Extract instructions from prompt"""
        instructions = []
        
        # Extract action verbs and their objects
        for pattern in self.instruction_patterns["action_verbs"]:
            matches = re.findall(pattern, prompt)
            for match in matches:
                if isinstance(match, tuple):
                    instruction = " ".join([m for m in match if m]).strip()
                else:
                    instruction = match
                if instruction and len(instruction) > 3:
                    instructions.append(instruction.capitalize())
        
        # Add quality indicators to instructions
        for pattern in self.instruction_patterns["quality_indicators"]:
            matches = re.findall(pattern, prompt)
            for match in matches:
                if match:
                    instructions.append(f"Ensure {match} quality")
        
        return instructions if instructions else ["Execute the requested task"]
    
    def _extract_source_data(self, prompt: str) -> Dict[str, Any]:
        """Extract source data information"""
        sources = {}
        
        # Check for document references
        doc_matches = []
        for pattern in self.source_patterns["documents"]:
            doc_matches.extend(re.findall(pattern, prompt))
        if doc_matches:
            sources["documents"] = list(set(doc_matches))
        
        # Check for URLs
        url_matches = re.findall(r'https?://[^\s]+', prompt)
        if url_matches:
            sources["urls"] = url_matches
        
        return sources if sources else {}
    
    def _extract_tools(self, prompt: str) -> List[str]:
        """Extract tools and methodologies"""
        tools = []
        
        for pattern in self.tool_patterns["frameworks"]:
            matches = re.findall(pattern, prompt)
            tools.extend(matches)
        
        for pattern in self.tool_patterns["styles"]:
            matches = re.findall(pattern, prompt)
            tools.extend([f"Use {match} style" for match in matches if match])
        
        return list(set(tools))
    
    def _extract_variables(self, prompt: str) -> Dict[str, str]:
        """Extract variable parameters"""
        variables = {}
        
        # Extract tone
        tone_matches = re.findall(r'tone:\s*(\w+)', prompt)
        if tone_matches:
            variables["tone"] = tone_matches[0]
        else:
            for pattern in self.variable_patterns["tone"]:
                if re.search(pattern, prompt):
                    variables["tone"] = "professional"  # Default
        
        # Extract length
        length_match = re.search(r'(\d+\s+words|\d+\s+pages)', prompt)
        if length_match:
            variables["length"] = length_match.group()
        
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