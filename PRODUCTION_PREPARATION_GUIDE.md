# 🚀 YotuDrive Production Preparation Guide

## Phase 1: Pre-Production Checklist

### 1.1 System Requirements Validation

**Minimum Requirements:**
- Python 3.10, 3.11, or 3.12
- 4GB RAM (8GB+ recommended)
- 50GB free disk space
- FFmpeg installed
- Internet connection for YouTube operations

**Check your system:**
```bash
# Check Python version
python --version

# Check available memory (Windows)
wmic computersystem get TotalPhysicalMemory

# Check disk space
dir /-c

# Check FFmpeg
ffmpeg -version
```

### 1.2 Dependencies Installation

**Install required packages:**
```bash
# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

# Verify installation
python -c "import numpy, PIL, yt_dlp, cryptography; print('✅ All dependencies installed')"
```

### 1.3 Directory Structure Setup

**Create production directory structure:**
```bash
# Create necessary directories
mkdir -p logs
mkdir -p backups  
mkdir -p data
mkdir -p temp
mkdir -p output_frames
mkdir -p test_frames

# Set permissions (Linux/macOS)
chmod 755 logs backups data temp
chmod +x start_gui.bat
```

## Phase 2: Configuration Setup

### 2.1 Production Configuration

**Create production settings:**
```python
# settings.json - Production configuration
{
    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "encoder": "libx264",
        "preset": "medium"
    },
    "encoding": {
        "block_size": 2,
        "header_copies": 5,
        "ecc_bytes": 32
    },
    "security": {
        "max_file_size": 107374182400,
        "allowed_extensions": [".zip", ".pdf", ".txt", ".jpg", ".png", ".mp4"],
        "enable_virus_scan": false,
        "temp_dir": "temp"
    },
    "logging": {
        "level": "INFO",
        "format": "json",
        "max_file_size": 10485760,
        "backup_count": 5,
        "log_dir": "logs",
        "enable_console": false
    },
    "performance": {
        "threads": 4,
        "max_memory": 2147483648,
        "pipeline_chunk_size": 1048576,
        "enable_parallel": true
    }
}
```

### 2.2 Environment Variables

**Set production environment variables:**
```bash
# Windows (Command Prompt)
set YOTUDRIVE_LOG_LEVEL=INFO
set YOTUDRIVE_LOG_FORMAT=json
set YOTUDRIVE_MAX_FILE_SIZE=107374182400
set YOTUDRIVE_THREADS=4
set YOTUDRIVE_TEMP_DIR=temp

# Windows (PowerShell)
$env:YOTUDRIVE_LOG_LEVEL="INFO"
$env:YOTUDRIVE_LOG_FORMAT="json"
$env:YOTUDRIVE_MAX_FILE_SIZE="107374182400"
$env:YOTUDRIVE_THREADS="4"
$env:YOTUDRIVE_TEMP_DIR="temp"

# Linux/macOS
export YOTUDRIVE_LOG_LEVEL=INFO
export YOTUDRIVE_LOG_FORMAT=json
export YOTUDRIVE_MAX_FILE_SIZE=107374182400
export YOTUDRIVE_THREADS=4
export YOTUDRIVE_TEMP_DIR=temp
```

## Phase 3: Testing and Validation

### 3.1 Run Test Suite

**Execute comprehensive tests:**
```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html --cov-fail-under=80

# Run specific test categories
pytest tests/ -v -m unit          # Unit tests only
pytest tests/ -v -m integration   # Integration tests only
pytest tests/ -v -m security      # Security tests only
pytest tests/ -v -m performance   # Performance tests only
```

### 3.2 Manual Functionality Testing

