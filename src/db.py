import json
import os
import time
import uuid
from typing import Dict, List, Optional

DB_FILE = "yotudrive.json"

class FileDatabase:
    def __init__(self, db_path: str = DB_FILE):
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

    def add_multipart_file(self, file_name: str, file_size: int, total_parts: int, metadata: dict = None) -> str:
        """Create a logical parent entry for split payloads."""
        parent_id = str(uuid.uuid4())
        entry = {
            "id": parent_id,
            "file_name": file_name,
            "video_id": "multipart_pending",
            "file_size": file_size,
            "upload_date": time.time(),
            "metadata": {
                "multipart": True,
                "total_parts": int(total_parts),
                "parts": [],
                **(metadata or {}),
            },
        }
        self.data[parent_id] = entry
        self.save()
        return parent_id

    def add_part_to_group(self, group_id: str, part_file_id: str, part_index: int) -> bool:
        group = self.data.get(group_id)
        if not group:
            return False
        meta = group.setdefault("metadata", {})
        parts = meta.setdefault("parts", [])
        parts.append({"part_index": int(part_index), "file_id": part_file_id})
        parts.sort(key=lambda p: p.get("part_index", 0))
        self.save()
        return True

    def list_group_parts(self, group_id: str) -> List[dict]:
        group = self.data.get(group_id)
        if not group:
            return []
        parts = group.get("metadata", {}).get("parts", [])
        resolved = []
        for part in sorted(parts, key=lambda p: p.get("part_index", 0)):
            file_id = part.get("file_id")
            if file_id and file_id in self.data:
                resolved.append(self.data[file_id])
        return resolved

    def get_file(self, file_id: str) -> Optional[dict]:
        return self.data.get(file_id)

    def list_files(self) -> List[dict]:
        return list(self.data.values())

    def find_by_video_id(self, video_id: str) -> List[dict]:
        return [entry for entry in self.data.values() if entry.get("video_id") == video_id]

    def attach_video(self, file_id: str, video_id: str, video_url: str = None) -> bool:
        entry = self.data.get(file_id)
        if not entry:
            return False
        entry["video_id"] = video_id
        meta = entry.setdefault("metadata", {})
        if video_url:
            meta["video_url"] = video_url
        self.save()
        return True

    def remove_file(self, file_id: str):
        if file_id in self.data:
            del self.data[file_id]
            self.save()
            print(f"[DB] Removed ID: {file_id}")
            return True
        return False
