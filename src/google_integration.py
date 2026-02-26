"""
YotuDrive 2.0 - Google Integration Module
Complete Google ecosystem integration with OAuth, Drive API, and YouTube API
"""

import os
import json
import time
import uuid
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
    try:
        import google.oauth2.credentials
        import google_auth_oauthlib.flow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.auth.transport.requests import Request
    except ImportError:
        # Fallback for environments where namespace packages are tricky
        import sys
        import subprocess
        # Try to re-install if missing (last resort on Render)
        try:
            print("[DEBUG] Attempting emergency package install...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "google-api-python-client", "google-auth", "google-auth-oauthlib", "google-auth-httplib2", "google-api-core", "googleapis-common-protos"])
            import google.oauth2.credentials
            import google_auth_oauthlib.flow
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            from google.auth.transport.requests import Request
            print("[DEBUG] Emergency install successful")
        except Exception as e:
            print(f"[ERROR] Emergency install failed: {e}")
            import sys
            print(f"[DEBUG] Initial import failed. Python path: {sys.path}")
            # Try to force namespace refresh if possible, though usually not needed if installed correctly
            try:
                import google
                import google.oauth2
                import google.oauth2.credentials
            except ImportError as ie:
                print(f"[ERROR] Critical import failure: {ie}")
                raise

import logging

from src.config_manager import config_manager
from src.advanced_logger import get_logger
from src.utils import YotuDriveException, ErrorCodes

logger = get_logger()

@dataclass
class GoogleUser:
    """Google user profile with enhanced metadata"""
    google_id: str
    email: str
    name: str
    picture_url: str
    locale: str
    verified_email: bool
    storage_quota: int = 15 * 1024 * 1024 * 1024  # 15GB default
    storage_used: int = 0
    created_at: float = None
    last_active: float = None
    preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_active is None:
            self.last_active = time.time()
        if self.preferences is None:
            self.preferences = {
                'auto_upload_to_youtube': True,
                'video_quality': '1080p',
                'privacy_setting': 'unlisted',
                'auto_backup': True
            }

@dataclass
class FileMetadata:
    """File metadata for database storage"""
    id: str
    user_id: str
    google_file_id: Optional[str] = None
    youtube_video_id: Optional[str] = None
    original_name: str
    file_size: int
    mime_type: str
    created_at: float = None
    modified_at: float = None
    encoding_status: str = "pending"  # pending, processing, completed, failed
    video_details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.modified_at is None:
            self.modified_at = time.time()
        if self.video_details is None:
            self.video_details = {}

class GoogleAuthManager:
    """Google OAuth 2.0 authentication management"""
    
    def __init__(self):
        self.client_config = {
            'web': {
                'client_id': config_manager.get('google.client_id', ''),
                'client_secret': config_manager.get('google.client_secret', ''),
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': ['http://localhost:5000/auth/callback']
            }
        }
        self.scopes = [
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata',
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]
        
        # Store credentials in memory (in production, use database)
        self.credentials_store = {}
    
    def get_authorization_url(self, state: str = None) -> str:
        """Get Google OAuth authorization URL"""
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                redirect_uri='http://localhost:5000/auth/callback'
            )
            
            if state:
                flow.state = state
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            logger.log_structured('info', 'Generated Google auth URL', 
                              authorization_url=authorization_url)
            
            return authorization_url
            
        except Exception as e:
            logger.log_exception('Failed to generate auth URL', e)
            raise YotuDriveException("Authentication URL generation failed", 
                                  ErrorCodes.AUTHENTICATION_ERROR, e)
    
    def handle_oauth_callback(self, authorization_response: str) -> google.oauth2.credentials.Credentials:
        """Handle OAuth callback and exchange code for credentials"""
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                redirect_uri='http://localhost:5000/auth/callback'
            )
            
            flow.fetch_token(authorization_response=authorization_response)
            credentials = flow.credentials
            
            logger.log_structured('info', 'OAuth callback successful', 
                              email=self._get_user_email(credentials))
            
            return credentials
            
        except Exception as e:
            logger.log_exception('OAuth callback failed', e)
            raise YotuDriveException("OAuth callback failed", 
                                  ErrorCodes.AUTHENTICATION_ERROR, e)
    
    def _get_user_email(self, credentials: google.oauth2.credentials.Credentials) -> str:
        """Get user email from credentials"""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info.get('email', '')
        except Exception:
            return ''
    
    def refresh_credentials(self, user_id: str) -> Optional[google.oauth2.credentials.Credentials]:
        """Refresh expired credentials"""
        if user_id not in self.credentials_store:
            return None
        
        credentials = self.credentials_store[user_id]
        
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                self.credentials_store[user_id] = credentials
                logger.log_structured('info', 'Credentials refreshed', user_id=user_id)
                return credentials
            except Exception as e:
                logger.log_exception('Credential refresh failed', e)
                return None
        
        return credentials
    
    def store_credentials(self, user_id: str, credentials: google.oauth2.credentials.Credentials):
        """Store user credentials"""
        self.credentials_store[user_id] = credentials
        logger.log_structured('info', 'Credentials stored', user_id=user_id)

