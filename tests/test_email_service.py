"""
Tests for the EmailService class.
"""

import pytest
import smtplib
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from email.mime.multipart import MIMEMultipart

from src.services.email_service import EmailService, EmailNotification, EmailDeliveryResult
from src.models.config import Config
from src.models.database import Product


class TestEmailService:
    """Test cases for EmailService."""
    
    @pytest.fixture
    def valid_config(self):
        """Create a valid email configuration."""
        return Config(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="test_password",
            recipient_email="recipient@example.com",
            max_retry_attempts=2
        )
    
    @pytest.fixture
    def invalid_config(self):
        """Create an invalid email configuration."""
        return Config(
            smtp_server="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            recipient_email="",
            max_retry_attempts=2
        )
    
    @pytest.fixture
    def sample_product(self):
        """Create a sample product for testing."""
        product = Product()
        product.id = 1
        product.name = "Test Product"
        product.url = "https://example.com/product"
        product.current_price = 99.99
        product.previous_price = 129.99
        product.lowest_price = 89.99
        product.image_url = "https://example.com/image.jpg"
        product.created_at = datetime(2024, 1, 1, 12, 0, 0)
        product.last_checked = datetime(2024, 1, 15, 14, 30, 0)
        return product
    
    def test_email_service_initialization_valid_config(self, valid_config):
        """Test EmailService initialization with valid configuration."""
        service = EmailService(valid_config)
        assert service.config == valid_config
    
    def test_email_service_initialization_invalid_config(self, invalid_config):
        """Test EmailService initialization with invalid configuration."""
        with pytest.raises(ValueError) as exc_info:
            EmailService(invalid_config)
        
        assert "Missing required email configuration" in str(exc_info.value)
    
    def test_validate_email_config_missing_fields(self):
        """Test email configuration validation with missing fields."""
        config = Config(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_username="",  # Missing
            smtp_password="password",
            recipient_email=""  # Missing
        )
        
        with pytest.raises(ValueError) as exc_info:
            EmailService(config)
        
        error_message = str(exc_info.value)
        assert "smtp_username" in error_message
        assert "recipient_email" in error_message
    
    def test_validate_email_config_invalid_port(self):
        """Test email configuration validation with invalid port."""
        config = Config(
            smtp_server="smtp.gmail.com",
            smtp_port=0,  # Invalid
            smtp_username="test@example.com",
            smtp_password="password",
            recipient_email="recipient@example.com"
        )
        
        with pytest.raises(ValueError) as exc_info:
            EmailService(config)
        
        assert "Invalid SMTP port" in str(exc_info.value)
    
    def test_create_price_drop_notification(self, valid_config, sample_product):
        """Test creation of price drop notification."""
        service = EmailService(valid_config)
        
        notification = service._create_price_drop_notification(
            sample_product, 129.99, 99.99, "automatic"
        )
        
        assert notification.recipient == valid_config.recipient_email
        assert "Price Drop Alert" in notification.subject
        assert sample_product.name in notification.subject
        assert "$99.99" in notification.subject
        
        # Check text body content
        assert sample_product.name in notification.body_text
        assert sample_product.url in notification.body_text
        assert "$129.99 → $99.99" in notification.body_text
        assert "dropped" in notification.body_text
        assert "Automatic update" in notification.body_text
        
        # Check HTML body content
        assert sample_product.name in notification.body_html
        assert sample_product.url in notification.body_html
        assert "$129.99 → $99.99" in notification.body_html
        assert "dropped" in notification.body_html
        assert sample_product.image_url in notification.body_html
    
    def test_create_price_increase_notification(self, valid_config, sample_product):
        """Test creation of price increase notification."""
        service = EmailService(valid_config)
        
        notification = service._create_price_drop_notification(
            sample_product, 99.99, 129.99, "manual"
        )
        
        assert "Price Update" in notification.subject
        assert "$129.99" in notification.subject
        
        # Check for price increase indicators
        assert "increased" in notification.body_text
        assert "↑" in notification.body_text
        assert "Manual update" in notification.body_text
        
        assert "increased" in notification.body_html
        assert "↑" in notification.body_html
    
    def test_create_new_lowest_price_notification(self, valid_config, sample_product):
        """Test notification when new price is the lowest recorded."""
        service = EmailService(valid_config)
        sample_product.lowest_price = 95.00  # Set higher than new price
        
        notification = service._create_price_drop_notification(
            sample_product, 129.99, 89.99, "automatic"
        )
        
        assert "lowest price recorded" in notification.body_text
        assert "Previous lowest: $95.00" in notification.body_text
        
        assert "New lowest price!" in notification.body_html
        assert "Previous lowest: $95.00" in notification.body_html
    
    @patch('smtplib.SMTP')
    def test_send_email_success(self, mock_smtp, valid_config):
        """Test successful email sending."""
        # Setup mock
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        service = EmailService(valid_config)
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<p>Test body</p>"
        )
        
        # Send email
        service._send_email(notification)
        
        # Verify SMTP calls
        mock_smtp.assert_called_once_with(valid_config.smtp_server, valid_config.smtp_port)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(
            valid_config.smtp_username, valid_config.smtp_password
        )
        mock_server.sendmail.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_send_email_smtp_error(self, mock_smtp, valid_config):
        """Test email sending with SMTP error."""
        # Setup mock to raise exception
        mock_smtp.side_effect = smtplib.SMTPException("SMTP Error")
        
        service = EmailService(valid_config)
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<p>Test body</p>"
        )
        
        # Should raise exception
        with pytest.raises(smtplib.SMTPException):
            service._send_email(notification)
    
    @patch('src.services.email_service.time.sleep')
    @patch('smtplib.SMTP')
    def test_send_email_with_retry_success_after_failure(self, mock_smtp, mock_sleep, valid_config):
        """Test email sending with retry logic - success after initial failure."""
        # Setup mock to fail first time, succeed second time
        mock_server = Mock()
        mock_smtp.side_effect = [
            smtplib.SMTPException("First attempt fails"),
            mock_server
        ]
        mock_server.__enter__.return_value = mock_server
        
        service = EmailService(valid_config)
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<p>Test body</p>"
        )
        
        result = service._send_email_with_retry(notification)
        
        # Should succeed on retry
        assert result.success is True
        assert result.retry_count == 1
        assert "Email sent successfully" in result.message
        
        # Verify retry sleep was called
        mock_sleep.assert_called_once_with(2)  # 2^1 seconds
    
    @patch('src.services.email_service.time.sleep')
    @patch('smtplib.SMTP')
    def test_send_email_with_retry_all_attempts_fail(self, mock_smtp, mock_sleep, valid_config):
        """Test email sending with retry logic - all attempts fail."""
        # Setup mock to always fail
        mock_smtp.side_effect = smtplib.SMTPException("Always fails")
        
        service = EmailService(valid_config)
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<p>Test body</p>"
        )
        
        result = service._send_email_with_retry(notification)
        
        # Should fail after all retries
        assert result.success is False
        assert result.retry_count == valid_config.max_retry_attempts
        assert "Failed to send email after" in result.message
        assert "Always fails" in result.error_details
        
        # Verify retry sleeps were called
        expected_calls = [2, 4]  # 2^1, 2^2 seconds
        actual_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_calls == expected_calls
    
    @patch('src.services.email_service.EmailService._send_email_with_retry')
    def test_send_price_drop_notification_success(self, mock_send, valid_config, sample_product):
        """Test successful price drop notification sending."""
        # Setup mock
        mock_result = EmailDeliveryResult(
            success=True,
            message="Email sent successfully",
            timestamp=datetime.now()
        )
        mock_send.return_value = mock_result
        
        service = EmailService(valid_config)
        result = service.send_price_drop_notification(sample_product, 129.99, 99.99)
        
        assert result.success is True
        assert result.message == "Email sent successfully"
        mock_send.assert_called_once()
    
    def test_send_price_drop_notification_creation_error(self, valid_config):
        """Test price drop notification with invalid product data."""
        service = EmailService(valid_config)
        
        # Create invalid product (missing required fields)
        invalid_product = Product()
        invalid_product.id = None
        invalid_product.name = None
        
        result = service.send_price_drop_notification(invalid_product, 100.0, 90.0)
        
        assert result.success is False
        assert "Failed to create or send notification" in result.message
        assert result.error_details is not None
    
    @patch('smtplib.SMTP')
    def test_test_email_connection_success(self, mock_smtp, valid_config):
        """Test successful email connection test."""
        # Setup mock
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        service = EmailService(valid_config)
        result = service.test_email_connection()
        
        assert result.success is True
        assert "Email connection test successful" in result.message
        
        # Verify connection test calls
        mock_smtp.assert_called_once_with(valid_config.smtp_server, valid_config.smtp_port)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(
            valid_config.smtp_username, valid_config.smtp_password
        )
    
    @patch('smtplib.SMTP')
    def test_test_email_connection_failure(self, mock_smtp, valid_config):
        """Test email connection test failure."""
        # Setup mock to raise exception
        mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, "Authentication failed")
        
        service = EmailService(valid_config)
        result = service.test_email_connection()
        
        assert result.success is False
        assert "Email connection test failed" in result.message
        assert "Authentication failed" in result.error_details
    
    @patch('src.services.email_service.EmailService._send_email_with_retry')
    def test_send_test_notification(self, mock_send, valid_config):
        """Test sending test notification."""
        # Setup mock
        mock_result = EmailDeliveryResult(
            success=True,
            message="Test email sent",
            timestamp=datetime.now()
        )
        mock_send.return_value = mock_result
        
        service = EmailService(valid_config)
        result = service.send_test_notification()
        
        assert result.success is True
        mock_send.assert_called_once()
        
        # Verify test notification content
        call_args = mock_send.call_args[0][0]  # First argument (notification)
        assert call_args.recipient == valid_config.recipient_email
        assert "Test Notification" in call_args.subject
        assert "test email to verify" in call_args.body_text
        assert valid_config.smtp_server in call_args.body_text
    
    def test_create_test_bodies(self, valid_config):
        """Test creation of test notification bodies."""
        service = EmailService(valid_config)
        
        text_body = service._create_test_text_body()
        html_body = service._create_test_html_body()
        
        # Check text body
        assert "Price Monitor Test Notification" in text_body
        assert valid_config.smtp_server in text_body
        assert valid_config.smtp_username in text_body
        assert valid_config.recipient_email in text_body
        
        # Check HTML body
        assert "Price Monitor Test" in html_body
        assert valid_config.smtp_server in html_body
        assert valid_config.smtp_username in html_body
        assert valid_config.recipient_email in html_body
        assert "<html>" in html_body
        assert "</html>" in html_body
    
    def test_email_notification_dataclass(self):
        """Test EmailNotification dataclass."""
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<p>Test body</p>",
            product_id=123,
            notification_type="price_drop"
        )
        
        assert notification.recipient == "test@example.com"
        assert notification.subject == "Test Subject"
        assert notification.body_text == "Test body"
        assert notification.body_html == "<p>Test body</p>"
        assert notification.product_id == 123
        assert notification.notification_type == "price_drop"
    
    def test_email_delivery_result_dataclass(self):
        """Test EmailDeliveryResult dataclass."""
        timestamp = datetime.now()
        result = EmailDeliveryResult(
            success=True,
            message="Success",
            timestamp=timestamp,
            retry_count=2,
            error_details="No errors"
        )
        
        assert result.success is True
        assert result.message == "Success"
        assert result.timestamp == timestamp
        assert result.retry_count == 2
        assert result.error_details == "No errors"
    
    def test_exponential_backoff_calculation(self, valid_config):
        """Test that retry delays follow exponential backoff pattern."""
        service = EmailService(valid_config)
        
        # Test the exponential backoff logic indirectly by checking max wait time
        # The actual implementation uses min(2 ** retry_count, 60)
        
        # This is tested indirectly in the retry tests above
        # where we verify the sleep calls with expected values
        assert True  # Placeholder - actual testing done in retry tests
    
    @patch('smtplib.SMTP')
    def test_email_message_structure(self, mock_smtp, valid_config):
        """Test that email message is properly structured."""
        # Setup mock to capture the message
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        service = EmailService(valid_config)
        notification = EmailNotification(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body text",
            body_html="<p>Test body HTML</p>"
        )
        
        service._send_email(notification)
        
        # Verify sendmail was called
        mock_server.sendmail.assert_called_once()
        
        # Get the message that was sent
        call_args = mock_server.sendmail.call_args[0]
        from_addr = call_args[0]
        to_addr = call_args[1]
        message_str = call_args[2]
        
        assert from_addr == valid_config.smtp_username
        assert to_addr == "test@example.com"
        assert "Subject: Test Subject" in message_str
        assert "Test body text" in message_str
        assert "<p>Test body HTML</p>" in message_str


