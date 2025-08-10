"""
Configuration data models for the price monitoring application.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Config:
    """Main configuration class containing all application settings."""
    
    # Database settings
    database_path: str = "data/database.db"
    
    # Email settings
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    recipient_email: str = ""
    
    # Monitoring settings
    check_frequency_hours: int = 24
    max_retry_attempts: int = 3
    request_timeout_seconds: int = 30
    
    # AI/Parsing settings
    ai_api_key: Optional[str] = None
    ai_api_endpoint: Optional[str] = None
    enable_ai_parsing: bool = False
    
    # Security settings (mTLS)
    enable_mtls: bool = False
    server_cert_path: str = "certs/server.crt"
    server_key_path: str = "certs/server.key"
    ca_cert_path: str = "certs/ca.crt"
    client_cert_required: bool = True
    api_port: int = 5000
    
    # Application settings
    log_level: str = "INFO"
    log_file_path: str = "logs/price_monitor.log"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_types()
    
    def _validate_types(self):
        """Ensure all configuration values have correct types."""
        if not isinstance(self.smtp_port, int) or self.smtp_port <= 0:
            raise ValueError("smtp_port must be a positive integer")
        
        if not isinstance(self.check_frequency_hours, int) or self.check_frequency_hours <= 0:
            raise ValueError("check_frequency_hours must be a positive integer")
        
        if not isinstance(self.max_retry_attempts, int) or self.max_retry_attempts < 0:
            raise ValueError("max_retry_attempts must be a non-negative integer")
        
        if not isinstance(self.request_timeout_seconds, int) or self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be a positive integer")
        
        if not isinstance(self.api_port, int) or not (1 <= self.api_port <= 65535):
            raise ValueError("api_port must be an integer between 1 and 65535")
        
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("log_level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")


@dataclass
class ConfigValidationError:
    """Represents a configuration validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning
    
    def __str__(self):
        return f"{self.severity.upper()}: {self.field} - {self.message}"


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: list[ConfigValidationError]
    warnings: list[ConfigValidationError]
    
    def __post_init__(self):
        """Separate errors and warnings."""
        all_issues = self.errors + self.warnings
        self.errors = [e for e in all_issues if e.severity == "error"]
        self.warnings = [e for e in all_issues if e.severity == "warning"]
    
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0
    
    def get_error_summary(self) -> str:
        """Get a formatted summary of all errors and warnings."""
        lines = []
        
        if self.errors:
            lines.append("Configuration Errors:")
            for error in self.errors:
                lines.append(f"  - {error}")
        
        if self.warnings:
            lines.append("Configuration Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        
        return "\n".join(lines) if lines else "Configuration is valid"