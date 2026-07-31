# tests/test_llm_mapper.py
import unittest
import sys
import os
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.llm_mapper import LLMISTVONMapper
from utils.json_parser import JSONParser

class TestLLMMapper(unittest.TestCase):
    """Test LLM mapper functionality"""
    
    def setUp(self):
        # Use explicit None to force no LLM model for unit tests
        self.llm_mapper = LLMISTVONMapper(api_key=None)
        self.json_parser = JSONParser()
    
    def test_initialization_without_api_key(self):
        """Test LLM mapper initialization with explicit None api_key"""
        mapper = LLMISTVONMapper(api_key=None)
        self.assertIsNone(mapper.model)
    
    def test_initialization_with_invalid_api_key(self):
        """Test LLM mapper initialization with invalid API key"""
        mapper = LLMISTVONMapper(api_key="invalid-key")
        self.assertIsNone(mapper.model)
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_initialization_with_valid_api_key(self, mock_model_cls, mock_configure):
        """Test LLM mapper initialization with valid API key"""
        mock_model_cls.return_value = Mock()
        
        mapper = LLMISTVONMapper(api_key="AIzaSyAValidKeyForTesting123456")
        # Should not raise exception and model should be set
        self.assertIsNotNone(mapper)
        self.assertIsNotNone(mapper.model)
    
    def test_enhance_mapping_without_model(self):
        """Test enhancement mapping without LLM model"""
        mapper = LLMISTVONMapper(api_key=None)  # Force no model
        prompt = "Write a professional email"
        preliminary_map = {"I": ["Write email"]}
        context = {"domain": "business"}
        
        result = mapper.enhance_mapping(prompt, preliminary_map, context)
        
        # Should return preliminary map when no model available
        self.assertEqual(result, preliminary_map)
    
    def test_build_enhancement_prompt(self):
        """Test enhancement prompt building"""
        prompt = "Write a professional email"
        preliminary_map = {"I": ["Write email"]}
        context = {"domain": "business", "complexity": "medium"}
        
        enhancement_prompt = self.llm_mapper._build_enhancement_prompt(prompt, preliminary_map, context)
        
        self.assertIn("ISTVON framework expert", enhancement_prompt)
        self.assertIn(prompt, enhancement_prompt)
        self.assertIn("business", enhancement_prompt)
        self.assertIn("medium", enhancement_prompt)
    
    def test_parse_llm_response_valid_json(self):
        """Test parsing valid LLM response"""
        response_text = '{"I": ["Write professional email"], "O": {"format": "email"}}'
        
        result = self.llm_mapper._parse_llm_response(response_text)
        
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertEqual(result["I"], ["Write professional email"])
        self.assertEqual(result["O"]["format"], "email")
    
    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid LLM response"""
        response_text = "This is not JSON"
        
        result = self.llm_mapper._parse_llm_response(response_text)
        
        self.assertEqual(result, {})
    
    def test_parse_llm_response_with_text_and_json(self):
        """Test parsing LLM response with text and JSON"""
        response_text = 'Here is the ISTVON JSON: {"I": ["Write email"], "O": {"format": "email"}} This is the result.'
        
        result = self.llm_mapper._parse_llm_response(response_text)
        
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertEqual(result["I"], ["Write email"])
    
    def test_merge_mappings(self):
        """Test merging rule-based and LLM mappings"""
        rule_based = {
            "I": ["Write email"],
            "T": ["Email templates"],
            "V": {"tone": "professional"}
        }
        
        llm_enhanced = {
            "I": ["Write professional email", "Include call to action"],
            "T": ["Email templates", "CTA generators"],
            "V": {"tone": "professional", "length": "concise"},
            "O": {"format": "email", "delivery": "direct"}
        }
        
        merged = self.llm_mapper._merge_mappings(rule_based, llm_enhanced)
        
        # Instructions should be merged
        self.assertIn("Write email", merged["I"])
        self.assertIn("Write professional email", merged["I"])
        self.assertIn("Include call to action", merged["I"])
        
        # Tools should be merged without duplicates
        self.assertIn("Email templates", merged["T"])
        self.assertIn("CTA generators", merged["T"])
        self.assertEqual(len(merged["T"]), 2)
        
        # Variables should be merged
        self.assertEqual(merged["V"]["tone"], "professional")
        self.assertEqual(merged["V"]["length"], "concise")
        
        # New fields should be added
        self.assertIn("O", merged)
        self.assertEqual(merged["O"]["format"], "email")

class TestJSONParser(unittest.TestCase):
    """Test JSON parser functionality"""
    
    def setUp(self):
        self.json_parser = JSONParser()
    
    def test_parse_gemini_response_valid(self):
        """Test parsing valid Gemini response"""
        response = '{"I": ["Write email"], "O": {"format": "email", "delivery": "direct"}}'
        
        result = self.json_parser.parse_gemini_response(response)
        
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertEqual(result["I"], ["Write email"])
        self.assertEqual(result["O"]["format"], "email")
    
    def test_parse_gemini_response_invalid(self):
        """Test parsing invalid Gemini response"""
        response = "This is not JSON"
        
        result = self.json_parser.parse_gemini_response(response)
        
        # Should return fallback ISTVON
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertEqual(result["I"], ["Execute the requested task effectively"])
    
    def test_validate_istvon_structure(self):
        """Test ISTVON structure validation"""
        data = {
            "I": ["Write email"],
            "O": {"format": "email", "delivery": "direct"}
        }
        
        result = self.json_parser._validate_istvon_structure(data)
        
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertIn("S", result)
        self.assertIn("T", result)
        self.assertIn("V", result)
        self.assertIn("N", result)
    
    def test_sanitize_text(self):
        """Test text sanitization"""
        unsafe_text = "Write <script>alert('hack')</script> email"
        
        sanitized = self.json_parser._sanitize_text(unsafe_text)
        
        # Script tags AND their content should be fully removed
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("alert", sanitized)
        self.assertNotIn("hack", sanitized)
        self.assertIn("Write", sanitized)
        self.assertIn("email", sanitized)
    
    def test_is_valid_istvon(self):
        """Test ISTVON validation"""
        valid_istvon = {
            "I": ["Write email"],
            "O": {"format": "email", "delivery": "direct"}
        }
        
        invalid_istvon = {
            "I": [],
            "O": {"format": "email"}
        }
        
        self.assertTrue(self.json_parser.is_valid_istvon(valid_istvon))
        self.assertFalse(self.json_parser.is_valid_istvon(invalid_istvon))

if __name__ == '__main__':
    unittest.main()
