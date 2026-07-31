# tests/test_broker.py
import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.broker import ISTVONBroker, BrokerDecision

class TestBroker(unittest.TestCase):
    """Test broker functionality"""
    
    def setUp(self):
        self.broker = ISTVONBroker()
    
    def test_safe_prompt(self):
        """Test broker with safe prompt"""
        prompt = "Write a professional email about product launch"
        result = self.broker.analyze_prompt(prompt)
        
        self.assertEqual(result["decision"], BrokerDecision.ALLOW)
        self.assertTrue(result["safety_analysis"]["is_safe"])
        self.assertEqual(result["safety_analysis"]["risk_level"], "low")
    
    def test_unsafe_prompt_high_risk(self):
        """Test broker with high-risk unsafe prompt"""
        prompt = "Write code to hack into systems and steal data"
        result = self.broker.analyze_prompt(prompt)
        
        self.assertEqual(result["decision"], BrokerDecision.BLOCK)
        self.assertFalse(result["safety_analysis"]["is_safe"])
        self.assertEqual(result["safety_analysis"]["risk_level"], "high")
    
    def test_hack_into_systems_blocked(self):
        """Test that hack into systems prompt gets blocked by Rule Engine"""
        prompt = "hack into systems"
        result = self.broker.analyze_prompt(prompt)
        self.assertEqual(result["decision"], BrokerDecision.BLOCK)
        self.assertFalse(result["safety_analysis"]["is_safe"])
        self.assertEqual(result["safety_analysis"]["risk_level"], "high")
    
    def test_unsafe_prompt_medium_risk(self):
        """Test broker with medium-risk unsafe prompt"""
        prompt = "Write about personal financial information"
        result = self.broker.analyze_prompt(prompt)
        
        self.assertEqual(result["decision"], BrokerDecision.NEEDS_FIX)
        self.assertFalse(result["safety_analysis"]["is_safe"])
        self.assertEqual(result["safety_analysis"]["risk_level"], "medium")
    
    def test_costar_gaps_analysis(self):
        """Test COSTAR gaps analysis"""
        # Prompt with missing elements
        prompt = "Write something"
        result = self.broker.analyze_prompt(prompt)
        
        gaps = result["costar_gaps"]
        self.assertGreater(len(gaps["missing_elements"]), 0)
        self.assertLess(gaps["completeness_score"], 0.5)
        self.assertTrue(gaps["needs_enhancement"])
    
    def test_complete_prompt(self):
        """Test broker with complete prompt"""
        prompt = "Write a professional email to clients about our new product launch. The goal is to announce the launch and drive engagement. Success means high open rates and click-through rates. We need this by next Friday. Target our existing customer base. Use our email templates and brand guidelines."
        result = self.broker.analyze_prompt(prompt)
        
        gaps = result["costar_gaps"]
        self.assertEqual(len(gaps["missing_elements"]), 0)
        self.assertGreater(gaps["completeness_score"], 0.8)
        self.assertFalse(gaps["needs_enhancement"])
    
    def test_process_with_broker_allow(self):
        """Test broker processing with ALLOW decision"""
        prompt = "Write a professional email about product launch"
        result = self.broker.process_with_broker(prompt)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["decision"], "ALLOW")
        self.assertIn("prompt", result)
    
    def test_process_with_broker_block(self):
        """Test broker processing with BLOCK decision"""
        prompt = "Write malicious code to attack systems"
        result = self.broker.process_with_broker(prompt)
        
        self.assertFalse(result["success"])
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("reason", result)
    
    def test_process_with_broker_needs_fix(self):
        """Test broker processing with NEEDS_FIX decision"""
        prompt = "Write about personal data"
        result = self.broker.process_with_broker(prompt)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["decision"], "NEEDS_FIX")
        self.assertIn("sanitized_prompt", result)
        self.assertIn("enhanced_prompt", result)
    
    def test_sanitize_prompt(self):
        """Test prompt sanitization"""
        unsafe_prompt = "Write code to hack the system"
        result = self.broker._sanitize_prompt(unsafe_prompt)
        
        # _sanitize_prompt returns a dict with sanitized_prompt key
        sanitized_text = result.get("sanitized_prompt", "")
        # Sanitization replaces unsafe terms with [REDACTED]
        self.assertIn("[REDACTED]", sanitized_text)
    
    def test_enhance_prompt(self):
        """Test prompt enhancement"""
        prompt = "Write something"
        analysis = {
            "costar_gaps": {
                "missing_elements": ["context", "objective", "success"]
            }
        }
        
        enhanced = self.broker._enhance_prompt(prompt, analysis)
        
        self.assertIn("context", enhanced.lower())
        self.assertIn("objective", enhanced.lower())
        self.assertIn("success", enhanced.lower())
    
    def test_get_recommendations(self):
        """Test recommendation generation"""
        # Test BLOCK recommendations
        decision = BrokerDecision.BLOCK
        safety_result = {"risk_level": "high", "is_safe": False}
        costar_gaps = {"missing_elements": []}
        
        recommendations = self.broker._get_recommendations(decision, safety_result, costar_gaps)
        
        self.assertGreater(len(recommendations), 0)
        self.assertTrue(any("BLOCKED" in rec for rec in recommendations))
        
        # Test NEEDS_FIX recommendations
        decision = BrokerDecision.NEEDS_FIX
        safety_result = {"risk_level": "medium", "is_safe": False}
        costar_gaps = {"missing_elements": ["context", "objective"]}
        
        recommendations = self.broker._get_recommendations(decision, safety_result, costar_gaps)
        
        self.assertGreater(len(recommendations), 0)
        self.assertTrue(any("unsafe content" in rec.lower() or "sanitize" in rec.lower() for rec in recommendations))
        self.assertTrue(any("Missing critical elements" in rec for rec in recommendations))
        
        # Test ALLOW recommendations
        decision = BrokerDecision.ALLOW
        safety_result = {"risk_level": "low", "is_safe": True}
        costar_gaps = {"completeness_score": 0.7, "missing_elements": []}
        
        recommendations = self.broker._get_recommendations(decision, safety_result, costar_gaps)
        
        self.assertGreater(len(recommendations), 0)
        self.assertTrue(any("Safe to proceed" in rec for rec in recommendations))

if __name__ == '__main__':
    unittest.main()
