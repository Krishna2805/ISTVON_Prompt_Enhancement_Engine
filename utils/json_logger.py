# utils/json_logger.py
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

class RuleEngineLogger:
    """JSON file logger for local rule engine decisions"""
    
    def __init__(self, log_file: str = "rule_engine_logs.json"):
        self.log_file = log_file
        self.ensure_log_file_exists()
    
    def ensure_log_file_exists(self):
        """Ensure the log file exists with proper structure"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                pass  # Start with empty file for line-by-line JSON
    
    def log_decision(self, prompt: str, verdict: str, reason: Optional[str] = None) -> None:
        """Log a rule engine decision to JSON file in the specified format"""
        
        # Format timestamp as ISO with Z suffix
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        log_entry = {
            "ts": timestamp,
            "verdict": verdict,
            "prompt": prompt,
            "reason": reason
        }
        
        # Append as a single JSON line
        with open(self.log_file, 'a') as f:
            json.dump(log_entry, f)
            f.write('\n')
    
    def get_recent_logs(self, limit: int = 10) -> list:
        """Get recent log entries"""
        logs = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line.strip()))
            return logs[-limit:] if logs else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_logs_by_verdict(self, verdict: str) -> list:
        """Get logs filtered by verdict"""
        logs = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        log_entry = json.loads(line.strip())
                        if log_entry.get('verdict') == verdict:
                            logs.append(log_entry)
            return logs
        except (json.JSONDecodeError, FileNotFoundError):
            return []
