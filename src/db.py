import json
import os
import time
import uuid
from typing import Dict, List, Optional

DB_FILE = "yotudrive.json"

class FileDatabase:
    def __new__(cls, db_path: str = DB_FILE):
        if os.environ.get("SUPABASE_URL"):
            from src.supabase_store import SupaFileDatabase
            return SupaFileDatabase()
        if os.environ.get("DATABASE_URL"):
            from src.pg_store import PGFileDatabase
            return PGFileDatabase()
        return super().__new__(cls)

    def __init__(self, db_path: str = DB_FILE):
        if hasattr(self, "data"):
            return # already pg store initialized
        self.db_path = db_path
        self.data = {} # Key is UUID
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    raw_data = json.load(f)
                
                new_data = {}
                dirty = False
                
                # Check if raw_data is list (legacy v1 format?) or dict
                if isinstance(raw_data, list):
                     # Convert list to dict
                     for item in raw_data:
                         if isinstance(item, dict):
                             uid = item.get('id', str(uuid.uuid4()))
                             item['id'] = uid
                             new_data[uid] = item
                     dirty = True
                elif isinstance(raw_data, dict):
                    for key, entry in raw_data.items():
                        if not isinstance(entry, dict):
                            continue
                            
                        # Check if entry has an ID
                        if 'id' not in entry:
                            # Legacy entry
                            new_id = str(uuid.uuid4())
                            entry['id'] = new_id
                            new_data[new_id] = entry
                            dirty = True
                        else:
                            # Trust the entry ID
                            new_data[entry['id']] = entry
                
                self.data = new_data
                if dirty:
                    self.save()
            except (json.JSONDecodeError, OSError):
                self.data = {}
        else:
            self.data = {}

    def save(self):
        """Saves the database to disk safely using a temporary file."""
        temp_path = self.db_path + ".tmp"
        try:
            with open(temp_path, 'w') as f:
                # Save as dict, not list
                json.dump(self.data, f, indent=4)
            
            # Atomic replacement if possible
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            os.rename(temp_path, self.db_path)
        except Exception as e:
            print(f"Error saving database: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def add_file(self, file_name: str, video_id: str, file_size: int, metadata: dict = None) -> str:
        """
        Register a file uploaded to YouTube (or local frame storage).
        Returns the UUID of the new entry.
        """
        new_id = str(uuid.uuid4())
        entry = {
            "id": new_id,
            "file_name": file_name,
            "video_id": video_id,  # Can be a YouTube ID or local path
            "file_size": file_size,
            "upload_date": time.time(),
            "metadata": metadata or {}
        }
        self.data[new_id] = entry
        self.save()
        return new_id

    def get_file(self, file_id: str) -> Optional[dict]:
        return self.data.get(file_id)

    def list_files(self) -> List[dict]:
        return list(self.data.values())

    def remove_file(self, file_id: str):
        if file_id in self.data:
            del self.data[file_id]
            self.save()
            print(f"[DB] Removed ID: {file_id}")