class GoogleDriveManager:
    """Google Drive API integration"""
    
    def __init__(self, credentials: google.oauth2.credentials.Credentials):
        self.credentials = credentials
        self.drive_service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Drive API service"""
        try:
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            logger.log_structured('info', 'Drive API service initialized')
        except Exception as e:
            logger.log_exception('Drive API initialization failed', e)
            raise YotuDriveException("Drive API initialization failed", 
                                  ErrorCodes.EXTERNAL_API_ERROR, e)
    
    def upload_file(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        try:
            file_name = Path(file_path).name
            mime_type = self._get_mime_type(file_path)
            
            file_metadata = {
                'name': file_name,
                'parents': metadata.get('folder_id', []) if metadata else []
            }
            
            if metadata:
                file_metadata.update(metadata)
            
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,mimeType,createdTime,modifiedTime'
            ).execute()
            
            logger.log_structured('info', 'File uploaded to Drive', 
                              file_id=file.get('id'), 
                              file_name=file_name,
                              size=file.get('size'))
            
            return file
            
        except HttpError as e:
            logger.log_exception('Drive upload failed', e)
            raise YotuDriveException("Drive upload failed", 
                                  ErrorCodes.UPLOAD_FAILED, e)
        except Exception as e:
            logger.log_exception('Drive upload error', e)
            raise YotuDriveException("Drive upload error", 
                                  ErrorCodes.UPLOAD_FAILED, e)
    
    def create_folder(self, folder_name: str, parent_folder_id: str = None) -> Dict[str, Any]:
        """Create folder in Google Drive"""
        try:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id,name'
            ).execute()
            
            logger.log_structured('info', 'Folder created in Drive', 
                              folder_id=folder.get('id'),
                              folder_name=folder_name)
            
            return folder
            
        except HttpError as e:
            logger.log_exception('Drive folder creation failed', e)
            raise YotuDriveException("Drive folder creation failed", 
                                  ErrorCodes.DIRECTORY_NOT_WRITABLE, e)
    
    def list_files(self, folder_id: str = None, query: str = None) -> List[Dict[str, Any]]:
        """List files in Google Drive"""
        try:
            q = f"'{folder_id}' in parents" if folder_id else None
            if query:
                q = f"name contains '{query}'" + (f" and {q}" if q else "")
            
            results = self.drive_service.files().list(
                q=q,
                pageSize=1000,
                fields="files(id,name,size,mimeType,createdTime,modifiedTime,parents)"
            ).execute()
            
            files = results.get('files', [])
            
            logger.log_structured('info', 'Drive files listed', 
                              count=len(files))
            
            return files
            
        except HttpError as e:
            logger.log_exception('Drive file listing failed', e)
            raise YotuDriveException("Drive file listing failed", 
                                  ErrorCodes.DATABASE_ERROR, e)
    
    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get file information from Google Drive"""
        try:
            file = self.drive_service.files().get(
                fileId=file_id,
                fields='id,name,size,mimeType,createdTime,modifiedTime'
            ).execute()
            
            return file
            
        except HttpError as e:
            logger.log_exception('Drive file info failed', e)
            return {}
    
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

