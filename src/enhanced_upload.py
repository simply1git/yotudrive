"""
YotuDrive 2.0 - Enhanced Upload System
Creates detailed data files for each upload/video and collects comprehensive user input
"""

import os
import json
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib

from src.config_manager import config_manager
from src.advanced_logger import get_logger
from src.utils import YotuDriveException, ErrorCodes, FileValidator, NamingConvention

logger = get_logger()

@dataclass
class VideoDetails:
    """Comprehensive video details for encoding"""
    # Basic Information
    title: str
    description: str
    tags: List[str]
    category: str
    language: str
    
    # Technical Settings
    quality: str = "1080p"
    resolution: str = "1920x1080"
    fps: int = 30
    duration: Optional[float] = None
    
    # Privacy Settings
    privacy: str = "unlisted"  # public, unlisted, private
    allow_comments: bool = True
    allow_ratings: bool = True
    age_restriction: Optional[str] = None
    
    # Content Classification
    content_type: str = "general"  # general, music, gaming, education
    target_audience: str = "everyone"  # everyone, mature, restricted
    content_warnings: List[str] = None
    
    # Monetization
    monetize: bool = False
    license_type: str = "youtube"  # youtube, creative_commons
    
    # Additional Metadata
    location: Optional[str] = None
    recording_date: Optional[str] = None
    author: Optional[str] = None
    custom_thumbnail: Optional[str] = None
    
    def __post_init__(self):
        if self.content_warnings is None:
            self.content_warnings = []
        if self.tags is None:
            self.tags = []

@dataclass
class UploadSession:
    """Enhanced upload session with comprehensive data tracking"""
    session_id: str
    user_id: str
    upload_type: str  # file, folder, batch
    
    # Files Information
    files: List[Dict[str, Any]]
    total_size: int
    file_count: int
    
    # Upload Settings
    upload_method: str
    compression_level: str = "medium"
    encryption_enabled: bool = False
    auto_youtube_upload: bool = True
    
    # Processing Settings
    parallel_processing: bool = True
    thread_count: int = 4
    priority_level: str = "normal"  # low, normal, high
    
    # Timestamps
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

@dataclass
class FileProcessingData:
    """Detailed processing data for each file"""
    file_id: str
    original_name: str
    file_path: str
    file_size: int
    mime_type: str
    checksum: str
    
    # AI Analysis Results
    ai_analysis: Dict[str, Any] = None
    
    # Encoding Results
    encoding_status: str = "pending"  # pending, processing, completed, failed
    encoding_start: Optional[float] = None
    encoding_end: Optional[float] = None
    encoding_duration: Optional[float] = None
    
    # Video Generation
    video_path: Optional[str] = None
    video_size: Optional[int] = None
    video_quality: Optional[str] = None
    frame_count: Optional[int] = None
    
    # YouTube Upload
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    upload_status: str = "pending"  # pending, uploading, completed, failed
    
    # Error Handling
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.ai_analysis is None:
            self.ai_analysis = {}

