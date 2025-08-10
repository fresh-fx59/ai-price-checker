"""
Email service for sending price drop notifications.
"""

import smtplib
import ssl
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from ..models.config import Config
from ..models.database import Product


@dataclass
class EmailNotification:
    """Represents an email notification to be sent."""
    recipient: str
    subject: str
    body_text: str
    body_html: str
    product_id: Optional[int] = None
    notification_type: str = "price_drop"


@dataclass
class EmailDeliveryResult:
    """Result of email delivery attempt."""
    success: bool
    message: str
    timestamp: datetime
    retry_count: int = 0
    error_details: Optional[str] = None


class EmailService:
    """Service for handling email notifications with SMTP configuration."""
    
    def __init__(self, config: Config):
        """
        Initialize email service with configuration.
        
        Args:
            config: Application configuration containing email settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._validate_email_config()
    
    def _validate_email_config(self) -> None:
        """Validate email configuration settings."""
        required_fields = ['smtp_server', 'smtp_username', 'smtp_password', 'recipient_email']
        missing_fields = []
        
        for field in required_fields:
            value = getattr(self.config, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required email configuration: {', '.join(missing_fields)}")
        
        if self.config.smtp_port <= 0 or self.config.smtp_port > 65535:
            raise ValueError(f"Invalid SMTP port: {self.config.smtp_port}")
    
    def send_price_drop_notification(
        self, 
        product: Product, 
        old_price: float, 
        new_price: float,
        source: str = "automatic"
    ) -> EmailDeliveryResult:
        """
        Send price drop notification email.
        
        Args:
            product: Product with updated price
            old_price: Previous price
            new_price: Current (new) price
            source: Source of price update ('automatic' or 'manual')
            
        Returns:
            EmailDeliveryResult with delivery status
        """
        try:
            # Create email notification
            notification = self._create_price_drop_notification(
                product, old_price, new_price, source
            )
            
            # Send email with retry logic
            return self._send_email_with_retry(notification)
            
        except Exception as e:
            self.logger.error(f"Failed to send price drop notification for product {product.id}: {str(e)}")
            return EmailDeliveryResult(
                success=False,
                message=f"Failed to create or send notification: {str(e)}",
                timestamp=datetime.now(),
                error_details=str(e)
            )
    
    def _create_price_drop_notification(
        self, 
        product: Product, 
        old_price: float, 
        new_price: float,
        source: str
    ) -> EmailNotification:
        """
        Create price drop notification email content.
        
        Args:
            product: Product with updated price
            old_price: Previous price
            new_price: Current (new) price
            source: Source of price update
            
        Returns:
            EmailNotification with formatted content
        """
        price_change = old_price - new_price
        percentage_change = (price_change / old_price) * 100 if old_price > 0 else 0
        
        # Determine if this is actually a price drop
        is_price_drop = new_price < old_price
        
        # Create subject line
        if is_price_drop:
            subject = f"🔥 Price Drop Alert: {product.name} - ${new_price:.2f}"
        else:
            subject = f"📈 Price Update: {product.name} - ${new_price:.2f}"
        
        # Create text body
        body_text = self._create_text_body(
            product, old_price, new_price, price_change, percentage_change, source, is_price_drop
        )
        
        # Create HTML body
        body_html = self._create_html_body(
            product, old_price, new_price, price_change, percentage_change, source, is_price_drop
        )
        
        return EmailNotification(
            recipient=self.config.recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            product_id=product.id,
            notification_type="price_drop" if is_price_drop else "price_update"
        )
    
    def _create_text_body(
        self, 
        product: Product, 
        old_price: float, 
        new_price: float, 
        price_change: float, 
        percentage_change: float,
        source: str,
        is_price_drop: bool
    ) -> str:
        """Create plain text email body."""
        change_direction = "dropped" if is_price_drop else "increased"
        change_symbol = "↓" if is_price_drop else "↑"
        
        text_body = f"""
Price Monitor Alert

Product: {product.name}
URL: {product.url}

