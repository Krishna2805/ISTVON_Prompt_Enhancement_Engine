# engine/context_analyzer.py
from typing import Dict, Any

class ContextAnalyzer:
    """Analyze prompt context for better ISTVON mapping"""
    
    def __init__(self):
        # All keywords lowercased so they match against prompt.lower()
        self.domain_keywords = {
            "technical": ["code", "programming", "software", "algorithm", "api", "technical", "develop", "debug", "deploy", "database"],
            "business": ["report", "strategy", "marketing", "sales", "business", "client", "professional", "revenue", "stakeholder"],
            "creative": ["story", "poem", "content", "creative", "narrative", "blog", "article", "fiction", "screenplay"],
            "academic": ["research", "study", "paper", "thesis", "academic", "analysis", "hypothesis", "literature review"],
            "communication": ["email", "letter", "message", "communication", "announcement", "memo", "newsletter"]
        }
        
        # Complexity indicators — NO overlap between tiers
        # "simple" keywords are ONLY simple-tier words
        # "medium" keywords are ONLY medium-tier words
        # "complex" keywords are ONLY complex-tier words
        self.complexity_indicators = {
            "simple": ["brief", "simple", "quick", "short", "basic", "easy", "straightforward"],
            "medium": ["detailed", "explain", "describe", "outline", "moderate"],
            "complex": ["thorough", "in-depth", "comprehensive", "strategic", "exhaustive", "rigorous", "multi-faceted"]
        }
        
        # Multi-word phrases get bonus weight (checked separately)
        self.complexity_phrases = {
            "complex": ["comprehensive analysis", "in-depth research", "detailed research", "thorough analysis",
                        "strategic planning", "multi-step", "end-to-end"],
            "simple": ["keep it short", "just a quick", "simple and short"]
        }
    
    def analyze_prompt_context(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt context for better ISTVON mapping"""
        prompt_lower = prompt.lower()
        
        return {
            "domain": self._identify_domain(prompt_lower),
            "complexity": self._assess_complexity(prompt_lower),
            "specificity": self._measure_specificity(prompt_lower),
            "domain_specific_rules": self._apply_domain_rules(prompt_lower)
        }
    
    def _identify_domain(self, prompt: str) -> str:
        """Identify the primary domain of the prompt"""
        domain_scores = {}
        
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in prompt)
            domain_scores[domain] = score
        
        best_domain = max(domain_scores, key=domain_scores.get)
        return best_domain if domain_scores[best_domain] > 0 else "general"
    
    def _assess_complexity(self, prompt: str) -> str:
        """Assess the complexity level of the prompt"""
        complexity_scores = {"simple": 0, "medium": 0, "complex": 0}
        
        # Score single-word indicators
        for level, indicators in self.complexity_indicators.items():
            for indicator in indicators:
                if indicator in prompt:
                    complexity_scores[level] += 1
        
        # Score multi-word phrases (bonus weight of 2 each)
        for level, phrases in self.complexity_phrases.items():
            for phrase in phrases:
                if phrase in prompt:
                    complexity_scores[level] += 2
        
        # Also factor in prompt length as a tiebreaker for complexity
        word_count = len(prompt.split())
        if word_count > 40:
            complexity_scores["complex"] += 1
        elif word_count > 20:
            complexity_scores["medium"] += 0.5
        
        # Find the highest scoring level
        best_complexity = max(complexity_scores, key=complexity_scores.get)
        return best_complexity if complexity_scores[best_complexity] > 0 else "medium"
    
    def _measure_specificity(self, prompt: str) -> str:
        """Measure how specific/detailed the prompt is"""
        word_count = len(prompt.split())
        specific_indicators = ["specific", "detailed", "particular", "exact"]
        
        specificity_score = word_count / 10  # Normalize
        specificity_score += sum(1 for indicator in specific_indicators if indicator in prompt) * 2
        
        if specificity_score > 3:
            return "high"
        elif specificity_score > 1.5:
            return "medium"
        else:
            return "low"
    
    def _apply_domain_rules(self, prompt: str) -> Dict[str, Any]:
        """Apply domain-specific rules for ISTVON mapping"""
        domain = self._identify_domain(prompt)
        
        domain_rules = {
            "technical": {
                "default_tools": ["Code formatting", "Documentation standards", "Technical writing"],
                "default_outcome": {"format": "Technical document", "delivery": "Structured format"},
                "common_variables": {"complexity": "Technical", "format": "Markdown/Code"}
            },
            "business": {
                "default_tools": ["Business frameworks", "Professional templates", "Industry standards"],
                "default_outcome": {"format": "Business document", "delivery": "Professional format"},
                "common_variables": {"tone": "Professional", "length": "Comprehensive"}
            },
            "creative": {
                "default_tools": ["Creative writing techniques", "Style guides", "Literary devices"],
                "default_outcome": {"format": "Creative content", "delivery": "Engaging format"},
                "common_variables": {"tone": "Engaging", "format": "Narrative"}
            },
            "academic": {
                "default_tools": ["Academic standards", "Citation formats", "Research methodologies"],
                "default_outcome": {"format": "Academic paper", "delivery": "Formal structure"},
                "common_variables": {"tone": "Formal", "complexity": "Detailed"}
            },
            "communication": {
                "default_tools": ["Communication templates", "Professional etiquette", "Format guidelines"],
                "default_outcome": {"format": "Communication document", "delivery": "Direct delivery"},
                "common_variables": {"tone": "Appropriate", "length": "Concise"}
            }
        }
        
        return domain_rules.get(domain, {})