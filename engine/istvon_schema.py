# engine/istvon_schema.py
from config import Config

class ISTVONSchema:
    """ISTVON JSON schema definition and validation"""
    
    def __init__(self):
        self.schema = Config.ISTVON_SCHEMA
    
    def validate_istvon(self, istvon_data: dict) -> dict:
        """Validate ISTVON JSON against schema"""
        validated_data = {}
        
        for key, schema_def in self.schema.items():
            if key in istvon_data:
                # Basic type validation
                if schema_def["type"] == "array" and isinstance(istvon_data[key], list):
                    validated_data[key] = istvon_data[key]
                elif schema_def["type"] == "object" and isinstance(istvon_data[key], dict):
                    validated_data[key] = istvon_data[key]
                elif schema_def["type"] == "string" and isinstance(istvon_data[key], str):
                    validated_data[key] = istvon_data[key]
            elif schema_def["required"]:
                # Add default values for required fields
                validated_data[key] = self._get_default_value(key)
        
        return validated_data
    
    def _get_default_value(self, key: str):
        """Get default values for required ISTVON fields"""
        defaults = {
            "I": ["Execute the requested task effectively"],
            "O": {
                "format": "Text response",
                "delivery": "Inline display",
                "success_criteria": ["Meets user requirements", "High quality output"]
            }
        }
        return defaults.get(key, None)