"""
Advanced logging system with rotation, structured output, and monitoring capabilities.
"""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .config_manager import config_manager
from .utils import YotuDriveException, ErrorCodes

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)

class TextFormatter(logging.Formatter):
    """Enhanced text formatter with color support for console."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors."""
        # Basic format
        log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        
        # Add color for console
        if self.use_color:
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            log_format = f'{color}%(asctime)s - %(levelname)s{reset} - %(name)s - %(message)s'
        
        formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

class YotuDriveLogger:
    """Advanced logger with rotation and structured output."""
    
    def __init__(self, name: str = "yotudrive"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_complete = False
    
    def setup(self, console: Optional[bool] = None, level: Optional[str] = None) -> str:
        """Setup logging with rotation and structured output."""
        if self._setup_complete:
            return self._get_log_file_path()
        
        # Get configuration
        log_config = config_manager.logging
        log_level = level or log_config.level
        enable_console = console if console is not None else log_config.enable_console
        
        # Set logger level
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create log directory
        log_dir = Path(log_config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file handler with rotation
        log_file = log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        if log_config.format == "json":
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=log_config.max_file_size,
                backupCount=log_config.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=log_config.max_file_size,
                backupCount=log_config.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        self.logger.addHandler(file_handler)
        
        # Setup console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            if log_config.format == "json":
                console_handler.setFormatter(JSONFormatter())
            else:
                console_handler.setFormatter(TextFormatter())
            
            # Set console level to INFO or higher (less verbose)
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)
        
        # Log startup message
        self.logger.info("=== YotuDrive Session Started ===")
        self.logger.info(f"Log level: {log_level}")
        self.logger.info(f"Log format: {log_config.format}")
        self.logger.info(f"Log file: {log_file}")
        
        self._setup_complete = True
        return str(log_file)
    
    def _get_log_file_path(self) -> str:
        """Get current log file path."""
        for handler in self.logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                return handler.baseFilename
        return ""
    
    def log_structured(self, level: str, message: str, **kwargs) -> None:
        """Log structured message with extra fields."""
        log_method = getattr(self.logger, level.lower())
        log_method(message, extra=kwargs)
    
    def log_exception(self, message: str, exception: Exception, **kwargs) -> None:
        """Log exception with structured data."""
        if isinstance(exception, YotuDriveException):
            self.log_structured('error', message, 
                              error_code=exception.error_code,
                              exception_type=exception.__class__.__name__,
                              exception_message=str(exception),
                              **kwargs)
        else:
            self.log_structured('error', message,
                              exception_type=exception.__class__.__name__,
                              exception_message=str(exception),
                              **kwargs)
        self.logger.exception(message)
    
    def log_performance(self, operation: str, duration: float, **kwargs) -> None:
        """Log performance metrics."""
        self.log_structured('info', f"Performance: {operation}",
                          operation=operation,
                          duration_seconds=duration,
                          **kwargs)
    
    def log_file_operation(self, operation: str, file_path: str, 
                          file_size: Optional[int] = None, **kwargs) -> None:
        """Log file operation."""
        self.log_structured('info', f"File operation: {operation}",
                          operation=operation,
                          file_path=file_path,
                          file_size=file_size,
                          **kwargs)
    
    def log_security_event(self, event: str, details: Dict[str, Any], **kwargs) -> None:
        """Log security-related events."""
        self.log_structured('warning', f"Security event: {event}",
                          security_event=event,
                          details=details,
                          **kwargs)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        stats = {
            'logger_name': self.name,
            'handlers': len(self.logger.handlers),
            'level': self.logger.level,
            'effective_level': self.logger.getEffectiveLevel()
        }
        
        # Add file handler stats
        for handler in self.logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                stats['file_handler'] = {
                    'base_filename': handler.baseFilename,
                    'max_bytes': handler.maxBytes,
                    'backup_count': handler.backupCount,
                    'current_size': os.path.getsize(handler.baseFilename) if os.path.exists(handler.baseFilename) else 0
                }
                break
        
        return stats
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """Clean up old log files."""
        log_dir = Path(config_manager.logging.log_dir)
        if not log_dir.exists():
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        cleaned_count = 0
        
        for log_file in log_dir.glob(f"{self.name}_*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    cleaned_count += 1
                    self.logger.info(f"Cleaned up old log file: {log_file}")
                except OSError as e:
                    self.logger.error(f"Failed to clean up log file {log_file}: {e}")
        
        return cleaned_count

class LogMonitor:
    """Monitor and analyze log files."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of errors in the last N hours."""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        error_count = 0
        error_types = {}
        recent_errors = []
        
        for log_file in self.log_dir.glob("yotudrive_*.log"):
            if not log_file.exists():
                continue
                
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            if log_file.suffix == '.log' and line.strip().startswith('{'):
                                # JSON log
                                log_entry = json.loads(line)
                                entry_time = datetime.fromisoformat(log_entry['timestamp']).timestamp()
                                if entry_time >= cutoff_time and log_entry['level'] in ['ERROR', 'CRITICAL']:
                                    error_count += 1
                                    error_type = log_entry.get('exception_type', 'Unknown')
                                    error_types[error_type] = error_types.get(error_type, 0) + 1
                                    recent_errors.append(log_entry)
                            else:
                                # Text log
                                if 'ERROR' in line or 'CRITICAL' in line:
                                    error_count += 1
                                    recent_errors.append({'message': line.strip()})
                        except (json.JSONDecodeError, KeyError):
                            continue
            except OSError:
                continue
        
        return {
            'error_count': error_count,
            'error_types': error_types,
            'recent_errors': recent_errors[-10:],  # Last 10 errors
            'time_period_hours': hours
        }
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Extract performance metrics from logs."""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        operations = []
        
        for log_file in self.log_dir.glob("yotudrive_*.log"):
            if not log_file.exists():
                continue
                
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            if line.strip().startswith('{'):
                                log_entry = json.loads(line)
                                entry_time = datetime.fromisoformat(log_entry['timestamp']).timestamp()
                                if entry_time >= cutoff_time and 'operation' in log_entry and 'duration_seconds' in log_entry:
                                    operations.append({
                                        'operation': log_entry['operation'],
                                        'duration': log_entry['duration_seconds'],
                                        'timestamp': log_entry['timestamp']
                                    })
                        except (json.JSONDecodeError, KeyError):
                            continue
            except OSError:
                continue
        
        # Calculate statistics
        if operations:
            operation_stats = {}
            for op in operations:
                op_name = op['operation']
                if op_name not in operation_stats:
                    operation_stats[op_name] = []
                operation_stats[op_name].append(op['duration'])
            
            for op_name in operation_stats:
                durations = operation_stats[op_name]
                operation_stats[op_name] = {
                    'count': len(durations),
                    'avg_duration': sum(durations) / len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations)
                }
        else:
            operation_stats = {}
        
        return {
            'total_operations': len(operations),
            'operation_stats': operation_stats,
            'time_period_hours': hours
        }

# Global logger instance
yotudrive_logger = YotuDriveLogger()

def setup_logging(console: Optional[bool] = None, level: Optional[str] = None) -> str:
    """Setup logging system."""
    return yotudrive_logger.setup(console=console, level=level)

def get_logger(name: str = "yotudrive") -> YotuDriveLogger:
    """Get logger instance."""
    if name != "yotudrive":
        return YotuDriveLogger(name)
    return yotudrive_logger
