# engine/completion_rules.py
from typing import Dict, List, Any

class ISTVONCompletionEngine:
    """Apply rules to complete partial ISTVON mappings"""
    
    def apply_completion_rules(self, partial_map: Dict, context: Dict) -> Dict:
        """Apply rules to complete partial ISTVON mappings"""
        
        completed_map = partial_map.copy()
        
        # Ensure Instructions (I) are complete
        if not completed_map.get("I") or len(completed_map["I"]) == 0:
            completed_map["I"] = ["Execute the requested task effectively"]
        
        # Enhance Instructions based on domain and context
        completed_map["I"] = self._enhance_instructions(completed_map["I"], context)
        
        # Apply domain-specific defaults
        domain_rules = context.get("domain_specific_rules", {})
        completed_map = self._apply_domain_defaults(completed_map, domain_rules)
        
        # Ensure Outcome (O) is specified
        if not completed_map.get("O"):
            completed_map["O"] = {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements", "High quality output"]
            }
        else:
            # Enhance existing outcome
            completed_map["O"] = self._enhance_outcome(completed_map["O"], context)
        
        # Add default variables if missing
        if not completed_map.get("V"):
            completed_map["V"] = self._get_default_variables(context)
        
        return completed_map
    
    def _enhance_instructions(self, instructions: List[str], context: Dict) -> List[str]:
        """Enhance instructions based on context"""
        enhanced = instructions.copy()
        domain = context.get("domain", "general")
        complexity = context.get("complexity", "medium")
        
        # Domain-specific enhancements
        domain_enhancements = {
            "technical": [
                "Ensure code quality and best practices",
                "Include proper documentation where applicable"
            ],
            "business": [
                "Use professional business language",
                "Focus on actionable insights and clarity"
            ],
            "creative": [
                "Maintain creative flow and engagement",
                "Use appropriate literary devices and style"
            ],
            "academic": [
                "Maintain academic rigor and proper citations",
                "Use formal academic tone and structure"
            ],
            "communication": [
                "Ensure clarity and appropriate tone",
                "Focus on effective message delivery"
            ]
        }
        
        if domain in domain_enhancements:
            enhanced.extend(domain_enhancements[domain])
        
        # Complexity-based enhancements
        if complexity == "complex":
            enhanced.append("Provide comprehensive and detailed analysis")
        elif complexity == "simple":
            enhanced.append("Keep response concise and to the point")
        
        return enhanced
    
    def _enhance_outcome(self, outcome: Dict, context: Dict) -> Dict:
        """Enhance outcome specifications"""
        enhanced = outcome.copy()
        domain = context.get("domain", "general")
        
        # Ensure required fields exist
        if "format" not in enhanced:
            enhanced["format"] = "Appropriate format for the domain"
        
        if "delivery" not in enhanced:
            enhanced["delivery"] = "Standard delivery method"
        
        if "success_criteria" not in enhanced:
            enhanced["success_criteria"] = []
        
        # Domain-specific success criteria
        domain_criteria = {
            "technical": ["Technically accurate", "Well-structured code/documentation"],
            "business": ["Professionally formatted", "Actionable recommendations"],
            "creative": ["Engaging content", "Appropriate style and tone"],
            "academic": ["Academic rigor", "Proper citations and references"]
        }
        
        if domain in domain_criteria:
            enhanced["success_criteria"].extend(domain_criteria[domain])
        
        # Ensure uniqueness
        enhanced["success_criteria"] = list(set(enhanced["success_criteria"]))
        
        return enhanced
    
    def _apply_domain_defaults(self, istvon_map: Dict, domain_rules: Dict) -> Dict:
        """Apply domain-specific default values"""
        result = istvon_map.copy()
        
        # Apply tool defaults if no tools specified
        if not result.get("T") and domain_rules.get("default_tools"):
            result["T"] = domain_rules["default_tools"]
        
        # Enhance existing tools with domain defaults
        elif result.get("T") and domain_rules.get("default_tools"):
            result["T"].extend(domain_rules["default_tools"])
            result["T"] = list(set(result["T"]))  # Remove duplicates
        
        return result
    
    def _get_default_variables(self, context: Dict) -> Dict[str, str]:
        """Get default variables based on context"""
        domain = context.get("domain", "general")
        complexity = context.get("complexity", "medium")
        
        default_vars = {
            "tone": "professional",
            "complexity": complexity
        }
        
        # Domain-specific variable defaults
        domain_vars = {
            "technical": {"format": "Technical documentation"},
            "business": {"format": "Business document"},
            "creative": {"tone": "engaging", "format": "Creative content"},
            "academic": {"tone": "formal", "format": "Academic paper"}
        }
        
        if domain in domain_vars:
            default_vars.update(domain_vars[domain])
        
        return default_vars