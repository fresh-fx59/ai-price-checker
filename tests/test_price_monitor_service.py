"""
Tests for the PriceMonitorService.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import time

from src.services.price_monitor_service import PriceMonitorService, PriceCheckResult, MonitoringStats
from src.models.database import Product
from src.models.web_scraping import PageContent, ProductInfo, ScrapingResult
from src.parsers.product_parser import ParsingResult


class TestPriceCheckResult(unittest.TestCase):
    """Test PriceCheckResult data class."""
    
    def test_success_result_creation(self):
        """Test creating a successful price check result."""
        result = PriceCheckResult.success_result(
            product_id=1,
            product_name="Test Product",
            url="https://example.com/product",
            old_price=100.0,
            new_price=90.0,
            price_dropped=True,
            is_new_lowest=True
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.product_id, 1)
        self.assertEqual(result.product_name, "Test Product")
        self.assertEqual(result.url, "https://example.com/product")
        self.assertEqual(result.old_price, 100.0)
        self.assertEqual(result.new_price, 90.0)
        self.assertTrue(result.price_dropped)
        self.assertTrue(result.is_new_lowest)
        self.assertIsNone(result.error_message)
        self.assertIsInstance(result.check_timestamp, datetime)
    
    def test_error_result_creation(self):
        """Test creating an error price check result."""
        result = PriceCheckResult.error_result(
            product_id=1,
            product_name="Test Product",
            url="https://example.com/product",
            error_message="Failed to fetch page"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.product_id, 1)
        self.assertEqual(result.product_name, "Test Product")
        self.assertEqual(result.url, "https://example.com/product")
        self.assertEqual(result.error_message, "Failed to fetch page")
        self.assertIsNone(result.old_price)
        self.assertIsNone(result.new_price)
        self.assertFalse(result.price_dropped)
        self.assertFalse(result.is_new_lowest)


class TestMonitoringStats(unittest.TestCase):
    """Test MonitoringStats data class."""
    
    def test_stats_completion(self):
        """Test completing monitoring stats."""
        start_time = datetime.now()
        stats = MonitoringStats(
            total_products=10,
            successful_checks=8,
            failed_checks=2,
            price_drops_detected=3,
            new_lowest_prices=1,
            start_time=start_time
        )
        
        # Initially not completed
        self.assertIsNone(stats.end_time)
        self.assertIsNone(stats.duration_seconds)
        
        # Complete the stats
        stats.complete()
        
        # Should now have end time and duration
        self.assertIsNotNone(stats.end_time)
        self.assertIsNotNone(stats.duration_seconds)
        self.assertGreaterEqual(stats.duration_seconds, 0)


class TestPriceMonitorService(unittest.TestCase):
    """Test PriceMonitorService functionality."""
    
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
            check_timeout=30
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
    
    def test_check_product_success_price_drop(self):
        """Test successful product check with price drop."""
        # Mock product service
        self.mock_product_service.get_product.return_value = self.sample_product
        self.mock_product_service.update_product_price.return_value = True
        
        # Mock web scraping
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock parsing
        product_info = ProductInfo(name="Test Product", price=85.0)
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        # Execute check
        result = self.service.check_product(1)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.product_id, 1)
        self.assertEqual(result.product_name, "Test Product")
        self.assertEqual(result.old_price, 100.0)
        self.assertEqual(result.new_price, 85.0)
        self.assertTrue(result.price_dropped)
        self.assertTrue(result.is_new_lowest)  # 85.0 < 90.0 (lowest_price)
        
        # Verify service calls
        self.mock_product_service.get_product.assert_called_once_with(1)
        self.mock_web_scraping_service.fetch_page_content.assert_called_once_with("https://example.com/product")
        self.mock_parser_service.parse_product.assert_called_once_with("https://example.com/product", page_content)
        self.mock_product_service.update_product_price.assert_called_once_with(1, 85.0, 'automatic')
    
    def test_check_product_success_no_price_drop(self):
        """Test successful product check without price drop."""
        # Mock product service
        self.mock_product_service.get_product.return_value = self.sample_product
        self.mock_product_service.update_product_price.return_value = True
        
        # Mock web scraping
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock parsing with higher price
        product_info = ProductInfo(name="Test Product", price=105.0)
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        # Execute check
        result = self.service.check_product(1)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.new_price, 105.0)
        self.assertFalse(result.price_dropped)
        self.assertFalse(result.is_new_lowest)
    
    def test_check_product_not_found(self):
        """Test checking non-existent product."""
        self.mock_product_service.get_product.return_value = None
        
        result = self.service.check_product(999)
        
        self.assertFalse(result.success)
        self.assertEqual(result.product_id, 999)
        self.assertIn("not found", result.error_message)
    
    def test_check_product_inactive(self):
        """Test checking inactive product."""
        inactive_product = Product(
            id=1,
            url="https://example.com/product",
            name="Test Product",
            current_price=100.0,
            previous_price=110.0,
            lowest_price=90.0,
            image_url="https://example.com/image.jpg",
            created_at=datetime.now(),
            last_checked=datetime.now(),
            is_active=False  # Inactive
        )
        self.mock_product_service.get_product.return_value = inactive_product
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("not active", result.error_message)
    
    def test_check_product_scraping_failure(self):
        """Test product check with scraping failure."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mock scraping failure
        scraping_result = ScrapingResult.error_result("Connection timeout")
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("Failed to fetch page", result.error_message)
    
    def test_check_product_parsing_failure(self):
        """Test product check with parsing failure."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mock successful scraping
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock parsing failure
        parsing_result = Mock()
        parsing_result.success = False
        parsing_result.error_message = "No price found"
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("Failed to parse product info", result.error_message)
    
    def test_check_product_no_price_in_result(self):
        """Test product check when parsing returns no price."""
        self.mock_product_service.get_product.return_value = self.sample_product
        
        # Mock successful scraping
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        # Mock parsing with no price
        product_info = ProductInfo(name="Test Product", price=None)
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("No price information found", result.error_message)
    
    def test_check_product_database_update_failure(self):
        """Test product check with database update failure."""
        self.mock_product_service.get_product.return_value = self.sample_product
        self.mock_product_service.update_product_price.return_value = False  # Update fails
        
        # Mock successful scraping and parsing
        page_content = PageContent(
            url="https://example.com/product",
            html="<html><body>Product page</body></html>",
            status_code=200,
            headers={}
        )
        scraping_result = ScrapingResult.success_result(page_content)
        self.mock_web_scraping_service.fetch_page_content.return_value = scraping_result
        
        product_info = ProductInfo(name="Test Product", price=95.0)
        parsing_result = Mock()
        parsing_result.success = True
        parsing_result.product_info = product_info
        self.mock_parser_service.parse_product.return_value = parsing_result
        
        result = self.service.check_product(1)
        
        self.assertFalse(result.success)
        self.assertIn("Failed to update product price", result.error_message)
    
    def test_check_all_products_empty_list(self):
        """Test checking all products when no products exist."""
        self.mock_product_service.get_products_for_monitoring.return_value = []
        
        results = self.service.check_all_products()
        
        self.assertEqual(len(results), 0)
    
    def test_check_all_products_success(self):
        """Test checking all products successfully."""
        # Mock multiple products
        products = [
            Product(id=1, url="https://example.com/product1", name="Product 1", 
                   current_price=100.0, lowest_price=90.0, is_active=True),
            Product(id=2, url="https://example.com/product2", name="Product 2", 
                   current_price=200.0, lowest_price=180.0, is_active=True)
        ]
        self.mock_product_service.get_products_for_monitoring.return_value = products
        
        # Mock successful individual checks
        with patch.object(self.service, 'check_product') as mock_check:
            mock_check.side_effect = [
                PriceCheckResult.success_result(1, "Product 1", "https://example.com/product1", 
                                              100.0, 95.0, True, False),
                PriceCheckResult.success_result(2, "Product 2", "https://example.com/product2", 
                                              200.0, 190.0, True, False)
            ]
            
            results = self.service.check_all_products()
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))
        
        # Check statistics
        stats = self.service.get_monitoring_stats()
        self.assertEqual(stats['last_run']['total_products'], 2)
        self.assertEqual(stats['last_run']['successful_checks'], 2)
        self.assertEqual(stats['last_run']['failed_checks'], 0)
        self.assertEqual(stats['last_run']['price_drops_detected'], 2)
    
    @patch('src.services.price_monitor_service.schedule')
    def test_schedule_daily_checks(self, mock_schedule):
        """Test scheduling daily checks."""
        mock_schedule.every.return_value.day.at.return_value.do = Mock()
        
        self.service.schedule_daily_checks("10:30")
        
        mock_schedule.clear.assert_called_once()
        mock_schedule.every.return_value.day.at.assert_called_once_with("10:30")
    
    def test_schedule_daily_checks_invalid_time(self):
        """Test scheduling with invalid time format."""
        with self.assertRaises(ValueError):
            self.service.schedule_daily_checks("25:00")  # Invalid hour
        
        with self.assertRaises(ValueError):
            self.service.schedule_daily_checks("10:70")  # Invalid minute
        
        with self.assertRaises(ValueError):
            self.service.schedule_daily_checks("invalid")  # Invalid format
    
    @patch('src.services.price_monitor_service.schedule')
    def test_start_stop_scheduler(self, mock_schedule):
        """Test starting and stopping the scheduler."""
        mock_schedule.every.return_value.day.at.return_value.do = Mock()
        mock_schedule.next_run.return_value = datetime.now() + timedelta(hours=1)
        
        # Initially not running
        self.assertFalse(self.service.is_scheduler_running())
        
        # Start scheduler
        self.service.start_scheduler("09:00")
        self.assertTrue(self.service.is_scheduler_running())
        
        # Give thread time to start
        time.sleep(0.1)
        
        # Stop scheduler
        self.service.stop_scheduler()
        self.assertFalse(self.service.is_scheduler_running())
    
    def test_run_immediate_check_all_products(self):
        """Test running immediate check for all products."""
        with patch.object(self.service, 'check_all_products') as mock_check_all:
            mock_check_all.return_value = [
                PriceCheckResult.success_result(1, "Product 1", "url1", 100.0, 95.0, True, False)
            ]
            
            results = self.service.run_immediate_check()
            
            mock_check_all.assert_called_once()
            self.assertEqual(len(results), 1)
    
    def test_run_immediate_check_specific_products(self):
        """Test running immediate check for specific products."""
        with patch.object(self.service, 'check_product') as mock_check:
            mock_check.side_effect = [
                PriceCheckResult.success_result(1, "Product 1", "url1", 100.0, 95.0, True, False),
                PriceCheckResult.success_result(2, "Product 2", "url2", 200.0, 190.0, True, False)
            ]
            
            results = self.service.run_immediate_check([1, 2])
            
            self.assertEqual(mock_check.call_count, 2)
            self.assertEqual(len(results), 2)
    
    def test_get_monitoring_stats(self):
        """Test getting monitoring statistics."""
        # Initially no stats
        stats = self.service.get_monitoring_stats()
        self.assertEqual(stats['total_runs'], 0)
        self.assertEqual(stats['total_price_drops'], 0)
        self.assertFalse(stats['scheduler_running'])
        self.assertIsNone(stats['last_run'])
        
        # Simulate a run
        self.service._total_runs = 1
        self.service._total_price_drops = 2
        self.service._last_run_stats = MonitoringStats(
            total_products=5,
            successful_checks=4,
            failed_checks=1,
            price_drops_detected=2,
            new_lowest_prices=1,
            start_time=datetime.now()
        )
        self.service._last_run_stats.complete()
        
        stats = self.service.get_monitoring_stats()
        self.assertEqual(stats['total_runs'], 1)
        self.assertEqual(stats['total_price_drops'], 2)
        self.assertIsNotNone(stats['last_run'])
        self.assertEqual(stats['last_run']['total_products'], 5)
    
    def test_get_price_comparison_summary(self):
        """Test getting price comparison summary."""
        # Mock product and price history
        product = Product(
            id=1, name="Test Product", current_price=95.0, lowest_price=85.0,
            url="https://example.com", is_active=True
        )
        self.mock_product_service.get_product.return_value = product
        
        # Mock price history (prices going down over time - most recent first)
        from src.models.database import PriceHistory
        price_history = [
            PriceHistory(id=3, product_id=1, price=95.0, recorded_at=datetime.now(), source='automatic'),
            PriceHistory(id=2, product_id=1, price=100.0, recorded_at=datetime.now() - timedelta(days=5), source='automatic'),
            PriceHistory(id=1, product_id=1, price=105.0, recorded_at=datetime.now() - timedelta(days=10), source='automatic')
        ]
        self.mock_product_service.get_price_history.return_value = price_history
        
        summary = self.service.get_price_comparison_summary(1, 30)
        
        self.assertEqual(summary['product_name'], "Test Product")
        self.assertEqual(summary['current_price'], 95.0)
        self.assertEqual(summary['lowest_price'], 85.0)
        self.assertEqual(summary['highest_price_in_period'], 105.0)
        self.assertEqual(summary['lowest_price_in_period'], 95.0)
        self.assertEqual(summary['price_changes'], 2)
        self.assertEqual(summary['average_price'], 100.0)
        self.assertEqual(summary['price_trend'], 'decreasing')
    
    def test_get_price_comparison_summary_no_history(self):
        """Test price comparison summary with no price history."""
        product = Product(
            id=1, name="Test Product", current_price=95.0, lowest_price=85.0,
            url="https://example.com", is_active=True
        )
        self.mock_product_service.get_product.return_value = product
        self.mock_product_service.get_price_history.return_value = []
        
        summary = self.service.get_price_comparison_summary(1, 30)
        
        self.assertEqual(summary['product_name'], "Test Product")
        self.assertEqual(summary['current_price'], 95.0)
        self.assertEqual(summary['price_changes'], 0)
        self.assertEqual(summary['average_price'], 95.0)
        self.assertEqual(summary['price_trend'], 'stable')
    
    def test_get_price_comparison_summary_product_not_found(self):
        """Test price comparison summary for non-existent product."""
        self.mock_product_service.get_product.return_value = None
        
        summary = self.service.get_price_comparison_summary(999, 30)
        
        self.assertIn('error', summary)
        self.assertEqual(summary['error'], 'Product not found')


if __name__ == '__main__':
    unittest.main()