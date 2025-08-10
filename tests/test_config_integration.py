"""
Integration tests for configuration management system.
"""
import unittest
import tempfile
import os
from pathlib import Path

from src.services.config_service import ConfigService


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for the complete configuration system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_service = ConfigService()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_configuration_workflow(self):
        """Test the complete configuration loading and validation workflow."""
        # Create a comprehensive configuration file
        config_content = """# Complete Price Monitor Configuration

[database]
path = /app/data/price_monitor.db

[email]
smtp_server = smtp.gmail.com
smtp_port = 587
username = monitor@example.com
password = secure_app_password
recipient = alerts@example.com

[monitoring]
check_frequency_hours = 6
max_retry_attempts = 3
request_timeout_seconds = 45

[ai]
api_key = sk-test-api-key-12345
api_endpoint = https://api.openai.com/v1
enable_parsing = true

[security]
enable_mtls = false
server_cert_path = /app/certs/server.crt
server_key_path = /app/certs/server.key
ca_cert_path = /app/certs/ca.crt
client_cert_required = true
api_port = 8443

[app]
log_level = DEBUG
log_file_path = /app/logs/price_monitor.log
"""
        
        config_path = os.path.join(self.temp_dir, "complete.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Load and validate configuration
        config = self.config_service.load_config(config_path)
        
        # Verify all settings were loaded correctly
        # Database settings
        self.assertEqual(config.database_path, "/app/data/price_monitor.db")
        
        # Email settings
        self.assertEqual(config.smtp_server, "smtp.gmail.com")
        self.assertEqual(config.smtp_port, 587)
        self.assertEqual(config.smtp_username, "monitor@example.com")
        self.assertEqual(config.smtp_password, "secure_app_password")
        self.assertEqual(config.recipient_email, "alerts@example.com")
        
        # Monitoring settings
        self.assertEqual(config.check_frequency_hours, 6)
        self.assertEqual(config.max_retry_attempts, 3)
        self.assertEqual(config.request_timeout_seconds, 45)
        
        # AI settings
        self.assertEqual(config.ai_api_key, "sk-test-api-key-12345")
        self.assertEqual(config.ai_api_endpoint, "https://api.openai.com/v1")
        self.assertTrue(config.enable_ai_parsing)
        
        # Security settings
        self.assertFalse(config.enable_mtls)
        self.assertEqual(config.server_cert_path, "/app/certs/server.crt")
        self.assertEqual(config.server_key_path, "/app/certs/server.key")
        self.assertEqual(config.ca_cert_path, "/app/certs/ca.crt")
        self.assertTrue(config.client_cert_required)
        self.assertEqual(config.api_port, 8443)
        
        # Application settings
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.log_file_path, "/app/logs/price_monitor.log")
    
    def test_minimal_valid_configuration(self):
        """Test loading a minimal but valid configuration."""
        config_content = """[email]
smtp_server = smtp.test.com
username = test@example.com
password = testpass
recipient = user@example.com
"""
        
        config_path = os.path.join(self.temp_dir, "minimal.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Should load successfully with defaults for other settings
        config = self.config_service.load_config(config_path)
        
        # Verify required settings are loaded
        self.assertEqual(config.smtp_server, "smtp.test.com")
        self.assertEqual(config.smtp_username, "test@example.com")
        self.assertEqual(config.smtp_password, "testpass")
        self.assertEqual(config.recipient_email, "user@example.com")
        
        # Verify defaults are used for other settings
        self.assertEqual(config.database_path, "data/database.db")
        self.assertEqual(config.check_frequency_hours, 24)
        self.assertFalse(config.enable_mtls)
        self.assertFalse(config.enable_ai_parsing)
    
    def test_configuration_error_handling(self):
        """Test comprehensive error handling in configuration loading."""
        # Test with type conversion error first
        config_content = """[email]
smtp_port = not_a_number
"""
        
        config_path = os.path.join(self.temp_dir, "invalid_type.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        with self.assertRaises(ValueError) as cm:
            self.config_service.load_config(config_path)
        
        error_message = str(cm.exception)
        self.assertIn("Invalid value for email.smtp_port", error_message)
        
        # Test with validation errors
        config_content2 = """[email]
smtp_server = 
username = 
password = 
recipient = not-an-email
"""
        
        config_path2 = os.path.join(self.temp_dir, "invalid_validation.conf")
        with open(config_path2, 'w') as f:
            f.write(config_content2)
        
        with self.assertRaises(ValueError) as cm:
            self.config_service.load_config(config_path2)
        
        error_message = str(cm.exception)
        self.assertIn("Configuration validation failed", error_message)
        
        # Should contain multiple error messages
        self.assertIn("smtp_server", error_message)
        self.assertIn("smtp_username", error_message)
        self.assertIn("smtp_password", error_message)
        self.assertIn("valid email address", error_message)
    
    def test_default_config_file_creation_and_loading(self):
        """Test creating and loading a default configuration file."""
        config_path = os.path.join(self.temp_dir, "default.conf")
        
        # Create default configuration file
        self.config_service.create_default_config_file(config_path)
        
        # Verify file exists
        self.assertTrue(os.path.exists(config_path))
        
        # The default config has placeholder values that are technically valid
        # Let's verify we can load it (it will have warnings about directories)
        config = self.config_service.load_config(config_path)
        
        # Verify the placeholder values are loaded
        self.assertEqual(config.smtp_username, "your-email@gmail.com")
        self.assertEqual(config.smtp_password, "your-app-password")
        self.assertEqual(config.recipient_email, "recipient@example.com")
        
        # Modify the default config to add required settings
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Replace placeholder values with real ones
        content = content.replace("your-email@gmail.com", "test@example.com")
        content = content.replace("your-app-password", "testpass")
        content = content.replace("recipient@example.com", "alerts@example.com")
        
        with open(config_path, 'w') as f:
            f.write(content)
        
        # Now it should load successfully
        config = self.config_service.load_config(config_path)
        self.assertEqual(config.smtp_username, "test@example.com")
        self.assertEqual(config.recipient_email, "alerts@example.com")


if __name__ == '__main__':
    unittest.main()