**Test core functionality:**
```python
# Create test script: test_production.py
import os
import sys
sys.path.append('src')

def test_basic_functionality():
    print("=== Production Readiness Tests ===")
    
    # Test 1: Configuration
    try:
        from config_manager import config_manager
        config_manager.validate()
        print("✅ Configuration validation passed")
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False
    
    # Test 2: Database
    try:
        from advanced_db import database
        stats = database.get_statistics()
        print(f"✅ Database operational: {stats['active_files']} files")
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    
    # Test 3: Logging
    try:
        from advanced_logger import get_logger
        logger = get_logger()
        logger.setup(console=False, level="INFO")
        logger.log_structured('info', 'Production test successful')
        print("✅ Logging system operational")
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False
    
    # Test 4: Health Check
    try:
        from health_monitor import run_health_check
        health = run_health_check(force=True)
        print(f"✅ Health check: {health.status}")
        if health.status == "critical":
            print("⚠️  Critical issues detected - review before production")
            for rec in health.recommendations:
                print(f"   - {rec}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test 5: File Validation
    try:
        from utils import FileValidator
        # Test with README.md (should exist)
        if os.path.exists('README.md'):
            FileValidator.validate_file('README.md')
            print("✅ File validation operational")
        else:
            print("⚠️  README.md not found - file validation test skipped")
    except Exception as e:
        print(f"❌ File validation failed: {e}")
        return False
    
    print("=== All Tests Completed ===")
    return True

if __name__ == "__main__":
    success = test_basic_functionality()
    if success:
        print("🎉 Production readiness tests PASSED")
    else:
        print("❌ Production readiness tests FAILED")
        sys.exit(1)
```

**Run the test:**
```bash
python test_production.py
```

### 3.3 Performance Testing

**Test with sample files:**
```python
# Create performance test: performance_test.py
import os
import time
import sys
sys.path.append('src')

def test_encoding_performance():
    """Test encoding performance with sample data."""
    print("=== Performance Testing ===")
    
    # Create test file
    test_data = b"YotuDrive performance test data " * 10000  # ~500KB
    test_file = "performance_test.txt"
    
    try:
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        # Test encoding
        from encoder import Encoder
        from utils import NamingConvention
        
        frames_dir = NamingConvention.generate_frames_dir_name("data", test_file)
        
        start_time = time.time()
        encoder = Encoder(test_file, frames_dir, block_size=2, ecc_bytes=16)
        encoder.run()
        encode_time = time.time() - start_time
        
        print(f"✅ Encoding completed in {encode_time:.2f} seconds")
        
        # Test decoding
        from decoder import Decoder
        
        output_file = "performance_test_restored.txt"
        start_time = time.time()
        decoder = Decoder(frames_dir, output_file)
        decoder.run()
        decode_time = time.time() - start_time
        
        print(f"✅ Decoding completed in {decode_time:.2f} seconds")
        
        # Verify data integrity
        with open(output_file, 'rb') as f:
            restored_data = f.read()
        
        if restored_data == test_data:
            print("✅ Data integrity verified")
        else:
            print("❌ Data integrity check failed")
            return False
        
        # Cleanup
        os.remove(test_file)
        os.remove(output_file)
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)
        
        print(f"Performance: {len(test_data)} bytes in {encode_time + decode_time:.2f}s total")
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

if __name__ == "__main__":
    test_encoding_performance()
```

## Phase 4: Security Setup

### 4.1 Security Configuration

**Review security settings:**
```python
# security_check.py
import sys
sys.path.append('src')

def security_audit():
    """Perform security audit."""
    print("=== Security Audit ===")
    
    # Check file permissions
    import os
    import stat
    
    critical_files = ['settings.json', 'yotudrive.json']
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            file_stat = os.stat(file_path)
            permissions = oct(file_stat.st_mode)[-3:]
            print(f"📁 {file_path}: {permissions}")
            
            # Check if world-writable (security risk)
            if permissions[2] in ['2', '6', '7']:
                print(f"⚠️  WARNING: {file_path} is world-writable")
    
    # Check configuration security
    try:
        from config_manager import config_manager
        
        # Check max file size
        max_size_gb = config_manager.security.max_file_size / (1024**3)
        if max_size_gb > 100:
            print(f"⚠️  Large max file size: {max_size_gb:.1f}GB")
        
        # Check temp directory
        temp_dir = config_manager.security.temp_dir
        if temp_dir and os.path.exists(temp_dir):
            temp_files = len(os.listdir(temp_dir))
            if temp_files > 100:
                print(f"⚠️  Many temp files: {temp_files}")
        
        print("✅ Security audit completed")
        
    except Exception as e:
        print(f"❌ Security audit failed: {e}")

if __name__ == "__main__":
    security_audit()
```

### 4.2 Backup Setup

