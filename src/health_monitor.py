"""
Health monitoring and system checks for YotuDrive.
"""

import os
import sys
import psutil
import time
import json
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .config_manager import config_manager
from .advanced_logger import get_logger, LogMonitor
from .advanced_db import database
from .utils import YotuDriveException, ErrorCodes, format_file_size

logger = get_logger()

@dataclass
class HealthStatus:
    """Health status data structure."""
    status: str  # healthy, warning, critical
    timestamp: float
    checks: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]
    recommendations: List[str]

@dataclass
class SystemMetrics:
    """System metrics data structure."""
    cpu_percent: float
    memory_percent: float
    memory_available: int
    disk_usage_percent: float
    disk_free: int
    network_io: Dict[str, int]
    process_count: int
    uptime: float

class HealthChecker:
    """Main health checking system."""
    
    def __init__(self):
        self.log_monitor = LogMonitor()
        self.last_check_time = 0
        self.check_interval = 300  # 5 minutes
        self.health_history: List[HealthStatus] = []
        self.max_history_size = 100
    
    def run_health_check(self, force: bool = False) -> HealthStatus:
        """Run comprehensive health check."""
        current_time = time.time()
        
        if not force and current_time - self.last_check_time < self.check_interval:
            # Return cached result if available
            if self.health_history:
                return self.health_history[-1]
        
        logger.log_structured('info', "Running health check")
        
        checks = {}
        recommendations = []
        
        # System checks
        checks['system'] = self._check_system()
        
        # Disk space checks
        checks['disk_space'] = self._check_disk_space()
        
        # Memory checks
        checks['memory'] = self._check_memory()
        
        # Database checks
        checks['database'] = self._check_database()
        
        # Logging checks
        checks['logging'] = self._check_logging()
        
        # Configuration checks
        checks['configuration'] = self._check_configuration()
        
        # Performance checks
        checks['performance'] = self._check_performance()
        
        # Security checks
        checks['security'] = self._check_security()
        
        # Determine overall status
        status = self._determine_overall_status(checks)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(checks)
        
        # Create summary
        summary = self._create_summary(checks)
        
        health_status = HealthStatus(
            status=status,
            timestamp=current_time,
            checks=checks,
            summary=summary,
            recommendations=recommendations
        )
        
        # Store in history
        self.health_history.append(health_status)
        if len(self.health_history) > self.max_history_size:
            self.health_history.pop(0)
        
        self.last_check_time = current_time
        
        # Log health status
        logger.log_structured('info', f"Health check completed: {status.upper()}",
                            status=status, issues=len(recommendations))
        
        return health_status
    
    def _check_system(self) -> Dict[str, Any]:
        """Check system health."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Process count
            process_count = len(psutil.pids())
            
            # System uptime
            uptime = time.time() - psutil.boot_time()
            
            # Platform info
            platform_info = {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }
            
            # Python info
            python_info = {
                'version': sys.version,
                'executable': sys.executable,
                'path': sys.path[:5]  # First 5 paths
            }
            
            return {
                'status': 'healthy' if cpu_percent < 80 and memory.percent < 80 else 'warning',
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_usage_percent': disk.percent,
                'process_count': process_count,
                'uptime_hours': uptime / 3600,
                'platform': platform_info,
                'python': python_info
            }
            
        except Exception as e:
            logger.log_exception("System health check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space for critical directories."""
        critical_dirs = [
            str(Path.cwd()),
            config_manager.logging.log_dir,
            str(database.backup_dir),
            "data"
        ]
        
        results = {}
        overall_status = 'healthy'
        
        for dir_path in critical_dirs:
            try:
                if os.path.exists(dir_path):
                    disk_usage = psutil.disk_usage(dir_path)
                    free_percent = (disk_usage.free / disk_usage.total) * 100
                    
                    status = 'healthy'
                    if free_percent < 5:
                        status = 'critical'
                        overall_status = 'critical'
                    elif free_percent < 10:
                        status = 'warning'
                        if overall_status == 'healthy':
                            overall_status = 'warning'
                    
                    results[dir_path] = {
                        'status': status,
                        'total_gb': disk_usage.total / (1024**3),
                        'free_gb': disk_usage.free / (1024**3),
                        'used_gb': disk_usage.used / (1024**3),
                        'free_percent': free_percent
                    }
                else:
                    results[dir_path] = {
                        'status': 'warning',
                        'message': 'Directory does not exist'
                    }
                    
            except Exception as e:
                results[dir_path] = {
                    'status': 'critical',
                    'error': str(e)
                }
                overall_status = 'critical'
        
        return {
            'status': overall_status,
            'directories': results
        }
    
    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage and availability."""
        try:
            memory = psutil.virtual_memory()
            
            # Check if we're approaching memory limits
            status = 'healthy'
            if memory.percent > 90:
                status = 'critical'
            elif memory.percent > 75:
                status = 'warning'
            
            # Check YotuDrive process memory
            current_process = psutil.Process()
            process_memory = current_process.memory_info()
            
            return {
                'status': status,
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_gb': memory.used / (1024**3),
                'percent': memory.percent,
                'process_memory_mb': process_memory.rss / (1024**2),
                'process_memory_percent': (process_memory.rss / memory.total) * 100
            }
            
        except Exception as e:
            logger.log_exception("Memory check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            # Check database file
            db_status = 'healthy'
            issues = []
            
            if not database.db_path.exists():
                db_status = 'warning'
                issues.append('Database file does not exist')
            else:
                # Check database size
                db_size = database.db_path.stat().st_size
                if db_size == 0:
                    db_status = 'critical'
                    issues.append('Database file is empty')
                elif db_size > 100 * 1024 * 1024:  # 100MB
                    db_status = 'warning'
                    issues.append('Database file is large')
            
            # Check database lock
            if database.lock_file.exists():
                lock_age = time.time() - database.lock_file.stat().st_mtime
                if lock_age > 300:  # 5 minutes
                    db_status = 'critical'
                    issues.append('Database lock is stale')
            
            # Get database statistics
            stats = database.get_statistics()
            
            # Check backup status
            backup_status = 'healthy'
            if len(database.backups) == 0:
                backup_status = 'warning'
                issues.append('No backups found')
            elif len(database.backups) < 3:
                backup_status = 'warning'
                issues.append('Fewer than 3 backups available')
            
            return {
                'status': db_status,
                'issues': issues,
                'statistics': stats,
                'backup_status': backup_status,
                'backups_count': len(database.backups)
            }
            
        except Exception as e:
            logger.log_exception("Database check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_logging(self) -> Dict[str, Any]:
        """Check logging system health."""
        try:
            log_stats = logger.get_log_stats()
            
            # Check log file size
            status = 'healthy'
            issues = []
            
            if 'file_handler' in log_stats:
                file_handler = log_stats['file_handler']
                current_size = file_handler['current_size']
                max_size = file_handler['max_bytes']
                
                if current_size > max_size * 0.9:
                    status = 'warning'
                    issues.append('Log file approaching size limit')
                elif current_size > max_size:
                    status = 'critical'
                    issues.append('Log file exceeded size limit')
            
            # Check for recent errors
            error_summary = self.log_monitor.get_error_summary(hours=24)
            if error_summary['error_count'] > 100:
                status = 'critical'
                issues.append('High error rate detected')
            elif error_summary['error_count'] > 50:
                status = 'warning'
                issues.append('Elevated error rate detected')
            
            return {
                'status': status,
                'issues': issues,
                'statistics': log_stats,
                'error_summary': error_summary
            }
            
        except Exception as e:
            logger.log_exception("Logging check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            # Validate configuration
            config_manager.validate()
            
            status = 'healthy'
            issues = []
            
            # Check critical configuration values
            if config_manager.security.max_file_size > 1024 * 1024 * 1024 * 1024:  # 1TB
                status = 'warning'
                issues.append('Very large max file size configured')
            
            if config_manager.encoding.block_size > 8:
                status = 'warning'
                issues.append('Large block size may affect performance')
            
            # Check environment variables
            env_vars = [
                'YOTUDRIVE_LOG_LEVEL',
                'YOTUDRIVE_MAX_FILE_SIZE',
                'YOTUDRIVE_THREADS'
            ]
            
            env_config = {}
            for var in env_vars:
                value = os.getenv(var)
                if value:
                    env_config[var] = value
            
            return {
                'status': status,
                'issues': issues,
                'environment_variables': env_config,
                'config_summary': {
                    'video_encoder': config_manager.video.encoder,
                    'log_level': config_manager.logging.level,
                    'threads': config_manager.performance.threads,
                    'max_file_size_gb': config_manager.security.max_file_size / (1024**3)
                }
            }
            
        except Exception as e:
            logger.log_exception("Configuration check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_performance(self) -> Dict[str, Any]:
        """Check performance metrics."""
        try:
            # Get performance metrics from logs
            perf_metrics = self.log_monitor.get_performance_metrics(hours=1)
            
            status = 'healthy'
            issues = []
            
            # Check for slow operations
            slow_operations = []
            for op_name, stats in perf_metrics['operation_stats'].items():
                if stats['avg_duration'] > 60:  # 1 minute
                    status = 'warning'
                    issues.append(f'Slow operation: {op_name}')
                    slow_operations.append(op_name)
            
            # Check thread configuration
            optimal_threads = psutil.cpu_count()
            configured_threads = config_manager.performance.threads
            
            if configured_threads > optimal_threads * 2:
                status = 'warning'
                issues.append('Too many threads configured')
            elif configured_threads < optimal_threads // 2:
                status = 'warning'
                issues.append('Too few threads configured')
            
            return {
                'status': status,
                'issues': issues,
                'performance_metrics': perf_metrics,
                'thread_configuration': {
                    'configured': configured_threads,
                    'optimal': optimal_threads,
                    'cpu_count': psutil.cpu_count()
                },
                'slow_operations': slow_operations
            }
            
        except Exception as e:
            logger.log_exception("Performance check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _check_security(self) -> Dict[str, Any]:
        """Check security settings."""
        try:
            status = 'healthy'
            issues = []
            
            # Check file permissions
            critical_files = [
                database.db_path,
                config_manager.config_file
            ]
            
            file_permissions = {}
            for file_path in critical_files:
                if file_path.exists():
                    stat = file_path.stat()
                    permissions = oct(stat.st_mode)[-3:]
                    file_permissions[str(file_path)] = permissions
                    
                    # Check if file is world-writable
                    if permissions[2] in ['2', '6', '7']:
                        status = 'warning'
                        issues.append(f'File {file_path} is world-writable')
            
            # Check for sensitive data in logs
            log_dir = Path(config_manager.logging.log_dir)
            sensitive_patterns = ['password', 'token', 'key', 'secret']
            
            sensitive_found = []
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for pattern in sensitive_patterns:
                                if pattern in content.lower():
                                    sensitive_found.append(str(log_file))
                                    break
                    except (OSError, UnicodeDecodeError):
                        pass
            
            if sensitive_found:
                status = 'warning'
                issues.append('Sensitive data found in logs')
            
            # Check temp directory
            temp_dir = Path(config_manager.security.temp_dir or "temp")
            if temp_dir.exists():
                temp_files = list(temp_dir.glob("*"))
                if len(temp_files) > 100:
                    status = 'warning'
                    issues.append('Many files in temp directory')
            
            return {
                'status': status,
                'issues': issues,
                'file_permissions': file_permissions,
                'sensitive_in_logs': sensitive_found,
                'temp_files_count': len(temp_files) if temp_dir.exists() else 0
            }
            
        except Exception as e:
            logger.log_exception("Security check failed", e)
            return {
                'status': 'critical',
                'error': str(e)
            }
    
    def _determine_overall_status(self, checks: Dict[str, Dict[str, Any]]) -> str:
        """Determine overall health status."""
        statuses = [check.get('status', 'healthy') for check in checks.values()]
        
        if 'critical' in statuses:
            return 'critical'
        elif 'warning' in statuses:
            return 'warning'
        else:
            return 'healthy'
    
    def _generate_recommendations(self, checks: Dict[str, Dict[str, Any]]) -> List[str]:
        """Generate health recommendations."""
        recommendations = []
        
        # System recommendations
        system = checks.get('system', {})
        if system.get('cpu_percent', 0) > 80:
            recommendations.append("High CPU usage detected. Consider reducing thread count or closing other applications.")
        
        if system.get('memory_percent', 0) > 80:
            recommendations.append("High memory usage detected. Consider closing other applications or increasing RAM.")
        
        # Disk space recommendations
        disk_space = checks.get('disk_space', {})
        for dir_path, info in disk_space.get('directories', {}).items():
            if info.get('free_percent', 100) < 10:
                recommendations.append(f"Low disk space for {dir_path}. Consider cleaning up old files.")
        
        # Database recommendations
        db_check = checks.get('database', {})
        if db_check.get('backups_count', 0) < 3:
            recommendations.append("Create more database backups for better data protection.")
        
        # Logging recommendations
        logging_check = checks.get('logging', {})
        error_summary = logging_check.get('error_summary', {})
        if error_summary.get('error_count', 0) > 50:
            recommendations.append("High error rate detected. Check logs for recurring issues.")
        
        # Performance recommendations
        perf_check = checks.get('performance', {})
        slow_ops = perf_check.get('slow_operations', [])
        if slow_ops:
            recommendations.append(f"Slow operations detected: {', '.join(slow_ops)}. Consider optimization.")
        
        # Security recommendations
        security_check = checks.get('security', {})
        if security_check.get('sensitive_in_logs'):
            recommendations.append("Sensitive data found in logs. Review and clean up logs.")
        
        return recommendations
    
    def _create_summary(self, checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create health check summary."""
        summary = {
            'total_checks': len(checks),
            'healthy_checks': 0,
            'warning_checks': 0,
            'critical_checks': 0,
            'total_issues': 0
        }
        
        for check_name, check_data in checks.items():
            status = check_data.get('status', 'healthy')
            if status == 'healthy':
                summary['healthy_checks'] += 1
            elif status == 'warning':
                summary['warning_checks'] += 1
            elif status == 'critical':
                summary['critical_checks'] += 1
            
            # Count issues
            issues = check_data.get('issues', [])
            summary['total_issues'] += len(issues)
        
        return summary
    
    def get_health_report(self, format: str = 'json') -> str:
        """Get formatted health report."""
        health_status = self.run_health_check()
        
        if format == 'json':
            return json.dumps(asdict(health_status), indent=2, default=str)
        elif format == 'text':
            return self._format_text_report(health_status)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_text_report(self, health_status: HealthStatus) -> str:
        """Format health report as text."""
        lines = []
        lines.append("YOTU DRIVE HEALTH REPORT")
        lines.append("=" * 50)
        lines.append(f"Status: {health_status.status.upper()}")
        lines.append(f"Timestamp: {datetime.fromtimestamp(health_status.timestamp)}")
        lines.append("")
        
        # Summary
        summary = health_status.summary
        lines.append("SUMMARY")
        lines.append("-" * 20)
        lines.append(f"Total Checks: {summary['total_checks']}")
        lines.append(f"Healthy: {summary['healthy_checks']}")
        lines.append(f"Warning: {summary['warning_checks']}")
        lines.append(f"Critical: {summary['critical_checks']}")
        lines.append(f"Total Issues: {summary['total_issues']}")
        lines.append("")
        
        # Detailed checks
        lines.append("DETAILED CHECKS")
        lines.append("-" * 20)
        for check_name, check_data in health_status.checks.items():
            lines.append(f"{check_name.upper()}: {check_data.get('status', 'unknown').upper()}")
            
            # Add key metrics
            if check_name == 'system':
                lines.append(f"  CPU: {check_data.get('cpu_percent', 0):.1f}%")
                lines.append(f"  Memory: {check_data.get('memory_percent', 0):.1f}%")
                lines.append(f"  Disk: {check_data.get('disk_usage_percent', 0):.1f}%")
            
            elif check_name == 'database':
                stats = check_data.get('statistics', {})
                lines.append(f"  Files: {stats.get('active_files', 0)}")
                lines.append(f"  Backups: {check_data.get('backups_count', 0)}")
            
            # Add issues
            issues = check_data.get('issues', [])
            for issue in issues:
                lines.append(f"  ⚠️  {issue}")
            
            lines.append("")
        
        # Recommendations
        if health_status.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 20)
            for i, rec in enumerate(health_status.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network I/O
        network_io = psutil.net_io_counters()._asdict()
        
        # Process count
        process_count = len(psutil.pids())
        
        # Uptime
        uptime = time.time() - psutil.boot_time()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available=memory.available,
            disk_usage_percent=disk.percent,
            disk_free=disk.free,
            network_io=network_io,
            process_count=process_count,
            uptime=uptime
        )

# Global health checker instance
health_checker = HealthChecker()

def run_health_check(force: bool = False) -> HealthStatus:
    """Run health check."""
    return health_checker.run_health_check(force)

def get_health_report(format: str = 'json') -> str:
    """Get health report."""
    return health_checker.get_health_report(format)
