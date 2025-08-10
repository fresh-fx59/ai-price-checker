"""
Main application entry point for the Price Monitor system.
Handles application initialization, service dependency injection, and graceful shutdown.
"""

import os
import sys
import signal
import logging
import threading
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

from .services.config_service import ConfigService
from .services.product_service import ProductService
from .services.parser_service import ParserService
from .services.web_scraping_service import WebScrapingService
from .services.price_monitor_service import PriceMonitorService
from .services.email_service import EmailService
from .models.database import DatabaseManager
from .app import SecureFlaskApp


class PriceMonitorApplication:
    """Main application class for the Price Monitor system."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Price Monitor application.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.config_path = config_path or self._get_default_config_path()
        self.logger = None
        self.config_service = None
        self.config = None
        self.db_manager = None
        self.product_service = None
        self.web_scraping_service = None
        self.parser_service = None
        self.email_service = None
        self.price_monitor_service = None
        self.flask_app = None
        
        # Shutdown handling
        self._shutdown_event = threading.Event()
        self._shutdown_handlers = []
        self._is_running = False
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        # Look for config in several locations
        possible_paths = [
            "config/default.properties",
            "config.properties",
            os.path.expanduser("~/.price_monitor/config.properties"),
            "/etc/price_monitor/config.properties"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Return the first option as default
        return possible_paths[0]
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            if self.logger:
                self.logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
            else:
                print(f"Received {signal_name} signal, initiating graceful shutdown...")
            self.shutdown()
        
        # Handle common shutdown signals
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
        
        # Handle SIGHUP for configuration reload (Unix only)
        if hasattr(signal, 'SIGHUP'):
            def reload_handler(signum, frame):
                if self.logger:
                    self.logger.info("Received SIGHUP signal, reloading configuration...")
                self._reload_configuration()
            
            signal.signal(signal.SIGHUP, reload_handler)
    
    def initialize(self) -> bool:
        """
        Initialize all application components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize logging first
            self._setup_logging()
            
            self.logger.info("Starting Price Monitor application initialization...")
            
            # Load configuration
            if not self._load_configuration():
                return False
            
            # Initialize database
            if not self._initialize_database():
                return False
            
            # Initialize services
            if not self._initialize_services():
                return False
            
            # Initialize Flask application
            if not self._initialize_flask_app():
                return False
            
            # Start price monitoring scheduler
            if not self._start_monitoring_scheduler():
                return False
            
            self.logger.info("Price Monitor application initialized successfully")
            self._is_running = True
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize application: {str(e)}")
            else:
                print(f"Failed to initialize application: {str(e)}")
            return False
    
    def _setup_logging(self):
        """Setup application logging."""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/price_monitor.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging initialized")
    
    def _load_configuration(self) -> bool:
        """Load application configuration."""
        try:
            self.logger.info(f"Loading configuration from: {self.config_path}")
            
            # Create config service
            self.config_service = ConfigService()
            
            # Check if config file exists
            if not os.path.exists(self.config_path):
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self.logger.info("Creating default configuration file...")
                
                # Create directory if needed
                config_dir = os.path.dirname(self.config_path)
                if config_dir:
                    os.makedirs(config_dir, exist_ok=True)
                
                # Create default config
                self.config_service.create_default_config_file(self.config_path)
                self.logger.info(f"Default configuration created at: {self.config_path}")
                self.logger.info("Please edit the configuration file and restart the application")
                return False
            
            # Load configuration
            self.config = self.config_service.load_config(self.config_path)
            
            # Update logging level if specified in config
            if hasattr(self.config, 'log_level'):
                log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
                logging.getLogger().setLevel(log_level)
                self.logger.info(f"Log level set to: {self.config.log_level}")
            
            # Update log file path if specified
            if hasattr(self.config, 'log_file_path') and self.config.log_file_path:
                # Create log directory
                log_dir = os.path.dirname(self.config.log_file_path)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                
                # Add file handler for the configured log file
                file_handler = logging.FileHandler(self.config.log_file_path)
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                logging.getLogger().addHandler(file_handler)
                self.logger.info(f"Additional log file: {self.config.log_file_path}")
            
            self.logger.info("Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            return False
    
    def _initialize_database(self) -> bool:
        """Initialize database connection and schema."""
        try:
            self.logger.info("Initializing database...")
            
            # Create data directory if needed
            db_dir = os.path.dirname(self.config.database_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            # Initialize database manager
            self.db_manager = DatabaseManager(self.config.database_path)
            
            # Initialize database schema
            self.db_manager.initialize_database()
            
            self.logger.info(f"Database initialized: {self.config.database_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            return False
    
    def _initialize_services(self) -> bool:
        """Initialize all application services."""
        try:
            self.logger.info("Initializing services...")
            
            # Initialize product service
            self.product_service = ProductService(self.db_manager)
            self.logger.debug("Product service initialized")
            
            # Initialize web scraping service
            self.web_scraping_service = WebScrapingService(
                timeout=self.config.request_timeout_seconds,
                max_retries=self.config.max_retry_attempts
            )
            self.logger.debug("Web scraping service initialized")
            
            # Initialize parser service
            self.parser_service = ParserService(
                ai_api_key=getattr(self.config, 'ai_api_key', None),
                ai_api_endpoint=getattr(self.config, 'ai_api_endpoint', None),
                enable_ai_parsing=getattr(self.config, 'enable_ai_parsing', False)
            )
            self.logger.debug("Parser service initialized")
            
            # Initialize email service
            try:
                self.email_service = EmailService(self.config)
                
                # Test email connection
                test_result = self.email_service.test_email_connection()
                if test_result.success:
                    self.logger.info("Email service initialized and connection tested successfully")
                else:
                    self.logger.warning(f"Email service initialized but connection test failed: {test_result.message}")
                    
            except Exception as e:
                self.logger.warning(f"Email service initialization failed: {str(e)}")
                self.logger.warning("Continuing without email notifications")
                self.email_service = None
            
            # Initialize price monitor service
            self.price_monitor_service = PriceMonitorService(
                product_service=self.product_service,
                parser_service=self.parser_service,
                web_scraping_service=self.web_scraping_service,
                email_service=self.email_service,
                max_concurrent_checks=5,
                check_timeout=self.config.request_timeout_seconds,
                max_retries=self.config.max_retry_attempts
            )
            self.logger.debug("Price monitor service initialized")
            
            self.logger.info("All services initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {str(e)}")
            return False
    
    def _initialize_flask_app(self) -> bool:
        """Initialize Flask web application."""
        try:
            self.logger.info("Initializing Flask application...")
            
            # Create Flask app with all services
            self.flask_app = SecureFlaskApp(self.config_service)
            
            self.logger.info("Flask application initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Flask application: {str(e)}")
            return False
    
    def _start_monitoring_scheduler(self) -> bool:
        """Start the price monitoring scheduler."""
        try:
            self.logger.info("Starting price monitoring scheduler...")
            
            # Calculate check time based on frequency
            check_time = "09:00"  # Default to 9 AM
            
            # Start the scheduler
            self.price_monitor_service.start_scheduler(check_time)
            
            # Register shutdown handler for scheduler
            self._shutdown_handlers.append(self.price_monitor_service.stop_scheduler)
            
            self.logger.info(f"Price monitoring scheduler started (daily at {check_time})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring scheduler: {str(e)}")
            return False
    
    def run(self, host: str = '0.0.0.0', port: Optional[int] = None, debug: bool = False):
        """
        Run the application.
        
        Args:
            host: Host to bind to
            port: Port to bind to (uses config if not specified)
            debug: Enable debug mode
        """
        if not self._is_running:
            self.logger.error("Application not initialized. Call initialize() first.")
            return
        
        try:
            if port is None:
                port = self.config.api_port
            
            self.logger.info(f"Starting Price Monitor application on {host}:{port}")
            self.logger.info(f"mTLS enabled: {self.config.enable_mtls}")
            
            # Run Flask application
            self.flask_app.run(host=host, port=port, debug=debug)
            
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Application error: {str(e)}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Perform graceful shutdown of the application."""
        if not self._is_running:
            return
        
        self.logger.info("Initiating graceful shutdown...")
        self._shutdown_event.set()
        self._is_running = False
        
        # Execute shutdown handlers in reverse order
        for handler in reversed(self._shutdown_handlers):
            try:
                handler()
            except Exception as e:
                self.logger.error(f"Error during shutdown: {str(e)}")
        
        # Close database connections
        if self.db_manager:
            try:
                self.db_manager.close()
                self.logger.info("Database connections closed")
            except Exception as e:
                self.logger.error(f"Error closing database: {str(e)}")
        
        self.logger.info("Graceful shutdown completed")
    
    def _reload_configuration(self):
        """Reload configuration without restarting the application."""
        try:
            self.logger.info("Reloading configuration...")
            
            # Reload configuration
            new_config = self.config_service.load_config(self.config_path)
            
            # Update logging level if changed
            if new_config.log_level != self.config.log_level:
                log_level = getattr(logging, new_config.log_level.upper(), logging.INFO)
                logging.getLogger().setLevel(log_level)
                self.logger.info(f"Log level updated to: {new_config.log_level}")
            
            # Update configuration
            self.config = new_config
            
            # Restart scheduler if frequency changed
            if hasattr(new_config, 'check_frequency_hours'):
                self.price_monitor_service.stop_scheduler()
                time.sleep(1)  # Brief pause
                self.price_monitor_service.start_scheduler()
                self.logger.info("Price monitoring scheduler restarted with new configuration")
            
            self.logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {str(e)}")
    
    def is_running(self) -> bool:
        """Check if the application is running."""
        return self._is_running
    
    def get_status(self) -> dict:
        """Get application status information."""
        status = {
            'running': self._is_running,
            'config_path': self.config_path,
            'database_path': self.config.database_path if self.config else None,
            'mtls_enabled': self.config.enable_mtls if self.config else False,
            'email_enabled': self.email_service is not None,
            'scheduler_running': self.price_monitor_service.is_scheduler_running() if self.price_monitor_service else False,
            'startup_time': datetime.now().isoformat()
        }
        
        if self.price_monitor_service:
            status['monitoring_stats'] = self.price_monitor_service.get_monitoring_stats()
        
        if self.product_service:
            status['product_stats'] = self.product_service.get_product_statistics()
        
        return status


def main():
    """Main entry point for the application."""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Price Monitor Application')
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, help='Port to bind to (uses config if not specified)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--check-config', action='store_true', help='Check configuration and exit')
    parser.add_argument('--test-email', action='store_true', help='Test email configuration and exit')
    
    args = parser.parse_args()
    
    # Create application instance
    app = PriceMonitorApplication(config_path=args.config)
    
    # Initialize application
    if not app.initialize():
        print("Failed to initialize application")
        sys.exit(1)
    
    # Handle special modes
    if args.check_config:
        print("Configuration check passed")
        status = app.get_status()
        print(f"Config path: {status['config_path']}")
        print(f"Database path: {status['database_path']}")
        print(f"mTLS enabled: {status['mtls_enabled']}")
        print(f"Email enabled: {status['email_enabled']}")
        sys.exit(0)
    
    if args.test_email:
        if app.email_service:
            print("Testing email configuration...")
            result = app.email_service.send_test_notification()
            if result.success:
                print("Email test successful!")
            else:
                print(f"Email test failed: {result.message}")
                sys.exit(1)
        else:
            print("Email service not available")
            sys.exit(1)
        sys.exit(0)
    
    # Run the application
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Application error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()