"""
Tests for error handling functionality in PriceMonitorService.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from src.services.price_monitor_service import (
    PriceMonitorService, PriceCheckResult, ErrorType, ErrorRecord
)
from src.models.database import Product
from src.models.web_scraping import PageContent, ProductInfo, ScrapingResult


class TestErrorHandling(unittest.TestCase):
    """Test error handling functionality in PriceMonitorService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_product_service = Mock()
        self.mock_parser_service = Mock()
        self.mock_web_scraping_service = Mock()
        
        self.service = PriceMonitorService(
            product_service=self.mock_product_service,
            parser_service=self.mock_parser_service,
            web_scraping_service=self.mock_web_scraping_service,
            max_concurrent_checks=2,
            check_timeout=30,
            max_retries=2,
            retry_delay=0.1,  # Short delay for tests
            backoff_factor=2.0
        )
        
        # Sample product
        self.sample_product = Product(
            id=1,
            url="https://example.com/product",
            name="Test Product",
            current_price=100.0,
            previous_price=110.0,
            lowest_price=90.0,
            image_url="https://example.com/image.jpg",
            created_at=datetime.now(),
            last_checked=datetime.now(),
            is_active=True
        )
    
    def test_error_record_creation(self):
        """Test ErrorRecord data class."""
        error = ErrorRecord(
            product_id=1,
            product_url="https://example.com/product",
            error_type=ErrorType.NETWORK_ERROR,
            error_message="Connection timeout",
            timestamp=datetime.now(),
            retry_count=2
        )
        
        self.assertEqual(error.product_id, 1)
        self.assertEqual(error.error_type, ErrorType.NETWORK_ERROR)
        self.assertEqual(error.error_message, "Connection timeout")
        self.assertEqual(error.retry_count, 2)
        self.assertIsInstance(error.timestamp, datetime)
    
    def test_retry_logic_success_after_failure(self):
        """Test that retry logic works when first attempt fails but second succeeds."""
        self.mock_product_service.get_product.return_value = self.sample_product
        self.mock_product_service.update_product_price.return_value = True
        
        # Mock first attempt fails, second succeeds
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        
        # First call fails, second succeeds
        self.mock_web_scraping_service.fetch_page_content.side_effect = [
            ScrapingResult.error_result("Connection timeout"),
            ScrapingResult.success_result(page_content)
        ]
        
        # Mock parsing success
        product_info = ProductInfo(name="Test Product", price=95.0)
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        # Execute check
        result = self.service.check_product(1)
        
        # Should succeed after retry
        self.assertTrue(result.success)
        self.assertEqual(result.new_price, 95.0)
        
        # Should have called fetch_page_content twice
        self.assertEqual(self.mock_web_scraping_service.fetch_page_content.call_count, 2)
    
    def test_retry_logic_all_attempts_fail(self):
        """Test that retry logic eventually gives up after max retries."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mock all attempts fail
        self.mock_web_scraping_service.fetch_page_content.return_value = ScrapingResult.error_result("Connection timeout")
        
        # Execute check
        result = self.service.check_product(1)
        
        # Should fail after all retries
        self.assertFalse(result.success)
        self.assertIn("Failed to fetch page", result.error_message)
        
        # Should have called fetch_page_content max_retries + 1 times
        self.assertEqual(self.mock_web_scraping_service.fetch_page_content.call_count, 3)  # 2 retries + 1 initial
    
    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation."""
        # Test exponential backoff
        delay_0 = self.service._calculate_retry_delay(0)
        delay_1 = self.service._calculate_retry_delay(1)
        delay_2 = self.service._calculate_retry_delay(2)
        
        self.assertEqual(delay_0, 0.1)  # retry_delay * (backoff_factor ^ 0)
        self.assertEqual(delay_1, 0.2)  # retry_delay * (backoff_factor ^ 1)
        self.assertEqual(delay_2, 0.4)  # retry_delay * (backoff_factor ^ 2)
    
    def test_should_skip_url_recent_failure(self):
        """Test that URLs with recent failures are skipped."""
        url = "https://example.com/product"
        
        # Initially should not skip
        self.assertFalse(self.service._should_skip_url(url))
        
        # Record a recent failure
        self.service._failed_urls[url] = datetime.now()
        
        # Should now skip
        self.assertTrue(self.service._should_skip_url(url))
        
        # Old failure should not cause skip
        self.service._failed_urls[url] = datetime.now() - timedelta(hours=2)
        self.assertFalse(self.service._should_skip_url(url))
    
    def test_url_skipping_in_check_product(self):
        """Test that check_product skips URLs with recent failures."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mark URL as recently failed
        self.service._failed_urls[self.sample_product.url] = datetime.now()
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("temporarily disabled", result.error_message)
        
        # Should not have attempted to fetch the page
        self.mock_web_scraping_service.fetch_page_content.assert_not_called()
    
    def test_failure_tracking_and_reset(self):
        """Test failure tracking and reset on success."""
        product_id = 1
        url = "https://example.com/product"
        
        # Record some failures
        self.service._record_failure(product_id, url, "Error message", 0)
        self.service._record_failure(product_id, url, "Error message", 1)
        
        # Check tracking
        self.assertEqual(self.service._consecutive_failures[product_id], 2)
        self.assertIn(url, self.service._failed_urls)
        
        # Reset tracking
        self.service._reset_failure_tracking(product_id, url)
        
        # Should be cleared
        self.assertNotIn(product_id, self.service._consecutive_failures)
        self.assertNotIn(url, self.service._failed_urls)
    
    def test_error_recording(self):
        """Test error recording functionality."""
        product_id = 1
        url = "https://example.com/product"
        error_type = ErrorType.PARSING_ERROR
        error_message = "Failed to parse price"
        retry_count = 1
        
        # Initially no errors
        self.assertEqual(len(self.service._error_history), 0)
        
        # Record an error
        self.service._record_error(product_id, url, error_type, error_message, retry_count)
        
        # Should have one error
        self.assertEqual(len(self.service._error_history), 1)
        
        error = self.service._error_history[0]
        self.assertEqual(error.product_id, product_id)
        self.assertEqual(error.product_url, url)
        self.assertEqual(error.error_type, error_type)
        self.assertEqual(error.error_message, error_message)
        self.assertEqual(error.retry_count, retry_count)
    
    def test_error_history_limit(self):
        """Test that error history is limited to prevent memory issues."""
        # Record more than 1000 errors
        for i in range(1100):
            self.service._record_error(
                product_id=i % 10,
                url=f"https://example.com/product{i}",
                error_type=ErrorType.NETWORK_ERROR,
                error_message=f"Error {i}",
                retry_count=0
            )
        
        # Should be limited to 1000
        self.assertEqual(len(self.service._error_history), 1000)
        
        # Should keep the most recent ones
        self.assertEqual(self.service._error_history[-1].error_message, "Error 1099")
    
    def test_is_valid_price(self):
        """Test price validation."""
        # Valid prices
        self.assertTrue(self.service._is_valid_price(10.99))
        self.assertTrue(self.service._is_valid_price(0.01))
        self.assertTrue(self.service._is_valid_price(999999.99))
        
        # Invalid prices
        self.assertFalse(self.service._is_valid_price(None))
        self.assertFalse(self.service._is_valid_price(0))
        self.assertFalse(self.service._is_valid_price(-10))
        self.assertFalse(self.service._is_valid_price(0.001))  # Too small
        self.assertFalse(self.service._is_valid_price(1000001))  # Too large
    
    def test_invalid_price_handling(self):
        """Test handling of invalid prices during check."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mock successful scraping and parsing with invalid price
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock parsing with invalid price
        product_info = ProductInfo(name="Test Product", price=-10.0)  # Invalid negative price
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("Invalid price value", result.error_message)
    
    def test_get_error_summary(self):
        """Test error summary generation."""
        # Record some errors
        now = datetime.now()
        
        # Recent errors (within 24 hours)
        self.service._error_history = [
            ErrorRecord(1, "url1", ErrorType.NETWORK_ERROR, "Network error 1", now, 0),
            ErrorRecord(2, "url2", ErrorType.PARSING_ERROR, "Parse error 1", now, 1),
            ErrorRecord(1, "url1", ErrorType.NETWORK_ERROR, "Network error 2", now, 0),
            # Old error (should be excluded)
            ErrorRecord(3, "url3", ErrorType.DATABASE_ERROR, "DB error", now - timedelta(hours=25), 0)
        ]
        
        summary = self.service.get_error_summary(24)
        
        self.assertEqual(summary['total_errors'], 3)  # Excludes old error
        self.assertEqual(summary['error_types']['network_error'], 2)
        self.assertEqual(summary['error_types']['parsing_error'], 1)
        self.assertEqual(summary['affected_products'], 2)  # Products 1 and 2
        self.assertEqual(summary['time_period_hours'], 24)
        
        # Most common errors should be sorted by frequency
        self.assertTrue(len(summary['most_common_errors']) > 0)
    
    def test_get_error_summary_no_errors(self):
        """Test error summary when no errors exist."""
        summary = self.service.get_error_summary(24)
        
        self.assertEqual(summary['total_errors'], 0)
        self.assertEqual(summary['error_types'], {})
        self.assertEqual(summary['most_common_errors'], [])
        self.assertEqual(summary['affected_products'], 0)
    
    def test_get_failing_products(self):
        """Test getting list of failing products."""
        # Mock products
        product1 = Product(id=1, name="Product 1", url="url1", current_price=100, lowest_price=90, is_active=True)
        product2 = Product(id=2, name="Product 2", url="url2", current_price=200, lowest_price=180, is_active=True)
        
        self.mock_product_service.get_product.side_effect = lambda pid: product1 if pid == 1 else product2
        
        # Record failures
        self.service._consecutive_failures = {1: 3, 2: 1}
        self.service._failed_urls = {"url1": datetime.now(), "url2": datetime.now()}
        
        failing_products = self.service.get_failing_products()
        
        self.assertEqual(len(failing_products), 2)
        
        # Should be sorted by failure count (highest first)
        self.assertEqual(failing_products[0]['product_id'], 1)
        self.assertEqual(failing_products[0]['consecutive_failures'], 3)
        self.assertEqual(failing_products[1]['product_id'], 2)
        self.assertEqual(failing_products[1]['consecutive_failures'], 1)
    
    def test_clear_error_history(self):
        """Test clearing error history and failure tracking."""
        # Add some data
        self.service._error_history.append(
            ErrorRecord(1, "url1", ErrorType.NETWORK_ERROR, "Error", datetime.now(), 0)
        )
        self.service._failed_urls["url1"] = datetime.now()
        self.service._consecutive_failures[1] = 2
        
        # Clear
        self.service.clear_error_history()
        
        # Should be empty
        self.assertEqual(len(self.service._error_history), 0)
        self.assertEqual(len(self.service._failed_urls), 0)
        self.assertEqual(len(self.service._consecutive_failures), 0)
    
    def test_retry_failed_products(self):
        """Test retrying failed products."""
        # Mock failing products
        self.service._consecutive_failures = {1: 2, 2: 1}
        
        with patch.object(self.service, 'check_product') as mock_check:
            mock_check.side_effect = [
                PriceCheckResult.success_result(1, "Product 1", "url1", 100.0, 95.0, True, False),
                PriceCheckResult.success_result(2, "Product 2", "url2", 200.0, 190.0, True, False)
            ]
            
            results = self.service.retry_failed_products()
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))
        
        # Should have cleared error history
        self.assertEqual(len(self.service._error_history), 0)
        self.assertEqual(len(self.service._failed_urls), 0)
        self.assertEqual(len(self.service._consecutive_failures), 0)
    
    def test_retry_failed_products_no_failures(self):
        """Test retrying when no products are failing."""
        results = self.service.retry_failed_products()
        
        self.assertEqual(len(results), 0)
    
    def test_persistent_failure_handling(self):
        """Test handling of persistent failures."""
        product_id = 1
        url = "https://example.com/product"
        
        # Simulate many consecutive failures
        self.service._consecutive_failures[product_id] = 15
        
        with patch.object(self.service.logger, 'warning') as mock_warning:
            self.service._handle_persistent_failure(product_id, url)
            
            # Should log a warning about considering deactivation
            mock_warning.assert_called()
            warning_call = mock_warning.call_args[0][0]
            self.assertIn("Consider deactivating", warning_call)


if __name__ == '__main__':
    unittest.main()