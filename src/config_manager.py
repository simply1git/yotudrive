"""
Advanced configuration management with validation and environment variable support.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field
from .utils import ValidationError, YotuDriveException, ErrorCodes

@dataclass
class VideoConfig:
    """Video encoding configuration."""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    encoder: str = "libx264"
    preset: str = "medium"
    
    def validate(self) -> None:
        """Validate video configuration."""
        if self.width <= 0 or self.height <= 0:
            raise ValidationError("Video dimensions must be positive")
        if self.fps <= 0 or self.fps > 120:
            raise ValidationError("FPS must be between 1 and 120")
        valid_encoders = ["libx264", "nvenc", "qsv", "amf"]
        if self.encoder not in valid_encoders:
            raise ValidationError(f"Invalid encoder: {self.encoder}")
        valid_presets = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
        if self.preset not in valid_presets:
            raise ValidationError(f"Invalid preset: {self.preset}")

@dataclass
class EncodingConfig:
    """Data encoding configuration."""
    block_size: int = 2
    max_block_size: int = 15
    header_copies: int = 5
    ecc_bytes: int = 32
    rs_block_size: int = 255
    chunk_size: int = field(init=False)
    
    def __post_init__(self):
        """Calculate derived values."""
        self.chunk_size = (self.rs_block_size - self.ecc_bytes) * 1024
    
    def validate(self) -> None:
        """Validate encoding configuration."""
        if self.block_size <= 0 or self.block_size > self.max_block_size:
            raise ValidationError(f"Block size must be between 1 and {self.max_block_size}")
        if self.header_copies < 1 or self.header_copies > 10:
            raise ValidationError("Header copies must be between 1 and 10")
        if self.ecc_bytes < 0 or self.ecc_bytes >= self.rs_block_size:
            raise ValidationError(f"ECC bytes must be between 0 and {self.rs_block_size - 1}")

@dataclass
class SecurityConfig:
    """Security and encryption configuration."""
    max_file_size: int = 100 * 1024 * 1024 * 1024  # 100GB
    allowed_extensions: list = field(default_factory=lambda: [
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
        '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.exe', '.msi', '.deb', '.rpm', '.dmg', '.pkg',
        '.bin', '.iso', '.img', '.vhd', '.vmdk'
    ])
    enable_virus_scan: bool = False
    temp_dir: Optional[str] = None
    
    def validate(self) -> None:
        """Validate security configuration."""
        if self.max_file_size <= 0:
            raise ValidationError("Max file size must be positive")
        if self.temp_dir and not os.path.exists(self.temp_dir):
            raise ValidationError(f"Temp directory does not exist: {self.temp_dir}")

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"  # "json" or "text"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    log_dir: str = "logs"
    enable_console: bool = True
    
    def validate(self) -> None:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level not in valid_levels:
            raise ValidationError(f"Invalid log level: {self.level}")
        valid_formats = ["json", "text"]
        if self.format not in valid_formats:
            raise ValidationError(f"Invalid log format: {self.format}")
        if self.max_file_size <= 0:
            raise ValidationError("Max file size must be positive")
        if self.backup_count < 0:
            raise ValidationError("Backup count must be non-negative")

@dataclass
class PerformanceConfig:
    """Performance and threading configuration."""
    threads: int = field(default_factory=lambda: os.cpu_count() or 4)
    max_memory: int = 2 * 1024 * 1024 * 1024  # 2GB
    pipeline_chunk_size: int = 1024 * 1024  # 1MB
    enable_parallel: bool = True
    
    def validate(self) -> None:
        """Validate performance configuration."""
        if self.threads <= 0 or self.threads > 64:
            raise ValidationError("Threads must be between 1 and 64")
        if self.max_memory <= 0:
            raise ValidationError("Max memory must be positive")
        if self.pipeline_chunk_size <= 0:
            raise ValidationError("Pipeline chunk size must be positive")

class ConfigManager:
    """Advanced configuration manager with validation and environment support."""
    
    def __init__(self, config_file: str = "settings.json"):
        self.config_file = Path(config_file)
        self.logger = logging.getLogger(__name__)
        
        # Initialize default configurations
        self.video = VideoConfig()
        self.encoding = EncodingConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.performance = PerformanceConfig()
        
        # Load configuration
        self.load()
    
    def load(self) -> None:
        """Load configuration from file and environment variables."""
        # Load from file first
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._update_from_dict(data)
                self.logger.info(f"Configuration loaded from {self.config_file}")
            except (json.JSONDecodeError, OSError) as e:
                self.logger.warning(f"Failed to load config file: {e}")
        
        # Override with environment variables
        self._load_from_env()
        
        # Validate all configurations
        self.validate()
    
    def save(self) -> None:
        """Save current configuration to file."""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dictionary
            config_dict = {
                'video': self.video.__dict__,
                'encoding': self.encoding.__dict__,
                'security': self.security.__dict__,
                'logging': self.logging.__dict__,
                'performance': self.performance.__dict__
            }
            
            # Write to temporary file first
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4, sort_keys=True)
            
            # Atomic replace
            temp_file.replace(self.config_file)
            self.logger.info(f"Configuration saved to {self.config_file}")
            
        except OSError as e:
            raise YotuDriveException(f"Failed to save configuration: {e}", ErrorCodes.CONFIGURATION_ERROR, e)
    
    def validate(self) -> None:
        """Validate all configuration sections."""
        try:
            self.video.validate()
            self.encoding.validate()
            self.security.validate()
            self.logging.validate()
            self.performance.validate()
        except ValidationError as e:
            raise YotuDriveException(f"Configuration validation failed: {e}", ErrorCodes.CONFIGURATION_ERROR, e)
    
    def _update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary."""
        if 'video' in data:
            self._update_dataclass(self.video, data['video'])
        if 'encoding' in data:
            self._update_dataclass(self.encoding, data['encoding'])
        if 'security' in data:
            self._update_dataclass(self.security, data['security'])
        if 'logging' in data:
            self._update_dataclass(self.logging, data['logging'])
        if 'performance' in data:
            self._update_dataclass(self.performance, data['performance'])
    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]) -> None:
        """Update dataclass fields from dictionary."""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Video settings
        self.video.width = int(os.getenv('YOTUDRIVE_VIDEO_WIDTH', self.video.width))
        self.video.height = int(os.getenv('YOTUDRIVE_VIDEO_HEIGHT', self.video.height))
        self.video.fps = int(os.getenv('YOTUDRIVE_VIDEO_FPS', self.video.fps))
        self.video.encoder = os.getenv('YOTUDRIVE_VIDEO_ENCODER', self.video.encoder)
        self.video.preset = os.getenv('YOTUDRIVE_VIDEO_PRESET', self.video.preset)
        
        # Encoding settings
        self.encoding.block_size = int(os.getenv('YOTUDRIVE_BLOCK_SIZE', self.encoding.block_size))
        self.encoding.header_copies = int(os.getenv('YOTUDRIVE_HEADER_COPIES', self.encoding.header_copies))
        self.encoding.ecc_bytes = int(os.getenv('YOTUDRIVE_ECC_BYTES', self.encoding.ecc_bytes))
        
        # Security settings
        self.security.max_file_size = int(os.getenv('YOTUDRIVE_MAX_FILE_SIZE', self.security.max_file_size))
        self.security.enable_virus_scan = os.getenv('YOTUDRIVE_ENABLE_VIRUS_SCAN', 'false').lower() == 'true'
        self.security.temp_dir = os.getenv('YOTUDRIVE_TEMP_DIR', self.security.temp_dir)
        
        # Logging settings
        self.logging.level = os.getenv('YOTUDRIVE_LOG_LEVEL', self.logging.level).upper()
        self.logging.format = os.getenv('YOTUDRIVE_LOG_FORMAT', self.logging.format).lower()
        self.logging.max_file_size = int(os.getenv('YOTUDRIVE_LOG_MAX_SIZE', self.logging.max_file_size))
        self.logging.backup_count = int(os.getenv('YOTUDRIVE_LOG_BACKUP_COUNT', self.logging.backup_count))
        self.logging.log_dir = os.getenv('YOTUDRIVE_LOG_DIR', self.logging.log_dir)
        self.logging.enable_console = os.getenv('YOTUDRIVE_LOG_CONSOLE', 'true').lower() == 'true'
        
        # Performance settings
        self.performance.threads = int(os.getenv('YOTUDRIVE_THREADS', self.performance.threads))
        self.performance.max_memory = int(os.getenv('YOTUDRIVE_MAX_MEMORY', self.performance.max_memory))
        self.performance.pipeline_chunk_size = int(os.getenv('YOTUDRIVE_PIPELINE_CHUNK_SIZE', self.performance.pipeline_chunk_size))
        self.performance.enable_parallel = os.getenv('YOTUDRIVE_ENABLE_PARALLEL', 'true').lower() == 'true'
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using a dot-separated key (e.g., 'google.client_id')."""
        try:
            # First check if the key is in environment variables (mapped to YOTUDRIVE_*)
            env_key = f"YOTUDRIVE_{key.upper().replace('.', '_')}"
            env_val = os.getenv(env_key)
            if env_val is not None:
                return env_val

            # Special handling for google namespace since it might not be a dataclass yet
            if key.startswith('google.'):
                attr_name = key.split('.')[1]
                # Fallback to direct env lookups for common Google keys
                if attr_name == 'client_id':
                    return os.getenv('GOOGLE_CLIENT_ID', default)
                if attr_name == 'client_secret':
                    return os.getenv('GOOGLE_CLIENT_SECRET', default)
                if attr_name == 'redirect_uri':
                    return os.getenv('GOOGLE_REDIRECT_URI', default)

            # Standard attribute traversal
            parts = key.split('.')
            obj = self
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return default
            return obj
        except Exception:
            return default

    def get_effective_config(self) -> Dict[str, Any]:
        """Get effective configuration as dictionary."""
        return {
            'video': self.video.__dict__,
            'encoding': self.encoding.__dict__,
            'security': self.security.__dict__,
            'logging': self.logging.__dict__,
            'performance': self.performance.__dict__
        }
    
    def reset_to_defaults(self) -> None:
        """Reset all configurations to defaults."""
        self.video = VideoConfig()
        self.encoding = EncodingConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.performance = PerformanceConfig()
        self.logger.info("Configuration reset to defaults")
    
    def export_template(self, file_path: str) -> None:
        """Export configuration template with comments."""
        template = {
            "_comment": "YotuDrive Configuration Template",
            "_environment_variables": "See documentation for available environment variables",
            "video": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "encoder": "libx264",
                "preset": "medium",
                "_comment_encoder": "Options: libx264, nvenc, qsv, amf",
                "_comment_preset": "Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow"
            },
            "encoding": {
                "block_size": 2,
                "max_block_size": 15,
                "header_copies": 5,
                "ecc_bytes": 32,
                "rs_block_size": 255,
                "_comment_block_size": "Size of each pixel block (1-15)",
                "_comment_ecc_bytes": "Error correction bytes (0-254)"
            },
            "security": {
                "max_file_size": 107374182400,
                "allowed_extensions": [".zip", ".rar", ".7z", ".txt", ".pdf", ".jpg", ".png", ".mp4"],
                "enable_virus_scan": false,
                "temp_dir": null,
                "_comment_max_file_size": "Maximum file size in bytes (100GB default)"
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "max_file_size": 10485760,
                "backup_count": 5,
                "log_dir": "logs",
                "enable_console": true,
                "_comment_level": "Options: DEBUG, INFO, WARNING, ERROR, CRITICAL",
                "_comment_format": "Options: json, text"
            },
            "performance": {
                "threads": 8,
                "max_memory": 2147483648,
                "pipeline_chunk_size": 1048576,
                "enable_parallel": true,
                "_comment_threads": "Number of CPU threads to use",
                "_comment_max_memory": "Maximum memory usage in bytes"
            }
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=4, sort_keys=True)
            self.logger.info(f"Configuration template exported to {file_path}")
        except OSError as e:
            raise YotuDriveException(f"Failed to export template: {e}", ErrorCodes.CONFIGURATION_ERROR, e)

# Global configuration instance
config_manager = ConfigManager()