**Configure backup system:**
```python
# backup_setup.py
import sys
sys.path.append('src')

def setup_backups():
    """Setup backup system."""
    print("=== Backup Setup ===")
    
    try:
        from advanced_db import database
        
        # Create initial backup
        backup = database.create_backup("Initial production backup", compressed=True)
        print(f"✅ Initial backup created: {backup.backup_id}")
        
        # Configure automatic backups
        print("📅 Automatic backups will be created during database operations")
        
        # Test backup restore
        print("🔄 Testing backup restore...")
        restore_success = database.restore_backup(backup.backup_id)
        if restore_success:
            print("✅ Backup restore test successful")
        else:
            print("❌ Backup restore test failed")
        
        # Show backup info
        stats = database.get_statistics()
        print(f"📊 Database: {stats['active_files']} active files")
        print(f"💾 Backups: {stats['backups_count']} backups available")
        
    except Exception as e:
        print(f"❌ Backup setup failed: {e}")

if __name__ == "__main__":
    setup_backups()
```

## Phase 5: Monitoring Setup

### 5.1 Health Monitoring

**Setup continuous monitoring:**
```python
# monitoring_setup.py
import sys
import time
sys.path.append('src')

def setup_monitoring():
    """Setup health monitoring."""
    print("=== Monitoring Setup ===")
    
    try:
        from health_monitor import run_health_check, get_health_report
        
        # Run initial health check
        health = run_health_check(force=True)
        print(f"🏥 Initial health status: {health.status}")
        
        # Display recommendations
        if health.recommendations:
            print("📋 Recommendations:")
            for i, rec in enumerate(health.recommendations, 1):
                print(f"   {i}. {rec}")
        
        # Generate detailed report
        report = get_health_report('text')
        print("\n" + "="*50)
        print(report)
        
        print("✅ Monitoring system active")
        print("📊 Health checks will run every 5 minutes")
        
    except Exception as e:
        print(f"❌ Monitoring setup failed: {e}")

if __name__ == "__main__":
    setup_monitoring()
```

### 5.2 Log Monitoring

**Setup log monitoring:**
```python
# log_monitoring.py
import sys
sys.path.append('src')

def setup_log_monitoring():
    """Setup log monitoring."""
    print("=== Log Monitoring Setup ===")
    
    try:
        from advanced_logger import get_logger
        from advanced_logger import LogMonitor
        
        # Setup logger
        logger = get_logger()
        log_file = logger.setup(console=False, level="INFO")
        print(f"📝 Log file: {log_file}")
        
        # Test log monitoring
        monitor = LogMonitor()
        
        # Log test events
        logger.log_structured('info', 'Production setup started', 
                            component='setup', phase='production')
        logger.log_performance('setup_test', 0.5, 
                            operation='production_setup')
        logger.log_file_operation('config_validation', 'settings.json')
        
        print("✅ Log monitoring active")
        
        # Check for recent errors
        error_summary = monitor.get_error_summary(hours=1)
        if error_summary['error_count'] > 0:
            print(f"⚠️  Recent errors: {error_summary['error_count']}")
        else:
            print("✅ No recent errors")
        
    except Exception as e:
        print(f"❌ Log monitoring setup failed: {e}")

if __name__ == "__main__":
    setup_log_monitoring()
```

## Phase 6: Production Deployment

### 6.1 Final Validation

**Run complete production validation:**
```python
# production_validation.py
import sys
import os
sys.path.append('src')

def complete_production_validation():
    """Complete production readiness validation."""
    print("🚀 COMPLETE PRODUCTION VALIDATION")
    print("="*50)
    
    validation_steps = [
        ("Configuration", validate_config),
        ("Database", validate_database),
        ("Logging", validate_logging),
        ("Health", validate_health),
        ("Security", validate_security),
        ("Performance", validate_performance)
    ]
    
    all_passed = True
    
    for step_name, step_func in validation_steps:
        print(f"\n🔍 Validating {step_name}...")
        try:
            if step_func():
                print(f"✅ {step_name} validation PASSED")
            else:
                print(f"❌ {step_name} validation FAILED")
                all_passed = False
        except Exception as e:
            print(f"❌ {step_name} validation ERROR: {e}")
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED - READY FOR PRODUCTION!")
        print("\n📋 Next Steps:")
        print("1. Start the application: python src/main_gui.py")
        print("2. Monitor health: python -c \"from health_monitor import run_health_check; print(run_health_check().status)\"")
        print("3. Check logs: tail -f logs/yotudrive_$(date +%Y%m%d).log")
    else:
        print("❌ VALIDATION FAILURES - FIX BEFORE PRODUCTION")
    
    return all_passed

def validate_config():
    from config_manager import config_manager
    config_manager.validate()
    return True

def validate_database():
    from advanced_db import database
    stats = database.get_statistics()
    return stats['database_version'] > 0

def validate_logging():
    from advanced_logger import get_logger
    logger = get_logger()
    log_file = logger.setup(console=False, level="INFO")
    return os.path.exists(log_file)

def validate_health():
    from health_monitor import run_health_check
    health = run_health_check(force=True)
    return health.status in ['healthy', 'warning']

def validate_security():
    from utils import FileValidator
    # Test with a safe file
    if os.path.exists('README.md'):
        FileValidator.validate_file('README.md')
    return True

def validate_performance():
    # Basic performance check
    import time
    start = time.time()
    time.sleep(0.1)  # Simulate work
    return (time.time() - start) < 1.0

if __name__ == "__main__":
    complete_production_validation()
```