class YouTubeManager:
    """YouTube API integration for video upload/download"""
    
    def __init__(self, credentials: google.oauth2.credentials.Credentials):
        self.credentials = credentials
        self.youtube_service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize YouTube API service"""
        try:
            self.youtube_service = build('youtube', 'v3', credentials=self.credentials)
            logger.log_structured('info', 'YouTube API service initialized')
        except Exception as e:
            logger.log_exception('YouTube API initialization failed', e)
            raise YotuDriveException("YouTube API initialization failed", 
                                  ErrorCodes.EXTERNAL_API_ERROR, e)
    
    def upload_video(self, video_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Upload video to YouTube"""
        try:
            # Prepare video metadata
            video_metadata = {
                'snippet': {
                    'title': metadata.get('title', 'YotuDrive Video'),
                    'description': metadata.get('description', ''),
                    'tags': metadata.get('tags', []),
                    'categoryId': metadata.get('category_id', '22')  # People & Blogs
                },
                'status': {
                    'privacyStatus': metadata.get('privacy', 'unlisted'),
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Upload video
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            
            request = self.youtube_service.videos().insert(
                part=','.join(video_metadata.keys()),
                body=video_metadata,
                media_body=media
            )
            
            response = None
            error_retry_count = 0
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        logger.log_structured('info', 'YouTube upload progress', 
                                          progress=status.progress())
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504] and error_retry_count < 5:
                        error_retry_count += 1
                        logger.log_structured('warning', 'YouTube upload retry', 
                                          attempt=error_retry_count)
                        time.sleep(2 ** error_retry_count)
                    else:
                        raise
            
            video_id = response.get('id')
            
            logger.log_structured('info', 'Video uploaded to YouTube', 
                              video_id=video_id,
                              title=metadata.get('title'))
            
            return {
                'id': video_id,
                'url': f'https://www.youtube.com/watch?v={video_id}',
                'status': 'uploaded'
            }
            
        except HttpError as e:
            logger.log_exception('YouTube upload failed', e)
            raise YotuDriveException("YouTube upload failed", 
                                  ErrorCodes.YOUTUBE_API_ERROR, e)
        except Exception as e:
            logger.log_exception('YouTube upload error', e)
            raise YotuDriveException("YouTube upload error", 
                                  ErrorCodes.YOUTUBE_API_ERROR, e)
    
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Get video information from YouTube"""
        try:
            response = self.youtube_service.videos().list(
                part='snippet,contentDetails,status',
                id=video_id
            ).execute()
            
            items = response.get('items', [])
            if not items:
                return {}
            
            video = items[0]
            
            return {
                'id': video.get('id'),
                'title': video.get('snippet', {}).get('title', ''),
                'description': video.get('snippet', {}).get('description', ''),
                'duration': video.get('contentDetails', {}).get('duration', ''),
                'size': video.get('contentDetails', {}).get('size', 0),
                'viewCount': video.get('statistics', {}).get('viewCount', 0),
                'likeCount': video.get('statistics', {}).get('likeCount', 0),
                'publishedAt': video.get('snippet', {}).get('publishedAt', ''),
                'privacyStatus': video.get('status', {}).get('privacyStatus', '')
            }
            
        except HttpError as e:
            logger.log_exception('YouTube video info failed', e)
            return {}
    
    def get_playlist_videos(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get all videos from a playlist"""
        try:
            videos = []
            next_page_token = None
            
            while True:
                response = self.youtube_service.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()
                
                for item in response.get('items', []):
                    video_id = item.get('contentDetails', {}).get('videoId')
                    if video_id:
                        video_info = self.get_video_info(video_id)
                        videos.append(video_info)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            logger.log_structured('info', 'Playlist videos retrieved', 
                              playlist_id=playlist_id,
                              video_count=len(videos))
            
            return videos
            
        except HttpError as e:
            logger.log_exception('YouTube playlist retrieval failed', e)
            return []

class YotuDriveGoogleIntegration:
    """Main integration class combining all Google services"""
    
    def __init__(self):
        self.auth_manager = GoogleAuthManager()
        self.current_user = None
        self.drive_manager = None
        self.youtube_manager = None
        self.file_metadata_db = {}  # In production, use database
    
    def authenticate_user(self, authorization_code: str) -> GoogleUser:
        """Authenticate user with Google OAuth"""
        try:
            # Exchange authorization code for credentials
            credentials = self.auth_manager.handle_oauth_callback(authorization_code)
            
            # Get user profile
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            # Create user object
            user = GoogleUser(
                google_id=user_info.get('id'),
                email=user_info.get('email'),
                name=user_info.get('name'),
                picture_url=user_info.get('picture'),
                locale=user_info.get('locale'),
                verified_email=user_info.get('verified_email', False)
            )
            
            # Store credentials
            self.auth_manager.store_credentials(user.google_id, credentials)
            
            # Initialize service managers
            self.drive_manager = GoogleDriveManager(credentials)
            self.youtube_manager = YouTubeManager(credentials)
            self.current_user = user
            
            logger.log_structured('info', 'User authenticated', 
                              user_id=user.google_id,
                              email=user.email)
            
            return user
            
        except Exception as e:
            logger.log_exception('User authentication failed', e)
            raise YotuDriveException("User authentication failed", 
                                  ErrorCodes.AUTHENTICATION_ERROR, e)
    
    def upload_file_or_folder(self, path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload file or folder to Google Drive and prepare for encoding"""
        try:
            path_obj = Path(path)
            
            if path_obj.is_file():
                return self._upload_single_file(path, metadata)
            elif path_obj.is_dir():
                return self._upload_folder(path, metadata)
            else:
                raise YotuDriveException("Path does not exist", 
                                      ErrorCodes.FILE_NOT_FOUND)
                
        except Exception as e:
            logger.log_exception('File/folder upload failed', e)
            raise YotuDriveException("Upload failed", 
                                  ErrorCodes.UPLOAD_FAILED, e)
    
    def _upload_single_file(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload single file and create metadata"""
        # Upload to Google Drive
        drive_file = self.drive_manager.upload_file(file_path, metadata)
        
        # Create file metadata
        file_metadata = FileMetadata(
            id=str(uuid.uuid4()),
            user_id=self.current_user.google_id,
            google_file_id=drive_file.get('id'),
            original_name=Path(file_path).name,
            file_size=drive_file.get('size', 0),
            mime_type=drive_file.get('mimeType', ''),
            encoding_status="pending"
        )
        
        # Store metadata
        self.file_metadata_db[file_metadata.id] = file_metadata
        
        logger.log_structured('info', 'File uploaded and metadata created', 
                              file_id=file_metadata.id,
                              google_file_id=drive_file.get('id'))
        
        return {
            'file_id': file_metadata.id,
            'google_file_id': drive_file.get('id'),
            'status': 'uploaded',
            'next_step': 'encoding'
        }
    
    def _upload_folder(self, folder_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload folder recursively"""
        folder_path = Path(folder_path)
        folder_name = folder_path.name
        
        # Create folder in Google Drive
        drive_folder = self.drive_manager.create_folder(folder_name)
        
        uploaded_files = []
        
        # Upload all files in folder
        for item in folder_path.rglob('*'):
            if item.is_file():
                file_metadata = metadata.copy() if metadata else {}
                file_metadata['folder_id'] = drive_folder.get('id')
                
                result = self._upload_single_file(str(item), file_metadata)
                uploaded_files.append(result)
        
        return {
            'folder_id': drive_folder.get('id'),
            'files': uploaded_files,
            'status': 'uploaded'
        }
    
    def collect_video_details(self, file_id: str) -> Dict[str, Any]:
        """Collect video details from user for encoding"""
        try:
            if file_id not in self.file_metadata_db:
                raise YotuDriveException("File not found", ErrorCodes.FILE_NOT_FOUND)
            
            file_meta = self.file_metadata_db[file_id]
            
            # Return required video details
            return {
                'file_id': file_id,
                'original_name': file_meta.original_name,
                'file_size': file_meta.file_size,
                'mime_type': file_meta.mime_type,
                'current_details': file_meta.video_details,
                'required_details': {
                    'title': 'Required: Video title for YouTube',
                    'description': 'Required: Video description',
                    'tags': 'Required: Comma-separated tags',
                    'category': 'Required: Video category',
                    'privacy': 'Required: privacy setting (public, unlisted, private)'
                }
            }
            
        except Exception as e:
            logger.log_exception('Video details collection failed', e)
            raise YotuDriveException("Video details collection failed", 
                                  ErrorCodes.DATABASE_ERROR, e)
    
    def update_video_details(self, file_id: str, video_details: Dict[str, Any]) -> bool:
        """Update video details for encoding"""
        try:
            if file_id not in self.file_metadata_db:
                return False
            
            file_meta = self.file_metadata_db[file_id]
            file_meta.video_details = video_details
            file_meta.modified_at = time.time()
            
            self.file_metadata_db[file_id] = file_meta
            
            logger.log_structured('info', 'Video details updated', 
                              file_id=file_id,
                              video_details=video_details)
            
            return True
            
        except Exception as e:
            logger.log_exception('Video details update failed', e)
            return False
    
    def encode_and_upload_video(self, file_id: str) -> Dict[str, Any]:
        """Encode file to video and upload to YouTube"""
        try:
            if file_id not in self.file_metadata_db:
                raise YotuDriveException("File not found", ErrorCodes.FILE_NOT_FOUND)
            
            file_meta = self.file_metadata_db[file_id]
            
            # Update status to processing
            file_meta.encoding_status = "processing"
            self.file_metadata_db[file_id] = file_meta
            
            # Get file from Google Drive
            # (In real implementation, download from Drive)
            local_file_path = f"temp/{file_meta.original_name}"
            
            # Encode to video (using existing encoder)
            from src.encoder import Encoder
            from src.ffmpeg_utils import stitch_frames
            
            frames_dir = f"temp/frames/{file_id}"
            encoder = Encoder(local_file_path, frames_dir)
            encoder.run()
            
            video_path = f"temp/videos/{file_id}.mp4"
            stitch_frames(frames_dir, video_path)
            
            # Upload to YouTube
            video_details = file_meta.video_details or {}
            youtube_result = self.youtube_manager.upload_video(video_path, video_details)
            
            # Update metadata
            file_meta.youtube_video_id = youtube_result.get('id')
            file_meta.encoding_status = "completed"
            file_meta.modified_at = time.time()
            
            self.file_metadata_db[file_id] = file_meta
            
            # Cleanup temp files
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)
            os.remove(video_path)
            os.remove(local_file_path)
            
            logger.log_structured('info', 'Video encoded and uploaded', 
                              file_id=file_id,
                              youtube_id=youtube_result.get('id'))
            
            return {
                'file_id': file_id,
                'youtube_video_id': youtube_result.get('id'),
                'youtube_url': youtube_result.get('url'),
                'status': 'completed'
            }
            
        except Exception as e:
            logger.log_exception('Video encoding/upload failed', e)
            
            # Update status to failed
            if file_id in self.file_metadata_db:
                file_meta = self.file_metadata_db[file_id]
                file_meta.encoding_status = "failed"
                self.file_metadata_db[file_id] = file_meta
            
            raise YotuDriveException("Video encoding/upload failed", 
                                  ErrorCodes.ENCODING_FAILED, e)
    
    def recover_from_youtube(self, video_url: str) -> Dict[str, Any]:
        """Recover original file from YouTube video"""
        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(video_url)
            
            if not video_id:
                raise YotuDriveException("Invalid YouTube URL", 
                                      ErrorCodes.INVALID_VIDEO_ID)
            
            # Get video info
            video_info = self.youtube_manager.get_video_info(video_id)
            
            if not video_info:
                raise YotuDriveException("Video not found", 
                                      ErrorCodes.YOUTUBE_API_ERROR)
            
            # Find file metadata by YouTube video ID
            file_meta = None
            for meta in self.file_metadata_db.values():
                if meta.youtube_video_id == video_id:
                    file_meta = meta
                    break
            
            if not file_meta:
                raise YotuDriveException("File metadata not found", 
                                      ErrorCodes.DATABASE_ERROR)
            
            # Download video from YouTube
            # (In real implementation, use yt-dlp)
            video_path = f"temp/recovery/{file_meta.id}.mp4"
            
            # Decode video to original file
            from src.decoder import Decoder
            
            frames_dir = f"temp/recovery_frames/{file_meta.id}"
            decoder = Decoder(frames_dir, f"recovered_{file_meta.original_name}")
            decoder.run()
            
            # Upload recovered file to Google Drive
            recovered_file = self.drive_manager.upload_file(
                f"recovered_{file_meta.original_name}",
                {
                    'name': f"RECOVERED_{file_meta.original_name}",
                    'description': f"Recovered from YouTube video: {video_id}"
                }
            )
            
            logger.log_structured('info', 'File recovered from YouTube', 
                              original_file_id=file_meta.id,
                              youtube_id=video_id,
                              recovered_file_id=recovered_file.get('id'))
            
            return {
                'original_file_id': file_meta.id,
                'recovered_file_id': recovered_file.get('id'),
                'youtube_video_id': video_id,
                'status': 'recovered'
            }
            
        except Exception as e:
            logger.log_exception('YouTube recovery failed', e)
            raise YotuDriveException("YouTube recovery failed", 
                                  ErrorCodes.DECODING_FAILED, e)
    
    def _extract_video_id(self, video_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        import re
        
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'(?:youtube\.com/watch\?v=)([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        
        return None
    
    def get_user_files(self) -> List[Dict[str, Any]]:
        """Get all files for current user"""
        try:
            user_files = []
            
            for file_meta in self.file_metadata_db.values():
                if file_meta.user_id == self.current_user.google_id:
                    user_files.append(asdict(file_meta))
            
            return user_files
            
        except Exception as e:
            logger.log_exception('Get user files failed', e)
            return []
    
    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            user_files = self.get_user_files()
            
            stats = {
                'total_files': len(user_files),
                'uploaded_files': len([f for f in user_files if f['google_file_id']]),
                'encoded_files': len([f for f in user_files if f['youtube_video_id']]),
                'total_size': sum(f['file_size'] for f in user_files),
                'encoding_status': {
                    'pending': len([f for f in user_files if f['encoding_status'] == 'pending']),
                    'processing': len([f for f in user_files if f['encoding_status'] == 'processing']),
                    'completed': len([f for f in user_files if f['encoding_status'] == 'completed']),
                    'failed': len([f for f in user_files if f['encoding_status'] == 'failed'])
                }
            }
            
            return stats
            
        except Exception as e:
            logger.log_exception('Get user stats failed', e)
            return {}

# Global integration instance
google_integration = YotuDriveGoogleIntegration()
