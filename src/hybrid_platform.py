"""
YotuDrive 2.0 - Hybrid Platform
Combines offline capabilities with Google Drive integration and device uploads
"""

import os
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

from src.config_manager import config_manager
from src.advanced_logger import get_logger
from src.utils import YotuDriveException, ErrorCodes, FileValidator, NamingConvention
from src.google_integration import YotuDriveGoogleIntegration
from src.advanced_db import database

logger = get_logger()

class AccountType(Enum):
    """Account type options"""
    OFFLINE = "offline"
    GOOGLE = "google"
    HYBRID = "hybrid"

class UploadMethod(Enum):
    """Upload method options"""
    WEB = "web"
    DEVICE = "device"
    GOOGLE_DRIVE = "google_drive"
    HYBRID = "hybrid"

@dataclass
class HybridUser:
    """Enhanced user with hybrid capabilities"""
    id: str
    account_type: AccountType
    username: str
    email: Optional[str] = None
    display_name: str
    avatar_url: Optional[str] = None
    google_user_id: Optional[str] = None
    preferences: Dict[str, Any] = None
    created_at: float = None
    last_active: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_active is None:
            self.last_active = time.time()
        if self.preferences is None:
            self.preferences = {
                'default_upload_method': UploadMethod.WEB.value,
                'auto_sync': False,
                'preferred_storage': 'local',
                'device_upload_enabled': True,
                'google_integration_enabled': True if self.account_type in [AccountType.GOOGLE, AccountType.HYBRID] else False
            }

@dataclass
class HybridFileMetadata:
    """Enhanced file metadata for hybrid platform"""
    id: str
    user_id: str
    account_type: AccountType
    original_name: str
    file_size: int
    mime_type: str
    upload_method: UploadMethod
    storage_location: str  # local, google_drive, youtube
    google_file_id: Optional[str] = None
    youtube_video_id: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    video_details: Optional[Dict[str, Any]] = None
    encoding_status: str = "pending"
    sync_status: str = "not_synced"
    created_at: float = None
    modified_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.modified_at is None:
            self.modified_at = time.time()

