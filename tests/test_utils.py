"""
Test utility functions and validation.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.utils import (
    FileValidator, NamingConvention, YotuDriveException, ErrorCodes,
    ValidationError, format_file_size, ensure_directory_exists, safe_file_operation
)

class TestFileValidator:
    """Test file validation functionality."""
    
    def test_validate_existing_file(self, test_file):
        """Test validation of existing file."""
        file_path, file_size = FileValidator.validate_file(str(test_file))
        assert file_path == str(test_file)
        assert file_size == len(test_file.read_bytes())
    
    def test_validate_nonexistent_file(self, temp_dir):
        """Test validation of nonexistent file."""
        nonexistent = temp_dir / "nonexistent.txt"
        with pytest.raises(ValidationError, match="File does not exist"):
            FileValidator.validate_file(str(nonexistent))
    
    def test_validate_directory_instead_of_file(self, temp_dir):
        """Test validation when path is directory."""
        with pytest.raises(ValidationError, match="Path is not a file"):
            FileValidator.validate_file(str(temp_dir))
    
    def test_validate_empty_file(self, temp_dir):
        """Test validation of empty file."""
        empty_file = temp_dir / "empty.txt"
        empty_file.write_bytes(b"")
        with pytest.raises(ValidationError, match="File is empty"):
            FileValidator.validate_file(str(empty_file))
    
    def test_validate_file_too_large(self, temp_dir):
        """Test validation of file that's too large."""
        large_file = temp_dir / "large.txt"
        large_file.write_bytes(b"x" * 200)  # Larger than our test max size
        
        with pytest.raises(ValidationError, match="File too large"):
            FileValidator.validate_file(str(large_file), max_size=100)
    
    def test_validate_dangerous_filename(self, temp_dir):
        """Test validation of dangerous filenames."""
        dangerous_files = [
            "con.txt", "prn.doc", "aux.exe", "nul.bin",
            "com1.txt", "lpt2.doc", "script.bat", "malware.exe"
        ]
        
        for dangerous in dangerous_files:
            dangerous_file = temp_dir / dangerous
            dangerous_file.write_bytes(b"test content")
            
            with pytest.raises(ValidationError, match="dangerous pattern"):
                FileValidator.validate_file(str(dangerous_file))
    
    def test_validate_allowed_extensions(self, test_file):
        """Test validation of allowed file extensions."""
        # Should work with allowed extensions
        allowed_files = [
            "test.txt", "document.pdf", "image.jpg", "video.mp4",
            "archive.zip", "program.exe", "data.bin"
        ]
        
        for filename in allowed_files:
            test_file_path = test_file.parent / filename
            test_file_path.write_bytes(b"test content")
            file_path, file_size = FileValidator.validate_file(str(test_file_path))
            assert file_path == str(test_file_path)
    
    def test_validate_disallowed_extension(self, temp_dir):
        """Test validation of disallowed file extensions."""
        disallowed_file = temp_dir / "test.suspicious"
        disallowed_file.write_bytes(b"test content")
        
        with pytest.raises(ValidationError, match="File type not allowed"):
            FileValidator.validate_file(str(disallowed_file))
    
    def test_sanitize_path(self, temp_dir):
        """Test path sanitization."""
        # Normal path
        normal_path = temp_dir / "normal.txt"
        sanitized = FileValidator.sanitize_path(str(normal_path))
        assert sanitized == str(normal_path.resolve())
        
        # Path traversal attempt
        with pytest.raises(ValidationError, match="Directory traversal"):
            FileValidator.sanitize_path("../../../etc/passwd")
        
        # Empty path
        with pytest.raises(ValidationError, match="File path cannot be empty"):
            FileValidator.sanitize_path("")
    
    def test_validate_directory(self, temp_dir):
        """Test directory validation."""
        # Existing directory
        validated = FileValidator.validate_directory(str(temp_dir))
        assert validated == str(temp_dir)
        
        # Nonexistent directory (should be created)
        new_dir = temp_dir / "new_directory"
        validated = FileValidator.validate_directory(str(new_dir))
        assert os.path.exists(new_dir)
        assert validated == str(new_dir)
        
        # File instead of directory
        file_path = temp_dir / "not_a_dir.txt"
        file_path.write_bytes(b"content")
        
        with pytest.raises(ValidationError, match="Path is not a directory"):
            FileValidator.validate_directory(str(file_path))

