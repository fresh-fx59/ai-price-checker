"""
Integration tests for logging service with the main application.
"""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.main import PriceMonitorApplication
    from src.models.config import Config
    from src.services.logging_service import LoggingService
except ImportError:
    from main import PriceMonitorApplication
    from models.config import Config
    from services.logging_service import LoggingService


class TestLoggingIntegration(unittest.TestCase):
    """Test logging service integration with main application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.properties")
        
        # Create a minimal config file
        config_content = """
[database]
path = {}/test.db

[email]
smtp_server = smtp.example.com
smtp_port = 587
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
check_time = 09:00
max_retry_attempts = 3
request_timeout_seconds = 30

[ai]
api_key = 
api_endpoint = 
enable_parsing = false

[security]
enable_mtls = false
server_cert_path = /app/certs/server.crt
server_key_path = /app/certs/server.key
ca_cert_path = /app/certs/ca.crt
client_cert_required = false
api_port = 5000

[app]
log_level = INFO
log_file_path = {}/test.log

[logging]
enable_structured_logging = true
enable_performance_monitoring = true
enable_error_tracking = true
log_retention_days = 30
metrics_retention_hours = 24
error_retention_hours = 168
""".format(self.temp_dir, self.temp_dir)
        
        with open(self.config_path, 'w') as f:
            f.write(config_content)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.services.email_service.EmailService.__init__', return_value=None)
    @patch('src.services.email_service.EmailService.test_email_connection')
    def test_application_initialization_with_logging(self, mock_email_test, mock_email_init):
        """Test that the application initializes correctly with logging service."""
        # Mock email service to avoid SMTP connection
        mock_email_test.return_value = Mock(success=True, message="Test successful")
        
        # Create application
        app = PriceMonitorApplication(self.config_path)
        
        # Initialize application
        success = app.initialize()
        
        # Verify initialization
        self.assertTrue(success)
        self.assertIsNotNone(app.logging_service)
        self.assertIsInstance(app.logging_service, LoggingService)
        
        # Verify logging service is properly configured
        self.assertIsNotNone(app.logging_service.performance_monitor)
        self.assertIsNotNone(app.logging_service.error_tracker)
        
        # Verify log file was created
        log_file_path = os.path.join(self.temp_dir, "test.log")
        self.assertTrue(os.path.exists(log_file_path))
        
        # Clean up
        app.shutdown()
    
    @patch('src.services.email_service.EmailService.__init__', return_value=None)
    @patch('src.services.email_service.EmailService.test_email_connection')
    def test_logging_service_performance_monitoring(self, mock_email_test, mock_email_init):
        """Test that performance monitoring works in the application context."""
        # Mock email service
        mock_email_test.return_value = Mock(success=True, message="Test successful")
        
        # Create and initialize application
        app = PriceMonitorApplication(self.config_path)
        success = app.initialize()
        self.assertTrue(success)
        
        # Use performance monitoring
        with app.logging_service.measure_performance('test_operation', {'test': 'data'}):
            import time
            time.sleep(0.01)
        
        # Verify metrics were recorded
        stats = app.logging_service.get_performance_stats('test_operation')
        self.assertEqual(stats['operation'], 'test_operation')
        self.assertEqual(stats['total_calls'], 1)
        self.assertEqual(stats['success_count'], 1)
        self.assertGreater(stats['avg_duration_ms'], 0)
        
        # Clean up
        app.shutdown()
    
    @patch('src.services.email_service.EmailService.__init__', return_value=None)
    @patch('src.services.email_service.EmailService.test_email_connection')
    def test_logging_service_error_tracking(self, mock_email_test, mock_email_init):
        """Test that error tracking works in the application context."""
        # Mock email service
        mock_email_test.return_value = Mock(success=True, message="Test successful")
        
        # Create and initialize application
        app = PriceMonitorApplication(self.config_path)
        success = app.initialize()
        self.assertTrue(success)
        
        # Track an error
        test_error = ValueError("Test error for tracking")
        app.logging_service.track_error(test_error, {'context': 'integration_test'})
        
        # Verify error was tracked
        error_summary = app.logging_service.get_error_summary()
        self.assertEqual(error_summary['total_errors'], 1)
        self.assertEqual(error_summary['error_types']['ValueError'], 1)
        
        # Clean up
        app.shutdown()
    
    @patch('src.services.email_service.EmailService.__init__', return_value=None)
    @patch('src.services.email_service.EmailService.test_email_connection')
    def test_structured_logging_output(self, mock_email_test, mock_email_init):
        """Test that structured logging produces JSON output."""
        # Mock email service
        mock_email_test.return_value = Mock(success=True, message="Test successful")
        
        # Create and initialize application
        app = PriceMonitorApplication(self.config_path)
        success = app.initialize()
        self.assertTrue(success)
        
        # Log a message with context
        app.logging_service.log_with_context(
            'info',
            'Test structured log message',
            user_id=123,
            operation='test_operation'
        )
        
        # Read the log file and verify JSON structure
        log_file_path = os.path.join(self.temp_dir, "test.log")
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        
        # Find JSON log entries
        json_lines = []
        for line in log_content.split('\n'):
            if line.strip() and line.startswith('{'):
                try:
                    json_data = json.loads(line)
                    json_lines.append(json_data)
                except json.JSONDecodeError:
                    continue
        
        # Verify we have JSON log entries
        self.assertGreater(len(json_lines), 0)
        
        # Find our test message
        test_entries = [entry for entry in json_lines 
                       if entry.get('message') == 'Test structured log message']
        self.assertGreater(len(test_entries), 0)
        
        # Verify structure of our test entry
        test_entry = test_entries[0]
        self.assertEqual(test_entry['level'], 'INFO')
        self.assertIn('timestamp', test_entry)
        self.assertIn('extra_data', test_entry)
        self.assertEqual(test_entry['extra_data']['user_id'], 123)
        self.assertEqual(test_entry['extra_data']['operation'], 'test_operation')
        
        # Clean up
        app.shutdown()


if __name__ == '__main__':
    unittest.main()