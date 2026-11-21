# utils/json_parser.py
import json
import re
from typing import Dict, Any, Optional
from .logger import Logger

class JSONParser:
    """Extract the first JSON object from LLM output (fenced or surrounded by prose)."""
    
    def __init__(self):
        self.logger = Logger("JSONParser")
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from response text safely without greedy regex overreach"""
        if not text:
            return None

        # 1. Try markdown code block first: ```json ... ``` or ``` ... ```
        fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass

        # 2. Balanced bracket scan for JSON object {...}
        start = text.find('{')
        while start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = text[start:i+1]
                            try:
                                json.loads(candidate)
                                return candidate
                            except json.JSONDecodeError:
                                break
            start = text.find('{', start + 1)

        # 3. Balanced bracket scan for JSON array [...]
        start = text.find('[')
        while start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            candidate = text[start:i+1]
                            try:
                                json.loads(candidate)
                                return candidate
                            except json.JSONDecodeError:
                                break
            start = text.find('[', start + 1)

        # 4. Fallback: regex search
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group()

        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            return array_match.group()

        return None

    def extract_and_parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse first valid JSON dictionary from arbitrary text without applying schema defaults"""
        if not text:
            return None
        json_str = self._extract_json(text)
        if not json_str:
            return None
        return self._safe_json_parse(json_str)
    
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
