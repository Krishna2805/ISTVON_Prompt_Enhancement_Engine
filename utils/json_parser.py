# utils/json_parser.py
import json
import re
from typing import Dict, Any, Optional, List
from .logger import Logger

class JSONParser:
    """Safe JSON parser for Gemini output with validation and sanitization"""
    
    def __init__(self):
        self.logger = Logger("JSONParser")
        
        # ISTVON schema validation patterns
        self.istvon_patterns = {
            "I": r'"(?:I|Instructions?)"\s*:\s*\[(?:[^\[\]]*|"[^"]*")*\]',
            "S": r'"(?:S|Sources?)"\s*:\s*\{[^}]*\}',
            "T": r'"(?:T|Tools?)"\s*:\s*\[(?:[^\[\]]*|"[^"]*")*\]',
            "V": r'"(?:V|Variables?)"\s*:\s*\{[^}]*\}',
            "O": r'"(?:O|Outcome?)"\s*:\s*\{[^}]*\}',
            "N": r'"(?:N|Notifications?)"\s*:\s*\{[^}]*\}'
        }
    
    def parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate Gemini response for ISTVON JSON"""
        try:
            # Step 1: Extract JSON from response
            json_str = self._extract_json(response_text)
            
            if not json_str:
                self.logger.warning("No valid JSON found in response")
                return self._get_fallback_istvon()
            
            # Step 2: Parse JSON safely
            parsed_data = self._safe_json_parse(json_str)
            
            if not parsed_data:
                self.logger.warning("Failed to parse JSON")
                return self._get_fallback_istvon()
            
            # Step 3: Validate ISTVON structure
            validated_data = self._validate_istvon_structure(parsed_data)
            
            # Step 4: Sanitize content
            sanitized_data = self._sanitize_istvon_content(validated_data)
            
            self.logger.info("Successfully parsed and validated ISTVON JSON")
            return sanitized_data
            
        except Exception as e:
            self.logger.error(f"Error parsing Gemini response: {e}")
            return self._get_fallback_istvon()
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from response text"""
        # Try to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group()
        
        # Try to find JSON array
        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            return array_match.group()
        
        return None
    
    def _safe_json_parse(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON string"""
        try:
            # Basic validation
            if not json_str.strip():
                return None
            
            # Try to parse
            parsed = json.loads(json_str)
            
            # Ensure it's a dictionary
            if not isinstance(parsed, dict):
                return None
            
            return parsed
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON decode error: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error parsing JSON: {e}")
            return None
    
    def _validate_istvon_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix ISTVON structure"""
        validated = {}
        
        # Validate Instructions (I)
        if "I" in data and isinstance(data["I"], list):
            validated["I"] = [str(item) for item in data["I"] if item]
        else:
            validated["I"] = ["Execute the requested task effectively"]
        
        # Validate Sources (S)
        if "S" in data and isinstance(data["S"], dict):
            validated["S"] = self._validate_sources(data["S"])
        else:
            validated["S"] = {"documents": [], "urls": [], "data_points": {}}
        
        # Validate Tools (T)
        if "T" in data and isinstance(data["T"], list):
            validated["T"] = [str(item) for item in data["T"] if item]
        else:
            validated["T"] = []
        
        # Validate Variables (V)
        if "V" in data and isinstance(data["V"], dict):
            validated["V"] = self._validate_variables(data["V"])
        else:
            validated["V"] = {"tone": "professional", "complexity": "medium"}
        
        # Validate Outcome (O)
        if "O" in data and isinstance(data["O"], dict):
            validated["O"] = self._validate_outcome(data["O"])
        else:
            validated["O"] = {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements"]
            }
        
        # Validate Notifications (N)
        if "N" in data and isinstance(data["N"], dict):
            validated["N"] = self._validate_notifications(data["N"])
        else:
            validated["N"] = {"completion_notice": True}
        
        return validated
    
    def _validate_sources(self, sources: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sources structure"""
        validated_sources = {"documents": [], "urls": [], "data_points": {}}
        
        if "documents" in sources and isinstance(sources["documents"], list):
            validated_sources["documents"] = [str(doc) for doc in sources["documents"]]
        
        if "urls" in sources and isinstance(sources["urls"], list):
            validated_sources["urls"] = [str(url) for url in sources["urls"]]
        
        if "data_points" in sources and isinstance(sources["data_points"], dict):
            validated_sources["data_points"] = sources["data_points"]
        
        return validated_sources
    
    def _validate_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Validate variables structure"""
        validated_vars = {}
        
        valid_keys = ["tone", "length", "complexity", "format", "audience", "style"]
        
        for key, value in variables.items():
            if key in valid_keys and isinstance(value, (str, int, float)):
                validated_vars[key] = str(value)
        
        # Ensure required variables
        if "tone" not in validated_vars:
            validated_vars["tone"] = "professional"
        
        return validated_vars
    
    def _validate_outcome(self, outcome: Dict[str, Any]) -> Dict[str, Any]:
        """Validate outcome structure"""
        validated_outcome = {}
        
        if "format" in outcome and isinstance(outcome["format"], str):
            validated_outcome["format"] = outcome["format"]
        else:
            validated_outcome["format"] = "Text response"
        
        if "delivery" in outcome and isinstance(outcome["delivery"], str):
            validated_outcome["delivery"] = outcome["delivery"]
        else:
            validated_outcome["delivery"] = "Inline display"
        
        if "success_criteria" in outcome and isinstance(outcome["success_criteria"], list):
            validated_outcome["success_criteria"] = [str(criteria) for criteria in outcome["success_criteria"]]
        else:
            validated_outcome["success_criteria"] = ["Meets user requirements"]
        
        return validated_outcome
    
    def _validate_notifications(self, notifications: Dict[str, Any]) -> Dict[str, Any]:
        """Validate notifications structure"""
        validated_notifications = {}
        
        if "completion_notice" in notifications:
            validated_notifications["completion_notice"] = bool(notifications["completion_notice"])
        else:
            validated_notifications["completion_notice"] = True
        
        if "milestones" in notifications and isinstance(notifications["milestones"], list):
            validated_notifications["milestones"] = [str(milestone) for milestone in notifications["milestones"]]
        else:
            validated_notifications["milestones"] = []
        
        return validated_notifications
    
    def _sanitize_istvon_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize ISTVON content for safety"""
        sanitized = {}
        
        for key, value in data.items():
            if key == "I" and isinstance(value, list):
                sanitized[key] = [self._sanitize_text(item) for item in value]
            elif key == "T" and isinstance(value, list):
                sanitized[key] = [self._sanitize_text(item) for item in value]
            elif key == "O" and isinstance(value, dict) and "success_criteria" in value:
                sanitized[key] = value.copy()
                sanitized[key]["success_criteria"] = [self._sanitize_text(criteria) for criteria in value["success_criteria"]]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize text content"""
        if not isinstance(text, str):
            return str(text)
        
        # Step 1: Remove dangerous HTML tags AND their content
        dangerous_tags = r'<\s*(script|iframe|object|embed|style|link|meta|form|input|button)\b[^>]*>.*?</\s*\1\s*>'
        sanitized = re.sub(dangerous_tags, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Step 2: Remove any remaining HTML tags (opening, closing, self-closing)
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        # Step 3: Remove potentially harmful characters
        sanitized = re.sub(r'[<>"\'&;]', '', sanitized)
        
        # Step 4: Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    def _get_fallback_istvon(self) -> Dict[str, Any]:
        """Get fallback ISTVON structure when parsing fails"""
        return {
            "I": ["Execute the requested task effectively"],
            "S": {"documents": [], "urls": [], "data_points": {}},
            "T": [],
            "V": {"tone": "professional", "complexity": "medium"},
            "O": {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements"]
            },
            "N": {"completion_notice": True}
        }
    
    def is_valid_istvon(self, data: Dict[str, Any]) -> bool:
        """Check if data is valid ISTVON structure"""
        required_keys = ["I", "O"]
        
        # Check required keys
        if not all(key in data for key in required_keys):
            return False
        
        # Check Instructions is list
        if not isinstance(data["I"], list) or not data["I"]:
            return False
        
        # Check Outcome is dict with required fields
        if not isinstance(data["O"], dict):
            return False
        
        if "format" not in data["O"] or "delivery" not in data["O"]:
            return False
        
        return True
