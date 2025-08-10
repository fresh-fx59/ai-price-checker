"""
Configuration service for loading and validating application settings.
"""
import os
import configparser
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from ..models.config import Config, ConfigValidationError, ConfigValidationResult


class ConfigService:
    """Service for loading and validating application configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self._config = None
        if config_path:
            self._config = self.load_config(config_path)
    
    def get_config(self) -> Config:
        """
        Get the loaded configuration.
        
        Returns:
            Config object
            
        Raises:
            ValueError: If no configuration has been loaded
        """
        if self._config is None:
            raise ValueError("No configuration loaded. Call load_config() first.")
        return self._config
    
    def load_config(self, config_path: str) -> Config:
        """
        Load configuration from a property file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Config object with loaded settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid or has validation errors
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load configuration from file
        config_data = self._load_config_file(config_path)
        
        # Create Config object
        config = self._create_config_from_data(config_data)
        
        # Validate configuration
        validation_result = self.validate_config(config)
        
        if validation_result.has_errors():
            error_summary = validation_result.get_error_summary()
            raise ValueError(f"Configuration validation failed:\n{error_summary}")
        
        # Log warnings if any
        if validation_result.has_warnings():
            warning_summary = validation_result.get_error_summary()
            self.logger.warning(f"Configuration warnings:\n{warning_summary}")
        
        # Store the loaded config
        self._config = config
        return config
    
    def _load_config_file(self, config_path: str) -> Dict[str, Any]:
        """Load configuration data from file."""
        config_parser = configparser.ConfigParser()
        
        try:
            config_parser.read(config_path)
        except configparser.Error as e:
            raise ValueError(f"Failed to parse configuration file: {e}")
        
        # Convert to flat dictionary
        config_data = {}
        for section in config_parser.sections():
            for key, value in config_parser.items(section):
                # Use section.key format for namespacing
                config_key = f"{section}.{key}" if section != "DEFAULT" else key
                config_data[config_key] = value
        
        # Also include DEFAULT section items without prefix
        if config_parser.has_section("DEFAULT") or config_parser.defaults():
            for key, value in config_parser.defaults().items():
                if key not in config_data:
                    config_data[key] = value
        
        return config_data
    
    def _create_config_from_data(self, config_data: Dict[str, Any]) -> Config:
        """Create Config object from configuration data."""
        # Map configuration keys to Config fields
        config_mapping = {
            # Database settings
            "database.path": ("database_path", str),
            "database_path": ("database_path", str),
            
            # Email settings
            "email.smtp_server": ("smtp_server", str),
            "smtp_server": ("smtp_server", str),
            "email.smtp_port": ("smtp_port", int),
            "smtp_port": ("smtp_port", int),
            "email.username": ("smtp_username", str),
            "smtp_username": ("smtp_username", str),
            "email.password": ("smtp_password", str),
            "smtp_password": ("smtp_password", str),
            "email.recipient": ("recipient_email", str),
            "recipient_email": ("recipient_email", str),
            
            # Monitoring settings
            "monitoring.check_frequency_hours": ("check_frequency_hours", int),
            "check_frequency_hours": ("check_frequency_hours", int),
            "monitoring.max_retry_attempts": ("max_retry_attempts", int),
            "max_retry_attempts": ("max_retry_attempts", int),
            "monitoring.request_timeout_seconds": ("request_timeout_seconds", int),
            "request_timeout_seconds": ("request_timeout_seconds", int),
            
            # AI/Parsing settings
            "ai.api_key": ("ai_api_key", str),
            "ai_api_key": ("ai_api_key", str),
            "ai.api_endpoint": ("ai_api_endpoint", str),
            "ai_api_endpoint": ("ai_api_endpoint", str),
            "ai.enable_parsing": ("enable_ai_parsing", bool),
            "enable_ai_parsing": ("enable_ai_parsing", bool),
            
            # Security settings
            "security.enable_mtls": ("enable_mtls", bool),
            "enable_mtls": ("enable_mtls", bool),
            "security.server_cert_path": ("server_cert_path", str),
            "server_cert_path": ("server_cert_path", str),
            "security.server_key_path": ("server_key_path", str),
            "server_key_path": ("server_key_path", str),
            "security.ca_cert_path": ("ca_cert_path", str),
            "ca_cert_path": ("ca_cert_path", str),
            "security.client_cert_required": ("client_cert_required", bool),
            "client_cert_required": ("client_cert_required", bool),
            "security.api_port": ("api_port", int),
            "api_port": ("api_port", int),
            
            # Application settings
            "app.log_level": ("log_level", str),
            "log_level": ("log_level", str),
            "app.log_file_path": ("log_file_path", str),
            "log_file_path": ("log_file_path", str),
        }
        
        # Start with default Config
        config_kwargs = {}
        
        # Apply configuration values
        for config_key, raw_value in config_data.items():
            if config_key in config_mapping:
                field_name, field_type = config_mapping[config_key]
                try:
                    # Convert value to appropriate type
                    if field_type == bool:
                        value = self._parse_bool(raw_value)
                    elif field_type == int:
                        value = int(raw_value)
                    elif field_type == str:
                        value = str(raw_value) if raw_value is not None else None
                    else:
                        value = raw_value
                    
                    config_kwargs[field_name] = value
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value for {config_key}: {raw_value} ({e})")
        
        return Config(**config_kwargs)
    
    def _parse_bool(self, value: Any) -> bool:
        """Parse boolean value from string."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on", "enabled")
        return bool(value)
    
    def validate_config(self, config: Config) -> ConfigValidationResult:
        """
        Validate configuration settings.
        
        Args:
            config: Configuration object to validate
            
        Returns:
            ConfigValidationResult with validation results
        """
        errors = []
        warnings = []
        
        # Validate required email settings
        if not config.smtp_server:
            errors.append(ConfigValidationError(
                "smtp_server", 
                "SMTP server is required for email notifications"
            ))
        
        if not config.smtp_username:
            errors.append(ConfigValidationError(
                "smtp_username", 
                "SMTP username is required for email authentication"
            ))
        
        if not config.smtp_password:
            errors.append(ConfigValidationError(
                "smtp_password", 
                "SMTP password is required for email authentication"
            ))
        
        if not config.recipient_email:
            errors.append(ConfigValidationError(
                "recipient_email", 
                "Recipient email is required for notifications"
            ))
        elif "@" not in config.recipient_email:
            errors.append(ConfigValidationError(
                "recipient_email", 
                "Recipient email must be a valid email address"
            ))
        
        # Validate database path
        if config.database_path:
            db_dir = os.path.dirname(config.database_path)
            if db_dir and not os.path.exists(db_dir):
                warnings.append(ConfigValidationError(
                    "database_path", 
                    f"Database directory does not exist: {db_dir}",
                    "warning"
                ))
        
        # Validate mTLS settings if enabled
        if config.enable_mtls:
            cert_files = [
                ("server_cert_path", config.server_cert_path),
                ("server_key_path", config.server_key_path),
                ("ca_cert_path", config.ca_cert_path)
            ]
            
            for field_name, cert_path in cert_files:
                if not cert_path:
                    errors.append(ConfigValidationError(
                        field_name, 
                        f"{field_name} is required when mTLS is enabled"
                    ))
                elif not os.path.exists(cert_path):
                    errors.append(ConfigValidationError(
                        field_name, 
                        f"Certificate file not found: {cert_path}"
                    ))
        
        # Validate AI settings if enabled
        if config.enable_ai_parsing:
            if not config.ai_api_key:
                warnings.append(ConfigValidationError(
                    "ai_api_key", 
                    "AI API key is recommended when AI parsing is enabled",
                    "warning"
                ))
        
        # Validate log file path
        if config.log_file_path:
            log_dir = os.path.dirname(config.log_file_path)
            if log_dir and not os.path.exists(log_dir):
                warnings.append(ConfigValidationError(
                    "log_file_path", 
                    f"Log directory does not exist: {log_dir}",
                    "warning"
                ))
        
        # Validate monitoring settings
        if config.check_frequency_hours <= 1:
            warnings.append(ConfigValidationError(
                "check_frequency_hours", 
                "Check frequency of 1 hour or less may cause excessive requests",
                "warning"
            ))
        
        if config.request_timeout_seconds > 300:
            warnings.append(ConfigValidationError(
                "request_timeout_seconds", 
                "Request timeout over 5 minutes may cause performance issues",
                "warning"
            ))
        
        all_issues = errors + warnings
        return ConfigValidationResult(
            is_valid=len(errors) == 0,
            errors=all_issues,
            warnings=[]
        )
    
    def create_default_config_file(self, config_path: str) -> None:
        """
        Create a default configuration file with example settings.
        
        Args:
            config_path: Path where to create the config file
        """
        config_content = """# Price Monitor Configuration File

[database]
path = data/database.db

[email]
smtp_server = smtp.gmail.com
smtp_port = 587
username = your-email@gmail.com
password = your-app-password
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30

[ai]
api_key = 
api_endpoint = 
enable_parsing = false

[security]
enable_mtls = false
server_cert_path = certs/server.crt
server_key_path = certs/server.key
ca_cert_path = certs/ca.crt
client_cert_required = true
api_port = 5000

[app]
log_level = INFO
log_file_path = logs/price_monitor.log
"""
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        self.logger.info(f"Created default configuration file: {config_path}")