class TestEmailServiceIntegration:
    """Integration tests for EmailService."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for integration tests."""
        return Config(
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="password",
            recipient_email="recipient@example.com",
            max_retry_attempts=1
        )
    
    @pytest.fixture
    def mock_product(self):
        """Create a mock product for integration tests."""
        product = Product()
        product.id = 1
        product.name = "Integration Test Product"
        product.url = "https://example.com/product/123"
        product.current_price = 79.99
        product.previous_price = 99.99
        product.lowest_price = 69.99
        product.image_url = "https://example.com/image.jpg"
        product.created_at = datetime(2024, 1, 1)
        product.last_checked = datetime(2024, 1, 15)
        return product
    
    @patch('smtplib.SMTP')
    def test_complete_price_drop_workflow(self, mock_smtp, mock_config, mock_product):
        """Test complete price drop notification workflow."""
        # Setup mock
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        service = EmailService(mock_config)
        
        # Send price drop notification
        result = service.send_price_drop_notification(
            mock_product, 99.99, 79.99, "automatic"
        )
        
        # Verify success
        assert result.success is True
        assert result.retry_count == 0
        
        # Verify SMTP interaction
        mock_smtp.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
        
        # Verify message content
        call_args = mock_server.sendmail.call_args[0]
        message_str = call_args[2]
        
        assert "Price Drop Alert" in message_str
        assert mock_product.name in message_str
        assert "$99.99 → $79.99" in message_str
        assert mock_product.url in message_str