Price {change_direction}: ${old_price:.2f} → ${new_price:.2f}
Change: {change_symbol} ${abs(price_change):.2f} ({abs(percentage_change):.1f}%)
Source: {source.title()} update

"""
        
        if product.lowest_price and new_price <= product.lowest_price:
            text_body += f"🎉 This is the lowest price recorded! Previous lowest: ${product.lowest_price:.2f}\n"
        elif product.lowest_price:
            text_body += f"Lowest price on record: ${product.lowest_price:.2f}\n"
        
        text_body += f"""
Last checked: {product.last_checked.strftime('%Y-%m-%d %H:%M:%S') if product.last_checked else 'Never'}
Product added: {product.created_at.strftime('%Y-%m-%d %H:%M:%S')}

---
Price Monitor System
"""
        
        return text_body.strip()
    
    def _create_html_body(
        self, 
        product: Product, 
        old_price: float, 
        new_price: float, 
        price_change: float, 
        percentage_change: float,
        source: str,
        is_price_drop: bool
    ) -> str:
        """Create HTML email body with styling."""
        change_direction = "dropped" if is_price_drop else "increased"
        change_color = "#28a745" if is_price_drop else "#dc3545"
        change_symbol = "↓" if is_price_drop else "↑"
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Price Monitor Alert</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .product-info {{ background-color: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .price-change {{ font-size: 24px; font-weight: bold; color: {change_color}; margin: 15px 0; }}
        .price-details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .lowest-price {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        .product-link {{ display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
        .footer {{ font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; padding-top: 15px; margin-top: 20px; }}
        .image {{ max-width: 200px; height: auto; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔔 Price Monitor Alert</h1>
        <p>Your monitored product has a price update!</p>
    </div>
    
    <div class="product-info">
        <h2>{product.name}</h2>
        
        {f'<img src="{product.image_url}" alt="Product Image" class="image">' if product.image_url else ''}
        
        <div class="price-change">
            Price {change_direction}: ${old_price:.2f} → ${new_price:.2f}
        </div>
        
        <div class="price-details">
            <strong>Change:</strong> {change_symbol} ${abs(price_change):.2f} ({abs(percentage_change):.1f}%)<br>
            <strong>Source:</strong> {source.title()} update<br>
            <strong>Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        {f'<div class="lowest-price">🎉 <strong>New lowest price!</strong> Previous lowest: ${product.lowest_price:.2f}</div>' if product.lowest_price and new_price <= product.lowest_price else f'<p><strong>Lowest price on record:</strong> ${product.lowest_price:.2f}</p>' if product.lowest_price else ''}
        
        <a href="{product.url}" class="product-link" target="_blank">View Product</a>
    </div>
    
    <div class="footer">
        <p><strong>Product Details:</strong></p>
        <p>Last checked: {product.last_checked.strftime('%Y-%m-%d %H:%M:%S') if product.last_checked else 'Never'}</p>
        <p>Product added: {product.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>---</p>
        <p>Price Monitor System - Automated price tracking</p>
    </div>
</body>
</html>
"""
        
        return html_body.strip()
    
    def _send_email_with_retry(self, notification: EmailNotification) -> EmailDeliveryResult:
        """
        Send email with retry logic.
        
        Args:
            notification: Email notification to send
            
        Returns:
            EmailDeliveryResult with delivery status
        """
        max_retries = self.config.max_retry_attempts
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                self._send_email(notification)
                
                self.logger.info(
                    f"Email notification sent successfully to {notification.recipient} "
                    f"(product_id: {notification.product_id}, attempts: {retry_count + 1})"
                )
                
                return EmailDeliveryResult(
                    success=True,
                    message="Email sent successfully",
                    timestamp=datetime.now(),
                    retry_count=retry_count
                )
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                self.logger.warning(
                    f"Email send attempt {retry_count} failed for product {notification.product_id}: {str(e)}"
                )
                
                if retry_count <= max_retries:
                    # Wait before retry (exponential backoff)
                    wait_time = min(2 ** retry_count, 60)  # Max 60 seconds
                    self.logger.info(f"Retrying email send in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        # All retries failed
        error_message = f"Failed to send email after {max_retries + 1} attempts: {str(last_error)}"
        self.logger.error(error_message)
        
        return EmailDeliveryResult(
            success=False,
            message=error_message,
            timestamp=datetime.now(),
            retry_count=retry_count - 1,
            error_details=str(last_error)
        )
    
    def _send_email(self, notification: EmailNotification) -> None:
        """
        Send email using SMTP.
        
        Args:
            notification: Email notification to send
            
        Raises:
            Exception: If email sending fails
        """
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = notification.subject
        message["From"] = self.config.smtp_username
        message["To"] = notification.recipient
        
        # Add text and HTML parts
        text_part = MIMEText(notification.body_text, "plain")
        html_part = MIMEText(notification.body_html, "html")
        
        message.attach(text_part)
        message.attach(html_part)
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Send email
        with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
            server.starttls(context=context)
            server.login(self.config.smtp_username, self.config.smtp_password)
            server.sendmail(
                self.config.smtp_username,
                notification.recipient,
                message.as_string()
            )
    
    def test_email_connection(self) -> EmailDeliveryResult:
        """
        Test email connection and configuration.
        
        Returns:
            EmailDeliveryResult indicating connection test result
        """
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Test connection
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.config.smtp_username, self.config.smtp_password)
            
            self.logger.info("Email connection test successful")
            return EmailDeliveryResult(
                success=True,
                message="Email connection test successful",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            error_message = f"Email connection test failed: {str(e)}"
            self.logger.error(error_message)
            return EmailDeliveryResult(
                success=False,
                message=error_message,
                timestamp=datetime.now(),
                error_details=str(e)
            )
    
    def send_test_notification(self) -> EmailDeliveryResult:
        """
        Send a test notification email.
        
        Returns:
            EmailDeliveryResult with delivery status
        """
        try:
            # Create test notification
            test_notification = EmailNotification(
                recipient=self.config.recipient_email,
                subject="🧪 Price Monitor Test Notification",
                body_text=self._create_test_text_body(),
                body_html=self._create_test_html_body(),
                notification_type="test"
            )
            
            return self._send_email_with_retry(test_notification)
            
        except Exception as e:
            self.logger.error(f"Failed to send test notification: {str(e)}")
            return EmailDeliveryResult(
                success=False,
                message=f"Failed to send test notification: {str(e)}",
                timestamp=datetime.now(),
                error_details=str(e)
            )
    
    def _create_test_text_body(self) -> str:
        """Create test notification text body."""
        return f"""
Price Monitor Test Notification

This is a test email to verify that your Price Monitor email configuration is working correctly.

Configuration Details:
- SMTP Server: {self.config.smtp_server}:{self.config.smtp_port}
- From: {self.config.smtp_username}
- To: {self.config.recipient_email}
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you received this email, your email notifications are configured correctly!

---
Price Monitor System
"""
    
    def _create_test_html_body(self) -> str:
        """Create test notification HTML body."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Price Monitor Test</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #e7f3ff; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; }}
        .content {{ background-color: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .success {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .config-details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .footer {{ font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; padding-top: 15px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 Price Monitor Test</h1>
        <p>Email Configuration Test</p>
    </div>
    
    <div class="content">
        <div class="success">
            <strong>✅ Success!</strong> This is a test email to verify that your Price Monitor email configuration is working correctly.
        </div>
        
        <div class="config-details">
            <h3>Configuration Details:</h3>
            <p><strong>SMTP Server:</strong> {self.config.smtp_server}:{self.config.smtp_port}</p>
            <p><strong>From:</strong> {self.config.smtp_username}</p>
            <p><strong>To:</strong> {self.config.recipient_email}</p>
            <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <p>If you received this email, your email notifications are configured correctly and you will receive price drop alerts!</p>
    </div>
    
    <div class="footer">
        <p>---</p>
        <p>Price Monitor System - Automated price tracking</p>
    </div>
</body>
</html>
"""