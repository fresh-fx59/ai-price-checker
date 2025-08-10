"""
Unit tests for ConfigService and Config models.
"""
import unittest
import tempfile
import os
from pathlib import Path

from src.models.config import Config, ConfigValidationError, ConfigValidationResult
from src.services.config_service import ConfigService


class TestConfig(unittest.TestCase):
    """Test cases for Config data model."""
    
    def test_config_default_values(self):
        """Test that Config has appropriate default values."""
        config = Config()
        
        # Database settings
        self.assertEqual(config.database_path, "data/database.db")
        
        # Email settings
        self.assertEqual(config.smtp_server, "")
        self.assertEqual(config.smtp_port, 587)
        self.assertEqual(config.smtp_username, "")
        self.assertEqual(config.smtp_password, "")
        self.assertEqual(config.recipient_email, "")
        
        # Monitoring settings
        self.assertEqual(config.check_frequency_hours, 24)
        self.assertEqual(config.max_retry_attempts, 3)
        self.assertEqual(config.request_timeout_seconds, 30)
        
        # AI/Parsing settings
        self.assertIsNone(config.ai_api_key)
        self.assertIsNone(config.ai_api_endpoint)
        self.assertFalse(config.enable_ai_parsing)
        
        # Security settings
        self.assertFalse(config.enable_mtls)
        self.assertEqual(config.server_cert_path, "certs/server.crt")
        self.assertEqual(config.server_key_path, "certs/server.key")
        self.assertEqual(config.ca_cert_path, "certs/ca.crt")
        self.assertTrue(config.client_cert_required)
        self.assertEqual(config.api_port, 5000)
        
        # Application settings
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.log_file_path, "logs/price_monitor.log")
    
    def test_config_type_validation(self):
        """Test that Config validates types correctly."""
        # Test invalid smtp_port
        with self.assertRaises(ValueError) as cm:
            Config(smtp_port=-1)
        self.assertIn("smtp_port must be a positive integer", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            Config(smtp_port=0)
        self.assertIn("smtp_port must be a positive integer", str(cm.exception))
        
        # Test invalid check_frequency_hours
        with self.assertRaises(ValueError) as cm:
            Config(check_frequency_hours=0)
        self.assertIn("check_frequency_hours must be a positive integer", str(cm.exception))
        
        # Test invalid max_retry_attempts
        with self.assertRaises(ValueError) as cm:
            Config(max_retry_attempts=-1)
        self.assertIn("max_retry_attempts must be a non-negative integer", str(cm.exception))
        
        # Test invalid request_timeout_seconds
        with self.assertRaises(ValueError) as cm:
            Config(request_timeout_seconds=0)
        self.assertIn("request_timeout_seconds must be a positive integer", str(cm.exception))
        
        # Test invalid api_port
        with self.assertRaises(ValueError) as cm:
            Config(api_port=0)
        self.assertIn("api_port must be an integer between 1 and 65535", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            Config(api_port=70000)
        self.assertIn("api_port must be an integer between 1 and 65535", str(cm.exception))
        
        # Test invalid log_level
        with self.assertRaises(ValueError) as cm:
            Config(log_level="INVALID")
        self.assertIn("log_level must be one of", str(cm.exception))
    
    def test_config_valid_values(self):
        """Test that Config accepts valid values."""
        config = Config(
            smtp_port=25,
            check_frequency_hours=1,
            max_retry_attempts=0,
            request_timeout_seconds=60,
            api_port=8080,
            log_level="DEBUG"
        )
        
        self.assertEqual(config.smtp_port, 25)
        self.assertEqual(config.check_frequency_hours, 1)
        self.assertEqual(config.max_retry_attempts, 0)
        self.assertEqual(config.request_timeout_seconds, 60)
        self.assertEqual(config.api_port, 8080)
        self.assertEqual(config.log_level, "DEBUG")


class TestConfigValidationError(unittest.TestCase):
    """Test cases for ConfigValidationError."""
    
    def test_validation_error_creation(self):
        """Test creating validation errors."""
        error = ConfigValidationError("test_field", "Test message")
        self.assertEqual(error.field, "test_field")
        self.assertEqual(error.message, "Test message")
        self.assertEqual(error.severity, "error")
        
        warning = ConfigValidationError("test_field", "Test warning", "warning")
        self.assertEqual(warning.severity, "warning")
    
    def test_validation_error_string_representation(self):
        """Test string representation of validation errors."""
        error = ConfigValidationError("test_field", "Test message")
        self.assertEqual(str(error), "ERROR: test_field - Test message")
        
        warning = ConfigValidationError("test_field", "Test warning", "warning")
        self.assertEqual(str(warning), "WARNING: test_field - Test warning")


class TestConfigValidationResult(unittest.TestCase):
    """Test cases for ConfigValidationResult."""
    
    def test_validation_result_with_errors(self):
        """Test validation result with errors."""
        errors = [
            ConfigValidationError("field1", "Error 1"),
            ConfigValidationError("field2", "Warning 1", "warning")
        ]
        
        result = ConfigValidationResult(is_valid=False, errors=errors, warnings=[])
        
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors())
        self.assertTrue(result.has_warnings())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 1)
    
    def test_validation_result_summary(self):
        """Test validation result error summary."""
        errors = [
            ConfigValidationError("field1", "Error 1"),
            ConfigValidationError("field2", "Warning 1", "warning")
        ]
        
        result = ConfigValidationResult(is_valid=False, errors=errors, warnings=[])
        summary = result.get_error_summary()
        
        self.assertIn("Configuration Errors:", summary)
        self.assertIn("Configuration Warnings:", summary)
        self.assertIn("field1 - Error 1", summary)
        self.assertIn("field2 - Warning 1", summary)
    
    def test_validation_result_valid(self):
        """Test validation result when valid."""
        result = ConfigValidationResult(is_valid=True, errors=[], warnings=[])
        
        self.assertTrue(result.is_valid)
        self.assertFalse(result.has_errors())
        self.assertFalse(result.has_warnings())
        self.assertEqual(result.get_error_summary(), "Configuration is valid")


