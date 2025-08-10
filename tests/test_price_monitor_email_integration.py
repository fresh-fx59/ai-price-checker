"""
Integration tests for price monitoring with email notifications.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.services.price_monitor_service import PriceMonitorService, PriceCheckResult
from src.services.email_service import EmailService, EmailDeliveryResult
from src.services.product_service import ProductService
from src.services.parser_service import ParserService
from src.services.web_scraping_service import WebScrapingService
from src.models.config import Config
from src.models.database import Product, DatabaseManager
from src.models.web_scraping import ProductInfo, ScrapingResult, ParsingResult


class TestPriceMonitorEmailIntegration:
    """Integration tests for price monitoring with email notifications."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return Config(
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="password",
            recipient_email="recipient@example.com",
            max_retry_attempts=1
        )
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        return Mock(spec=DatabaseManager)
    
    @pytest.fixture
    def mock_product_service(self, mock_db_manager):
        """Create a mock product service."""
        return Mock(spec=ProductService)
    
    @pytest.fixture
    def mock_parser_service(self):
        """Create a mock parser service."""
        return Mock(spec=ParserService)
    
    @pytest.fixture
    def mock_web_scraping_service(self):
        """Create a mock web scraping service."""
        return Mock(spec=WebScrapingService)
    
    @pytest.fixture
    def mock_email_service(self, mock_config):
        """Create a mock email service."""
        return Mock(spec=EmailService)
    
    @pytest.fixture
    def sample_product(self):
        """Create a sample product."""
        product = Product()
        product.id = 1
        product.name = "Test Product"
        product.url = "https://example.com/product"
        product.current_price = 99.99
        product.previous_price = 129.99
        product.lowest_price = 89.99
        product.image_url = "https://example.com/image.jpg"
        product.created_at = datetime(2024, 1, 1)
        product.last_checked = datetime(2024, 1, 15)
        product.is_active = True
        return product
    
    @pytest.fixture
    def price_monitor_service(self, mock_product_service, mock_parser_service, 
                            mock_web_scraping_service, mock_email_service):
        """Create a price monitor service with email integration."""
        return PriceMonitorService(
            product_service=mock_product_service,
            parser_service=mock_parser_service,
            web_scraping_service=mock_web_scraping_service,
            email_service=mock_email_service,
            max_concurrent_checks=2,
            max_retries=1
        )
    
    def test_automatic_price_drop_with_notification(self, price_monitor_service, 
                                                  mock_product_service, mock_parser_service,
                                                  mock_web_scraping_service, mock_email_service,
                                                  sample_product):
        """Test automatic price drop detection with email notification."""
        # Setup mocks
        mock_product_service.get_product.return_value = sample_product
        
        # Mock successful scraping
        scraping_result = ScrapingResult(
            success=True,
            page_content="<html>Product page</html>",
            url=sample_product.url
        )
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock successful parsing with price drop
        new_price = 79.99  # Lower than current price (99.99)
        product_info = ProductInfo(
            name=sample_product.name,
            price=new_price,
            image_url=sample_product.image_url
        )
        parsing_result = ParsingResult(
            success=True,
            product_info=product_info,
            url=sample_product.url
        )
        mock_parser_service.parse_product.return_value = parsing_result
        
        # Mock successful price update
        mock_product_service.update_product_price.return_value = True
        
        # Create updated product for notification
        updated_product = Product()
        updated_product.id = sample_product.id
        updated_product.name = sample_product.name
        updated_product.url = sample_product.url
        updated_product.current_price = new_price
        updated_product.previous_price = sample_product.current_price
        updated_product.lowest_price = min(new_price, sample_product.lowest_price)
        updated_product.image_url = sample_product.image_url
        updated_product.created_at = sample_product.created_at
        updated_product.last_checked = datetime.now()
        updated_product.is_active = True
        
        # Mock getting updated product for notification
        mock_product_service.get_product.side_effect = [sample_product, updated_product]
        
        # Mock successful email notification
        email_result = EmailDeliveryResult(
            success=True,
            message="Email sent successfully",
            timestamp=datetime.now()
        )
        mock_email_service.send_price_drop_notification.return_value = email_result
        
        # Execute price check
        result = price_monitor_service.check_product(sample_product.id)
        
        # Verify result
        assert result.success is True
        assert result.product_id == sample_product.id
        assert result.old_price == sample_product.current_price
        assert result.new_price == new_price
        assert result.price_dropped is True
        assert result.notification_sent is True
        assert result.notification_error is None
        
        # Verify service calls
        mock_web_scraping_service.fetch_page_content.assert_called_once_with(sample_product.url)
        mock_parser_service.parse_product.assert_called_once()
        mock_product_service.update_product_price.assert_called_once_with(
            sample_product.id, new_price, 'automatic'
        )
        mock_email_service.send_price_drop_notification.assert_called_once_with(
            updated_product, sample_product.current_price, new_price, 'automatic'
        )
    
    def test_automatic_price_update_no_drop_with_notification(self, price_monitor_service,
                                                            mock_product_service, mock_parser_service,
                                                            mock_web_scraping_service, mock_email_service,
                                                            sample_product):
        """Test automatic price update (no drop) with email notification."""
        # Setup mocks
        mock_product_service.get_product.return_value = sample_product
        
        # Mock successful scraping
        scraping_result = ScrapingResult(
            success=True,
            page_content="<html>Product page</html>",
            url=sample_product.url
        )
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock successful parsing with price increase
        new_price = 109.99  # Higher than current price (99.99)
        product_info = ProductInfo(
            name=sample_product.name,
            price=new_price,
            image_url=sample_product.image_url
        )
        parsing_result = ParsingResult(
            success=True,
            product_info=product_info,
            url=sample_product.url
        )
        mock_parser_service.parse_product.return_value = parsing_result
        
        # Mock successful price update
        mock_product_service.update_product_price.return_value = True
        
        # Create updated product for notification
        updated_product = Product()
        updated_product.id = sample_product.id
        updated_product.name = sample_product.name
        updated_product.url = sample_product.url
        updated_product.current_price = new_price
        updated_product.previous_price = sample_product.current_price
        updated_product.lowest_price = sample_product.lowest_price
        updated_product.image_url = sample_product.image_url
        updated_product.created_at = sample_product.created_at
        updated_product.last_checked = datetime.now()
        updated_product.is_active = True
        
        # Mock getting updated product for notification
        mock_product_service.get_product.side_effect = [sample_product, updated_product]
        
        # Mock successful email notification
        email_result = EmailDeliveryResult(
            success=True,
            message="Email sent successfully",
            timestamp=datetime.now()
        )
        mock_email_service.send_price_drop_notification.return_value = email_result
        
        # Execute price check
        result = price_monitor_service.check_product(sample_product.id)
        
        # Verify result
        assert result.success is True
        assert result.price_dropped is False
        assert result.notification_sent is True  # Should still send notification for price change
        assert result.notification_error is None
        
        # Verify email service was called for price update (not just drops)
        mock_email_service.send_price_drop_notification.assert_called_once_with(
            updated_product, sample_product.current_price, new_price, 'automatic'
        )
    
    def test_automatic_price_check_notification_failure(self, price_monitor_service,
                                                       mock_product_service, mock_parser_service,
                                                       mock_web_scraping_service, mock_email_service,
                                                       sample_product):
        """Test automatic price check with notification failure."""
        # Setup mocks for successful price check
        mock_product_service.get_product.return_value = sample_product
        
        scraping_result = ScrapingResult(
            success=True,
            page_content="<html>Product page</html>",
            url=sample_product.url
        )
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        new_price = 79.99
        product_info = ProductInfo(
            name=sample_product.name,
            price=new_price,
            image_url=sample_product.image_url
        )
        parsing_result = ParsingResult(
            success=True,
            product_info=product_info,
            url=sample_product.url
        )
        mock_parser_service.parse_product.return_value = parsing_result
        mock_product_service.update_product_price.return_value = True
        
        # Create updated product
        updated_product = Product()
        updated_product.id = sample_product.id
        updated_product.name = sample_product.name
        updated_product.url = sample_product.url
        updated_product.current_price = new_price
        updated_product.previous_price = sample_product.current_price
        updated_product.lowest_price = new_price
        updated_product.image_url = sample_product.image_url
        updated_product.created_at = sample_product.created_at
        updated_product.last_checked = datetime.now()
        updated_product.is_active = True
        
        mock_product_service.get_product.side_effect = [sample_product, updated_product]
        
        # Mock failed email notification
        email_result = EmailDeliveryResult(
            success=False,
            message="SMTP connection failed",
            timestamp=datetime.now(),
            error_details="Connection timeout"
        )
        mock_email_service.send_price_drop_notification.return_value = email_result
        
        # Execute price check
        result = price_monitor_service.check_product(sample_product.id)
        
        # Verify result - price check should still succeed even if notification fails
        assert result.success is True
        assert result.price_dropped is True
        assert result.notification_sent is False
        assert result.notification_error == "SMTP connection failed"
        
        # Verify email service was called
        mock_email_service.send_price_drop_notification.assert_called_once()
    
    def test_manual_price_update_with_notification(self, price_monitor_service,
                                                  mock_product_service, mock_email_service,
                                                  sample_product):
        """Test manual price update with email notification."""
        # Setup mocks
        mock_product_service.get_product.return_value = sample_product
        mock_product_service.update_product_price.return_value = True
        
        # Create updated product for notification
        new_price = 69.99  # Lower than current price (99.99)
        updated_product = Product()
        updated_product.id = sample_product.id
        updated_product.name = sample_product.name
        updated_product.url = sample_product.url
        updated_product.current_price = new_price
        updated_product.previous_price = sample_product.current_price
        updated_product.lowest_price = new_price  # New lowest
        updated_product.image_url = sample_product.image_url
        updated_product.created_at = sample_product.created_at
        updated_product.last_checked = datetime.now()
        updated_product.is_active = True
        
        # Mock getting updated product for notification
        mock_product_service.get_product.side_effect = [sample_product, updated_product]
        
        # Mock successful email notification
        email_result = EmailDeliveryResult(
            success=True,
            message="Email sent successfully",
            timestamp=datetime.now()
        )
        mock_email_service.send_price_drop_notification.return_value = email_result
        
        # Execute manual price update
        result = price_monitor_service.update_product_price_manually(sample_product.id, new_price)
        
        # Verify result
        assert result.success is True
        assert result.product_id == sample_product.id
        assert result.old_price == sample_product.current_price
        assert result.new_price == new_price
        assert result.price_dropped is True
        assert result.is_new_lowest is True
        assert result.notification_sent is True
        assert result.notification_error is None
        
        # Verify service calls
        mock_product_service.update_product_price.assert_called_once_with(
            sample_product.id, new_price, 'manual'
        )
        mock_email_service.send_price_drop_notification.assert_called_once_with(
            updated_product, sample_product.current_price, new_price, 'manual'
        )
    
    def test_manual_price_update_no_change(self, price_monitor_service,
                                         mock_product_service, mock_email_service,
                                         sample_product):
        """Test manual price update with no actual price change."""
        # Setup mocks
        mock_product_service.get_product.return_value = sample_product
        
        # Try to update with the same price
        same_price = sample_product.current_price
        
        # Execute manual price update
        result = price_monitor_service.update_product_price_manually(sample_product.id, same_price)
        
        # Verify result
        assert result.success is True
        assert result.price_dropped is False
        assert result.is_new_lowest is False
        assert result.notification_sent is False
        assert result.notification_error == "No price change detected"
        
        # Verify no database update or email was sent
        mock_product_service.update_product_price.assert_not_called()
        mock_email_service.send_price_drop_notification.assert_not_called()
    
    def test_price_monitor_without_email_service(self, mock_product_service, mock_parser_service,
                                                mock_web_scraping_service, sample_product):
        """Test price monitoring without email service configured."""
        # Create service without email service
        service = PriceMonitorService(
            product_service=mock_product_service,
            parser_service=mock_parser_service,
            web_scraping_service=mock_web_scraping_service,
            email_service=None  # No email service
        )
        
        # Setup mocks for successful price check
        mock_product_service.get_product.return_value = sample_product
        
        scraping_result = ScrapingResult(
            success=True,
            page_content="<html>Product page</html>",
            url=sample_product.url
        )
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        new_price = 79.99
        product_info = ProductInfo(
            name=sample_product.name,
            price=new_price,
            image_url=sample_product.image_url
        )
        parsing_result = ParsingResult(
            success=True,
            product_info=product_info,
            url=sample_product.url
        )
        mock_parser_service.parse_product.return_value = parsing_result
        mock_product_service.update_product_price.return_value = True
        
        # Execute price check
        result = service.check_product(sample_product.id)
        
        # Verify result - should succeed but no notification
        assert result.success is True
        assert result.price_dropped is True
        assert result.notification_sent is False
        assert result.notification_error is None
    
    def test_monitoring_stats_with_notifications(self, price_monitor_service,
                                                mock_product_service, mock_parser_service,
                                                mock_web_scraping_service, mock_email_service):
        """Test monitoring statistics include notification counts."""
        # Create multiple products
        products = []
        for i in range(3):
            product = Product()
            product.id = i + 1
            product.name = f"Product {i + 1}"
            product.url = f"https://example.com/product{i + 1}"
            product.current_price = 100.0 + i
            product.previous_price = 120.0 + i
            product.lowest_price = 90.0 + i
            product.is_active = True
            products.append(product)
        
        # Mock product service
        mock_product_service.get_products_for_monitoring.return_value = products
        mock_product_service.get_product.side_effect = products + products  # For notifications
        mock_product_service.update_product_price.return_value = True
        
        # Mock successful scraping and parsing for all products
        scraping_result = ScrapingResult(success=True, page_content="<html>Product</html>", url="")
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        def create_parsing_result(url):
            product_info = ProductInfo(name="Product", price=85.0, image_url="")
            return ParsingResult(success=True, product_info=product_info, url=url)
        
        mock_parser_service.parse_product.side_effect = lambda url, content: create_parsing_result(url)
        
        # Mock email notifications - 2 succeed, 1 fails
        email_results = [
            EmailDeliveryResult(success=True, message="Success", timestamp=datetime.now()),
            EmailDeliveryResult(success=True, message="Success", timestamp=datetime.now()),
            EmailDeliveryResult(success=False, message="Failed", timestamp=datetime.now())
        ]
        mock_email_service.send_price_drop_notification.side_effect = email_results
        
        # Execute monitoring
        results = price_monitor_service.check_all_products()
        
        # Verify results
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.price_dropped for r in results)
        
        # Check notification results
        notifications_sent = sum(1 for r in results if r.notification_sent)
        notification_failures = sum(1 for r in results if r.notification_error)
        
        assert notifications_sent == 2
        assert notification_failures == 1
        
        # Verify statistics
        stats = price_monitor_service.get_monitoring_stats()
        assert stats['last_run']['notifications_sent'] == 2
        assert stats['last_run']['notification_failures'] == 1
    
    def test_notification_exception_handling(self, price_monitor_service,
                                           mock_product_service, mock_parser_service,
                                           mock_web_scraping_service, mock_email_service,
                                           sample_product):
        """Test handling of exceptions during notification sending."""
        # Setup mocks for successful price check
        mock_product_service.get_product.return_value = sample_product
        
        scraping_result = ScrapingResult(
            success=True,
            page_content="<html>Product page</html>",
            url=sample_product.url
        )
        mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        new_price = 79.99
        product_info = ProductInfo(
            name=sample_product.name,
            price=new_price,
            image_url=sample_product.image_url
        )
        parsing_result = ParsingResult(
            success=True,
            product_info=product_info,
            url=sample_product.url
        )
        mock_parser_service.parse_product.return_value = parsing_result
        mock_product_service.update_product_price.return_value = True
        
        # Mock getting updated product for notification
        updated_product = Product()
        updated_product.id = sample_product.id
        updated_product.name = sample_product.name
        mock_product_service.get_product.side_effect = [sample_product, updated_product]
        
        # Mock email service to raise exception
        mock_email_service.send_price_drop_notification.side_effect = Exception("Email service error")
        
        # Execute price check
        result = price_monitor_service.check_product(sample_product.id)
        
        # Verify result - price check should still succeed
        assert result.success is True
        assert result.price_dropped is True
        assert result.notification_sent is False
        assert "Notification error: Email service error" in result.notification_error
        
        # Verify email service was called
        mock_email_service.send_price_drop_notification.assert_called_once()


class TestPriceMonitorEmailIntegrationEdgeCases:
    """Edge case tests for price monitoring with email integration."""
    
    def test_notification_with_missing_updated_product(self):
        """Test notification handling when updated product cannot be retrieved."""
        # This would test the case where get_product returns None after update
        # Implementation would depend on specific error handling requirements
        pass
    
    def test_notification_with_invalid_email_config(self):
        """Test notification handling with invalid email configuration."""
        # This would test graceful handling of email service initialization failures
        pass
    
    def test_concurrent_notifications(self):
        """Test handling of concurrent notification sending."""
        # This would test thread safety of notification sending
        pass