# utils/logger.py
import logging
import sys
from datetime import datetime
from typing import Any, Optional
import json

class Logger:
    """Enhanced logging utility for ISTVON application"""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, data: Optional[Any] = None):
        """Log debug message"""
        if data is not None:
            message += f" | Data: {self._format_data(data)}"
        self.logger.debug(message)
    
    def info(self, message: str, data: Optional[Any] = None):
        """Log info message"""
        if data is not None:
            message += f" | Data: {self._format_data(data)}"
        self.logger.info(message)
    
    def warning(self, message: str, data: Optional[Any] = None):
        """Log warning message"""
        if data is not None:
            message += f" | Data: {self._format_data(data)}"
        self.logger.warning(message)
    
    def error(self, message: str, data: Optional[Any] = None):
        """Log error message"""
        if data is not None:
            message += f" | Data: {self._format_data(data)}"
        self.logger.error(message)
    
    def critical(self, message: str, data: Optional[Any] = None):
        """Log critical message"""
        if data is not None:
            message += f" | Data: {self._format_data(data)}"
        self.logger.critical(message)
    
    def _format_data(self, data: Any) -> str:
        """Format data for logging"""
        try:
            if isinstance(data, (dict, list)):
                return json.dumps(data, indent=2, default=str)
            else:
                return str(data)
        except Exception:
            return str(data)
    
    def log_istvon_processing(self, prompt: str, result: dict, processing_time: float):
        """Log ISTVON processing details"""
        self.info("ISTVON Processing", {
            "prompt_length": len(prompt),
            "processing_time_ms": processing_time,
            "success": result.get("success", False),
            "domain": result.get("context", {}).get("domain", "unknown")
        })
    
    def log_broker_decision(self, decision: str, analysis: dict):
        """Log broker decision details"""
        self.info("Broker Decision", {
            "decision": decision,
            "risk_level": analysis.get("safety_analysis", {}).get("risk_level", "unknown"),
            "completeness_score": analysis.get("costar_gaps", {}).get("completeness_score", 0)
        })
    
    def log_api_call(self, endpoint: str, success: bool, response_time: float, error: Optional[str] = None):
        """Log API call details"""
        if success:
            self.info("API Call Success", {
                "endpoint": endpoint,
                "response_time_ms": response_time
            })
        else:
            self.error("API Call Failed", {
                "endpoint": endpoint,
                "response_time_ms": response_time,
                "error": error
            })
    
    def log_safety_analysis(self, prompt: str, safety_result: dict):
        """Log safety analysis results"""
        if safety_result.get("is_safe", True):
            self.info("Safety Analysis: Safe", {
                "risk_level": safety_result.get("risk_level", "low"),
                "issues_count": len(safety_result.get("issues", []))
            })
        else:
            self.warning("Safety Analysis: Unsafe", {
                "risk_level": safety_result.get("risk_level", "unknown"),
                "issues": safety_result.get("issues", [])
            })
    
    def log_json_parsing(self, success: bool, error: Optional[str] = None, fallback_used: bool = False):
        """Log JSON parsing results"""
        if success:
            self.info("JSON Parsing Success")
        else:
            self.error("JSON Parsing Failed", {
                "error": error,
                "fallback_used": fallback_used
            })
    
    def log_database_operation(self, operation: str, success: bool, record_id: Optional[str] = None):
        """Log database operations"""
        if success:
            self.info(f"Database {operation} Success", {"record_id": record_id})
        else:
            self.error(f"Database {operation} Failed", {"record_id": record_id})
    
    def log_performance_metrics(self, metrics: dict):
        """Log performance metrics"""
        self.info("Performance Metrics", metrics)
    
    def log_user_action(self, action: str, user_data: dict):
        """Log user actions (sanitized)"""
        sanitized_data = self._sanitize_user_data(user_data)
        self.info(f"User Action: {action}", sanitized_data)
    
    def _sanitize_user_data(self, data: dict) -> dict:
        """Sanitize user data for logging"""
        sanitized = {}
        safe_keys = ["prompt_length", "domain", "complexity", "processing_time"]
        
        for key, value in data.items():
            if key in safe_keys:
                sanitized[key] = value
        
        return sanitized

# Global logger instances
app_logger = Logger("ISTVONApp")
broker_logger = Logger("ISTVONBroker")
llm_logger = Logger("ISTVONLLM")
db_logger = Logger("ISTVONDB")
