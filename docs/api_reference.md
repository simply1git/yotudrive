# YotuDrive API Reference

This document provides comprehensive API documentation for YotuDrive's internal modules and functions.

## Table of Contents

- [Core Modules](#core-modules)
- [Configuration Management](#configuration-management)
- [Database Operations](#database-operations)
- [Logging System](#logging-system)
- [Health Monitoring](#health-monitoring)
- [Utility Functions](#utility-functions)
- [Error Handling](#error-handling)

## Core Modules

### Encoder (`src.encoder`)

The `Encoder` class handles converting files into video frames for YouTube storage.

#### Class: `Encoder`

```python
class Encoder:
    def __init__(self, input_file, output_dir, password=None, progress_callback=None, 
                 block_size=DEFAULT_BLOCK_SIZE, ecc_bytes=DEFAULT_ECC_BYTES, threads=None, check_cancel=None)
```

**Parameters:**
- `input_file` (str): Path to the file to encode
- `output_dir` (str): Directory where video frames will be saved
- `password` (str, optional): Password for encryption
- `progress_callback` (callable, optional): Progress callback function
- `block_size` (int): Size of each pixel block (default: 2)
- `ecc_bytes` (int): Error correction bytes (default: 32)
- `threads` (int, optional): Number of threads to use
- `check_cancel` (callable, optional): Cancellation check function

**Methods:**

##### `run() -> None`
Main encoding method that processes the input file and generates video frames.

**Example:**
```python
from src.encoder import Encoder

encoder = Encoder("input.zip", "frames/", block_size=4, ecc_bytes=16)
encoder.run()
```

### Decoder (`src.decoder`)

The `Decoder` class handles converting video frames back to original files.

#### Class: `Decoder`

```python
class Decoder:
    def __init__(self, input_dir, output_file, password=None, progress_callback=None, check_cancel=None)
```

**Parameters:**
- `input_dir` (str): Directory containing video frames
- `output_file` (str): Path for the restored file
- `password` (str, optional): Password for decryption
- `progress_callback` (callable, optional): Progress callback function
- `check_cancel` (callable, optional): Cancellation check function

**Methods:**

##### `run() -> None`
Main decoding method that processes video frames and restores the original file.

**Example:**
```python
from src.decoder import Decoder

decoder = Decoder("frames/", "restored.zip")
decoder.run()
```

## Configuration Management

### ConfigManager (`src.config_manager`)

Advanced configuration management with validation and environment variable support.

#### Class: `ConfigManager`

```python
class ConfigManager:
    def __init__(self, config_file: str = "settings.json")
```

**Configuration Sections:**

##### Video Configuration
```python
@dataclass
class VideoConfig:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    encoder: str = "libx264"
    preset: str = "medium"
```

##### Encoding Configuration
```python
@dataclass
class EncodingConfig:
    block_size: int = 2
    max_block_size: int = 15
    header_copies: int = 5
    ecc_bytes: int = 32
    rs_block_size: int = 255
```

##### Security Configuration
```python
@dataclass
class SecurityConfig:
    max_file_size: int = 100 * 1024 * 1024 * 1024  # 100GB
    allowed_extensions: list = [...]
    enable_virus_scan: bool = False
    temp_dir: Optional[str] = None
```

**Methods:**

##### `load() -> None`
Load configuration from file and environment variables.

##### `save() -> None`
Save current configuration to file.

##### `validate() -> None`
Validate all configuration sections.

##### `reset_to_defaults() -> None`
Reset all configurations to defaults.

**Example:**
```python
from src.config_manager import config_manager

# Access configuration
print(config_manager.video.width)
print(config_manager.encoding.block_size)

# Modify configuration
config_manager.video.width = 1280
config_manager.save()

# Validate configuration
config_manager.validate()
```

## Database Operations

### AdvancedDatabase (`src.advanced_db`)

Advanced database system with backup, migration, and transaction support.

#### Class: `AdvancedDatabase`

```python
class AdvancedDatabase:
    def __init__(self, db_path: str = "yotudrive.json", backup_dir: str = "backups")
```

**Data Structures:**

##### FileEntry
```python
@dataclass
class FileEntry:
    id: str
    file_name: str
    video_id: str
    file_size: int
    upload_date: float
    metadata: Dict[str, Any]
    checksum: Optional[str] = None
    tags: List[str] = None
    status: str = "active"
```

**Methods:**

##### `add_file(file_name, video_id, file_size, metadata=None, checksum=None, tags=None) -> str`
Add a new file entry.

##### `get_file(file_id: str) -> Optional[FileEntry]`
Get file entry by ID.

##### `find_files(**criteria) -> List[FileEntry]`
Find files matching criteria.

##### `update_file(file_id: str, **updates) -> bool`
Update file entry.

##### `delete_file(file_id: str, permanent: bool = False) -> bool`
Delete file entry (soft delete by default).

##### `list_files(include_deleted: bool = False) -> List[FileEntry]`
List all files.

##### `create_backup(description: str = None, compressed: bool = False) -> BackupInfo`
Create manual backup.

##### `restore_backup(backup_id: str) -> bool`
Restore from backup.

##### `get_statistics() -> Dict[str, Any]`
Get database statistics.

**Example:**
```python
from src.advanced_db import database

# Add file
file_id = database.add_file("test.zip", "dQw4w9WgXcQ", 1024000)

# Find files
files = database.find_files(file_name__contains="test")

# Get statistics
stats = database.get_statistics()
print(f"Total files: {stats['active_files']}")
```

## Logging System

### YotuDriveLogger (`src.advanced_logger`)

Advanced logging system with rotation and structured output.

#### Class: `YotuDriveLogger`

```python
class YotuDriveLogger:
    def __init__(self, name: str = "yotudrive")
```

**Methods:**

##### `setup(console: Optional[bool] = None, level: Optional[str] = None) -> str`
Setup logging with rotation and structured output.

##### `log_structured(level: str, message: str, **kwargs) -> None`
Log structured message with extra fields.

##### `log_exception(message: str, exception: Exception, **kwargs) -> None`
Log exception with structured data.

##### `log_performance(operation: str, duration: float, **kwargs) -> None`
Log performance metrics.

##### `log_file_operation(operation: str, file_path: str, file_size: Optional[int] = None, **kwargs) -> None`
Log file operation.

##### `log_security_event(event: str, details: Dict[str, Any], **kwargs) -> None`
Log security-related events.

**Example:**
```python
from src.advanced_logger import get_logger

logger = get_logger()

# Setup logging
log_file = logger.setup(console=True, level="INFO")

# Structured logging
logger.log_structured('info', 'File processed', 
                    file_path='test.zip', 
                    file_size=1024000,
                    operation='encode')

# Performance logging
logger.log_performance('encoding', 45.2, 
                      file_count=10, 
                      block_size=4)

# Exception logging
try:
    # Some operation
    pass
except Exception as e:
    logger.log_exception('Operation failed', e, operation='encoding')
```

## Health Monitoring

### HealthChecker (`src.health_monitor`)

Comprehensive health monitoring system.

#### Class: `HealthChecker`

```python
class HealthChecker:
    def __init__(self)
```

**Methods:**

##### `run_health_check(force: bool = False) -> HealthStatus`
Run comprehensive health check.

##### `get_health_report(format: str = 'json') -> str`
Get formatted health report.

##### `get_system_metrics() -> SystemMetrics`
Get current system metrics.

**Health Status Structure:**
```python
@dataclass
class HealthStatus:
    status: str  # healthy, warning, critical
    timestamp: float
    checks: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]
    recommendations: List[str]
```

**Example:**
```python
from src.health_monitor import run_health_check, get_health_report

# Run health check
health_status = run_health_check()
print(f"Status: {health_status.status}")

# Get formatted report
report = get_health_report('text')
print(report)
```

## Utility Functions

### FileValidator (`src.utils`)

File validation and sanitization utilities.

#### Methods:

##### `validate_file(file_path: str, max_size: Optional[int] = None) -> Tuple[str, int]`
Validate file exists, is accessible, and meets security criteria.

##### `sanitize_path(file_path: str) -> str`
Sanitize file path to prevent directory traversal attacks.

##### `validate_directory(dir_path: str) -> str`
Validate directory exists and is writable.

**Example:**
```python
from src.utils import FileValidator

# Validate file
file_path, file_size = FileValidator.validate_file("input.zip", max_size=100*1024*1024)

# Validate directory
frames_dir = FileValidator.validate_directory("frames/")
```

### NamingConvention (`src.utils`)

File naming convention utilities.

#### Methods:

##### `sanitize_filename(filename: str) -> str`
Sanitize filename for cross-platform compatibility.

##### `generate_video_name(input_filename: str, timestamp: Optional[int] = None) -> str`
Generate clean video filename from input filename.

##### `generate_frames_dir_name(base_dir: str, input_filename: str) -> str`
Generate clean frames directory name.

##### `generate_restored_filename(original_name: str, suffix: str = "restored") -> str`
Generate restored filename with proper suffix.

**Example:**
```python
from src.utils import NamingConvention

# Sanitize filename
clean_name = NamingConvention.sanitize_filename("file<>with|special?chars*.txt")

# Generate video name
video_name = NamingConvention.generate_video_name("test.zip")

# Generate frames directory
frames_dir = NamingConvention.generate_frames_dir_name("data/", "test.zip")
```

## Error Handling

### YotuDriveException (`src.utils`)

Base exception class with error codes.

#### Class: `YotuDriveException`

```python
class YotuDriveException(Exception):
    def __init__(self, message: str, error_code: int = 0, original_error: Optional[Exception] = None)
```

#### Error Codes

```python
class ErrorCodes:
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
```

**Example:**
```python
from src.utils import YotuDriveException, ErrorCodes

try:
    # Some operation
    pass
except Exception as e:
    raise YotuDriveException(
        "Encoding operation failed",
        ErrorCodes.ENCODING_FAILED,
        e
    )
```

## Environment Variables

YotuDrive supports the following environment variables for configuration:

### Video Settings
- `YOTUDRIVE_VIDEO_WIDTH`: Video width (default: 1920)
- `YOTUDRIVE_VIDEO_HEIGHT`: Video height (default: 1080)
- `YOTUDRIVE_VIDEO_FPS`: Video FPS (default: 30)
- `YOTUDRIVE_VIDEO_ENCODER`: Video encoder (default: libx264)
- `YOTUDRIVE_VIDEO_PRESET`: Video preset (default: medium)

### Encoding Settings
- `YOTUDRIVE_BLOCK_SIZE`: Block size (default: 2)
- `YOTUDRIVE_HEADER_COPIES`: Header copies (default: 5)
- `YOTUDRIVE_ECC_BYTES`: ECC bytes (default: 32)

### Security Settings
- `YOTUDRIVE_MAX_FILE_SIZE`: Maximum file size in bytes
- `YOTUDRIVE_ENABLE_VIRUS_SCAN`: Enable virus scan (true/false)
- `YOTUDRIVE_TEMP_DIR`: Temporary directory

### Logging Settings
- `YOTUDRIVE_LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `YOTUDRIVE_LOG_FORMAT`: Log format (json/text)
- `YOTUDRIVE_LOG_MAX_SIZE`: Maximum log file size in bytes
- `YOTUDRIVE_LOG_BACKUP_COUNT`: Number of log backups to keep
- `YOTUDRIVE_LOG_DIR`: Log directory
- `YOTUDRIVE_LOG_CONSOLE`: Enable console logging (true/false)

### Performance Settings
- `YOTUDRIVE_THREADS`: Number of threads
- `YOTUDRIVE_MAX_MEMORY`: Maximum memory usage in bytes
- `YOTUDRIVE_PIPELINE_CHUNK_SIZE`: Pipeline chunk size in bytes
- `YOTUDRIVE_ENABLE_PARALLEL`: Enable parallel processing (true/false)

## Usage Examples

### Basic Encoding and Decoding
```python
from src.encoder import Encoder
from src.decoder import Decoder
from src.utils import FileValidator, NamingConvention

# Validate input file
file_path, file_size = FileValidator.validate_file("input.zip")

# Encode file
encoder = Encoder(file_path, "frames/", block_size=4, ecc_bytes=16)
encoder.run()

# Decode file
decoder = Decoder("frames/", "restored.zip")
decoder.run()
```

### Configuration Management
```python
from src.config_manager import config_manager

# Load configuration
config_manager.load()

# Modify settings
config_manager.video.width = 1280
config_manager.encoding.block_size = 4
config_manager.logging.level = "DEBUG"

# Save and validate
config_manager.save()
config_manager.validate()
```

### Database Operations
```python
from src.advanced_db import database

# Add file entry
file_id = database.add_file(
    file_name="test.zip",
    video_id="dQw4w9WgXcQ",
    file_size=1024000,
    metadata={"category": "documents"},
    tags=["test", "sample"]
)

# Find files
files = database.find_files(tags__contains="test")

# Create backup
backup = database.create_backup("Manual backup", compressed=True)

# Get statistics
stats = database.get_statistics()
```

### Health Monitoring
```python
from src.health_monitor import run_health_check, get_health_report

# Run health check
health_status = run_health_check()

if health_status.status != "healthy":
    print("Health issues detected:")
    for recommendation in health_status.recommendations:
        print(f"- {recommendation}")

# Get detailed report
report = get_health_report('text')
print(report)
```

### Logging
```python
from src.advanced_logger import get_logger

logger = get_logger()
logger.setup(console=True, level="INFO")

# Structured logging
logger.log_structured('info', 'Processing file', 
                    file_path='test.zip', 
                    operation='encode')

# Performance logging
import time
start_time = time.time()
# ... operation ...
duration = time.time() - start_time
logger.log_performance('file_encoding', duration)
```

## Best Practices

1. **Always validate input files** using `FileValidator.validate_file()`
2. **Use structured logging** for better monitoring and debugging
3. **Handle exceptions properly** with specific error codes
4. **Run health checks** regularly to monitor system status
5. **Create backups** before major operations
6. **Use environment variables** for deployment-specific configuration
7. **Follow naming conventions** for consistent file and directory names
8. **Monitor performance** using the built-in performance logging
9. **Validate configuration** before starting operations
10. **Use proper error handling** with try-catch blocks and specific exceptions
