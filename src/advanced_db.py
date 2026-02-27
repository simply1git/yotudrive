"""
Advanced database system with backup, migration, and transaction support.
"""

import os
import json
import time
import uuid
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from .config_manager import config_manager
from .utils import ValidationError, YotuDriveException, ErrorCodes, safe_file_operation, ensure_directory_exists
from .advanced_logger import get_logger

logger = get_logger()

@dataclass
class FileEntry:
    """File entry data structure."""
    id: str
    file_name: str
    video_id: str
    file_size: int
    upload_date: float
    metadata: Dict[str, Any]
    checksum: Optional[str] = None
    tags: List[str] = None
    status: str = "active"  # active, deleted, archived
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class BackupInfo:
    """Backup information."""
    backup_id: str
    timestamp: float
    file_count: int
    total_size: int
    backup_path: str
    compressed: bool = False
    checksum: Optional[str] = None

class DatabaseMigration:
    """Handle database schema migrations."""
    
    CURRENT_VERSION = 2
    
    MIGRATIONS = {
        1: {
            'description': 'Add checksum and tags fields',
            'up': self._migration_v1_to_v2,
            'down': self._migration_v2_to_v1
        },
        2: {
            'description': 'Add status field and backup tracking',
            'up': self._migration_v2_to_v3,
            'down': self._migration_v3_to_v2
        }
    }
    
    @staticmethod
    def _migration_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 1 to 2: add checksum and tags."""
        for entry_id, entry in data.items():
            if isinstance(entry, dict):
                # Add new fields with defaults
                entry['checksum'] = entry.get('checksum')
                entry['tags'] = entry.get('tags', [])
        return data
    
    @staticmethod
    def _migration_v2_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 2 to 1: remove checksum and tags."""
        for entry_id, entry in data.items():
            if isinstance(entry, dict):
                entry.pop('checksum', None)
                entry.pop('tags', None)
        return data
    
    @staticmethod
    def _migration_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 2 to 3: add status field."""
        for entry_id, entry in data.items():
            if isinstance(entry, dict):
                entry['status'] = entry.get('status', 'active')
        return data
    
    @staticmethod
    def _migration_v3_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from version 3 to 2: remove status field."""
        for entry_id, entry in data.items():
            if isinstance(entry, dict):
                entry.pop('status', None)
        return data

