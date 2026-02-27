"""
YotuDrive 2.0 - Enhanced Recovery System
Provides video identification and confirmation during recovery process
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from .config_manager import config_manager
from .advanced_logger import get_logger
from .utils import YotuDriveException, ErrorCodes
from .google_integration import YouTubeManager

logger = get_logger()

@dataclass
class VideoIdentification:
    """Video identification information"""
    video_id: str
    title: str
    description: str
    channel_name: str
    upload_date: str
    duration: str
    thumbnail_url: str
    view_count: int
    like_count: int
    file_count: int
    estimated_size: str
    quality: str
    privacy_status: str
    tags: List[str]
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass
class RecoverySession:
    """Enhanced recovery session with video identification"""
    session_id: str
    user_id: str
    youtube_url: str
    video_identification: Optional[VideoIdentification] = None
    recovery_status: str = "pending"  # pending, identified, confirmed, downloading, decoding, completed, failed
    created_at: float = None
    confirmed_at: Optional[float] = None
    download_started_at: Optional[float] = None
    decoding_started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    confidence_score: float = 0.0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class EnhancedRecoveryManager:
    """Enhanced recovery manager with video identification"""
    
    def __init__(self):
        self.active_sessions = {}
        self.recovery_history = []
        self.youtube_manager = None
        
        # Recovery data directory
        self.recovery_dir = Path("recovery_data")
        self.recovery_dir.mkdir(exist_ok=True)
        
        # Subdirectories
        self.sessions_dir = self.recovery_dir / "sessions"
        self.downloads_dir = self.recovery_dir / "downloads"
        self.decoded_files_dir = self.recovery_dir / "decoded_files"
        
        for dir_path in [self.sessions_dir, self.downloads_dir, self.decoded_files_dir]:
            dir_path.mkdir(exist_ok=True)
    
    def create_recovery_session(self, user_id: str, youtube_url: str) -> str:
        """Create recovery session with video identification"""
        session_id = str(uuid.uuid4())
        
        session = RecoverySession(
            session_id=session_id,
            user_id=user_id,
            youtube_url=youtube_url
        )
        
        self.active_sessions[session_id] = session
        
        # Save session
        self._save_session(session)
        
        logger.log_structured('info', 'Recovery session created', 
                          session_id=session_id,
                          youtube_url=youtube_url)
        
        return session_id
    
    def identify_video(self, session_id: str, credentials = None) -> Dict[str, Any]:
        """Identify YouTube video and provide detailed information"""
        if session_id not in self.active_sessions:
            raise YotuDriveException("Invalid session ID", ErrorCodes.INVALID_SESSION)
        
        session = self.active_sessions[session_id]
        
        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(session.youtube_url)
            
            if not video_id:
                session.recovery_status = "failed"
                session.error_message = "Invalid YouTube URL"
                self._save_session(session)
                return {'error': 'Invalid YouTube URL'}
            
            # Initialize YouTube manager
            if credentials:
                self.youtube_manager = YouTubeManager(credentials)
            
            # Get video information
            video_info = self.youtube_manager.get_video_info(video_id)
            
            if not video_info:
                session.recovery_status = "failed"
                session.error_message = "Video not found or private"
                self._save_session(session)
                return {'error': 'Video not found or private'}
            
            # Create video identification
            identification = VideoIdentification(
                video_id=video_info.get('id', ''),
                title=video_info.get('title', 'Unknown Video'),
                description=video_info.get('description', ''),
                channel_name=video_info.get('channel_name', 'Unknown Channel'),
                upload_date=video_info.get('publishedAt', ''),
                duration=video_info.get('duration', '0:00'),
                thumbnail_url=self._get_thumbnail_url(video_info.get('id', '')),
                view_count=video_info.get('viewCount', 0),
                like_count=video_info.get('likeCount', 0),
                file_count=self._estimate_file_count(video_info),
                estimated_size=self._estimate_file_size(video_info),
                quality=self._determine_quality(video_info),
                privacy_status=video_info.get('privacyStatus', 'unknown'),
                tags=self._extract_tags(video_info)
            )
            
            # Calculate confidence score
            identification.confidence_score = self._calculate_confidence_score(video_info)
            
            session.video_identification = identification
            session.recovery_status = "identified"
            session.confirmed_at = time.time()
            
            self._save_session(session)
            
            logger.log_structured('info', 'Video identified', 
                              session_id=session_id,
                              video_id=video_id,
                              title=identification.title,
                              confidence=identification.confidence_score)
            
            return {
                'session_id': session_id,
                'status': 'identified',
                'video_info': asdict(identification),
                'confidence_score': identification.confidence_score,
                'next_step': 'user_confirmation'
            }
            
        except Exception as e:
            session.recovery_status = "failed"
            session.error_message = str(e)
            self._save_session(session)
            
            logger.log_exception('Video identification failed', e)
            return {'error': str(e)}
    
    def confirm_recovery(self, session_id: str, user_confirmed: bool) -> Dict[str, Any]:
        """User confirms they want to recover this video"""
        if session_id not in self.active_sessions:
            raise YotuDriveException("Invalid session ID", ErrorCodes.INVALID_SESSION)
        
        session = self.active_sessions[session_id]
        
        if not user_confirmed:
            # User cancelled
            session.recovery_status = "cancelled"
            self._save_session(session)
            
            return {
                'session_id': session_id,
                'status': 'cancelled',
                'message': 'Recovery cancelled by user'
            }
        
        if session.recovery_status != "identified":
            return {
                'session_id': session_id,
                'status': 'error',
                'message': 'Session not ready for confirmation'
            }
        
        session.recovery_status = "confirmed"
        
        self._save_session(session)
        
        logger.log_structured('info', 'Recovery confirmed by user', 
                          session_id=session_id,
                          video_id=session.video_identification.video_id)
        
        return {
            'session_id': session_id,
            'status': 'confirmed',
            'message': 'Recovery confirmed. Starting download...',
            'next_step': 'download'
        }
    
    def download_video(self, session_id: str) -> Dict[str, Any]:
        """Download identified video"""
        if session_id not in self.active_sessions:
            raise YotuDriveException("Invalid session ID", ErrorCodes.INVALID_SESSION)
        
        session = self.active_sessions[session_id]
        
        if session.recovery_status != "confirmed":
            return {
                'session_id': session_id,
                'status': 'error',
                'message': 'Session not confirmed for download'
            }
        
        try:
            session.recovery_status = "downloading"
            session.download_started_at = time.time()
            self._save_session(session)
            
            video_id = session.video_identification.video_id
            
            # Download video using yt-dlp (or similar)
            download_path = self.downloads_dir / f"{session_id}.mp4"
            
            # Simulate download (in real implementation, use yt-dlp)
            download_result = self._simulate_video_download(video_id, download_path)
            
            if not download_result['success']:
                session.recovery_status = "failed"
                session.error_message = download_result['error']
                self._save_session(session)
                
                return {
                    'session_id': session_id,
                    'status': 'failed',
                    'error': download_result['error']
                }
            
            session.recovery_status = "downloaded"
            self._save_session(session)
            
            logger.log_structured('info', 'Video downloaded', 
                              session_id=session_id,
                              video_id=video_id,
                              download_path=str(download_path))
            
            return {
                'session_id': session_id,
                'status': 'downloaded',
                'download_path': str(download_path),
                'file_size': download_result['file_size'],
                'next_step': 'decoding'
            }
            
        except Exception as e:
            session.recovery_status = "failed"
            session.error_message = str(e)
            self._save_session(session)
            
            logger.log_exception('Video download failed', e)
            return {
                'session_id': session_id,
                'status': 'failed',
                'error': str(e)
            }
    
    def decode_video(self, session_id: str) -> Dict[str, Any]:
        """Decode downloaded video to original files"""
        if session_id not in self.active_sessions:
            raise YotuDriveException("Invalid session ID", ErrorCodes.INVALID_SESSION)
        
        session = self.active_sessions[session_id]
        
        if session.recovery_status != "downloaded":
            return {
                'session_id': session_id,
                'status': 'error',
                'message': 'Video not downloaded yet'
            }
        
        try:
            session.recovery_status = "decoding"
            session.decoding_started_at = time.time()
            self._save_session(session)
            
            video_path = self.downloads_dir / f"{session_id}.mp4"
            
            # Decode video to original files
            decode_result = self._decode_video_to_files(video_path, session_id)
            
            if not decode_result['success']:
                session.recovery_status = "failed"
                session.error_message = decode_result['error']
                self._save_session(session)
                
                return {
                    'session_id': session_id,
                    'status': 'failed',
                    'error': decode_result['error']
                }
            
            session.recovery_status = "completed"
            session.completed_at = time.time()
            self._save_session(session)
            
            # Add to recovery history
            self.recovery_history.append({
                'session_id': session_id,
                'user_id': session.user_id,
                'video_id': session.video_identification.video_id,
                'video_title': session.video_identification.title,
                'recovered_files': decode_result['files'],
                'completed_at': session.completed_at,
                'total_duration': session.completed_at - session.created_at
            })
            
            logger.log_structured('info', 'Video decoded successfully', 
                              session_id=session_id,
                              files_count=len(decode_result['files']))
            
            return {
                'session_id': session_id,
                'status': 'completed',
                'recovered_files': decode_result['files'],
                'recovery_path': str(self.decoded_files_dir / session_id),
                'total_duration': session.completed_at - session.created_at
            }
            
        except Exception as e:
            session.recovery_status = "failed"
            session.error_message = str(e)
            self._save_session(session)
            
            logger.log_exception('Video decoding failed', e)
            return {
                'session_id': session_id,
                'status': 'failed',
                'error': str(e)
            }
    
    def get_recovery_status(self, session_id: str) -> Dict[str, Any]:
        """Get current recovery session status"""
        if session_id not in self.active_sessions:
            return {'error': 'Session not found'}
        
        session = self.active_sessions[session_id]
        
        status_data = {
            'session_id': session_id,
            'status': session.recovery_status,
            'created_at': session.created_at,
            'youtube_url': session.youtube_url,
            'error_message': session.error_message
        }
        
        if session.video_identification:
            status_data['video_identification'] = asdict(session.video_identification)
        
        # Add timing information
        if session.confirmed_at:
            status_data['confirmation_duration'] = session.confirmed_at - session.created_at
        
        if session.download_started_at:
            status_data['download_duration'] = session.download_started_at - session.confirmed_at
        
        if session.decoding_started_at:
            status_data['decoding_duration'] = session.decoding_started_at - session.download_started_at
        
        if session.completed_at:
            status_data['total_duration'] = session.completed_at - session.created_at
        
        return status_data
    
    def _extract_video_id(self, youtube_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        import re
        
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'(?:youtube\.com/watch\?v=)([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        return None
    
    def _get_thumbnail_url(self, video_id: str) -> str:
        """Get high-quality thumbnail URL"""
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    
    def _estimate_file_count(self, video_info: Dict[str, Any]) -> int:
        """Estimate number of files based on video characteristics"""
        duration = video_info.get('duration', '0:00')
        
        # Parse duration (format: PT4M13S)
        if duration.startswith('PT'):
            try:
                # Remove 'PT' and split
                duration_clean = duration[2:]
                parts = duration_clean.split('M')
                
                if len(parts) >= 2:
                    minutes = int(parts[0])
                    seconds_part = parts[1].replace('S', '')
                    seconds = int(seconds_part) if seconds_part else 0
                    
                    total_seconds = minutes * 60 + seconds
                    
                    # Estimate: 1 file per 30 seconds of video
                    return max(1, total_seconds // 30)
            except:
                pass
        
        return 10  # Default estimate
    
    def _estimate_file_size(self, video_info: Dict[str, Any]) -> str:
        """Estimate original file size based on video characteristics"""
        file_count = self._estimate_file_count(video_info)
        duration = video_info.get('duration', '0:00')
        
        # Parse duration to seconds
        total_seconds = 0
        if duration.startswith('PT'):
            try:
                duration_clean = duration[2:]
                parts = duration_clean.split('M')
                if len(parts) >= 2:
                    minutes = int(parts[0])
                    seconds_part = parts[1].replace('S', '')
                    seconds = int(seconds_part) if seconds_part else 0
                    total_seconds = minutes * 60 + seconds
            except:
                pass
        
        # Estimate: 1MB per 30 seconds per file
        estimated_size = (total_seconds // 30) * 1024 * 1024  # MB
        
        return f"{estimated_size / (1024*1024):.1f} MB"
    
    def _determine_quality(self, video_info: Dict[str, Any]) -> str:
        """Determine video quality"""
        # This would analyze video definition
        # For now, return based on common indicators
        title = video_info.get('title', '').lower()
        description = video_info.get('description', '').lower()
        
        if any(quality in title + description for quality in ['4k', '2160p', 'uhd']):
            return "4K"
        elif any(quality in title + description for quality in ['1080p', 'hd', 'full hd']):
            return "1080p"
        elif any(quality in title + description for quality in ['720p', 'hd']):
            return "720p"
        else:
            return "480p"
    
    def _extract_tags(self, video_info: Dict[str, Any]) -> List[str]:
        """Extract tags from video info"""
        tags = []
        
        title = video_info.get('title', '')
        description = video_info.get('description', '')
        
        # Extract common keywords
        text = f"{title} {description}".lower()
        
        common_tags = ['tutorial', 'review', 'unboxing', 'demo', 'presentation', 
                     'music', 'gaming', 'education', 'vlog', 'comedy']
        
        for tag in common_tags:
            if tag in text:
                tags.append(tag)
        
        return tags[:10]  # Limit to 10 tags
    
    def _calculate_confidence_score(self, video_info: Dict[str, Any]) -> float:
        """Calculate confidence score for video identification"""
        score = 0.0
        
        # Title exists and is meaningful
        title = video_info.get('title', '')
        if title and len(title) > 3:
            score += 30
        
        # Description exists
        description = video_info.get('description', '')
        if description and len(description) > 10:
            score += 20
        
        # Channel information
        if video_info.get('channel_name'):
            score += 15
        
        # View count (indicates public video)
        view_count = video_info.get('viewCount', 0)
        if view_count > 0:
            score += min(20, view_count / 1000)  # Max 20 points for views
        
        # Duration (reasonable length)
        duration = video_info.get('duration', '')
        if duration and 'PT' in duration:
            try:
                duration_clean = duration[2:]
                parts = duration_clean.split('M')
                if len(parts) >= 2:
                    minutes = int(parts[0])
                    if 1 <= minutes <= 60:  # Reasonable length
                        score += 10
            except:
                pass
        
        # Privacy status
        privacy = video_info.get('privacyStatus', '')
        if privacy in ['public', 'unlisted']:
            score += 15
        
        return min(100, score)
    
    def _simulate_video_download(self, video_id: str, download_path: Path) -> Dict[str, Any]:
        """Simulate video download (in real implementation, use yt-dlp)"""
        try:
            # Simulate download progress
            import time
            import random
            
            # Simulate download time based on "video size"
            simulated_size = random.randint(50, 500) * 1024 * 1024  # 50-500 MB
            
            # Simulate download progress
            for i in range(10):
                time.sleep(0.1)  # Simulate download time
                progress = (i + 1) * 10
                print(f"Downloading {video_id}: {progress}%")
            
            # Create dummy file
            with open(download_path, 'wb') as f:
                f.write(b'0' * simulated_size)
            
            return {
                'success': True,
                'file_size': simulated_size,
                'download_time': 1.0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _decode_video_to_files(self, video_path: Path, session_id: str) -> Dict[str, Any]:
        """Decode video to original files"""
        try:
            # Create output directory
            output_dir = self.decoded_files_dir / session_id
            output_dir.mkdir(exist_ok=True)
            
            # Simulate decoding process
            recovered_files = []
            
            # Simulate multiple files being recovered
            file_types = [
                {'name': 'document.pdf', 'size': 1024 * 1024},
                {'name': 'presentation.pptx', 'size': 2 * 1024 * 1024},
                {'name': 'image.jpg', 'size': 512 * 1024},
                {'name': 'data.xlsx', 'size': 3 * 1024 * 1024}
            ]
            
            for i, file_info in enumerate(file_types):
                file_path = output_dir / file_info['name']
                
                # Create dummy file
                with open(file_path, 'wb') as f:
                    f.write(b'0' * file_info['size'])
                
                recovered_files.append({
                    'name': file_info['name'],
                    'path': str(file_path),
                    'size': file_info['size']
                })
            
            return {
                'success': True,
                'files': recovered_files
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_session(self, session: RecoverySession):
        """Save recovery session"""
        session_file = self.sessions_dir / f"session_{session.session_id}.json"
        
        session_data = asdict(session)
        if session.video_identification:
            session_data['video_identification'] = asdict(session.video_identification)
        
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.log_exception('Failed to save session', e)
    
    def get_recovery_history(self, user_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recovery history"""
        history = self.recovery_history
        
        if user_id:
            history = [h for h in history if h.get('user_id') == user_id]
        
        # Sort by completion time (most recent first)
        history.sort(key=lambda x: x.get('completed_at', 0), reverse=True)
        
        return history[:limit]
    
    def cleanup_old_sessions(self, days: int = 7) -> int:
        """Clean up old recovery sessions"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0
        
        # Clean old sessions from memory
        old_sessions = []
        for session_id, session in self.active_sessions.items():
            if session.created_at < cutoff_time:
                old_sessions.append(session_id)
        
        for session_id in old_sessions:
            del self.active_sessions[session_id]
            cleaned_count += 1
        
        # Clean old session files
        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                file_time = session_file.stat().st_mtime
                if file_time < cutoff_time:
                    session_file.unlink()
                    cleaned_count += 1
            except Exception:
                pass
        
        logger.log_structured('info', 'Old recovery sessions cleaned', 
                          cleaned_count=cleaned_count,
                          days=days)
        
        return cleaned_count

# Global enhanced recovery manager
enhanced_recovery_manager = EnhancedRecoveryManager()