class DataFileManager:
    """Manages detailed data files for each upload/video"""
    
    def __init__(self, data_dir: str = "data_files"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Subdirectories
        self.sessions_dir = self.data_dir / "sessions"
        self.videos_dir = self.data_dir / "videos"
        self.files_dir = self.data_dir / "files"
        self.analytics_dir = self.data_dir / "analytics"
        
        for dir_path in [self.sessions_dir, self.videos_dir, self.files_dir, self.analytics_dir]:
            dir_path.mkdir(exist_ok=True)
    
    def create_session_data_file(self, session: UploadSession) -> str:
        """Create comprehensive session data file"""
        session_file = self.sessions_dir / f"session_{session.session_id}.json"
        
        session_data = {
            'session_info': asdict(session),
            'upload_summary': {
                'total_files': session.file_count,
                'total_size': session.total_size,
                'estimated_duration': self._estimate_processing_time(session),
                'recommended_settings': self._get_recommended_settings(session)
            },
            'system_info': self._get_system_info(),
            'configuration': self._get_current_configuration()
        }
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        logger.log_structured('info', 'Session data file created', 
                          session_id=session.session_id,
                          file_path=str(session_file))
        
        return str(session_file)
    
    def create_video_data_file(self, file_data: FileProcessingData, 
                           video_details: VideoDetails) -> str:
        """Create detailed video data file"""
        video_file = self.videos_dir / f"video_{file_data.file_id}.json"
        
        video_data = {
            'file_info': {
                'file_id': file_data.file_id,
                'original_name': file_data.original_name,
                'file_path': file_data.file_path,
                'file_size': file_data.file_size,
                'mime_type': file_data.mime_type,
                'checksum': file_data.checksum,
                'upload_timestamp': time.time()
            },
            'video_details': asdict(video_details),
            'processing_timeline': {
                'upload_completed': file_data.encoding_start,
                'encoding_started': file_data.encoding_start,
                'encoding_completed': file_data.encoding_end,
                'youtube_upload_started': None,  # Will be updated
                'youtube_upload_completed': None
            },
            'ai_analysis': file_data.ai_analysis,
            'encoding_results': {
                'status': file_data.encoding_status,
                'duration': file_data.encoding_duration,
                'video_path': file_data.video_path,
                'video_size': file_data.video_size,
                'video_quality': file_data.video_quality,
                'frame_count': file_data.frame_count
            },
            'youtube_results': {
                'video_id': file_data.youtube_video_id,
                'url': file_data.youtube_url,
                'upload_status': file_data.upload_status
            },
            'error_tracking': {
                'error_message': file_data.error_message,
                'error_code': file_data.error_code,
                'retry_count': file_data.retry_count
            },
            'performance_metrics': self._calculate_performance_metrics(file_data)
        }
        
        with open(video_file, 'w', encoding='utf-8') as f:
            json.dump(video_data, f, indent=2, ensure_ascii=False)
        
        logger.log_structured('info', 'Video data file created', 
                          file_id=file_data.file_id,
                          video_file=str(video_file))
        
        return str(video_file)
    
    def create_file_data_file(self, file_data: FileProcessingData) -> str:
        """Create detailed file data file"""
        file_data_file = self.files_dir / f"file_{file_data.file_id}.json"
        
        file_data_content = {
            'file_info': {
                'file_id': file_data.file_id,
                'original_name': file_data.original_name,
                'file_path': file_data.file_path,
                'file_size': file_data.file_size,
                'mime_type': file_data.mime_type,
                'checksum': file_data.checksum,
                'upload_timestamp': time.time()
            },
            'ai_analysis': file_data.ai_analysis,
            'processing_info': {
                'encoding_status': file_data.encoding_status,
                'encoding_start': file_data.encoding_start,
                'encoding_end': file_data.encoding_end,
                'encoding_duration': file_data.encoding_duration
            },
            'video_generation': {
                'video_path': file_data.video_path,
                'video_size': file_data.video_size,
                'video_quality': file_data.video_quality,
                'frame_count': file_data.frame_count
            },
            'error_tracking': {
                'error_message': file_data.error_message,
                'error_code': file_data.error_code,
                'retry_count': file_data.retry_count
            }
        }
        
        with open(file_data_file, 'w', encoding='utf-8') as f:
            json.dump(file_data_content, f, indent=2, ensure_ascii=False)
        
        logger.log_structured('info', 'File data file created', 
                          file_id=file_data.file_id,
                          file_data_file=str(file_data_file))
        
        return str(file_data_file)
    
    def update_video_data_file(self, file_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing video data file"""
        video_file = self.videos_dir / f"video_{file_id}.json"
        
        if not video_file.exists():
            return False
        
        try:
            with open(video_file, 'r', encoding='utf-8') as f:
                video_data = json.load(f)
            
            # Deep update
            self._deep_update(video_data, updates)
            
            with open(video_file, 'w', encoding='utf-8') as f:
                json.dump(video_data, f, indent=2, ensure_ascii=False)
            
            logger.log_structured('info', 'Video data file updated', 
                              file_id=file_id,
                              updates=updates)
            
            return True
            
        except Exception as e:
            logger.log_exception('Failed to update video data file', e)
            return False
    
    def _deep_update(self, data: Dict[str, Any], updates: Dict[str, Any]):
        """Deep update nested dictionary"""
        for key, value in updates.items():
            if key in data and isinstance(data[key], dict) and isinstance(value, dict):
                data[key].update(value)
            else:
                data[key] = value
    
    def _estimate_processing_time(self, session: UploadSession) -> Dict[str, Any]:
        """Estimate processing time based on session data"""
        total_size_mb = session.total_size / (1024 * 1024)
        file_count = session.file_count
        
        # Base processing time (seconds)
        base_time = max(60, total_size_mb * 2)  # 2 seconds per MB minimum
        
        # Adjust for file count
        if file_count > 10:
            base_time *= 1.5
        
        # Adjust for quality
        if hasattr(session, 'video_quality') and session.video_quality == "4K":
            base_time *= 2.0
        elif hasattr(session, 'video_quality') and session.video_quality == "720p":
            base_time *= 0.7
        
        return {
            'estimated_seconds': int(base_time),
            'estimated_minutes': round(base_time / 60, 1),
            'factors': {
                'file_size_mb': total_size_mb,
                'file_count': file_count,
                'quality_multiplier': 1.5 if hasattr(session, 'video_quality') and session.video_quality == "4K" else 1.0
            }
        }
    
    def _get_recommended_settings(self, session: UploadSession) -> Dict[str, Any]:
        """Get recommended settings based on session data"""
        total_size_mb = session.total_size / (1024 * 1024)
        
        recommendations = {
            'video_quality': '1080p',
            'compression_level': 'medium',
            'thread_count': min(8, max(2, os.cpu_count() or 4)),
            'parallel_processing': True
        }
        
        # Adjust based on file size
        if total_size_mb > 1000:  # Large files
            recommendations['video_quality'] = '720p'
            recommendations['compression_level'] = 'high'
        elif total_size_mb < 10:  # Small files
            recommendations['video_quality'] = '4K'
            recommendations['compression_level'] = 'low'
        
        # Adjust based on file count
        if session.file_count > 20:
            recommendations['thread_count'] = min(12, os.cpu_count() or 8)
            recommendations['parallel_processing'] = True
        
        return recommendations
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        try:
            import psutil
            
            return {
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage': psutil.disk_usage('/').percent,
                'platform': os.name,
                'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
            }
        except ImportError:
            return {
                'cpu_count': os.cpu_count() or 4,
                'platform': os.name,
                'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
            }
    
    def _get_current_configuration(self) -> Dict[str, Any]:
        """Get current YotuDrive configuration"""
        try:
            return {
                'video_settings': {
                    'width': config_manager.video.width,
                    'height': config_manager.video.height,
                    'fps': config_manager.video.fps,
                    'encoder': config_manager.video.encoder
                },
                'encoding_settings': {
                    'block_size': config_manager.encoding.block_size,
                    'ecc_bytes': config_manager.encoding.ecc_bytes,
                    'header_copies': config_manager.encoding.header_copies
                },
                'security_settings': {
                    'max_file_size': config_manager.security.max_file_size,
                    'allowed_extensions': config_manager.security.allowed_extensions
                },
                'performance_settings': {
                    'threads': config_manager.performance.threads,
                    'max_memory': config_manager.performance.max_memory
                }
            }
        except Exception as e:
            logger.log_exception('Failed to get configuration', e)
            return {}
    
    def _calculate_performance_metrics(self, file_data: FileProcessingData) -> Dict[str, Any]:
        """Calculate performance metrics for file processing"""
        metrics = {
            'processing_speed_mbps': 0,
            'compression_ratio': 0,
            'efficiency_score': 0,
            'quality_score': 0
        }
        
        if (file_data.encoding_start and file_data.encoding_end and 
            file_data.file_size and file_data.video_size):
            
            duration = file_data.encoding_end - file_data.encoding_start
            if duration > 0:
                # Processing speed (MB per second)
                size_mb = file_data.file_size / (1024 * 1024)
                metrics['processing_speed_mbps'] = round(size_mb / duration, 2)
            
            # Compression ratio
            if file_data.video_size:
                metrics['compression_ratio'] = round(file_data.video_size / file_data.file_size, 2)
            
            # Efficiency score (0-100)
            # Based on speed, compression, and error rate
            speed_score = min(100, (metrics['processing_speed_mbps'] / 10) * 100)
            compression_score = max(0, 100 - (metrics['compression_ratio'] - 1) * 50)
            error_penalty = file_data.retry_count * 10
            
            metrics['efficiency_score'] = max(0, (speed_score + compression_score) / 2 - error_penalty)
        
        return metrics
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session summary"""
        session_file = self.sessions_dir / f"session_{session_id}.json"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.log_exception('Failed to read session file', e)
            return None
    
    def get_video_details(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get video details"""
        video_file = self.videos_dir / f"video_{file_id}.json"
        
        if not video_file.exists():
            return None
        
        try:
            with open(video_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.log_exception('Failed to read video file', e)
            return None
    
    def get_file_details(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file details"""
        file_data_file = self.files_dir / f"file_{file_id}.json"
        
        if not file_data_file.exists():
            return None
        
        try:
            with open(file_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.log_exception('Failed to read file data', e)
            return None
    
    def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old data files"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0
        
        for directory in [self.sessions_dir, self.videos_dir, self.files_dir]:
            for file_path in directory.glob("*.json"):
                try:
                    file_age = file_path.stat().st_mtime
                    if file_age < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    logger.log_exception('Failed to cleanup old data file', e)
        
        logger.log_structured('info', 'Old data files cleaned', 
                          cleaned_count=cleaned_count,
                          days=days)
        
        return cleaned_count

class EnhancedUploadManager:
    """Enhanced upload manager with comprehensive data collection"""
    
    def __init__(self):
        self.data_manager = DataFileManager()
        self.active_sessions = {}
        self.file_processing_queue = {}
    
    def create_upload_session(self, user_id: str, files: List[str], 
                          upload_type: str = "file") -> str:
        """Create enhanced upload session"""
        session_id = str(uuid.uuid4())
        
        # Calculate total size
        total_size = 0
        file_data = []
        
        for file_path in files:
            try:
                validated_path, file_size = FileValidator.validate_file(file_path)
                total_size += file_size
                
                file_data.append({
                    'path': validated_path,
                    'size': file_size,
                    'name': Path(validated_path).name,
                    'mime_type': self._get_mime_type(validated_path)
                })
            except Exception as e:
                logger.log_exception('File validation failed', e)
                continue
        
        # Create session
        session = UploadSession(
            session_id=session_id,
            user_id=user_id,
            upload_type=upload_type,
            files=file_data,
            total_size=total_size,
            file_count=len(files)
        )
        
        # Store session
        self.active_sessions[session_id] = session
        
        # Create session data file
        self.data_manager.create_session_data_file(session)
        
        logger.log_structured('info', 'Enhanced upload session created', 
                          session_id=session_id,
                          file_count=len(files),
                          total_size=total_size)
        
        return session_id
    
    def collect_user_input(self, session_id: str, file_id: str) -> Dict[str, Any]:
        """Collect comprehensive user input for video details"""
        user_input = {
            'required_fields': {
                'title': {
                    'type': 'text',
                    'label': 'Video Title',
                    'description': 'Enter a descriptive title for your video',
                    'required': True,
                    'max_length': 100,
                    'example': 'Q4 Financial Report 2024'
                },
                'description': {
                    'type': 'textarea',
                    'label': 'Description',
                    'description': 'Describe what this video contains',
                    'required': False,
                    'max_length': 5000,
                    'example': 'This video contains the Q4 financial presentation with revenue charts and growth analysis...'
                },
                'category': {
                    'type': 'select',
                    'label': 'Category',
                    'description': 'Select the best category for your video',
                    'required': True,
                    'options': [
                        {'value': 'general', 'label': 'General'},
                        {'value': 'music', 'label': 'Music'},
                        {'value': 'gaming', 'label': 'Gaming'},
                        {'value': 'education', 'label': 'Education'},
                        {'value': 'entertainment', 'label': 'Entertainment'},
                        {'value': 'news', 'label': 'News & Politics'},
                        {'value': 'howto', 'label': 'How-to & Style'}
                    ],
                    'example': 'education'
                },
                'tags': {
                    'type': 'tags',
                    'label': 'Tags',
                    'description': 'Add tags to help others find this video',
                    'required': False,
                    'max_tags': 15,
                    'example': 'financial, report, quarterly, revenue, growth, charts'
                }
            },
            'optional_fields': {
                'quality': {
                    'type': 'select',
                    'label': 'Video Quality',
                    'description': 'Choose video quality for encoding',
                    'required': False,
                    'options': [
                        {'value': '2160p', 'label': '4K (2160p) - Ultra HD'},
                        {'value': '1080p', 'label': 'Full HD (1080p) - Recommended'},
                        {'value': '720p', 'label': 'HD (720p) - Good Quality'},
                        {'value': '480p', 'label': 'SD (480p) - Standard'}
                    ],
                    'default': '1080p'
                },
                'privacy': {
                    'type': 'select',
                    'label': 'Privacy Settings',
                    'description': 'Who can see this video',
                    'required': False,
                    'options': [
                        {'value': 'public', 'label': 'Public - Anyone can see'},
                        {'value': 'unlisted', 'label': 'Unlisted - Only with link'},
                        {'value': 'private', 'label': 'Private - Only you'}
                    ],
                    'default': 'unlisted'
                },
                'language': {
                    'type': 'text',
                    'label': 'Language',
                    'description': 'Primary language spoken in the video',
                    'required': False,
                    'example': 'English'
                },
                'target_audience': {
                    'type': 'select',
                    'label': 'Target Audience',
                    'description': 'Intended audience for this content',
                    'required': False,
                    'options': [
                        {'value': 'everyone', 'label': 'Everyone'},
                        {'value': 'mature', 'label': 'Mature (18+)'},
                        {'value': 'restricted', 'label': 'Restricted'}
                    ],
                    'default': 'everyone'
                },
                'location': {
                    'type': 'text',
                    'label': 'Location',
                    'description': 'Where was this video recorded?',
                    'required': False,
                    'example': 'New York, NY'
                },
                'recording_date': {
                    'type': 'date',
                    'label': 'Recording Date',
                    'description': 'When was this video recorded?',
                    'required': False
                }
            },
            'advanced_fields': {
                'allow_comments': {
                    'type': 'checkbox',
                    'label': 'Allow Comments',
                    'description': 'Let viewers comment on your video',
                    'default': True
                },
                'allow_ratings': {
                    'type': 'checkbox',
                    'label': 'Allow Ratings',
                    'description': 'Let viewers rate your video',
                    'default': True
                },
                'monetize': {
                    'type': 'checkbox',
                    'label': 'Monetize Video',
                    'description': 'Enable monetization features',
                    'default': False
                },
                'custom_thumbnail': {
                    'type': 'file',
                    'label': 'Custom Thumbnail',
                    'description': 'Upload a custom thumbnail image',
                    'accept': 'image/*'
                }
            }
        }
        
        # Store user input template
        input_file = self.data_manager.data_dir / f"user_input_{file_id}.json"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(user_input, f, indent=2, ensure_ascii=False)
        
        logger.log_structured('info', 'User input template created', 
                          session_id=session_id,
                          file_id=file_id)
        
        return user_input
    
    def process_user_input(self, session_id: str, file_id: str, 
                        user_input: Dict[str, Any]) -> VideoDetails:
        """Process user input and create video details"""
        try:
            # Validate required fields
            if not user_input.get('title'):
                raise YotuDriveException("Video title is required", ErrorCodes.MISSING_REQUIRED_FIELD)
            
            # Create video details
            video_details = VideoDetails(
                title=user_input.get('title', '').strip(),
                description=user_input.get('description', '').strip(),
                tags=user_input.get('tags', []),
                category=user_input.get('category', 'general'),
                language=user_input.get('language', 'English'),
                quality=user_input.get('quality', '1080p'),
                privacy=user_input.get('privacy', 'unlisted'),
                allow_comments=user_input.get('allow_comments', True),
                allow_ratings=user_input.get('allow_ratings', True),
                age_restriction=user_input.get('age_restriction'),
                content_type=user_input.get('content_type', 'general'),
                target_audience=user_input.get('target_audience', 'everyone'),
                content_warnings=user_input.get('content_warnings', []),
                monetize=user_input.get('monetize', False),
                license_type=user_input.get('license_type', 'youtube'),
                location=user_input.get('location'),
                recording_date=user_input.get('recording_date'),
                author=user_input.get('author'),
                custom_thumbnail=user_input.get('custom_thumbnail')
            )
            
            # Validate and clean data
            video_details = self._validate_and_clean_video_details(video_details)
            
            logger.log_structured('info', 'User input processed', 
                              session_id=session_id,
                              file_id=file_id,
                              title=video_details.title)
            
            return video_details
            
        except Exception as e:
            logger.log_exception('Failed to process user input', e)
            raise YotuDriveException("User input processing failed", ErrorCodes.INVALID_FORMAT, e)
    
    def _validate_and_clean_video_details(self, video_details: VideoDetails) -> VideoDetails:
        """Validate and clean video details"""
        # Clean title
        video_details.title = video_details.title.strip()[:100]
        
        # Clean description
        video_details.description = video_details.description.strip()[:5000]
        
        # Clean and validate tags
        if video_details.tags:
            # Remove duplicates and limit to 15
            unique_tags = list(set(tag.strip() for tag in video_details.tags if tag.strip()))
            video_details.tags = unique_tags[:15]
        
        # Validate quality
        valid_qualities = ['2160p', '1080p', '720p', '480p']
        if video_details.quality not in valid_qualities:
            video_details.quality = '1080p'
        
        # Validate privacy
        valid_privacy = ['public', 'unlisted', 'private']
        if video_details.privacy not in valid_privacy:
            video_details.privacy = 'unlisted'
        
        # Validate category
        valid_categories = ['general', 'music', 'gaming', 'education', 'entertainment', 'news', 'howto']
        if video_details.category not in valid_categories:
            video_details.category = 'general'
        
        return video_details
    
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

# Global enhanced upload manager
enhanced_upload_manager = EnhancedUploadManager()