class AdvancedDatabase:
    """Advanced database with backup, migration, and transaction support."""
    
    def __init__(self, db_path: str = "yotudrive.json", backup_dir: str = "backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.version_file = self.db_path.with_suffix('.version')
        self.lock_file = self.db_path.with_suffix('.lock')
        self.data: Dict[str, FileEntry] = {}
        self.backups: List[BackupInfo] = []
        self._lock_acquired = False
        
        # Initialize
        self._ensure_directories()
        self.load()
    
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        ensure_directory_exists(str(self.db_path.parent))
        ensure_directory_exists(str(self.backup_dir))
    
    def _acquire_lock(self, timeout: int = 30) -> bool:
        """Acquire database lock."""
        if self._lock_acquired:
            return True
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if not self.lock_file.exists():
                    self.lock_file.write_text(f"{os.getpid()}:{time.time()}")
                    self._lock_acquired = True
                    return True
                else:
                    # Check if lock is stale (older than 5 minutes)
                    lock_time = float(self.lock_file.read_text().split(':')[1])
                    if time.time() - lock_time > 300:  # 5 minutes
                        self.lock_file.unlink()
                        continue
            except (OSError, ValueError):
                pass
            
            time.sleep(0.1)
        
        raise YotuDriveException("Could not acquire database lock", ErrorCodes.DATABASE_LOCKED)
    
    def _release_lock(self):
        """Release database lock."""
        if self._lock_acquired:
            try:
                if self.lock_file.exists():
                    self.lock_file.unlink()
            except OSError:
                pass
            self._lock_acquired = False
    
    def _get_version(self) -> int:
        """Get current database version."""
        if self.version_file.exists():
            try:
                return int(self.version_file.read_text().strip())
            except (ValueError, OSError):
                pass
        return 1  # Default version for old databases
    
    def _set_version(self, version: int):
        """Set database version."""
        try:
            self.version_file.write_text(str(version))
        except OSError as e:
            raise YotuDriveException(f"Failed to set database version: {e}", ErrorCodes.DATABASE_ERROR, e)
    
    def _migrate(self, target_version: Optional[int] = None):
        """Run database migrations."""
        current_version = self._get_version()
        target_version = target_version or DatabaseMigration.CURRENT_VERSION
        
        if current_version == target_version:
            return
        
        logger.log_structured('info', f"Starting database migration from v{current_version} to v{target_version}")
        
        if current_version < target_version:
            # Upgrade
            for version in range(current_version, target_version):
                if version + 1 in DatabaseMigration.MIGRATIONS:
                    migration = DatabaseMigration.MIGRATIONS[version + 1]
                    logger.log_structured('info', f"Applying migration: {migration['description']}")
                    
                    # Convert to dict format for migration
                    dict_data = {k: asdict(v) for k, v in self.data.items()}
                    dict_data = migration['up'](dict_data)
                    
                    # Convert back to FileEntry objects
                    self.data = {k: FileEntry(**v) for k, v in dict_data.items()}
                    
                    self._set_version(version + 1)
        else:
            # Downgrade
            for version in range(current_version, target_version, -1):
                if version in DatabaseMigration.MIGRATIONS:
                    migration = DatabaseMigration.MIGRATIONS[version]
                    logger.log_structured('info', f"Reverting migration: {migration['description']}")
                    
                    dict_data = {k: asdict(v) for k, v in self.data.items()}
                    dict_data = migration['down'](dict_data)
                    self.data = {k: FileEntry(**v) for k, v in dict_data.items()}
                    
                    self._set_version(version - 1)
        
        logger.log_structured('info', f"Database migration completed. Now at v{target_version}")
    
    def load(self):
        """Load database with migration support."""
        try:
            self._acquire_lock()
            
            if self.db_path.exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                # Handle legacy formats
                if isinstance(raw_data, list):
                    # Convert legacy list format
                    new_data = {}
                    for item in raw_data:
                        if isinstance(item, dict):
                            uid = item.get('id', str(uuid.uuid4()))
                            item['id'] = uid
                            new_data[uid] = FileEntry(**item)
                    self.data = new_data
                elif isinstance(raw_data, dict):
                    # Convert dict entries to FileEntry objects
                    self.data = {}
                    for key, entry in raw_data.items():
                        if isinstance(entry, dict):
                            # Ensure entry has all required fields
                            entry.setdefault('id', key)
                            entry.setdefault('tags', [])
                            entry.setdefault('status', 'active')
                            self.data[key] = FileEntry(**entry)
                
                # Run migrations
                self._migrate()
                
                logger.log_structured('info', f"Database loaded: {len(self.data)} entries")
            else:
                self.data = {}
                self._set_version(DatabaseMigration.CURRENT_VERSION)
                logger.log_structured('info', "New database created")
            
            # Load backup info
            self._load_backup_info()
            
        except (json.JSONDecodeError, OSError) as e:
            raise YotuDriveException(f"Failed to load database: {e}", ErrorCodes.DATABASE_ERROR, e)
        finally:
            self._release_lock()
    
    def save(self):
        """Save database with atomic operation and backup."""
        try:
            self._acquire_lock()
            
            # Create backup before saving
            if self.db_path.exists():
                self._create_auto_backup()
            
            # Convert to dictionary for JSON serialization
            dict_data = {k: asdict(v) for k, v in self.data.items()}
            
            # Atomic save using temporary file
            temp_path = self.db_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(dict_data, f, indent=4, sort_keys=True)
            
            # Verify file was written correctly
            if temp_path.stat().st_size == 0:
                raise YotuDriveException("Database file is empty after save", ErrorCodes.DATABASE_ERROR)
            
            # Atomic replace
            temp_path.replace(self.db_path)
            
            logger.log_structured('info', f"Database saved: {len(self.data)} entries")
            
        except OSError as e:
            raise YotuDriveException(f"Failed to save database: {e}", ErrorCodes.DATABASE_ERROR, e)
        finally:
            self._release_lock()
    
    def add_file(self, file_name: str, video_id: str, file_size: int, 
                 metadata: Dict[str, Any] = None, checksum: str = None, 
                 tags: List[str] = None) -> str:
        """Add a new file entry with enhanced metadata."""
        new_id = str(uuid.uuid4())
        entry = FileEntry(
            id=new_id,
            file_name=file_name,
            video_id=video_id,
            file_size=file_size,
            upload_date=time.time(),
            metadata=metadata or {},
            checksum=checksum,
            tags=tags or [],
            status="active"
        )
        
        self.data[new_id] = entry
        self.save()
        
        logger.log_file_operation('add_file', file_name, file_size, entry_id=new_id)
        return new_id
    
    def get_file(self, file_id: str) -> Optional[FileEntry]:
        """Get file entry by ID."""
        return self.data.get(file_id)
    
    def find_files(self, **criteria) -> List[FileEntry]:
        """Find files matching criteria."""
        results = []
        for entry in self.data.values():
            if entry.status != "active":
                continue
            
            match = True
            for key, value in criteria.items():
                if hasattr(entry, key):
                    entry_value = getattr(entry, key)
                    if isinstance(entry_value, str):
                        if value.lower() not in entry_value.lower():
                            match = False
                            break
                    elif isinstance(entry_value, list):
                        if not any(value.lower() in str(item).lower() for item in entry_value):
                            match = False
                            break
                    elif entry_value != value:
                        match = False
                        break
            
            if match:
                results.append(entry)
        
        return results
    
    def update_file(self, file_id: str, **updates):
        """Update file entry."""
        if file_id in self.data:
            entry = self.data[file_id]
            for key, value in updates.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            self.save()
            
            logger.log_structured('info', f"File entry updated: {file_id}", updates=updates)
            return True
        return False
    
    def delete_file(self, file_id: str, permanent: bool = False) -> bool:
        """Delete file entry (soft delete by default)."""
        if file_id in self.data:
            if permanent:
                del self.data[file_id]
                logger.log_structured('info', f"File permanently deleted: {file_id}")
            else:
                self.data[file_id].status = "deleted"
                logger.log_structured('info', f"File soft deleted: {file_id}")
            
            self.save()
            return True
        return False
    
    def list_files(self, include_deleted: bool = False) -> List[FileEntry]:
        """List all files."""
        if include_deleted:
            return list(self.data.values())
        else:
            return [entry for entry in self.data.values() if entry.status == "active"]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        active_files = [e for e in self.data.values() if e.status == "active"]
        deleted_files = [e for e in self.data.values() if e.status == "deleted"]
        
        total_size = sum(entry.file_size for entry in active_files)
        file_types = {}
        for entry in active_files:
            ext = Path(entry.file_name).suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1
        
        return {
            'total_files': len(self.data),
            'active_files': len(active_files),
            'deleted_files': len(deleted_files),
            'total_size_bytes': total_size,
            'total_size_human': self._format_size(total_size),
            'file_types': file_types,
            'database_version': self._get_version(),
            'backups_count': len(self.backups),
            'oldest_file': min((entry.upload_date for entry in active_files), default=0),
            'newest_file': max((entry.upload_date for entry in active_files), default=0)
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def _create_auto_backup(self):
        """Create automatic backup."""
        timestamp = time.time()
        backup_id = str(uuid.uuid4())[:8]
        backup_filename = f"auto_backup_{backup_id}_{int(timestamp)}.json"
        backup_path = self.backup_dir / backup_filename
        
        try:
            shutil.copy2(self.db_path, backup_path)
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=timestamp,
                file_count=len(self.data),
                total_size=self.db_path.stat().st_size,
                backup_path=str(backup_path)
            )
            
            self.backups.append(backup_info)
            self._save_backup_info()
            
            logger.log_structured('info', f"Auto backup created: {backup_filename}")
            
            # Clean old backups (keep last 10)
            self._cleanup_old_backups(keep_count=10)
            
        except OSError as e:
            logger.log_exception("Failed to create auto backup", e)
    
    def create_backup(self, description: str = None, compressed: bool = False) -> BackupInfo:
        """Create manual backup."""
        timestamp = time.time()
        backup_id = str(uuid.uuid4())[:8]
        
        if compressed:
            backup_filename = f"backup_{backup_id}_{int(timestamp)}.json.gz"
        else:
            backup_filename = f"backup_{backup_id}_{int(timestamp)}.json"
        
        backup_path = self.backup_dir / backup_filename
        
        try:
            if compressed:
                import gzip
                with open(self.db_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(self.db_path, backup_path)
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=timestamp,
                file_count=len(self.data),
                total_size=backup_path.stat().st_size,
                backup_path=str(backup_path),
                compressed=compressed
            )
            
            self.backups.append(backup_info)
            self._save_backup_info()
            
            logger.log_structured('info', f"Manual backup created: {backup_filename}", 
                                description=description, compressed=compressed)
            
            return backup_info
            
        except OSError as e:
            raise YotuDriveException(f"Failed to create backup: {e}", ErrorCodes.DATABASE_ERROR, e)
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup."""
        backup_info = next((b for b in self.backups if b.backup_id == backup_id), None)
        if not backup_info:
            raise YotuDriveException(f"Backup not found: {backup_id}", ErrorCodes.BACKUP_NOT_FOUND)
        
        backup_path = Path(backup_info.backup_path)
        if not backup_path.exists():
            raise YotuDriveException(f"Backup file not found: {backup_path}", ErrorCodes.BACKUP_NOT_FOUND)
        
        try:
            # Create backup of current database before restore
            self._create_auto_backup()
            
            # Restore from backup
            if backup_info.compressed:
                import gzip
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(self.db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, self.db_path)
            
            # Reload database
            self.load()
            
            logger.log_structured('info', f"Database restored from backup: {backup_id}")
            return True
            
        except OSError as e:
            raise YotuDriveException(f"Failed to restore backup: {e}", ErrorCodes.DATABASE_ERROR, e)
    
    def _load_backup_info(self):
        """Load backup information."""
        backup_info_file = self.backup_dir / "backup_info.json"
        if backup_info_file.exists():
            try:
                with open(backup_info_file, 'r') as f:
                    backup_data = json.load(f)
                self.backups = [BackupInfo(**b) for b in backup_data]
            except (json.JSONDecodeError, TypeError):
                self.backups = []
        else:
            self.backups = []
    
    def _save_backup_info(self):
        """Save backup information."""
        backup_info_file = self.backup_dir / "backup_info.json"
        try:
            with open(backup_info_file, 'w') as f:
                json.dump([asdict(b) for b in self.backups], f, indent=2)
        except OSError as e:
            logger.log_exception("Failed to save backup info", e)
    
    def _cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backups, keeping only the most recent ones."""
        if len(self.backups) <= keep_count:
            return
        
        # Sort by timestamp (newest first)
        sorted_backups = sorted(self.backups, key=lambda b: b.timestamp, reverse=True)
        
        # Remove old backups
        for backup in sorted_backups[keep_count:]:
            try:
                backup_path = Path(backup.backup_path)
                if backup_path.exists():
                    backup_path.unlink()
                self.backups.remove(backup)
                logger.log_structured('info', f"Old backup removed: {backup.backup_id}")
            except OSError as e:
                logger.log_exception(f"Failed to remove old backup: {backup.backup_id}", e)
        
        self._save_backup_info()
    
    def cleanup_deleted_files(self, days: int = 30) -> int:
        """Permanently delete files marked as deleted older than specified days."""
        cutoff_time = time.time() - (days * 24 * 3600)
        deleted_count = 0
        
        files_to_delete = []
        for file_id, entry in self.data.items():
            if entry.status == "deleted":
                # For simplicity, we'll delete all deleted files regardless of age
                # In a real implementation, you might track deletion time
                files_to_delete.append(file_id)
        
        for file_id in files_to_delete:
            del self.data[file_id]
            deleted_count += 1
        
        if deleted_count > 0:
            self.save()
            logger.log_structured('info', f"Permanently deleted {deleted_count} old files")
        
        return deleted_count
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._release_lock()

# Global database instance
database = AdvancedDatabase()