class TestConfigService(unittest.TestCase):
    """Test cases for ConfigService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_service = ConfigService()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        non_existent_path = os.path.join(self.temp_dir, "nonexistent.conf")
        
        with self.assertRaises(FileNotFoundError) as cm:
            self.config_service.load_config(non_existent_path)
        
        self.assertIn("Configuration file not found", str(cm.exception))
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_content = """[email]
smtp_server = test.smtp.com
smtp_port = 25
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 12
max_retry_attempts = 5

[security]
enable_mtls = false
api_port = 8080
"""
        
        config_path = os.path.join(self.temp_dir, "test.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        config = self.config_service.load_config(config_path)
        
        # Verify loaded values
        self.assertEqual(config.smtp_server, "test.smtp.com")
        self.assertEqual(config.smtp_port, 25)
        self.assertEqual(config.smtp_username, "test@example.com")
        self.assertEqual(config.smtp_password, "testpass")
        self.assertEqual(config.recipient_email, "recipient@example.com")
        self.assertEqual(config.check_frequency_hours, 12)
        self.assertEqual(config.max_retry_attempts, 5)
        self.assertFalse(config.enable_mtls)
        self.assertEqual(config.api_port, 8080)
    
    def test_load_config_with_validation_errors(self):
        """Test loading config that fails validation."""
        config_content = """[email]
