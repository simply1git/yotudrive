"""
Utility functions for YotuDrive including validation, sanitization, and naming conventions.
"""

import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional, List, Tuple

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class FileValidator:
    """Handles file validation and sanitization."""
    
    # Allowed file extensions for security
    ALLOWED_EXTENSIONS = {
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
        '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.exe', '.msi', '.deb', '.rpm', '.dmg', '.pkg',
        '.bin', '.iso', '.img', '.vhd', '.vmdk'
    }
    
    # Maximum file size (100GB default)
    MAX_FILE_SIZE = 100 * 1024 * 1024 * 1024
    
    # Dangerous file patterns to block
    DANGEROUS_PATTERNS = [
        r'\.exe$', r'\.bat$', r'\.cmd$', r'\.scr$', r'\.vbs$', r'\.js$',
        r'\.jar$', r'\.app$', r'\.deb$', r'\.rpm$', r'\.dmg$',
        r'con$', r'prn$', r'aux$', r'nul$', r'com[1-9]$', r'lpt[1-9]$'
    ]
    
    @staticmethod
    def sanitize_path(file_path: str) -> str:
        """Sanitize file path to prevent directory traversal attacks."""
        if not file_path:
            raise ValidationError("File path cannot be empty")
        
        # Convert to Path object for safe handling
        try:
            path = Path(file_path).resolve()
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid file path: {e}")
        
        # Check for directory traversal
        if '..' in str(path):
            raise ValidationError("Directory traversal not allowed")
        
        return str(path)
    
    @staticmethod
    def validate_file(file_path: str, max_size: Optional[int] = None) -> Tuple[str, int]:
        """Validate file exists, is accessible, and meets security criteria."""
        file_path = FileValidator.sanitize_path(file_path)
        
        if not os.path.exists(file_path):
            raise ValidationError(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise ValidationError(f"Path is not a file: {file_path}")
        
        # Check file permissions
        if not os.access(file_path, os.R_OK):
            raise ValidationError(f"File is not readable: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = max_size or FileValidator.MAX_FILE_SIZE
        if file_size > max_size:
            raise ValidationError(f"File too large: {file_size} bytes (max: {max_size} bytes)")
        
        if file_size == 0:
            raise ValidationError(f"File is empty: {file_path}")
        
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext and file_ext not in FileValidator.ALLOWED_EXTENSIONS:
            raise ValidationError(f"File type not allowed: {file_ext}")
        
        # Check for dangerous patterns in filename
        filename = os.path.basename(file_path)
        for pattern in FileValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                raise ValidationError(f"Filename contains dangerous pattern: {filename}")
        
        return file_path, file_size
    
    @staticmethod
    def validate_directory(dir_path: str) -> str:
        """Validate directory exists and is writable."""
        dir_path = FileValidator.sanitize_path(dir_path)
        
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                raise ValidationError(f"Cannot create directory: {e}")
        
        if not os.path.isdir(dir_path):
            raise ValidationError(f"Path is not a directory: {dir_path}")
        
        if not os.access(dir_path, os.W_OK):
            raise ValidationError(f"Directory is not writable: {dir_path}")
        
        return dir_path

class NamingConvention:
    """Handles proper naming conventions for output files."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for cross-platform compatibility."""
        if not filename:
            return "unnamed"
        
        # Remove path separators
        filename = os.path.basename(filename)
        
        # Replace problematic characters
        replacements = {
            '<': '_', '>': '_', ':': '_', '"': "'", '/': '_', '\\': '_', 
            '|': '_', '?': '_', '*': '_', ' ': '_'
        }
        
        for old, new in replacements.items():
            filename = filename.replace(old, new)
        
        # Remove control characters
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Limit length (255 chars max for most filesystems)
        if len(filename) > 200:  # Leave room for extension and timestamp
            name, ext = os.path.splitext(filename)
            filename = name[:200] + ext
        
        # Ensure it doesn't start with dot (hidden file)
        if filename.startswith('.'):
            filename = 'file' + filename
        
        return filename
    
    @staticmethod
    def generate_video_name(input_filename: str, timestamp: Optional[int] = None) -> str:
        """Generate clean video filename from input filename."""
        timestamp = timestamp or int(time.time())
        
        # Sanitize input filename
        clean_name = NamingConvention.sanitize_filename(input_filename)
        
        # Remove existing extension
        name_without_ext = os.path.splitext(clean_name)[0]
        
        # Generate unique but readable name
        unique_id = str(uuid.uuid4())[:8]
        video_name = f"{name_without_ext}_{timestamp}_{unique_id}.mp4"
        
        return video_name
    
    @staticmethod
    def generate_frames_dir_name(base_dir: str, input_filename: str) -> str:
        """Generate clean frames directory name."""
        clean_name = NamingConvention.sanitize_filename(input_filename)
        name_without_ext = os.path.splitext(clean_name)[0]
        
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        frames_dir = os.path.join(base_dir, f"frames_{name_without_ext}_{timestamp}_{unique_id}")
        return frames_dir
    
    @staticmethod
    def generate_restored_filename(original_name: str, suffix: str = "restored") -> str:
        """Generate restored filename with proper suffix."""
        clean_name = NamingConvention.sanitize_filename(original_name)
        name_without_ext, ext = os.path.splitext(clean_name)
        
        return f"{name_without_ext}_{suffix}{ext}"

class ErrorCodes:
    """Standardized error codes for better error handling."""
    
    # File system errors (1000-1099)
    FILE_NOT_FOUND = 1001
    FILE_TOO_LARGE = 1002
    FILE_NOT_READABLE = 1003
    INVALID_FILE_TYPE = 1004
    DIRECTORY_NOT_WRITABLE = 1005
    DISK_FULL = 1006
    
    # Validation errors (1100-1199)
    INVALID_PATH = 1101
    DANGEROUS_FILENAME = 1102
    MISSING_REQUIRED_FIELD = 1103
    INVALID_FORMAT = 1104
    
    # Encoding/Decoding errors (1200-1299)
    ENCODING_FAILED = 1201
    DECODING_FAILED = 1202
    HEADER_CORRUPT = 1203
    CHECKSUM_MISMATCH = 1204
    ECC_CORRECTION_FAILED = 1205
    
    # YouTube/Network errors (1300-1399)
    YOUTUBE_API_ERROR = 1301
    DOWNLOAD_FAILED = 1302
    NETWORK_TIMEOUT = 1303
    INVALID_VIDEO_ID = 1304
    
    # System errors (1400-1499)
    FFMPEG_NOT_FOUND = 1401
    INSUFFICIENT_MEMORY = 1402
    THREADING_ERROR = 1403
    CONFIGURATION_ERROR = 1404

class YotuDriveException(Exception):
    """Base exception class for YotuDrive with error codes."""
    
    def __init__(self, message: str, error_code: int = 0, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.error_code = error_code
        self.original_error = original_error
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for logging."""
        return {
            'error_type': self.__class__.__name__,
            'message': str(self),
            'error_code': self.error_code,
            'timestamp': self.timestamp,
            'original_error': str(self.original_error) if self.original_error else None
        }

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def ensure_directory_exists(dir_path: str) -> str:
    """Ensure directory exists, create if necessary."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
    except OSError as e:
        raise ValidationError(f"Cannot create directory {dir_path}: {e}")

def safe_file_operation(operation_func, *args, **kwargs):
    """Safely execute file operations with proper error handling."""
    try:
        return operation_func(*args, **kwargs)
    except OSError as e:
        raise YotuDriveException(
            f"File operation failed: {e}",
            ErrorCodes.FILE_NOT_READABLE,
            e
        )
    except Exception as e:
        raise YotuDriveException(
            f"Unexpected error during file operation: {e}",
            0,
            e
        )
