# database.py - PostgreSQL Database Manager for ISTVON Prompt Engine
try:
    import psycopg2
    from psycopg2 import extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import json
from datetime import datetime
from typing import Dict, Any, Optional
from config import Config

class DatabaseManager:
    """Manage PostgreSQL database operations for ISTVON logging and telemetry"""
    
    def __init__(self):
        # Load PostgreSQL connection parameters from Config (loaded from .env)
        self.host = Config.POSTGRES_HOST
        self.port = Config.POSTGRES_PORT
        self.dbname = Config.POSTGRES_DB
        self.user = Config.POSTGRES_USER
        self.password = Config.POSTGRES_PASSWORD
        self.database_url = Config.DATABASE_URL
        
        self.connection = None
        self._db_available = False
        
        # Only attempt setup if psycopg2 is installed and credentials/URL are configured
        if HAS_PSYCOPG2 and (self.database_url or (self.user and self.dbname)):
            self.setup_database()
    
    def get_connection(self):
        """Get or establish PostgreSQL database connection"""
        if not HAS_PSYCOPG2:
            return None
        if not self.database_url and not (self.user and self.dbname):
            return None
        
        try:
            if self.connection is None or self.connection.closed:
                if self.database_url:
                    self.connection = psycopg2.connect(self.database_url)
                else:
                    self.connection = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        dbname=self.dbname,
                        user=self.user,
                        password=self.password
                    )
                self._db_available = True
            return self.connection
        except Exception as e:
            if not hasattr(self, '_connection_warned'):
                print(f"PostgreSQL connection info: {e}")
                self._connection_warned = True
            return None
    
    def close_connection(self):
        """Close PostgreSQL database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None
    
    def setup_database(self):
        """Initialize database schema with prompt_log table and JSONB support"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cursor:
                # Create prompt_log table with JSONB and standard PostgreSQL types
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS prompt_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        original_prompt TEXT NOT NULL,
                        verdict VARCHAR(20) NOT NULL,
                        reason TEXT,
                        sanitized_prompt TEXT,
                        final_response TEXT,
                        istvon_map_json JSONB NOT NULL
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_prompt_log_timestamp ON prompt_log (timestamp DESC);
                    CREATE INDEX IF NOT EXISTS idx_prompt_log_verdict ON prompt_log (verdict);
                ''')
                conn.commit()
                print("✅ PostgreSQL prompt_log table & indexes verified successfully")
        except Exception as e:
            print(f"Error setting up PostgreSQL database: {e}")
            if conn:
                conn.rollback()
    
    def log_transformation(self, original_prompt: str, istvon_json: Dict, 
                          success: bool, domain: str = "auto", 
                          processing_time: int = 0, verdict: str = None,
                          reason: str = None, sanitized_prompt: str = None,
                          response: str = None) -> bool:
        """Log prompt transformation telemetry into PostgreSQL prompt_log table"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            if verdict is None:
                verdict = "ALLOW" if success else "BLOCK"
            
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO prompt_log 
                    (timestamp, original_prompt, verdict, reason, sanitized_prompt, final_response, istvon_map_json)
                    VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
                ''', (
                    original_prompt,
                    verdict,
                    reason,
                    sanitized_prompt,
                    response,
                    json.dumps(istvon_json)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error logging transformation to PostgreSQL: {e}")
            if conn:
                conn.rollback()
            return False
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get transformation analytics from PostgreSQL"""
        conn = self.get_connection()
        if not conn:
            return {"total_transformations": 0, "avg_prompt_length": 0, "success_rate": 0}
        
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total,
                        COALESCE(AVG(LENGTH(original_prompt)), 0) as avg_length,
                        COALESCE(COUNT(CASE WHEN verdict = 'ALLOW' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as success_rate
                    FROM prompt_log
                ''')
                result = cursor.fetchone()
                
                return {
                    "total_transformations": result[0] or 0,
                    "avg_prompt_length": round(float(result[1] or 0), 1),
                    "success_rate": round(float(result[2] or 0), 1)
                }
        except Exception as e:
            print(f"Error getting analytics: {e}")
            return {"total_transformations": 0, "avg_prompt_length": 0, "success_rate": 0}
    
    def get_recent_transformations(self, limit: int = 5) -> list:
        """Get recent transformations for UI display"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT original_prompt, istvon_map_json, timestamp, verdict
                    FROM prompt_log 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                ''', (limit,))
                results = cursor.fetchall()
                
                return [
                    {
                        "prompt": str(row[0])[:100] + "..." if len(str(row[0])) > 100 else str(row[0]),
                        "timestamp": row[2].strftime("%Y-%m-%d %H:%M:%S") if hasattr(row[2], 'strftime') else str(row[2]),
                        "success": row[3] == "ALLOW"
                    }
                    for row in results
                ]
        except Exception as e:
            print(f"Error getting recent transformations: {e}")
            return []
    
    def get_sanitized_prompts(self, limit: int = 10) -> list:
        """Get recent sanitized prompts for UI display"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT original_prompt, istvon_map_json, sanitized_prompt, timestamp, verdict
                    FROM prompt_log 
                    WHERE sanitized_prompt IS NOT NULL AND sanitized_prompt != ''
                    ORDER BY timestamp DESC 
                    LIMIT %s
                ''', (limit,))
                results = cursor.fetchall()
                
                return [
                    {
                        "original_prompt": str(row[0]),
                        "istvon_json": row[1] if isinstance(row[1], dict) else json.loads(str(row[1])) if row[1] else {},
                        "sanitized_prompt": str(row[2]) if row[2] else "",
                        "timestamp": row[3].strftime("%Y-%m-%d %H:%M:%S") if hasattr(row[3], 'strftime') else str(row[3]),
                        "verdict": row[4]
                    }
                    for row in results
                ]
        except Exception as e:
            print(f"Error getting sanitized prompts: {e}")
            return []
    
    def import_from_json_file(self, json_filepath: str) -> bool:
        """Import response data from a JSON file and store in PostgreSQL database"""
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                response_data = json.load(f)
            
            if 'original_prompt' in response_data:
                original_prompt = response_data.get('original_prompt', '')
                verdict = response_data.get('verdict', 'ALLOW')
                reason = response_data.get('reason', 'Imported from JSON')
                sanitized_prompt = response_data.get('sanitized_prompt')
                final_response = response_data.get('final_response', '')
                istvon_data = response_data.get('istvon_map_json', {})
                metadata = response_data.get('metadata', {})
                processing_time = metadata.get('processing_time_ms', 0)
            else:
                metadata = response_data.get('metadata', {})
                input_data = response_data.get('input', {})
                istvon_data = response_data.get('istvon_framework', {})
                generated_response = response_data.get('generated_response', '')
                
                original_prompt = input_data.get('original_prompt', '')
                verdict = metadata.get('verdict', 'ALLOW')
                reason = metadata.get('reason', 'Imported from JSON')
                sanitized_prompt = input_data.get('sanitized_prompt')
                final_response = generated_response
                processing_time = metadata.get('processing_time_ms', 0)
            
            return self.log_transformation(
                original_prompt=original_prompt,
                istvon_json=istvon_data,
                success=verdict == 'ALLOW',
                domain='auto',
                processing_time=processing_time,
                verdict=verdict,
                reason=reason,
                sanitized_prompt=sanitized_prompt,
                response=final_response
            )
        except Exception as e:
            print(f"Error importing from JSON file: {str(e)}")
            return False
    
    def get_response_by_timestamp(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Get response data by timestamp"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, timestamp, original_prompt, verdict, reason, 
                           sanitized_prompt, final_response, istvon_map_json
                    FROM prompt_log 
                    WHERE TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') LIKE %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (f"%{timestamp}%",))
                result = cursor.fetchone()
                
                if result:
                    return {
                        "id": result[0],
                        "timestamp": result[1].strftime("%Y-%m-%d %H:%M:%S") if hasattr(result[1], 'strftime') else str(result[1]),
                        "original_prompt": str(result[2]),
                        "verdict": result[3],
                        "reason": str(result[4]) if result[4] else "",
                        "sanitized_prompt": str(result[5]) if result[5] else "",
                        "final_response": str(result[6]) if result[6] else "",
                        "istvon_map_json": result[7] if isinstance(result[7], dict) else json.loads(str(result[7])) if result[7] else {}
                    }
                return None
        except Exception as e:
            print(f"Error getting response by timestamp: {e}")
            return None
