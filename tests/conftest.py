"""
Pytest configuration and fixtures for YotuDrive tests.
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import FileValidator, NamingConvention, YotuDriveException, ErrorCodes
from src.config_manager import ConfigManager
from src.advanced_logger import setup_logging

@pytest.fixture(scope="session")
def test_config():
    """Test configuration manager with temporary settings."""
    config = ConfigManager()
    config.logging.level = "DEBUG"
    config.logging.format = "text"
    config.security.max_file_size = 10 * 1024 * 1024  # 10MB for tests
    return config

@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)

@pytest.fixture(scope="function")
def test_file(temp_dir):
    """Create a test file with known content."""
    test_content = b"Hello, YotuDrive! This is test content." * 100
    test_file_path = temp_dir / "test_file.txt"
    test_file_path.write_bytes(test_content)
    return test_file_path

@pytest.fixture(scope="function")
def large_test_file(temp_dir):
    """Create a larger test file for performance testing."""
    test_content = b"A" * (1024 * 1024)  # 1MB
    test_file_path = temp_dir / "large_test_file.bin"
    test_file_path.write_bytes(test_content)
    return test_file_path

@pytest.fixture(scope="function")
def setup_logging():
    """Setup logging for tests."""
    log_file = setup_logging(console=False, level="DEBUG")
    yield log_file

@pytest.fixture
def sample_frames_dir(temp_dir):
    """Create a sample frames directory with dummy PNG files."""
    frames_dir = temp_dir / "frames"
    frames_dir.mkdir()
    
    # Create dummy frame files
    for i in range(10):
        frame_file = frames_dir / f"frame_{i:08d}.png"
        # Create minimal PNG header (1x1 black pixel)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        frame_file.write_bytes(png_data)
    
    return frames_dir

@pytest.fixture
def mock_youtube_video():
    """Mock YouTube video information."""
    return {
        'id': 'dQw4w9WgXcQ',
        'title': 'Test Video',
        'duration': 180,
        'uploader': 'Test Channel'
    }

class MockProgressCallback:
    """Mock progress callback for testing."""
    
    def __init__(self):
        self.calls = []
    
    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
    
    def assert_called(self):
        assert len(self.calls) > 0, "Progress callback was not called"
    
    def assert_call_count(self, count):
        assert len(self.calls) == count, f"Expected {count} calls, got {len(self.calls)}"

@pytest.fixture
def mock_progress():
    """Mock progress callback fixture."""
    return MockProgressCallback()

# Test data generators
def generate_test_data(size: int = 1024) -> bytes:
    """Generate test data of specified size."""
    import random
    return bytes([random.randint(0, 255) for _ in range(size)])

def create_test_files(temp_dir: Path, count: int = 5, size: int = 1024) -> list:
    """Create multiple test files."""
    files = []
    for i in range(count):
        test_file = temp_dir / f"test_file_{i:03d}.bin"
        test_file.write_bytes(generate_test_data(size))
        files.append(test_file)
    return files

# Custom markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-related"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )

# Skip conditions
def skip_if_no_internet():
    """Skip test if no internet connection."""
    try:
        import urllib.request
        urllib.request.urlopen('http://www.google.com', timeout=5)
        return False
    except:
        return True

def skip_if_windows():
    """Skip test on Windows."""
    return sys.platform.startswith('win')

def skip_if_not_windows():
    """Skip test on non-Windows systems."""
    return not sys.platform.startswith('win')
