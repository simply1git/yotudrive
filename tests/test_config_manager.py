"""
Test configuration management functionality.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path

from src.config_manager import (
    ConfigManager, VideoConfig, EncodingConfig, SecurityConfig, 
    LoggingConfig, PerformanceConfig, ValidationError
)
from src.utils import YotuDriveException, ErrorCodes

class TestVideoConfig:
    """Test video configuration."""
    
    def test_default_video_config(self):
        """Test default video configuration."""
        config = VideoConfig()
        assert config.width == 1920
        assert config.height == 1080
        assert config.fps == 30
        assert config.encoder == "libx264"
        assert config.preset == "medium"
    
    def test_video_config_validation(self):
        """Test video configuration validation."""
        config = VideoConfig()
        
        # Valid configuration
        config.validate()  # Should not raise
        
        # Invalid dimensions
        config.width = -1
        with pytest.raises(ValidationError, match="Video dimensions must be positive"):
            config.validate()
        
        config.width = 1920
        config.height = 0
        with pytest.raises(ValidationError, match="Video dimensions must be positive"):
            config.validate()
        
        config.height = 1080
        
        # Invalid FPS
        config.fps = -1
        with pytest.raises(ValidationError, match="FPS must be between 1 and 120"):
            config.validate()
        
        config.fps = 150
        with pytest.raises(ValidationError, match="FPS must be between 1 and 120"):
            config.validate()
        
        config.fps = 30
        
        # Invalid encoder
        config.encoder = "invalid_encoder"
        with pytest.raises(ValidationError, match="Invalid encoder"):
            config.validate()
        
        config.encoder = "libx264"
        
        # Invalid preset
        config.preset = "invalid_preset"
        with pytest.raises(ValidationError, match="Invalid preset"):
            config.validate()

class TestEncodingConfig:
    """Test encoding configuration."""
    
    def test_default_encoding_config(self):
        """Test default encoding configuration."""
        config = EncodingConfig()
        assert config.block_size == 2
        assert config.max_block_size == 15
        assert config.header_copies == 5
        assert config.ecc_bytes == 32
        assert config.rs_block_size == 255
        assert config.chunk_size == (255 - 32) * 1024
    
    def test_encoding_config_validation(self):
        """Test encoding configuration validation."""
        config = EncodingConfig()
        
        # Valid configuration
        config.validate()  # Should not raise
        
        # Invalid block size
        config.block_size = 0
        with pytest.raises(ValidationError, match="Block size must be between"):
            config.validate()
        
        config.block_size = 16  # Too large
        with pytest.raises(ValidationError, match="Block size must be between"):
            config.validate()
        
        config.block_size = 2
        
        # Invalid header copies
        config.header_copies = 0
        with pytest.raises(ValidationError, match="Header copies must be between"):
            config.validate()
        
        config.header_copies = 11  # Too many
        with pytest.raises(ValidationError, match="Header copies must be between"):
            config.validate()
        
        config.header_copies = 5
        
        # Invalid ECC bytes
        config.ecc_bytes = -1
        with pytest.raises(ValidationError, match="ECC bytes must be between"):
            config.validate()
        
        config.ecc_bytes = 255  # Too many
        with pytest.raises(ValidationError, match="ECC bytes must be between"):
            config.validate()

class TestSecurityConfig:
    """Test security configuration."""
    
    def test_default_security_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.max_file_size == 100 * 1024 * 1024 * 1024  # 100GB
        assert len(config.allowed_extensions) > 0
        assert not config.enable_virus_scan
        assert config.temp_dir is None
    
    def test_security_config_validation(self):
        """Test security configuration validation."""
        config = SecurityConfig()
        
        # Valid configuration
        config.validate()  # Should not raise
        
        # Invalid max file size
        config.max_file_size = -1
        with pytest.raises(ValidationError, match="Max file size must be positive"):
            config.validate()
        
        config.max_file_size = 100 * 1024 * 1024 * 1024
        
        # Invalid temp directory
        config.temp_dir = "/nonexistent/directory"
        with pytest.raises(ValidationError, match="Temp directory does not exist"):
            config.validate()

class TestLoggingConfig:
    """Test logging configuration."""
    
    def test_default_logging_config(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
        assert config.backup_count == 5
        assert config.log_dir == "logs"
        assert config.enable_console
    
    def test_logging_config_validation(self):
        """Test logging configuration validation."""
        config = LoggingConfig()
        
        # Valid configuration
        config.validate()  # Should not raise
        
        # Invalid level
        config.level = "INVALID"
        with pytest.raises(ValidationError, match="Invalid log level"):
            config.validate()
        
        config.level = "DEBUG"
        
        # Invalid format
        config.format = "invalid"
        with pytest.raises(ValidationError, match="Invalid log format"):
            config.validate()
        
        config.format = "json"
        
        # Invalid max file size
        config.max_file_size = -1
        with pytest.raises(ValidationError, match="Max file size must be positive"):
            config.validate()
        
        config.max_file_size = 10 * 1024 * 1024
        
        # Invalid backup count
        config.backup_count = -1
        with pytest.raises(ValidationError, match="Backup count must be non-negative"):
            config.validate()

class TestPerformanceConfig:
    """Test performance configuration."""
    
    def test_default_performance_config(self):
        """Test default performance configuration."""
        config = PerformanceConfig()
        assert config.threads > 0
        assert config.max_memory == 2 * 1024 * 1024 * 1024  # 2GB
        assert config.pipeline_chunk_size == 1024 * 1024  # 1MB
        assert config.enable_parallel
    
    def test_performance_config_validation(self):
        """Test performance configuration validation."""
        config = PerformanceConfig()
        
        # Valid configuration
        config.validate()  # Should not raise
        
        # Invalid threads
        config.threads = 0
        with pytest.raises(ValidationError, match="Threads must be between"):
            config.validate()
        
        config.threads = 65  # Too many
        with pytest.raises(ValidationError, match="Threads must be between"):
            config.validate()
        
        config.threads = 4
        
        # Invalid max memory
        config.max_memory = -1
        with pytest.raises(ValidationError, match="Max memory must be positive"):
            config.validate()
        
        config.max_memory = 2 * 1024 * 1024 * 1024
        
        # Invalid pipeline chunk size
        config.pipeline_chunk_size = 0
        with pytest.raises(ValidationError, match="Pipeline chunk size must be positive"):
            config.validate()

class TestConfigManager:
    """Test configuration manager."""
    
    def test_default_config_manager(self, temp_dir):
        """Test default configuration manager."""
        config_file = temp_dir / "test_config.json"
        manager = ConfigManager(str(config_file))
        
        # Should load defaults
        assert manager.video.width == 1920
        assert manager.encoding.block_size == 2
        assert manager.security.max_file_size == 100 * 1024 * 1024 * 1024
        assert manager.logging.level == "INFO"
        assert manager.performance.threads > 0
    
    def test_load_from_file(self, temp_dir):
        """Test loading configuration from file."""
        config_file = temp_dir / "test_config.json"
        
        # Create test configuration
        test_config = {
            "video": {
                "width": 1280,
                "height": 720,
                "fps": 25,
                "encoder": "nvenc",
                "preset": "fast"
            },
            "encoding": {
                "block_size": 4,
                "header_copies": 3,
                "ecc_bytes": 16
            },
            "security": {
                "max_file_size": 50 * 1024 * 1024 * 1024,  # 50GB
                "enable_virus_scan": True
            },
            "logging": {
                "level": "DEBUG",
                "format": "text",
                "backup_count": 3
            },
            "performance": {
                "threads": 8,
                "max_memory": 4 * 1024 * 1024 * 1024  # 4GB
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        manager = ConfigManager(str(config_file))
        
        # Verify loaded configuration
        assert manager.video.width == 1280
        assert manager.video.height == 720
        assert manager.video.fps == 25
        assert manager.video.encoder == "nvenc"
        assert manager.video.preset == "fast"
        
        assert manager.encoding.block_size == 4
        assert manager.encoding.header_copies == 3
        assert manager.encoding.ecc_bytes == 16
        
        assert manager.security.max_file_size == 50 * 1024 * 1024 * 1024
        assert manager.security.enable_virus_scan
        
        assert manager.logging.level == "DEBUG"
        assert manager.logging.format == "text"
        assert manager.logging.backup_count == 3
        
        assert manager.performance.threads == 8
        assert manager.performance.max_memory == 4 * 1024 * 1024 * 1024
    
    def test_save_configuration(self, temp_dir):
        """Test saving configuration to file."""
        config_file = temp_dir / "test_config.json"
        manager = ConfigManager(str(config_file))
        
        # Modify some settings
        manager.video.width = 1280
        manager.encoding.block_size = 4
        manager.logging.level = "DEBUG"
        
        # Save configuration
        manager.save()
        
        # Verify file was created and contains correct data
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['video']['width'] == 1280
        assert saved_data['encoding']['block_size'] == 4
        assert saved_data['logging']['level'] == "DEBUG"
    
    def test_environment_variable_override(self, temp_dir):
        """Test environment variable overrides."""
        config_file = temp_dir / "test_config.json"
        
        # Set environment variables
        env_vars = {
            'YOTUDRIVE_VIDEO_WIDTH': '1280',
            'YOTUDRIVE_VIDEO_FPS': '25',
            'YOTUDRIVE_BLOCK_SIZE': '4',
            'YOTUDRIVE_LOG_LEVEL': 'DEBUG',
            'YOTUDRIVE_THREADS': '8',
            'YOTUDRIVE_ENABLE_PARALLEL': 'false'
        }
        
        # Set environment variables
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            manager = ConfigManager(str(config_file))
            
            # Verify environment overrides
            assert manager.video.width == 1280
            assert manager.video.fps == 25
            assert manager.encoding.block_size == 4
            assert manager.logging.level == "DEBUG"
            assert manager.performance.threads == 8
            assert not manager.performance.enable_parallel
            
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    
    def test_validation_failure(self, temp_dir):
        """Test configuration validation failure."""
        config_file = temp_dir / "test_config.json"
        
        # Create invalid configuration
        invalid_config = {
            "video": {
                "width": -1,  # Invalid
                "height": 1080,
                "fps": 30
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(invalid_config, f)
        
        with pytest.raises(YotuDriveException, match="Configuration validation failed"):
            ConfigManager(str(config_file))
    
    def test_reset_to_defaults(self, temp_dir):
        """Test resetting configuration to defaults."""
        config_file = temp_dir / "test_config.json"
        manager = ConfigManager(str(config_file))
        
        # Modify settings
        manager.video.width = 1280
        manager.encoding.block_size = 4
        manager.logging.level = "DEBUG"
        
        # Reset to defaults
        manager.reset_to_defaults()
        
        # Verify defaults are restored
        assert manager.video.width == 1920
        assert manager.encoding.block_size == 2
        assert manager.logging.level == "INFO"
    
    def test_export_template(self, temp_dir):
        """Test exporting configuration template."""
        config_file = temp_dir / "test_config.json"
        manager = ConfigManager(str(config_file))
        
        template_file = temp_dir / "template.json"
        manager.export_template(str(template_file))
        
        # Verify template file exists and has expected structure
        assert template_file.exists()
        
        with open(template_file, 'r') as f:
            template_data = json.load(f)
        
        assert "_comment" in template_data
        assert "video" in template_data
        assert "encoding" in template_data
        assert "security" in template_data
        assert "logging" in template_data
        assert "performance" in template_data
    
    def test_get_effective_config(self, temp_dir):
        """Test getting effective configuration."""
        config_file = temp_dir / "test_config.json"
        manager = ConfigManager(str(config_file))
        
        effective_config = manager.get_effective_config()
        
        assert isinstance(effective_config, dict)
        assert "video" in effective_config
        assert "encoding" in effective_config
        assert "security" in effective_config
        assert "logging" in effective_config
        assert "performance" in effective_config
        
        # Verify structure
        assert isinstance(effective_config["video"], dict)
        assert "width" in effective_config["video"]
        assert "height" in effective_config["video"]
        assert "fps" in effective_config["video"]

if __name__ == "__main__":
    pytest.main([__file__])
