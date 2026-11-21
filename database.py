# database.py - PostgreSQL Database Manager for ISTVON Prompt Engine
try:
    import psycopg2
    from psycopg2 import extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import json
import time
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
        self._retry_at = 0.0  # after a failed connect, skip attempts until this time.monotonic()
        
        # Only attempt setup if psycopg2 is installed and credentials/URL are configured
        if HAS_PSYCOPG2 and (self.database_url or (self.user and self.dbname)):
            self.setup_database()
    
    def get_connection(self):
        """Get or establish PostgreSQL database connection"""
        if not HAS_PSYCOPG2:
            return None
        if not self.database_url and not (self.user and self.dbname):
            return None
        if time.monotonic() < self._retry_at:
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
            # A refused connect can take seconds (Windows retries); don't pay that on every request.
            self._retry_at = time.monotonic() + 60
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
                print("[OK] PostgreSQL prompt_log table & indexes verified successfully")
        except Exception as e:
            print(f"Error setting up PostgreSQL database: {e}")
            if conn:
                conn.rollback()
    
    def log_transformation(self, original_prompt: str, istvon_json: Dict, 
                          success: bool, domain: str = "auto", 
                          processing_time: int = 0, verdict: str = None,
                          reason: str = None, sanitized_prompt: str = None,
                          response: str = None) -> Optional[int]:
        """Insert one prompt_log row; returns its id, or None if the database is unavailable."""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            if verdict is None:
                verdict = "ALLOW" if success else "BLOCK"
            
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO prompt_log 
                    (timestamp, original_prompt, verdict, reason, sanitized_prompt, final_response, istvon_map_json)
                    VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    original_prompt,
                    verdict,
                    reason,
                    sanitized_prompt,
                    response,
                    json.dumps(istvon_json)
                ))
                row_id = cursor.fetchone()[0]
                conn.commit()
                return row_id
        except Exception as e:
            print(f"Error logging transformation to PostgreSQL: {e}")
            if conn:
                conn.rollback()
            return None

    def log_response(self, row_id: int, response: str) -> bool:
        """Store the generated LLM response on an existing prompt_log row."""
        conn = self.get_connection()
        if not conn or not row_id:
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE prompt_log SET final_response = %s WHERE id = %s", (response, row_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error storing response in PostgreSQL: {e}")
            conn.rollback()
            return False
