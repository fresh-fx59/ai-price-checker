"""
Tests for the comprehensive logging and monitoring service.
"""
import json
import logging
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.services.logging_service import (
        LoggingService, JSONFormatter, PerformanceMonitor, ErrorTracker,
        LogEntry, PerformanceMetric, ErrorMetric
    )
    from src.models.config import Config
except ImportError:
    from services.logging_service import (
        LoggingService, JSONFormatter, PerformanceMonitor, ErrorTracker,
        LogEntry, PerformanceMetric, ErrorMetric
    )
    from models.config import Config


class TestJSONFormatter(unittest.TestCase):
    """Test JSON formatter for structured logging."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = JSONFormatter()
    
    def test_format_basic_log_record(self):
        """Test formatting a basic log record."""
        # Create a log record
        logger = logging.getLogger('test')
        record = logger.makeRecord(
            name='test.module',
            level=logging.INFO,
            fn='test_file.py',
            lno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON
        log_data = json.loads(formatted)
        
        # Verify structure
        self.assertIn('timestamp', log_data)
        self.assertEqual(log_data['level'], 'INFO')
        self.assertEqual(log_data['logger_name'], 'test.module')
        self.assertEqual(log_data['message'], 'Test message')
        self.assertEqual(log_data['line_number'], 42)
        self.assertIsInstance(log_data['thread_id'], int)
        self.assertIsInstance(log_data['process_id'], int)
    
    def test_format_log_record_with_exception(self):
        """Test formatting a log record with exception information."""
        logger = logging.getLogger('test')
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logger.makeRecord(
                name='test.module',
                level=logging.ERROR,
                fn='test_file.py',
                lno=42,
                msg='Error occurred',
                args=(),
                exc_info=sys.exc_info()
            )
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON
        log_data = json.loads(formatted)
        
        # Verify exception information
        self.assertIn('exception_info', log_data)
        self.assertEqual(log_data['exception_info']['type'], 'ValueError')
        self.assertEqual(log_data['exception_info']['message'], 'Test exception')
        self.assertIsInstance(log_data['exception_info']['traceback'], list)
    
    def test_format_log_record_with_extra_data(self):
        """Test formatting a log record with extra data."""
        logger = logging.getLogger('test')
        record = logger.makeRecord(
            name='test.module',
            level=logging.INFO,
            fn='test_file.py',
            lno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Add extra data
        record.extra_data = {'user_id': 123, 'operation': 'test_op'}
        
        # Format the record
        formatted = self.formatter.format(record)
        
        # Parse the JSON
        log_data = json.loads(formatted)
        
        # Verify extra data
        self.assertEqual(log_data['extra_data']['user_id'], 123)
        self.assertEqual(log_data['extra_data']['operation'], 'test_op')


class TestPerformanceMonitor(unittest.TestCase):
    """Test performance monitoring functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = PerformanceMonitor()
    
    def test_measure_operation_success(self):
        """Test measuring a successful operation."""
        with self.monitor.measure_operation('test_operation', {'param': 'value'}):
            time.sleep(0.01)  # Simulate work
        
        # Check metrics
        metrics = self.monitor.get_metrics()
        self.assertEqual(len(metrics), 1)
        
        metric = metrics[0]
        self.assertEqual(metric.operation, 'test_operation')
        self.assertTrue(metric.success)
        self.assertIsNone(metric.error_message)
        self.assertGreater(metric.duration_ms, 0)
        self.assertEqual(metric.extra_data['param'], 'value')
    
    def test_measure_operation_failure(self):
        """Test measuring a failed operation."""
        with self.assertRaises(ValueError):
            with self.monitor.measure_operation('test_operation'):
                raise ValueError("Test error")
        
        # Check metrics
        metrics = self.monitor.get_metrics()
        self.assertEqual(len(metrics), 1)
        
        metric = metrics[0]
        self.assertEqual(metric.operation, 'test_operation')
        self.assertFalse(metric.success)
        self.assertEqual(metric.error_message, 'Test error')
        self.assertGreater(metric.duration_ms, 0)
    
    def test_get_operation_stats(self):
        """Test getting operation statistics."""
        # Add some metrics
        with self.monitor.measure_operation('test_op'):
            time.sleep(0.001)
        
        with self.monitor.measure_operation('test_op'):
            time.sleep(0.002)
        
        try:
            with self.monitor.measure_operation('test_op'):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Get stats
        stats = self.monitor.get_operation_stats('test_op')
        
        self.assertEqual(stats['operation'], 'test_op')
        self.assertEqual(stats['total_calls'], 3)
        self.assertEqual(stats['success_count'], 2)
        self.assertEqual(stats['failure_count'], 1)
        self.assertAlmostEqual(stats['success_rate'], 2/3, places=2)
        self.assertGreater(stats['avg_duration_ms'], 0)
        self.assertGreater(stats['max_duration_ms'], stats['min_duration_ms'])
    
    def test_cleanup_old_metrics(self):
        """Test cleaning up old metrics."""
        # Add a metric
        with self.monitor.measure_operation('test_op'):
            pass
        
        # Manually set old timestamp
        self.monitor.metrics[0].timestamp = (datetime.now() - timedelta(hours=25)).isoformat()
        
        # Add a recent metric
        with self.monitor.measure_operation('test_op'):
            pass
        
        # Clean up old metrics
        self.monitor.cleanup_old_metrics(max_age_hours=24)
        
        # Should have only 1 metric left
        self.assertEqual(len(self.monitor.metrics), 1)


