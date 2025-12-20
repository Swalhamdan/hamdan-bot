"""
Database module for persistent storage of download jobs.
Uses SQLite for simplicity.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class DownloadJobDB:
    """Database manager for download jobs."""
    
    def __init__(self, db_path: str = "download_jobs.db"):
        """
        Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create download_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                torrent_hash TEXT NOT NULL UNIQUE,
                torrent_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'downloading',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                notified BOOLEAN DEFAULT 0,
                channel_id INTEGER NULL,
                message_id INTEGER NULL
            )
        """)
        
        # Create index on torrent_hash for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_torrent_hash 
            ON download_jobs(torrent_hash)
        """)
        
        # Create index on status for faster filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status 
            ON download_jobs(status)
        """)
        
        conn.commit()
        conn.close()
    
    def add_job(
        self,
        user_id: int,
        torrent_hash: str,
        torrent_name: str,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None
    ) -> int:
        """
        Add a new download job.
        
        Args:
            user_id: Discord user ID who requested the download
            torrent_hash: Hash of the torrent
            torrent_name: Name of the torrent
            channel_id: Optional channel ID where the request was made
            message_id: Optional message ID of the request
            
        Returns:
            Job ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO download_jobs 
                (user_id, torrent_hash, torrent_name, status, channel_id, message_id)
                VALUES (?, ?, ?, 'downloading', ?, ?)
            """, (user_id, torrent_hash, torrent_name, channel_id, message_id))
            
            job_id = cursor.lastrowid
            conn.commit()
            return job_id
        finally:
            conn.close()
    
    def get_job_by_hash(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get a job by torrent hash.
        
        Args:
            torrent_hash: Hash of the torrent
            
        Returns:
            Job dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM download_jobs 
                WHERE torrent_hash = ?
            """, (torrent_hash,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all active (downloading) jobs.
        
        Returns:
            List of job dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM download_jobs 
                WHERE status = 'downloading' AND notified = 0
            """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def update_job_status(
        self,
        torrent_hash: str,
        status: str,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """
        Update the status of a job.
        
        Args:
            torrent_hash: Hash of the torrent
            status: New status (e.g., 'completed', 'failed', 'paused')
            completed_at: Optional completion timestamp
            
        Returns:
            True if updated, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if completed_at:
                cursor.execute("""
                    UPDATE download_jobs 
                    SET status = ?, completed_at = ?
                    WHERE torrent_hash = ?
                """, (status, completed_at.isoformat(), torrent_hash))
            else:
                cursor.execute("""
                    UPDATE download_jobs 
                    SET status = ?
                    WHERE torrent_hash = ?
                """, (status, torrent_hash))
            
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        finally:
            conn.close()
    
    def mark_notified(self, torrent_hash: str) -> bool:
        """
        Mark a job as notified.
        
        Args:
            torrent_hash: Hash of the torrent
            
        Returns:
            True if updated, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE download_jobs 
                SET notified = 1
                WHERE torrent_hash = ?
            """, (torrent_hash,))
            
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        finally:
            conn.close()
    
    def delete_job(self, torrent_hash: str) -> bool:
        """
        Delete a job.
        
        Args:
            torrent_hash: Hash of the torrent
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM download_jobs 
                WHERE torrent_hash = ?
            """, (torrent_hash,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            conn.close()

