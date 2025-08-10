"""
Tests for the main application entry point.
"""

import os
import sys
import signal
import tempfile
import threading
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import PriceMonitorApplication, main
from models.config import Config
from services.config_service import ConfigService


class TestPriceMonitorApplication:
    """Test cases for PriceMonitorApplication class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.properties")
        
        # Create a test configuration file
        config_content = """
[database]
path = test_database.db

[email]
smtp_server = smtp.test.com
smtp_port = 587
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30

[security]
enable_mtls = false
api_port = 5000

[app]
log_level = INFO
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_application_initialization(self):
        """Test basic application initialization."""
        app = PriceMonitorApplication(config_path=self.config_path)
        
        assert app.config_path == self.config_path
        assert not app._is_running
        assert app.config_service is None
        assert app.config is None
    
    def test_get_default_config_path(self):
        """Test default configuration path detection."""
        app = PriceMonitorApplication()
        default_path = app._get_default_config_path()
        
        # Should return the first option from possible paths
        assert default_path == "config/default.properties"
    
    @patch('main.logging')
    def test_setup_logging(self, mock_logging):
        """Test logging setup."""
        app = PriceMonitorApplication(config_path=self.config_path)
        
        with patch('pathlib.Path.mkdir'):
            app._setup_logging()
        
        # Verify logging was configured
        mock_logging.basicConfig.assert_called_once()
        assert app.logger is not None
    
    def test_load_configuration_success(self):
        """Test successful configuration loading."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        
        result = app._load_configuration()
        
        assert result is True
        assert app.config_service is not None
        assert app.config is not None
        assert app.config.smtp_server == "smtp.test.com"
    
    def test_load_configuration_missing_file(self):
        """Test configuration loading with missing file."""
        missing_config_path = os.path.join(self.temp_dir, "missing_config.properties")
        app = PriceMonitorApplication(config_path=missing_config_path)
        app._setup_logging()
        
        with patch.object(app.config_service, 'create_default_config_file') as mock_create:
            result = app._load_configuration()
        
        assert result is False
        mock_create.assert_called_once()
    
    @patch('main.DatabaseManager')
    def test_initialize_database_success(self, mock_db_manager):
        """Test successful database initialization."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        
        mock_db_instance = Mock()
        mock_db_manager.return_value = mock_db_instance
        
        result = app._initialize_database()
        
        assert result is True
        assert app.db_manager == mock_db_instance
        mock_db_instance.initialize_database.assert_called_once()
    
    @patch('main.DatabaseManager')
    def test_initialize_database_failure(self, mock_db_manager):
        """Test database initialization failure."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        
        mock_db_manager.side_effect = Exception("Database error")
        
        result = app._initialize_database()
        
        assert result is False
        assert app.db_manager is None
    
    @patch('main.EmailService')
    @patch('main.PriceMonitorService')
    @patch('main.ParserService')
    @patch('main.WebScrapingService')
    @patch('main.ProductService')
    def test_initialize_services_success(self, mock_product_service, mock_web_scraping,
                                       mock_parser, mock_price_monitor, mock_email):
        """Test successful services initialization."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        app.db_manager = Mock()
        
        # Mock email service test
        mock_email_instance = Mock()
        mock_email_instance.test_email_connection.return_value = Mock(success=True)
        mock_email.return_value = mock_email_instance
        
        result = app._initialize_services()
        
        assert result is True
        assert app.product_service is not None
        assert app.web_scraping_service is not None
        assert app.parser_service is not None
        assert app.email_service is not None
        assert app.price_monitor_service is not None
    
    @patch('main.EmailService')
    @patch('main.PriceMonitorService')
    @patch('main.ParserService')
    @patch('main.WebScrapingService')
    @patch('main.ProductService')
    def test_initialize_services_email_failure(self, mock_product_service, mock_web_scraping,
                                             mock_parser, mock_price_monitor, mock_email):
        """Test services initialization with email service failure."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        app.db_manager = Mock()
        
        # Mock email service failure
        mock_email.side_effect = Exception("Email configuration error")
        
        result = app._initialize_services()
        
        assert result is True  # Should continue without email
        assert app.email_service is None
        assert app.price_monitor_service is not None
    
    @patch('main.SecureFlaskApp')
    def test_initialize_flask_app_success(self, mock_flask_app):
        """Test successful Flask app initialization."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        
        mock_flask_instance = Mock()
        mock_flask_app.return_value = mock_flask_instance
        
        result = app._initialize_flask_app()
        
        assert result is True
        assert app.flask_app == mock_flask_instance
    
    def test_start_monitoring_scheduler_success(self):
        """Test successful monitoring scheduler start."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app.price_monitor_service = Mock()
        
        result = app._start_monitoring_scheduler()
        
        assert result is True
        app.price_monitor_service.start_scheduler.assert_called_once_with("09:00")
        assert app.price_monitor_service.stop_scheduler in app._shutdown_handlers
    
    def test_start_monitoring_scheduler_failure(self):
        """Test monitoring scheduler start failure."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app.price_monitor_service = Mock()
        app.price_monitor_service.start_scheduler.side_effect = Exception("Scheduler error")
        
        result = app._start_monitoring_scheduler()
        
        assert result is False
    
    @patch('main.PriceMonitorApplication._start_monitoring_scheduler')
    @patch('main.PriceMonitorApplication._initialize_flask_app')
    @patch('main.PriceMonitorApplication._initialize_services')
    @patch('main.PriceMonitorApplication._initialize_database')
    @patch('main.PriceMonitorApplication._load_configuration')
    @patch('main.PriceMonitorApplication._setup_logging')
    def test_full_initialization_success(self, mock_logging, mock_config, mock_db,
                                       mock_services, mock_flask, mock_scheduler):
        """Test full application initialization success."""
        app = PriceMonitorApplication(config_path=self.config_path)
        
        # Mock all initialization steps to succeed
        mock_config.return_value = True
        mock_db.return_value = True
        mock_services.return_value = True
        mock_flask.return_value = True
        mock_scheduler.return_value = True
        
        result = app.initialize()
        
        assert result is True
        assert app._is_running is True
        
        # Verify all initialization steps were called
        mock_logging.assert_called_once()
        mock_config.assert_called_once()
        mock_db.assert_called_once()
        mock_services.assert_called_once()
        mock_flask.assert_called_once()
        mock_scheduler.assert_called_once()
    
    @patch('main.PriceMonitorApplication._load_configuration')
    @patch('main.PriceMonitorApplication._setup_logging')
    def test_initialization_failure(self, mock_logging, mock_config):
        """Test application initialization failure."""
        app = PriceMonitorApplication(config_path=self.config_path)
        
        # Mock configuration loading to fail
        mock_config.return_value = False
        
        result = app.initialize()
        
        assert result is False
        assert app._is_running is False
    
    def test_shutdown_not_running(self):
        """Test shutdown when application is not running."""
        app = PriceMonitorApplication(config_path=self.config_path)
        
        # Should not raise any errors
        app.shutdown()
        
        assert not app._is_running
    
    def test_shutdown_with_handlers(self):
        """Test shutdown with registered handlers."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._is_running = True
        
        # Add mock shutdown handlers
        handler1 = Mock()
        handler2 = Mock()
        app._shutdown_handlers = [handler1, handler2]
        
        # Add mock database manager
        app.db_manager = Mock()
        
        app.shutdown()
        
        # Verify handlers were called in reverse order
        handler2.assert_called_once()
        handler1.assert_called_once()
        app.db_manager.close.assert_called_once()
        assert not app._is_running
    
    def test_shutdown_with_handler_error(self):
        """Test shutdown with handler that raises an error."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._is_running = True
        
        # Add mock shutdown handler that raises an error
        failing_handler = Mock(side_effect=Exception("Handler error"))
        app._shutdown_handlers = [failing_handler]
        app.db_manager = Mock()
        
        # Should not raise an exception
        app.shutdown()
        
        assert not app._is_running
        failing_handler.assert_called_once()
    
    def test_signal_handler_setup(self):
        """Test signal handler setup."""
        with patch('signal.signal') as mock_signal:
            app = PriceMonitorApplication(config_path=self.config_path)
            
            # Verify signal handlers were registered
            assert mock_signal.call_count >= 2  # At least SIGINT and SIGTERM
    
    def test_reload_configuration(self):
        """Test configuration reload."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        app.price_monitor_service = Mock()
        
        # Mock new configuration with different log level
        new_config = Mock()
        new_config.log_level = "DEBUG"
        app.config_service.load_config = Mock(return_value=new_config)
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            app._reload_configuration()
        
        # Verify configuration was reloaded
        app.config_service.load_config.assert_called_once_with(app.config_path)
        assert app.config == new_config
    
    def test_get_status(self):
        """Test status information retrieval."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        app._is_running = True
        
        # Mock services
        app.email_service = Mock()
        app.price_monitor_service = Mock()
        app.price_monitor_service.is_scheduler_running.return_value = True
        app.price_monitor_service.get_monitoring_stats.return_value = {"test": "stats"}
        
        app.product_service = Mock()
        app.product_service.get_product_statistics.return_value = {"products": 5}
        
        status = app.get_status()
        
        assert status['running'] is True
        assert status['config_path'] == self.config_path
        assert status['mtls_enabled'] is False
        assert status['email_enabled'] is True
        assert status['scheduler_running'] is True
        assert status['monitoring_stats'] == {"test": "stats"}
        assert status['product_stats'] == {"products": 5}
    
    def test_run_not_initialized(self):
        """Test running application that's not initialized."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        
        # Should log error and return without running
        app.run()
        
        # No exception should be raised
    
    @patch('main.PriceMonitorApplication.shutdown')
    def test_run_with_flask_app(self, mock_shutdown):
        """Test running application with Flask app."""
        app = PriceMonitorApplication(config_path=self.config_path)
        app._setup_logging()
        app._load_configuration()
        app._is_running = True
        
        # Mock Flask app
        app.flask_app = Mock()
        app.flask_app.run.side_effect = KeyboardInterrupt()
        
        app.run(debug=True)
        
        # Verify Flask app was called with correct parameters
        app.flask_app.run.assert_called_once_with(
            host='0.0.0.0', 
            port=5000, 
            debug=True
        )
        mock_shutdown.assert_called_once()


class TestMainFunction:
    """Test cases for the main function."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.properties")
        
        # Create a test configuration file
        config_content = """
[database]
path = test_database.db

[email]
smtp_server = smtp.test.com
smtp_port = 587
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30

[security]
enable_mtls = false
api_port = 5000

[app]
log_level = INFO
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('sys.argv', ['main.py', '--config', 'test_config.properties', '--check-config'])
    @patch('main.PriceMonitorApplication')
    def test_main_check_config(self, mock_app_class):
        """Test main function with --check-config flag."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_app.get_status.return_value = {
            'config_path': 'test_config.properties',
            'database_path': 'test.db',
            'mtls_enabled': False,
            'email_enabled': True
        }
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        mock_app.initialize.assert_called_once()
        mock_app.get_status.assert_called_once()
    
    @patch('sys.argv', ['main.py', '--config', 'test_config.properties', '--test-email'])
    @patch('main.PriceMonitorApplication')
    def test_main_test_email_success(self, mock_app_class):
        """Test main function with --test-email flag (success)."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_email_service = Mock()
        mock_email_service.send_test_notification.return_value = Mock(success=True)
        mock_app.email_service = mock_email_service
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        mock_email_service.send_test_notification.assert_called_once()
    
    @patch('sys.argv', ['main.py', '--config', 'test_config.properties', '--test-email'])
    @patch('main.PriceMonitorApplication')
    def test_main_test_email_failure(self, mock_app_class):
        """Test main function with --test-email flag (failure)."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_email_service = Mock()
        mock_email_service.send_test_notification.return_value = Mock(
            success=False, 
            message="Email test failed"
        )
        mock_app.email_service = mock_email_service
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['main.py', '--config', 'test_config.properties', '--test-email'])
    @patch('main.PriceMonitorApplication')
    def test_main_test_email_no_service(self, mock_app_class):
        """Test main function with --test-email flag when email service unavailable."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_app.email_service = None
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['main.py', '--config', 'test_config.properties'])
    @patch('main.PriceMonitorApplication')
    def test_main_initialization_failure(self, mock_app_class):
        """Test main function with initialization failure."""
        mock_app = Mock()
        mock_app.initialize.return_value = False
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['main.py', '--host', '127.0.0.1', '--port', '8080', '--debug'])
    @patch('main.PriceMonitorApplication')
    def test_main_run_with_args(self, mock_app_class):
        """Test main function with custom host, port, and debug."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_app.run.side_effect = KeyboardInterrupt()
        mock_app_class.return_value = mock_app
        
        main()
        
        mock_app.run.assert_called_once_with(host='127.0.0.1', port=8080, debug=True)
    
    @patch('sys.argv', ['main.py'])
    @patch('main.PriceMonitorApplication')
    def test_main_keyboard_interrupt(self, mock_app_class):
        """Test main function handling keyboard interrupt."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_app.run.side_effect = KeyboardInterrupt()
        mock_app_class.return_value = mock_app
        
        # Should not raise SystemExit
        main()
        
        mock_app.run.assert_called_once()
    
    @patch('sys.argv', ['main.py'])
    @patch('main.PriceMonitorApplication')
    def test_main_application_error(self, mock_app_class):
        """Test main function handling application error."""
        mock_app = Mock()
        mock_app.initialize.return_value = True
        mock_app.run.side_effect = Exception("Application error")
        mock_app_class.return_value = mock_app
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1


if __name__ == '__main__':
    pytest.main([__file__])