smtp_server = 
username = 
password = 
recipient = invalid-email
"""
        
        config_path = os.path.join(self.temp_dir, "invalid.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        with self.assertRaises(ValueError) as cm:
            self.config_service.load_config(config_path)
        
        error_message = str(cm.exception)
        self.assertIn("Configuration validation failed", error_message)
        self.assertIn("smtp_server", error_message)
        self.assertIn("smtp_username", error_message)
    
    def test_parse_bool_values(self):
        """Test boolean parsing from configuration."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("1", True),
            ("on", True),
            ("enabled", True),
            ("false", False),
            ("False", False),
            ("no", False),
            ("0", False),
            ("off", False),
            ("disabled", False),
            (True, True),
            (False, False),
        ]
        
        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                result = self.config_service._parse_bool(input_val)
                self.assertEqual(result, expected)
    
    def test_validate_config_missing_email_settings(self):
        """Test validation with missing email settings."""
        config = Config()  # Default config with empty email settings
        
        result = self.config_service.validate_config(config)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors())
        
        error_fields = [error.field for error in result.errors]
        self.assertIn("smtp_server", error_fields)
        self.assertIn("smtp_username", error_fields)
        self.assertIn("smtp_password", error_fields)
        self.assertIn("recipient_email", error_fields)
    
    def test_validate_config_invalid_email(self):
        """Test validation with invalid email address."""
        config = Config(
            smtp_server="smtp.test.com",
            smtp_username="user",
            smtp_password="pass",
            recipient_email="invalid-email"
        )
        
        result = self.config_service.validate_config(config)
        
        self.assertFalse(result.is_valid)
        error_messages = [error.message for error in result.errors]
        self.assertTrue(any("valid email address" in msg for msg in error_messages))
    
    def test_validate_config_mtls_missing_certs(self):
        """Test validation with mTLS enabled but missing certificates."""
        config = Config(
            smtp_server="smtp.test.com",
            smtp_username="user",
            smtp_password="pass",
            recipient_email="test@example.com",
            enable_mtls=True,
            server_cert_path="nonexistent.crt",
            server_key_path="nonexistent.key",
            ca_cert_path="nonexistent.ca"
        )
        
        result = self.config_service.validate_config(config)
        
        self.assertFalse(result.is_valid)
        error_fields = [error.field for error in result.errors]
        self.assertIn("server_cert_path", error_fields)
        self.assertIn("server_key_path", error_fields)
        self.assertIn("ca_cert_path", error_fields)
    
    def test_validate_config_warnings(self):
        """Test validation warnings for suboptimal settings."""
        config = Config(
            smtp_server="smtp.test.com",
            smtp_username="user",
            smtp_password="pass",
            recipient_email="test@example.com",
            check_frequency_hours=1,  # Valid but low value should trigger a warning
            request_timeout_seconds=400,  # This should trigger a warning
            enable_ai_parsing=True  # Without API key should trigger warning
        )
        
        result = self.config_service.validate_config(config)
        
        # Should be valid but have warnings
        self.assertTrue(result.is_valid)
        self.assertTrue(result.has_warnings())
    
    def test_create_default_config_file(self):
        """Test creating a default configuration file."""
        config_path = os.path.join(self.temp_dir, "default.conf")
        
        self.config_service.create_default_config_file(config_path)
        
        # Verify file was created
        self.assertTrue(os.path.exists(config_path))
        
        # Verify content is valid
        with open(config_path, 'r') as f:
            content = f.read()
        
        self.assertIn("[email]", content)
        self.assertIn("[monitoring]", content)
        self.assertIn("[security]", content)
        self.assertIn("smtp_server", content)
        self.assertIn("enable_mtls", content)
    
    def test_config_with_alternative_key_formats(self):
        """Test configuration loading with different key formats."""
        config_content = """[DEFAULT]
database_path = /custom/db.db
smtp_server = default.smtp.com
log_level = DEBUG

[email]
smtp_port = 465
"""
        
        config_path = os.path.join(self.temp_dir, "alt_format.conf")
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # This should not raise validation errors since we have required email settings
        config_content_complete = """[DEFAULT]
database_path = /custom/db.db
smtp_server = default.smtp.com
smtp_username = user
smtp_password = pass
recipient_email = test@example.com
log_level = DEBUG

[email]
smtp_port = 465
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content_complete)
        
        config = self.config_service.load_config(config_path)
        
        self.assertEqual(config.database_path, "/custom/db.db")
        self.assertEqual(config.smtp_server, "default.smtp.com")
        self.assertEqual(config.smtp_port, 465)
        self.assertEqual(config.log_level, "DEBUG")


if __name__ == '__main__':
    unittest.main()