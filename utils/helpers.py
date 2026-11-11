# utils/helpers.py
import time
from datetime import datetime
from typing import Any, Dict

class HelperFunctions:
    """General helper functions"""
    
    @staticmethod
    def format_timestamp(timestamp: Any) -> str:
        """Format timestamp for display"""
        if isinstance(timestamp, str):
            return timestamp
        elif hasattr(timestamp, 'strftime'):
            return timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return str(timestamp)
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text with ellipsis if too long"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    @staticmethod
    def get_file_size_info(data: Dict) -> str:
        """Get approximate size information for data"""
        json_str = str(data)
        size_kb = len(json_str.encode('utf-8')) / 1024
        return f"{size_kb:.1f} KB"

# Example usage helper
class ExamplePrompts:
    """Predefined example prompts for demonstration"""
    
    EXAMPLES = {
        "business_email": "Write a professional email to clients announcing our new product launch. Keep it under 200 words, use a friendly but professional tone, and include a call to action.",
        "technical_doc": "Create comprehensive API documentation for our new payment processing system. Include authentication methods, endpoint descriptions, error codes, and code examples in Python and JavaScript.",
        "blog_post": "Write an engaging blog post about the ethical implications of AI in healthcare. Target healthcare professionals, keep it around 800 words, and include real-world examples.",
        "research_summary": "Summarize the key findings from recent climate change research papers. Focus on actionable insights for policymakers, keep it concise but comprehensive."
    }
    
    @classmethod
    def get_example(cls, key: str) -> str:
        """Get a specific example prompt"""
        return cls.EXAMPLES.get(key, "")
    
    @classmethod
    def get_all_examples(cls) -> Dict[str, str]:
        """Get all example prompts"""
        return cls.EXAMPLES