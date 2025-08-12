"""
Comprehensive logging and monitoring service for the price monitoring application.
"""
import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading


@dataclass
class LogEntry:
    """Structured log entry for JSON logging."""
    timestamp: str
    level: str
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    extra_data: Optional[Dict[str, Any]] = None
    exception_info: Optional[Dict[str, Any]] = None


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    operation: str
    duration_ms: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class ErrorMetric:
    """Error tracking metric data structure."""
    error_type: str
    error_message: str
    module: str
    function: str
    line_number: int
    timestamp: str
    stack_trace: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create structured log entry
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module,
            function=record.funcName,
            line_number=record.lineno,
            thread_id=record.thread,
            process_id=record.process,
            extra_data=getattr(record, 'extra_data', None)
        )
        
        # Add exception information if present
        if record.exc_info:
            log_entry.exception_info = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(asdict(log_entry), default=str)


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def measure_operation(self, operation: str, extra_data: Optional[Dict[str, Any]] = None):
        """Context manager to measure operation performance."""
        start_time = time.time()
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            metric = PerformanceMetric(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=datetime.now().isoformat(),
                success=success,
                error_message=error_message,
                extra_data=extra_data
            )
            
            with self.lock:
                self.metrics.append(metric)
            
            # Log performance metric
            self.logger.info(
                f"Performance metric: {operation}",
                extra={
                    'extra_data': {
                        'operation': operation,
                        'duration_ms': duration_ms,
                        'success': success,
                        'error_message': error_message,
                        **(extra_data if extra_data else {})
                    }
                }
            )
    
    def get_metrics(self, operation: Optional[str] = None, 
                   since: Optional[datetime] = None) -> List[PerformanceMetric]:
        """Get performance metrics with optional filtering."""
        with self.lock:
            filtered_metrics = self.metrics.copy()
        
        if operation:
            filtered_metrics = [m for m in filtered_metrics if m.operation == operation]
        
        if since:
            since_iso = since.isoformat()
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= since_iso]
        
        return filtered_metrics
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for a specific operation."""
        metrics = self.get_metrics(operation=operation)
        
        if not metrics:
            return {}
        
        durations = [m.duration_ms for m in metrics]
        success_count = sum(1 for m in metrics if m.success)
        
        return {
            'operation': operation,
            'total_calls': len(metrics),
            'success_count': success_count,
            'failure_count': len(metrics) - success_count,
            'success_rate': success_count / len(metrics) if metrics else 0,
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'min_duration_ms': min(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0
        }
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Remove metrics older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cutoff_iso = cutoff_time.isoformat()
        
        with self.lock:
            self.metrics = [m for m in self.metrics if m.timestamp >= cutoff_iso]


class ErrorTracker:
    """Error tracking and analysis."""
    
    def __init__(self):
        self.errors: List[ErrorMetric] = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def track_error(self, error: Exception, extra_data: Optional[Dict[str, Any]] = None):
        """Track an error occurrence."""
        # Get caller information
        frame = sys._getframe(1)
        
        error_metric = ErrorMetric(
            error_type=type(error).__name__,
            error_message=str(error),
            module=frame.f_globals.get('__name__', 'unknown'),
            function=frame.f_code.co_name,
            line_number=frame.f_lineno,
            timestamp=datetime.now().isoformat(),
            stack_trace=traceback.format_exc(),
            extra_data=extra_data
        )
        
        with self.lock:
            self.errors.append(error_metric)
        
        # Log error metric
        self.logger.error(
            f"Error tracked: {error_metric.error_type}",
            extra={
                'extra_data': {
                    'error_type': error_metric.error_type,
                    'error_message': error_metric.error_message,
                    'module': error_metric.module,
                    'function': error_metric.function,
                    'line_number': error_metric.line_number,
                    **(extra_data if extra_data else {})
                }
            },
            exc_info=True
        )
    
    def get_errors(self, error_type: Optional[str] = None,
                  since: Optional[datetime] = None) -> List[ErrorMetric]:
        """Get error metrics with optional filtering."""
        with self.lock:
            filtered_errors = self.errors.copy()
        
        if error_type:
            filtered_errors = [e for e in filtered_errors if e.error_type == error_type]
        
        if since:
            since_iso = since.isoformat()
            filtered_errors = [e for e in filtered_errors if e.timestamp >= since_iso]
        
        return filtered_errors
    
    def get_error_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get error summary statistics."""
        errors = self.get_errors(since=since)
        
        if not errors:
            return {'total_errors': 0, 'error_types': {}}
        
        error_types = {}
        for error in errors:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
        
        return {
            'total_errors': len(errors),
            'error_types': error_types,
            'most_common_error': max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
        }
    
    def cleanup_old_errors(self, max_age_hours: int = 168):  # 7 days default
        """Remove errors older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cutoff_iso = cutoff_time.isoformat()
        
        with self.lock:
            self.errors = [e for e in self.errors if e.timestamp >= cutoff_iso]


class LoggingService:
    """Comprehensive logging and monitoring service."""
    
    def __init__(self, config):
        """Initialize logging service with configuration."""
        self.config = config
        self.performance_monitor = PerformanceMonitor()
        self.error_tracker = ErrorTracker()
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging service initialized")
    
    def _setup_logging(self):
        """Setup comprehensive logging configuration."""
        # Create logs directory
        log_dir = Path(self.config.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Set log level
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        root_logger.setLevel(log_level)
        
        # Create formatters
        json_formatter = JSONFormatter()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Setup file handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.config.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(log_level)
        
        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        
        # Setup error file handler (JSON format for errors only)
        error_log_path = str(Path(self.config.log_file_path).with_suffix('.errors.log'))
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setFormatter(json_formatter)
        error_handler.setLevel(logging.ERROR)
        
        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(error_handler)
        
        # Setup log retention cleanup
        self._setup_log_retention()
    
    def _setup_log_retention(self):
        """Setup log file retention and cleanup."""
        log_dir = Path(self.config.log_file_path).parent
        
        # Clean up old log files (keep last 30 days)
        cutoff_time = datetime.now() - timedelta(days=30)
        
        for log_file in log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time.timestamp():
                    log_file.unlink()
                    self.logger.info(f"Cleaned up old log file: {log_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up log file {log_file}: {e}")
    
    def log_with_context(self, level: str, message: str, **context):
        """Log message with additional context data."""
        logger = logging.getLogger('app')
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message, extra={'extra_data': context})
    
    def measure_performance(self, operation: str, extra_data: Optional[Dict[str, Any]] = None):
        """Get performance measurement context manager."""
        return self.performance_monitor.measure_operation(operation, extra_data)
    
    def track_error(self, error: Exception, extra_data: Optional[Dict[str, Any]] = None):
        """Track an error occurrence."""
        self.error_tracker.track_error(error, extra_data)
    
    def get_performance_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics."""
        if operation:
            return self.performance_monitor.get_operation_stats(operation)
        else:
            # Get stats for all operations
            all_metrics = self.performance_monitor.get_metrics()
            operations = set(m.operation for m in all_metrics)
            return {
                op: self.performance_monitor.get_operation_stats(op)
                for op in operations
            }
    
    def get_error_summary(self, since_hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the specified time period."""
        since = datetime.now() - timedelta(hours=since_hours)
        return self.error_tracker.get_error_summary(since=since)
    
    def cleanup_old_data(self):
        """Clean up old metrics and error data."""
        self.performance_monitor.cleanup_old_metrics()
        self.error_tracker.cleanup_old_errors()
        self.logger.info("Cleaned up old monitoring data")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the logging system."""
        try:
            # Check if we can write to log file
            test_logger = logging.getLogger('health_check')
            test_logger.info("Health check test log entry")
            
            # Get recent error summary
            error_summary = self.get_error_summary(since_hours=1)
            
            # Get performance stats
            recent_metrics = self.performance_monitor.get_metrics(
                since=datetime.now() - timedelta(hours=1)
            )
            
            return {
                'status': 'healthy',
                'log_file_writable': True,
                'recent_errors': error_summary.get('total_errors', 0),
                'recent_operations': len(recent_metrics),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }