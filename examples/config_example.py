#!/usr/bin/env python3
"""
Example script demonstrating the configuration management system.
"""
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.config_service import ConfigService
from src.models.config import Config


def main():
    """Demonstrate configuration loading and validation."""
    config_service = ConfigService()
    
    print("=== Price Monitor Configuration System Demo ===\n")
    
    # Example 1: Create a default configuration file
    print("1. Creating default configuration file...")
    default_config_path = "config/example.properties"
    
    try:
        config_service.create_default_config_file(default_config_path)
        print(f"✓ Created default configuration at: {default_config_path}")
    except Exception as e:
        print(f"✗ Failed to create default config: {e}")
    
    # Example 2: Load configuration with validation
    print("\n2. Loading configuration...")
    
    try:
        config = config_service.load_config(default_config_path)
        print("✓ Configuration loaded successfully!")
        
        # Display some key settings
        print(f"  - Database path: {config.database_path}")
        print(f"  - SMTP server: {config.smtp_server}")
        print(f"  - Check frequency: {config.check_frequency_hours} hours")
        print(f"  - mTLS enabled: {config.enable_mtls}")
        print(f"  - AI parsing enabled: {config.enable_ai_parsing}")
        
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
    
    # Example 3: Demonstrate validation
    print("\n3. Testing configuration validation...")
    
    # Create a config with validation issues
    test_config = Config(
        smtp_server="",  # Missing required setting
        recipient_email="invalid-email",  # Invalid email format
        enable_mtls=True,  # mTLS enabled but no certificates
        server_cert_path="nonexistent.crt"
    )
    
    validation_result = config_service.validate_config(test_config)
    
    if validation_result.has_errors():
        print("✗ Configuration has validation errors:")
        for error in validation_result.errors:
            print(f"    - {error}")
    
    if validation_result.has_warnings():
        print("⚠ Configuration has warnings:")
        for warning in validation_result.warnings:
            print(f"    - {warning}")
    
    # Example 4: Show a valid minimal configuration
    print("\n4. Creating minimal valid configuration...")
    
    minimal_config = Config(
        smtp_server="smtp.example.com",
        smtp_username="user@example.com",
        smtp_password="password123",
        recipient_email="alerts@example.com"
    )
    
    minimal_validation = config_service.validate_config(minimal_config)
    
    if minimal_validation.is_valid:
        print("✓ Minimal configuration is valid!")
        print(f"  - Will check prices every {minimal_config.check_frequency_hours} hours")
        print(f"  - Will send notifications to: {minimal_config.recipient_email}")
    else:
        print("✗ Minimal configuration is invalid")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()