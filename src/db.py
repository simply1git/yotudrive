import json
import os
import time
import uuid
import sqlite3
from typing import Dict, List, Optional

class FileDatabase:
    def __init__(self, db_path: str = "yotudrive.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            file_name TEXT,
            video_id TEXT,
            file_size INTEGER,
            upload_date REAL,
            metadata TEXT
        )''')
        self.conn.commit()

    def add_file(self, file_name: str, video_id: str, file_size: int, metadata: dict = None) -> str:
        """
        Register a file uploaded to YouTube (or local frame storage).
        Returns the UUID of the new entry.
        """
        new_id = str(uuid.uuid4())
        metadata_str = json.dumps(metadata or {})
        self.cursor.execute('INSERT INTO files VALUES (?, ?, ?, ?, ?, ?)', 
            (new_id, file_name, video_id, file_size, time.time(), metadata_str))
        self.conn.commit()
        return new_id

    def get_file(self, file_id: str) -> Optional[dict]:
        self.cursor.execute('SELECT id, file_name, video_id, file_size, upload_date, metadata FROM files WHERE id = ?', (file_id,))
        row = self.cursor.fetchone()
        if row:
            id, file_name, video_id, file_size, upload_date, metadata_str = row
            return {
                'id': id,
                'file_name': file_name,
                'video_id': video_id,
                'file_size': file_size,
                'upload_date': upload_date,
                'metadata': json.loads(metadata_str)
            }
        return None

    def list_files(self) -> List[dict]:
        self.cursor.execute('SELECT id, file_name, video_id, file_size, upload_date, metadata FROM files')
        rows = self.cursor.fetchall()
        files = []
        for row in rows:
            id, file_name, video_id, file_size, upload_date, metadata_str = row
            entry = {
                'id': id,
                'file_name': file_name,
                'video_id': video_id,
                'file_size': file_size,
                'upload_date': upload_date,
                'metadata': json.loads(metadata_str)
            }
            files.append(entry)
        return files

    def remove_file(self, file_id: str):
        self.cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        self.conn.commit()
        print(f"[DB] Removed ID: {file_id}")
