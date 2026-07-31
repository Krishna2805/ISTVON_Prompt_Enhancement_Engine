# tests/test_rules.py
import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pattern_matchers import ISTVONPatternMatcher
from engine.context_analyzers import ContextAnalyzer
from engine.completion_rules import ISTVONCompletionEngine

class TestPatternMatchers(unittest.TestCase):
    """Test pattern matching functionality"""
    
    def setUp(self):
        self.pattern_matcher = ISTVONPatternMatcher()
    
    def test_extract_instructions(self):
        """Test instruction extraction"""
        prompt = "Write a professional email about product launch"
        result = self.pattern_matcher.extract_istvon_elements(prompt)
        
        self.assertIn("I", result)
        self.assertIsInstance(result["I"], list)
        self.assertGreater(len(result["I"]), 0)
    
    def test_extract_tools(self):
        """Test tool extraction"""
        prompt = "Create a report using SWOT analysis framework"
        result = self.pattern_matcher.extract_istvon_elements(prompt)
        
        self.assertIn("T", result)
        self.assertIsInstance(result["T"], list)
    
    def test_extract_variables(self):
        """Test variable extraction"""
        prompt = "Write a formal report in 500 words for executives"
        result = self.pattern_matcher.extract_istvon_elements(prompt)
        
        self.assertIn("V", result)
        self.assertIsInstance(result["V"], dict)
    
    def test_extract_outcome(self):
        """Test outcome extraction"""
        prompt = "Create a presentation as a PowerPoint file"
        result = self.pattern_matcher.extract_istvon_elements(prompt)
        
        self.assertIn("O", result)
        self.assertIsInstance(result["O"], dict)

class TestContextAnalyzer(unittest.TestCase):
    """Test context analysis functionality"""
    
    def setUp(self):
        self.context_analyzer = ContextAnalyzer()
    
    def test_identify_domain(self):
        """Test domain identification"""
        # Technical prompt
        tech_prompt = "Write code for API integration with authentication"
        context = self.context_analyzer.analyze_prompt_context(tech_prompt)
        self.assertEqual(context["domain"], "technical")
        
        # Business prompt
        business_prompt = "Create a marketing strategy for product launch"
        context = self.context_analyzer.analyze_prompt_context(business_prompt)
        self.assertEqual(context["domain"], "business")
    
    def test_assess_complexity(self):
        """Test complexity assessment"""
        # Simple prompt
        simple_prompt = "Write a brief email"
        context = self.context_analyzer.analyze_prompt_context(simple_prompt)
        self.assertEqual(context["complexity"], "simple")
        
        # Complex prompt
        complex_prompt = "Create a comprehensive analysis with detailed research"
        context = self.context_analyzer.analyze_prompt_context(complex_prompt)
        self.assertEqual(context["complexity"], "complex")
    
    def test_measure_specificity(self):
        """Test specificity measurement"""
        # Low specificity
        vague_prompt = "Write something"
        context = self.context_analyzer.analyze_prompt_context(vague_prompt)
        self.assertEqual(context["specificity"], "low")
        
        # High specificity
        specific_prompt = "Write a detailed technical documentation for the new payment API with specific authentication methods, error handling, and Python code examples"
        context = self.context_analyzer.analyze_prompt_context(specific_prompt)
        self.assertEqual(context["specificity"], "high")

class TestCompletionRules(unittest.TestCase):
    """Test completion rules functionality"""
    
    def setUp(self):
        self.completion_engine = ISTVONCompletionEngine()
    
    def test_apply_completion_rules(self):
        """Test completion rules application"""
        partial_map = {
            "I": ["Write a report"],
            "O": {"format": "document"}
        }
        context = {
            "domain": "business",
            "complexity": "medium",
            "specificity": "medium"
        }
        
        result = self.completion_engine.apply_completion_rules(partial_map, context)
        
        # Check that all required fields are present
        self.assertIn("I", result)
        self.assertIn("O", result)
        self.assertIn("V", result)
        
        # Check that instructions are enhanced
        self.assertGreater(len(result["I"]), len(partial_map["I"]))
        
        # Check that outcome is complete
        self.assertIn("format", result["O"])
        self.assertIn("delivery", result["O"])
        self.assertIn("success_criteria", result["O"])
    
    def test_enhance_instructions(self):
        """Test instruction enhancement"""
        instructions = ["Write a report"]
        context = {"domain": "technical", "complexity": "complex"}
        
        enhanced = self.completion_engine._enhance_instructions(instructions, context)
        
        self.assertGreater(len(enhanced), len(instructions))
        self.assertIn("Ensure code quality and best practices", enhanced)
        self.assertIn("Provide comprehensive and detailed analysis", enhanced)
    
    def test_get_default_variables(self):
        """Test default variable generation"""
        context = {"domain": "creative", "complexity": "medium"}
        
        variables = self.completion_engine._get_default_variables(context)
        
        self.assertIn("tone", variables)
        self.assertIn("complexity", variables)
        self.assertEqual(variables["tone"], "engaging")
        self.assertEqual(variables["format"], "Creative content")

if __name__ == '__main__':
    unittest.main()