class TestNamingConvention:
    """Test naming convention functionality."""
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        test_cases = [
            ("normal_file.txt", "normal_file.txt"),
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("file<>with|special?chars*.txt", "file_with_special_chars_.txt"),
            ("file:with\"quotes.txt", "file_with'quotes.txt"),
            ("file/with\\slashes.txt", "file_with_slashes.txt"),
            (".hidden_file", "file_hidden_file"),
            ("", "unnamed"),
            ("a" * 250 + ".txt", "a" * 200 + ".txt"),  # Long filename truncation
        ]
        
        for input_name, expected in test_cases:
            result = NamingConvention.sanitize_filename(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}"
    
    def test_generate_video_name(self):
        """Test video name generation."""
        video_name = NamingConvention.generate_video_name("test_file.txt", 1234567890)
        
        assert video_name.endswith(".mp4")
        assert "test_file" in video_name
        assert "1234567890" in video_name
        assert len(video_name.split("_")) >= 3  # Should have multiple parts
    
    def test_generate_frames_dir_name(self, temp_dir):
        """Test frames directory name generation."""
        frames_dir = NamingConvention.generate_frames_dir_name(str(temp_dir), "test_file.txt")
        
        assert "frames_test_file" in frames_dir
        assert str(temp_dir) in frames_dir
        assert frames_dir.startswith(str(temp_dir))
    
    def test_generate_restored_filename(self):
        """Test restored filename generation."""
        restored = NamingConvention.generate_restored_filename("original.txt", "restored")
        assert restored == "original_restored.txt"
        
        restored = NamingConvention.generate_restored_filename("document.pdf")
        assert restored == "document_restored.pdf"

class TestErrorHandling:
    """Test error handling and exceptions."""
    
    def test_yotudrive_exception(self):
        """Test YotuDriveException functionality."""
        original_error = ValueError("Original error")
        exception = YotuDriveException("Test message", ErrorCodes.FILE_NOT_FOUND, original_error)
        
        assert str(exception) == "Test message"
        assert exception.error_code == ErrorCodes.FILE_NOT_FOUND
        assert exception.original_error == original_error
        assert exception.timestamp > 0
        
        # Test to_dict conversion
        exception_dict = exception.to_dict()
        assert exception_dict['error_type'] == 'YotuDriveException'
        assert exception_dict['message'] == 'Test message'
        assert exception_dict['error_code'] == ErrorCodes.FILE_NOT_FOUND
        assert 'timestamp' in exception_dict
    
    def test_error_codes(self):
        """Test error code constants."""
        assert ErrorCodes.FILE_NOT_FOUND == 1001
        assert ErrorCodes.ENCODING_FAILED == 1201
        assert ErrorCodes.YOUTUBE_API_ERROR == 1301

class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_format_file_size(self):
        """Test file size formatting."""
        test_cases = [
            (0, "0 B"),
            (512, "512.0 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
            (1024 * 1024 * 1024 * 1024, "1.0 TB"),
        ]
        
        for size_bytes, expected in test_cases:
            result = format_file_size(size_bytes)
            assert result == expected, f"Failed for {size_bytes}: got {result}, expected {expected}"
    
    def test_ensure_directory_exists(self, temp_dir):
        """Test directory creation utility."""
        new_dir = temp_dir / "new_subdir"
        
        # Create new directory
        result = ensure_directory_exists(str(new_dir))
        assert os.path.exists(new_dir)
        assert result == str(new_dir)
        
        # Existing directory should work fine
        result = ensure_directory_exists(str(new_dir))
        assert result == str(new_dir)
    
    def test_safe_file_operation_success(self, test_file):
        """Test safe file operation with success."""
        def read_operation(file_path):
            with open(file_path, 'r') as f:
                return f.read()
        
        result = safe_file_operation(read_operation, str(test_file))
        assert result == test_file.read_text()
    
    def test_safe_file_operation_failure(self, temp_dir):
        """Test safe file operation with failure."""
        def failing_operation(file_path):
            raise OSError("Permission denied")
        
        with pytest.raises(YotuDriveException, match="File operation failed"):
            safe_file_operation(failing_operation, str(temp_dir / "nonexistent.txt"))

class TestSecurityValidation:
    """Test security-related validation."""
    
    @pytest.mark.security
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "file/../../../etc/passwd",
            "normal\\..\\..\\dangerous"
        ]
        
        for dangerous_path in dangerous_paths:
            with pytest.raises(ValidationError):
                FileValidator.sanitize_path(dangerous_path)
    
    @pytest.mark.security
    def test_file_extension_filtering(self, temp_dir):
        """Test file extension security filtering."""
        # Test with potentially dangerous extensions
        dangerous_extensions = [
            ".scr", ".vbs", ".js", ".jar", ".app", ".com", ".bat", ".cmd"
        ]
        
        for ext in dangerous_extensions:
            dangerous_file = temp_dir / f"test{ext}"
            dangerous_file.write_bytes(b"test content")
            
            with pytest.raises(ValidationError, match="File type not allowed"):
                FileValidator.validate_file(str(dangerous_file))
    
    @pytest.mark.security
    def test_filename_injection_prevention(self):
        """Test prevention of filename injection attacks."""
        dangerous_names = [
            "file$(whoami).txt",
            "file`whoami`.txt",
            "file;rm -rf /.txt",
            "file|cat /etc/passwd.txt",
            "file&&echo hack.txt",
            "file||echo hack.txt"
        ]
        
        for dangerous_name in dangerous_names:
            sanitized = NamingConvention.sanitize_filename(dangerous_name)
            # Ensure dangerous characters are removed or replaced
            assert "$" not in sanitized
            assert "`" not in sanitized
            assert ";" not in sanitized
            assert "|" not in sanitized
            assert "&" not in sanitized

if __name__ == "__main__":
    pytest.main([__file__])
