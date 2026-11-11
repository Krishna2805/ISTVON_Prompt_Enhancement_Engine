# utils/validators.py
import re
import json
from typing import Dict, Any

class ISTVONValidator:
    """Validation utilities for ISTVON data"""
    
    @staticmethod
    def validate_json_syntax(json_str: str) -> bool:
        """Validate if string is valid JSON"""
        try:
            json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False
    
    @staticmethod
    def validate_prompt_length(prompt: str, max_length: int = 1000) -> bool:
        """Validate prompt length"""
        return len(prompt) <= max_length and len(prompt.strip()) > 0
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Basic input sanitization"""
        # Remove potentially harmful characters while preserving meaningful content
        sanitized = re.sub(r'[<>"\'&]', '', text)
        return sanitized.strip()