class TestErrorTracker(unittest.TestCase):
    """Test error tracking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = ErrorTracker()
    
    def test_track_error(self):
        """Test tracking an error."""
        error = ValueError("Test error")
        extra_data = {'context': 'test'}
        
        self.tracker.track_error(error, extra_data)
        
        # Check errors
        errors = self.tracker.get_errors()
        self.assertEqual(len(errors), 1)
        
        error_metric = errors[0]
        self.assertEqual(error_metric.error_type, 'ValueError')
        self.assertEqual(error_metric.error_message, 'Test error')
        self.assertEqual(error_metric.extra_data['context'], 'test')
        self.assertIsNotNone(error_metric.stack_trace)
    
    def test_get_error_summary(self):
        """Test getting error summary."""
        # Track some errors
        self.tracker.track_error(ValueError("Error 1"))
        self.tracker.track_error(ValueError("Error 2"))
        self.tracker.track_error(TypeError("Error 3"))
        
        # Get summary
        summary = self.tracker.get_error_summary()
        
        self.assertEqual(summary['total_errors'], 3)
        self.assertEqual(summary['error_types']['ValueError'], 2)
        self.assertEqual(summary['error_types']['TypeError'], 1)
        self.assertEqual(summary['most_common_error'], 'ValueError')
    
    def test_cleanup_old_errors(self):
        """Test cleaning up old errors."""
        # Track an error
        self.tracker.track_error(ValueError("Test error"))
        
        # Manually set old timestamp
        self.tracker.errors[0].timestamp = (datetime.now() - timedelta(hours=200)).isoformat()
        
        # Track a recent error
        self.tracker.track_error(TypeError("Recent error"))
        
        # Clean up old errors
        self.tracker.cleanup_old_errors(max_age_hours=168)
        
        # Should have only 1 error left
        self.assertEqual(len(self.tracker.errors), 1)
        self.assertEqual(self.tracker.errors[0].error_type, 'TypeError')


class TestLoggingService(unittest.TestCase):
    """Test comprehensive logging service."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test configuration
        self.config = Config(
            log_level="INFO",
            log_file_path=os.path.join(self.temp_dir, "test.log"),
            enable_structured_logging=True,
            enable_performance_monitoring=True,
            enable_error_tracking=True,
            log_retention_days=30,
            metrics_retention_hours=24,
            error_retention_hours=168
        )
        
        self.logging_service = LoggingService(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test logging service initialization."""
        self.assertIsNotNone(self.logging_service.performance_monitor)
        self.assertIsNotNone(self.logging_service.error_tracker)
        self.assertTrue(os.path.exists(self.config.log_file_path))
    
    def test_log_with_context(self):
        """Test logging with context data."""
        self.logging_service.log_with_context(
            'info', 
            'Test message', 
            user_id=123, 
            operation='test'
        )
        
        # Verify log file exists and has content
        self.assertTrue(os.path.exists(self.config.log_file_path))
        
        with open(self.config.log_file_path, 'r') as f:
            content = f.read()
            self.assertIn('Test message', content)
    
    def test_measure_performance(self):
        """Test performance measurement."""
        with self.logging_service.measure_performance('test_operation', {'param': 'value'}):
            time.sleep(0.01)
        
        # Get performance stats
        stats = self.logging_service.get_performance_stats('test_operation')
        
        self.assertEqual(stats['operation'], 'test_operation')
        self.assertEqual(stats['total_calls'], 1)
        self.assertEqual(stats['success_count'], 1)
        self.assertGreater(stats['avg_duration_ms'], 0)
    
    def test_track_error(self):
        """Test error tracking."""
        error = ValueError("Test error")
        self.logging_service.track_error(error, {'context': 'test'})
        
        # Get error summary
        summary = self.logging_service.get_error_summary()
        
        self.assertEqual(summary['total_errors'], 1)
        self.assertEqual(summary['error_types']['ValueError'], 1)
    
    def test_get_health_status(self):
        """Test health status reporting."""
        health = self.logging_service.get_health_status()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertTrue(health['log_file_writable'])
        self.assertIn('timestamp', health)
    
    def test_cleanup_old_data(self):
        """Test cleaning up old monitoring data."""
        # Add some data
        with self.logging_service.measure_performance('test_op'):
            pass
        
        self.logging_service.track_error(ValueError("Test error"))
        
        # Clean up (should not remove recent data)
        self.logging_service.cleanup_old_data()
        
        # Verify data still exists
        stats = self.logging_service.get_performance_stats()
        self.assertIn('test_op', stats)
        
        summary = self.logging_service.get_error_summary()
        self.assertEqual(summary['total_errors'], 1)


class TestLoggingIntegration(unittest.TestCase):
    """Test logging service integration with other components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(
            log_level="INFO",
            log_file_path=os.path.join(self.temp_dir, "test.log")
        )
        self.logging_service = LoggingService(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_rotation(self):
        """Test log file rotation."""
        # Write enough data to trigger rotation
        logger = logging.getLogger('test')
        
        # Write a large amount of data
        large_message = "x" * 1000
        for i in range(100):
            logger.info(f"Message {i}: {large_message}")
        
        # Check that log files exist
        log_files = list(Path(self.temp_dir).glob("*.log*"))
        self.assertGreater(len(log_files), 0)
    
    def test_error_log_separation(self):
        """Test that errors are logged to separate file."""
        logger = logging.getLogger('test')
        
        # Log an error
        logger.error("Test error message")
        
        # Check that error log file exists
        error_log_path = str(Path(self.config.log_file_path).with_suffix('.errors.log'))
        self.assertTrue(os.path.exists(error_log_path))
        
        # Verify error is in the error log
        with open(error_log_path, 'r') as f:
            content = f.read()
            self.assertIn('Test error message', content)


if __name__ == '__main__':
    unittest.main()