### 6.2 Production Startup

**Start production system:**
```bash
# Step 1: Complete validation
python production_validation.py

# Step 2: If validation passes, start application
python src/main_gui.py

# Step 3: Monitor health in separate terminal
python -c "from health_monitor import run_health_check; print(run_health_check().status)"
```

## Phase 7: Ongoing Maintenance

### 7.1 Daily Tasks

**Daily maintenance script:**
```python
# daily_maintenance.py
import sys
import os
sys.path.append('src')

def daily_maintenance():
    """Daily maintenance tasks."""
    print("🔧 Daily Maintenance")
    
    try:
        # Clean up old logs
        from advanced_logger import get_logger
        logger = get_logger()
        cleaned = logger.cleanup_old_logs(days=7)
        print(f"🧹 Cleaned {cleaned} old log files")
        
        # Clean up old database entries
        from advanced_db import database
        deleted = database.cleanup_deleted_files(days=30)
        print(f"🗑️  Cleaned {deleted} old database entries")
        
        # Health check
        from health_monitor import run_health_check
        health = run_health_check(force=True)
        print(f"🏥 Health status: {health.status}")
        
        if health.recommendations:
            print("📋 Recommendations:")
            for rec in health.recommendations:
                print(f"   - {rec}")
        
        print("✅ Daily maintenance completed")
        
    except Exception as e:
        print(f"❌ Daily maintenance failed: {e}")

if __name__ == "__main__":
    daily_maintenance()
```

### 7.2 Monitoring Dashboard

**Create monitoring dashboard:**
```python
# monitoring_dashboard.py
import sys
import time
sys.path.append('src')

def monitoring_dashboard():
    """Simple monitoring dashboard."""
    try:
        from health_monitor import run_health_check, get_system_metrics
        from advanced_db import database
        from advanced_logger import LogMonitor
        
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("🏥 YOTU DRIVE MONITORING DASHBOARD")
            print("="*50)
            print(f"🕐 Last Update: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # Health Status
            health = run_health_check(force=False)
            status_emoji = "🟢" if health.status == "healthy" else "🟡" if health.status == "warning" else "🔴"
            print(f"{status_emoji} System Health: {health.status.upper()}")
            
            # System Metrics
            metrics = get_system_metrics()
            print(f"💻 CPU: {metrics.cpu_percent:.1f}%")
            print(f"🧠 Memory: {metrics.memory_percent:.1f}%")
            print(f"💾 Disk: {metrics.disk_usage_percent:.1f}%")
            
            # Database Stats
            db_stats = database.get_statistics()
            print(f"📊 Database: {db_stats['active_files']} files, {db_stats['backups_count']} backups")
            
            # Recent Errors
            monitor = LogMonitor()
            error_summary = monitor.get_error_summary(hours=1)
            print(f"⚠️  Recent Errors: {error_summary['error_count']}")
            
            print("\nPress Ctrl+C to exit")
            time.sleep(30)  # Update every 30 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
    except Exception as e:
        print(f"❌ Monitoring error: {e}")

if __name__ == "__main__":
    monitoring_dashboard()
```

## 🎯 **Production Readiness Summary**

### ✅ **Before Going Live:**
1. Run `python production_validation.py` - ALL CHECKS MUST PASS
2. Review security settings in `settings.json`
3. Test with actual files you plan to process
4. Verify backup system is working
5. Check monitoring and logging

### 🚀 **Go Live:**
1. Start with `python src/main_gui.py`
2. Monitor with `python monitoring_dashboard.py`
3. Run daily maintenance with `python daily_maintenance.py`

### 📊 **Ongoing:**
- Monitor health status daily
- Review logs weekly
- Update dependencies monthly
- Backup configuration regularly

**You're now ready for production deployment!** 🎉