class DeviceUploadService:
    """Device upload service with multiple protocols"""
    
    def __init__(self):
        self.upload_sessions = {}
        self.supported_protocols = ['HTTP', 'WebDAV', 'FTP', 'SMB']
        self.max_file_size = 100 * 1024 * 1024 * 1024  # 100GB
    
    def create_upload_session(self, user_id: str, protocol: str = 'HTTP') -> str:
        """Create upload session for device"""
        session_id = str(uuid.uuid4())
        
        self.upload_sessions[session_id] = {
            'user_id': user_id,
            'protocol': protocol,
            'created_at': time.time(),
            'expires_at': time.time() + 3600,  # 1 hour
            'status': 'active',
            'uploaded_files': []
        }
        
        logger.log_structured('info', 'Device upload session created', 
                          session_id=session_id,
                          protocol=protocol,
                          user_id=user_id)
        
        return session_id
    
    def upload_file(self, session_id: str, file_data: bytes, 
                   filename: str, mime_type: str) -> Dict[str, Any]:
        """Upload file from device"""
        if session_id not in self.upload_sessions:
            raise YotuDriveException("Invalid upload session", ErrorCodes.AUTHENTICATION_ERROR)
        
        session = self.upload_sessions[session_id]
        
        # Validate session
        if time.time() > session['expires_at']:
            raise YotuDriveException("Upload session expired", ErrorCodes.AUTHENTICATION_ERROR)
        
        # Validate file
        if len(file_data) > self.max_file_size:
            raise YotuDriveException("File too large", ErrorCodes.FILE_TOO_LARGE)
        
        # Create file metadata
        file_id = str(uuid.uuid4())
        temp_path = f"temp/device_uploads/{session_id}/{file_id}"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        # Save file temporarily
        with open(temp_path, 'wb') as f:
            f.write(file_data)
        
        # Add to session
        file_info = {
            'file_id': file_id,
            'filename': filename,
            'size': len(file_data),
            'mime_type': mime_type,
            'temp_path': temp_path,
            'uploaded_at': time.time()
        }
        
        session['uploaded_files'].append(file_info)
        
        logger.log_structured('info', 'Device file uploaded', 
                          session_id=session_id,
                          file_id=file_id,
                          filename=filename,
                          size=len(file_data))
        
        return {
            'file_id': file_id,
            'status': 'uploaded',
            'next_step': 'processing'
        }
    
    def complete_upload_session(self, session_id: str) -> Dict[str, Any]:
        """Complete upload session and process files"""
        if session_id not in self.upload_sessions:
            raise YotuDriveException("Invalid upload session", ErrorCodes.AUTHENTICATION_ERROR)
        
        session = self.upload_sessions[session_id]
        processed_files = []
        
        # Process all uploaded files
        for file_info in session['uploaded_files']:
            try:
                # Create file metadata
                file_metadata = HybridFileMetadata(
                    id=file_info['file_id'],
                    user_id=session['user_id'],
                    account_type=AccountType.OFFLINE,  # Will be updated based on user
                    original_name=file_info['filename'],
                    file_size=file_info['size'],
                    mime_type=file_info['mime_type'],
                    upload_method=UploadMethod.DEVICE,
                    storage_location='local',
                    device_info={
                        'protocol': session['protocol'],
                        'session_id': session_id,
                        'upload_time': file_info['uploaded_at']
                    }
                )
                
                # Move file to permanent location
                permanent_path = f"data/files/{file_info['file_id']}/{file_info['filename']}"
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                os.rename(file_info['temp_path'], permanent_path)
                
                processed_files.append({
                    'file_id': file_info['file_id'],
                    'filename': file_info['filename'],
                    'permanent_path': permanent_path,
                    'status': 'processed'
                })
                
                # Store in database
                database.add_file(
                    file_name=file_info['filename'],
                    video_id="",  # Will be set after encoding
                    file_size=file_info['size'],
                    metadata={
                        'account_type': AccountType.OFFLINE.value,
                        'upload_method': UploadMethod.DEVICE.value,
                        'storage_location': 'local',
                        'device_info': file_metadata.device_info
                    }
                )
                
            except Exception as e:
                logger.log_exception('File processing failed', e)
                processed_files.append({
                    'file_id': file_info['file_id'],
                    'filename': file_info['filename'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Clean up session
        del self.upload_sessions[session_id]
        
        logger.log_structured('info', 'Device upload session completed', 
                          session_id=session_id,
                          files_processed=len(processed_files))
        
        return {
            'session_id': session_id,
            'files': processed_files,
            'status': 'completed'
        }
    
    def get_upload_status(self, session_id: str) -> Dict[str, Any]:
        """Get upload session status"""
        if session_id not in self.upload_sessions:
            return {'error': 'Session not found'}
        
        session = self.upload_sessions[session_id]
        
        return {
            'session_id': session_id,
            'protocol': session['protocol'],
            'status': session['status'],
            'files_uploaded': len(session['uploaded_files']),
            'total_size': sum(f['size'] for f in session['uploaded_files']),
            'expires_at': session['expires_at'],
            'time_remaining': max(0, session['expires_at'] - time.time())
        }

class HybridPlatform:
    """Main hybrid platform combining offline and Google Drive capabilities"""
    
    def __init__(self):
        self.google_integration = YotuDriveGoogleIntegration()
        self.device_service = DeviceUploadService()
        self.current_user = None
        self.user_preferences = {}
        
        # Load configuration
        self.load_configuration()
    
    def load_configuration(self):
        """Load platform configuration"""
        try:
            config_file = "hybrid_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    
                self.user_preferences = config.get('user_preferences', {})
                logger.log_structured('info', 'Hybrid configuration loaded')
            else:
                # Create default configuration
                self.create_default_configuration()
                
        except Exception as e:
            logger.log_exception('Failed to load configuration', e)
            self.create_default_configuration()
    
    def create_default_configuration(self):
        """Create default configuration"""
        default_config = {
            'platform_settings': {
                'default_account_type': AccountType.OFFLINE.value,
                'allow_device_uploads': True,
                'allow_google_integration': True,
                'auto_sync_enabled': False,
                'preferred_storage': 'local'
            },
            'device_settings': {
                'supported_protocols': ['HTTP', 'WebDAV', 'FTP'],
                'max_file_size': 100 * 1024 * 1024 * 1024,
                'session_timeout': 3600
            },
            'google_settings': {
                'auto_upload_to_youtube': True,
                'default_privacy': 'unlisted',
                'default_quality': '1080p'
            },
            'user_preferences': {}
        }
        
        try:
            with open("hybrid_config.json", 'w') as f:
                json.dump(default_config, f, indent=2)
            
            self.user_preferences = default_config['user_preferences']
            logger.log_structured('info', 'Default configuration created')
            
        except Exception as e:
            logger.log_exception('Failed to create configuration', e)
    
    def create_account(self, account_type: AccountType, username: str, 
                     email: str = None, display_name: str = None) -> HybridUser:
        """Create account based on type"""
        user_id = str(uuid.uuid4())
        
        user = HybridUser(
            id=user_id,
            account_type=account_type,
            username=username,
            email=email,
            display_name=display_name or username
        )
        
        # Handle different account types
        if account_type == AccountType.GOOGLE:
            # Will be handled by Google OAuth flow
            pass
        elif account_type == AccountType.OFFLINE:
            # Create local account
            self._create_local_account(user)
        elif account_type == AccountType.HYBRID:
            # Create hybrid account
            self._create_hybrid_account(user)
        
        logger.log_structured('info', 'Account created', 
                          user_id=user_id,
                          account_type=account_type.value,
                          username=username)
        
        return user
    
    def _create_local_account(self, user: HybridUser):
        """Create local offline account"""
        # Store user in local database
        user_data = asdict(user)
        
        # In production, use proper database
        users_file = "data/users.json"
        os.makedirs(os.path.dirname(users_file), exist_ok=True)
        
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users = json.load(f)
        else:
            users = {}
        
        users[user.id] = user_data
        
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def _create_hybrid_account(self, user: HybridUser):
        """Create hybrid account (local + Google)"""
        # Create local account first
        self._create_local_account(user)
        
        # Google integration will be handled separately
        logger.log_structured('info', 'Hybrid account created', 
                          user_id=user.id,
                          username=user.username)
    
    def authenticate_user(self, account_type: AccountType, credentials: Dict[str, Any]) -> Optional[HybridUser]:
        """Authenticate user based on account type"""
        try:
            if account_type == AccountType.GOOGLE:
                # Handle Google OAuth
                google_user = self.google_integration.authenticate_user(
                    credentials.get('authorization_code')
                )
                
                if google_user:
                    # Convert to hybrid user
                    hybrid_user = HybridUser(
                        id=google_user.id,
                        account_type=AccountType.GOOGLE,
                        username=google_user.username,
                        email=google_user.email,
                        display_name=google_user.display_name,
                        google_user_id=google_user.id
                    )
                    
                    self.current_user = hybrid_user
                    return hybrid_user
                
            elif account_type == AccountType.OFFLINE:
                # Handle local authentication
                return self._authenticate_local_user(credentials)
            
            elif account_type == AccountType.HYBRID:
                # Handle hybrid authentication
                return self._authenticate_hybrid_user(credentials)
            
            return None
            
        except Exception as e:
            logger.log_exception('User authentication failed', e)
            raise YotuDriveException("Authentication failed", ErrorCodes.AUTHENTICATION_ERROR, e)
    
    def _authenticate_local_user(self, credentials: Dict[str, Any]) -> Optional[HybridUser]:
        """Authenticate local user"""
        username = credentials.get('username')
        password = credentials.get('password')
        
        # In production, use proper password hashing
        users_file = "data/users.json"
        
        if not os.path.exists(users_file):
            return None
        
        with open(users_file, 'r') as f:
            users = json.load(f)
        
        for user_data in users.values():
            if user_data.get('username') == username:
                # Simple password check (in production, use bcrypt)
                if user_data.get('password') == password:
                    user = HybridUser(**user_data)
                    self.current_user = user
                    return user
        
        return None
    
    def _authenticate_hybrid_user(self, credentials: Dict[str, Any]) -> Optional[HybridUser]:
        """Authenticate hybrid user (local + Google)"""
        # Try local authentication first
        local_user = self._authenticate_local_user(credentials)
        
        if local_user:
            # Try Google authentication if provided
            if 'google_code' in credentials:
                google_user = self.google_integration.authenticate_user(
                    credentials.get('google_code')
                )
                
                if google_user:
                    # Update user with Google info
                    local_user.google_user_id = google_user.id
                    local_user.email = google_user.email
                    local_user.account_type = AccountType.HYBRID
                    
                    # Update stored user data
                    self._update_user_in_database(local_user)
            
            self.current_user = local_user
            return local_user
        
        return None
    
    def _update_user_in_database(self, user: HybridUser):
        """Update user in local database"""
        users_file = "data/users.json"
        
        with open(users_file, 'r') as f:
            users = json.load(f)
        
        users[user.id] = asdict(user)
        
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def upload_file(self, file_path: str, upload_method: UploadMethod = None, 
                   metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload file using preferred method"""
        if not self.current_user:
            raise YotuDriveException("User not authenticated", ErrorCodes.AUTHENTICATION_ERROR)
        
        # Determine upload method
        if not upload_method:
            upload_method = UploadMethod(self.current_user.preferences.get('default_upload_method', UploadMethod.WEB.value))
        
        try:
            if upload_method == UploadMethod.WEB:
                return self._web_upload(file_path, metadata)
            elif upload_method == UploadMethod.DEVICE:
                return self._device_upload(file_path, metadata)
            elif upload_method == UploadMethod.GOOGLE_DRIVE:
                return self._google_drive_upload(file_path, metadata)
            elif upload_method == UploadMethod.HYBRID:
                return self._hybrid_upload(file_path, metadata)
            else:
                raise YotuDriveException("Unsupported upload method", ErrorCodes.INVALID_FORMAT)
                
        except Exception as e:
            logger.log_exception('File upload failed', e)
            raise YotuDriveException("File upload failed", ErrorCodes.UPLOAD_FAILED, e)
    
    def _web_upload(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Web upload (original YotuDrive method)"""
        # Validate file
        validated_path, file_size = FileValidator.validate_file(file_path)
        
        # Create file metadata
        file_metadata = HybridFileMetadata(
            id=str(uuid.uuid4()),
            user_id=self.current_user.id,
            account_type=self.current_user.account_type,
            original_name=Path(file_path).name,
            file_size=file_size,
            mime_type=self._get_mime_type(file_path),
            upload_method=UploadMethod.WEB,
            storage_location='local'
        )
        
        # Process file (encoding to video)
        from src.encoder import Encoder
        from src.ffmpeg_utils import stitch_frames
        
        frames_dir = f"data/frames/{file_metadata.id}"
        encoder = Encoder(file_path, frames_dir)
        encoder.run()
        
        video_path = f"data/videos/{file_metadata.id}.mp4"
        stitch_frames(frames_dir, video_path)
        
        # Store in database
        database.add_file(
            file_name=file_metadata.original_name,
            video_id="",  # Will be set after YouTube upload
            file_size=file_size,
            metadata={
                'account_type': self.current_user.account_type.value,
                'upload_method': UploadMethod.WEB.value,
                'storage_location': 'local',
                'video_path': video_path
            }
        )
        
        return {
            'file_id': file_metadata.id,
            'status': 'uploaded',
            'video_path': video_path,
            'next_step': 'youtube_upload'
        }
    
    def _device_upload(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Device upload (mobile/desktop app)"""
        # Similar to web upload but with device-specific handling
        result = self._web_upload(file_path, metadata)
        
        # Add device-specific metadata
        if metadata and 'device_info' in metadata:
            # Update file metadata with device info
            pass
        
        return result
    
    def _google_drive_upload(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Upload to Google Drive"""
        if not self.current_user.google_user_id:
            raise YotuDriveException("Google account not linked", ErrorCodes.AUTHENTICATION_ERROR)
        
        return self.google_integration.upload_file_or_folder(file_path, metadata)
    
    def _hybrid_upload(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Hybrid upload (local + Google Drive)"""
        # Upload locally first
        local_result = self._web_upload(file_path, metadata)
        
        # Also upload to Google Drive if enabled
        if self.current_user.preferences.get('google_integration_enabled', False):
            google_result = self._google_drive_upload(file_path, metadata)
            
            # Update metadata with Google info
            local_result['google_file_id'] = google_result.get('google_file_id')
            local_result['storage_location'] = 'hybrid'
        
        return local_result
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for file"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed'
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def get_user_files(self, storage_filter: str = None) -> List[Dict[str, Any]]:
        """Get user files from all storage locations"""
        if not self.current_user:
            raise YotuDriveException("User not authenticated", ErrorCodes.AUTHENTICATION_ERROR)
        
        all_files = []
        
        # Get local files
        local_files = database.list_files()
        for file_entry in local_files:
            if file_entry.metadata.get('user_id') == self.current_user.id:
                file_data = asdict(file_entry)
                file_data['storage_location'] = 'local'
                all_files.append(file_data)
        
        # Get Google Drive files if integrated
        if self.current_user.account_type in [AccountType.GOOGLE, AccountType.HYBRID]:
            try:
                google_files = self.google_integration.get_user_files()
                for file_data in google_files:
                    file_data['storage_location'] = 'google_drive'
                    all_files.append(file_data)
            except Exception as e:
                logger.log_exception('Failed to get Google Drive files', e)
        
        # Apply filter
        if storage_filter:
            all_files = [f for f in all_files if f.get('storage_location') == storage_filter]
        
        return all_files
    
    def sync_files(self, direction: str = 'bidirectional') -> Dict[str, Any]:
        """Sync files between local and Google Drive"""
        if not self.current_user:
            raise YotuDriveException("User not authenticated", ErrorCodes.AUTHENTICATION_ERROR)
        
        if self.current_user.account_type not in [AccountType.HYBRID]:
            return {'error': 'Sync not available for this account type'}
        
        try:
            sync_result = {
                'local_to_google': [],
                'google_to_local': [],
                'conflicts': [],
                'status': 'completed'
            }
            
            if direction in ['local_to_google', 'bidirectional']:
                # Sync local files to Google Drive
                local_files = [f for f in self.get_user_files('local')]
                for file_data in local_files:
                    try:
                        google_result = self.google_integration.upload_file_or_folder(
                            file_data['file_path'],
                            {'sync_operation': True}
                        )
                        sync_result['local_to_google'].append({
                            'file_id': file_data['id'],
                            'google_file_id': google_result.get('google_file_id'),
                            'status': 'synced'
                        })
                    except Exception as e:
                        logger.log_exception('Sync to Google failed', e)
                        sync_result['local_to_google'].append({
                            'file_id': file_data['id'],
                            'status': 'failed',
                            'error': str(e)
                        })
            
            if direction in ['google_to_local', 'bidirectional']:
                # Sync Google Drive files to local
                google_files = [f for f in self.get_user_files('google_drive')]
                for file_data in google_files:
                    try:
                        # Download from Google Drive
                        local_result = self._download_from_google_drive(file_data)
                        sync_result['google_to_local'].append({
                            'google_file_id': file_data['google_file_id'],
                            'local_file_id': local_result.get('file_id'),
                            'status': 'synced'
                        })
                    except Exception as e:
                        logger.log_exception('Sync from Google failed', e)
                        sync_result['google_to_local'].append({
                            'google_file_id': file_data['google_file_id'],
                            'status': 'failed',
                            'error': str(e)
                        })
            
            logger.log_structured('info', 'File sync completed', 
                              direction=direction,
                              files_synced=len(sync_result['local_to_google']) + len(sync_result['google_to_local']))
            
            return sync_result
            
        except Exception as e:
            logger.log_exception('File sync failed', e)
            raise YotuDriveException("File sync failed", ErrorCodes.DATABASE_ERROR, e)
    
    def _download_from_google_drive(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from Google Drive"""
        # Implementation would download file from Google Drive
        # and store it locally
        return {
            'file_id': str(uuid.uuid4()),
            'status': 'downloaded'
        }
    
    def get_platform_stats(self) -> Dict[str, Any]:
        """Get platform statistics"""
        if not self.current_user:
            return {'error': 'User not authenticated'}
        
        stats = {
            'user_info': asdict(self.current_user),
            'storage_stats': {
                'local_files': len([f for f in self.get_user_files('local')]),
                'google_files': len([f for f in self.get_user_files('google_drive')]),
                'total_files': len(self.get_user_files()),
                'local_storage_used': 0,  # Calculate from database
                'google_storage_used': 0  # Get from Google Drive API
            },
            'upload_methods': {
                'web': 0,
                'device': 0,
                'google_drive': 0,
                'hybrid': 0
            },
            'sync_status': {
                'last_sync': None,
                'pending_syncs': 0,
                'conflicts': 0
            }
        }
        
        # Calculate upload method stats
        for file_data in self.get_user_files():
            upload_method = file_data.get('metadata', {}).get('upload_method', 'web')
            if upload_method in stats['upload_methods']:
                stats['upload_methods'][upload_method] += 1
        
        return stats

# Global hybrid platform instance
hybrid_platform = HybridPlatform()
