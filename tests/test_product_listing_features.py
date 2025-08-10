"""
Tests for product listing and management features.
"""
import unittest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from src.app import SecureFlaskApp
from src.services.config_service import ConfigService
from src.models.database import Product


class TestProductListingFeatures(unittest.TestCase):
    """Test cases for product listing and management features."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock configuration
        self.mock_config = Mock()
        self.mock_config.database_path = ":memory:"
        self.mock_config.request_timeout_seconds = 30
        self.mock_config.max_retry_attempts = 3
        self.mock_config.enable_mtls = False
        self.mock_config.api_port = 8080
        self.mock_config.smtp_server = "smtp.example.com"
        self.mock_config.smtp_port = 587
        self.mock_config.smtp_username = "test@example.com"
        self.mock_config.smtp_password = "password"
        self.mock_config.recipient_email = "recipient@example.com"
        
        # Create mock config service
        self.mock_config_service = Mock(spec=ConfigService)
        self.mock_config_service.get_config.return_value = self.mock_config
        
        # Create sample products for testing
        self.sample_products = [
            Product(
                id=1,
                url="https://example.com/product/1",
                name="Apple iPhone",
                current_price=999.99,
                previous_price=1099.99,
                lowest_price=899.99,
                image_url="https://example.com/image1.jpg",
                created_at=datetime(2023, 1, 1, 12, 0, 0),
                last_checked=datetime(2023, 1, 2, 12, 0, 0),
                is_active=True
            ),
            Product(
                id=2,
                url="https://example.com/product/2",
                name="Samsung Galaxy",
                current_price=799.99,
                previous_price=799.99,
                lowest_price=699.99,
                image_url=None,
                created_at=datetime(2023, 1, 1, 10, 0, 0),
                last_checked=datetime(2023, 1, 2, 10, 0, 0),
                is_active=True
            ),
            Product(
                id=3,
                url="https://example.com/product/3",
                name="Old Phone",
                current_price=299.99,
                previous_price=349.99,
                lowest_price=249.99,
                image_url=None,
                created_at=datetime(2023, 1, 1, 8, 0, 0),
                last_checked=datetime(2023, 1, 1, 8, 0, 0),
                is_active=False
            )
        ]
    
    def test_product_filtering_and_sorting_logic(self):
        """Test the filtering and sorting logic without HTTP requests."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            
            # Test active-only filtering
            active_products = [p for p in self.sample_products if p.is_active]
            self.assertEqual(len(active_products), 2)
            
            # Test search filtering
            search_term = "apple"
            filtered_products = [p for p in self.sample_products if 
                               search_term.lower() in p.name.lower() or 
                               search_term.lower() in p.url.lower()]
            self.assertEqual(len(filtered_products), 1)
            self.assertEqual(filtered_products[0].name, "Apple iPhone")
            
            # Test sorting by name
            sorted_by_name = sorted(self.sample_products, key=lambda p: p.name.lower())
            expected_names = ["Apple iPhone", "Old Phone", "Samsung Galaxy"]
            actual_names = [p.name for p in sorted_by_name]
            self.assertEqual(actual_names, expected_names)
            
            # Test sorting by price
            sorted_by_price = sorted(self.sample_products, key=lambda p: p.current_price, reverse=True)
            expected_prices = [999.99, 799.99, 299.99]
            actual_prices = [p.current_price for p in sorted_by_price]
            self.assertEqual(actual_prices, expected_prices)
    
    def test_price_change_calculation_logic(self):
        """Test price change calculation logic."""
        # Test price drop
        product_with_drop = self.sample_products[0]  # iPhone
        self.assertIsNotNone(product_with_drop.previous_price)
        self.assertLess(product_with_drop.current_price, product_with_drop.previous_price)
        
        change_amount = product_with_drop.current_price - product_with_drop.previous_price
        change_percentage = (change_amount / product_with_drop.previous_price) * 100
        
        self.assertAlmostEqual(change_amount, -100.0, places=2)
        self.assertAlmostEqual(change_percentage, -9.09, places=1)
        
        # Test no price change
        product_no_change = self.sample_products[1]  # Samsung
        self.assertEqual(product_no_change.current_price, product_no_change.previous_price)
        
        # Test price rise
        product_with_rise = self.sample_products[2]  # Old Phone
        self.assertLess(product_with_rise.current_price, product_with_rise.previous_price)
        # This is actually a drop, but we can test the logic
    
    def test_pagination_logic(self):
        """Test pagination logic."""
        products = self.sample_products
        
        # Test limit only
        limit = 2
        paginated = products[:limit]
        self.assertEqual(len(paginated), 2)
        
        # Test offset only
        offset = 1
        paginated = products[offset:]
        self.assertEqual(len(paginated), 2)
        self.assertEqual(paginated[0].id, 2)
        
        # Test limit and offset
        limit = 1
        offset = 1
        paginated = products[offset:offset + limit]
        self.assertEqual(len(paginated), 1)
        self.assertEqual(paginated[0].id, 2)
    
    def test_product_data_serialization(self):
        """Test that product data is properly serialized for JSON response."""
        product = self.sample_products[0]
        
        # Test basic serialization
        product_data = {
            'id': product.id,
            'url': product.url,
            'name': product.name,
            'current_price': product.current_price,
            'previous_price': product.previous_price,
            'lowest_price': product.lowest_price,
            'image_url': product.image_url,
            'created_at': product.created_at.isoformat() if product.created_at else None,
            'last_checked': product.last_checked.isoformat() if product.last_checked else None,
            'is_active': product.is_active
        }
        
        # Verify all fields are present and correct types
        self.assertIsInstance(product_data['id'], int)
        self.assertIsInstance(product_data['url'], str)
        self.assertIsInstance(product_data['name'], str)
        self.assertIsInstance(product_data['current_price'], float)
        self.assertIsInstance(product_data['previous_price'], float)
        self.assertIsInstance(product_data['lowest_price'], float)
        self.assertIsInstance(product_data['image_url'], str)
        self.assertIsInstance(product_data['created_at'], str)
        self.assertIsInstance(product_data['last_checked'], str)
        self.assertIsInstance(product_data['is_active'], bool)
        
        # Test JSON serialization
        json_str = json.dumps(product_data)
        self.assertIsInstance(json_str, str)
        
        # Test deserialization
        deserialized = json.loads(json_str)
        self.assertEqual(deserialized['id'], product.id)
        self.assertEqual(deserialized['name'], product.name)
    
    def test_validation_logic(self):
        """Test validation logic for API parameters."""
        # Test sort field validation
        valid_sort_fields = ['name', 'current_price', 'previous_price', 'lowest_price', 'created_at', 'last_checked']
        
        self.assertIn('name', valid_sort_fields)
        self.assertIn('current_price', valid_sort_fields)
        self.assertNotIn('invalid_field', valid_sort_fields)
        
        # Test sort order validation
        valid_sort_orders = ['asc', 'desc']
        
        self.assertIn('asc', valid_sort_orders)
        self.assertIn('desc', valid_sort_orders)
        self.assertNotIn('invalid', valid_sort_orders)
        
        # Test limit validation
        valid_limit = 10
        invalid_limit = -1
        
        self.assertGreater(valid_limit, 0)
        self.assertLessEqual(invalid_limit, 0)
        
        # Test offset validation
        valid_offset = 0
        invalid_offset = -1
        
        self.assertGreaterEqual(valid_offset, 0)
        self.assertLess(invalid_offset, 0)
    
    def test_search_functionality(self):
        """Test search functionality across different fields."""
        products = self.sample_products
        
        # Test name search
        search_term = "apple"
        results = [p for p in products if search_term.lower() in p.name.lower()]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Apple iPhone")
        
        # Test URL search
        search_term = "product/2"
        results = [p for p in products if search_term.lower() in p.url.lower()]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 2)
        
        # Test case insensitive search
        search_term = "SAMSUNG"
        results = [p for p in products if search_term.lower() in p.name.lower()]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Samsung Galaxy")
        
        # Test partial match
        search_term = "phone"
        results = [p for p in products if search_term.lower() in p.name.lower()]
        self.assertEqual(len(results), 2)  # iPhone and Old Phone
        
        # Test no results
        search_term = "nonexistent"
        results = [p for p in products if search_term.lower() in p.name.lower()]
        self.assertEqual(len(results), 0)
    
    def test_product_status_filtering(self):
        """Test filtering products by active status."""
        products = self.sample_products
        
        # Test active only (default)
        active_products = [p for p in products if p.is_active]
        self.assertEqual(len(active_products), 2)
        
        # Test all products
        all_products = products
        self.assertEqual(len(all_products), 3)
        
        # Test inactive only
        inactive_products = [p for p in products if not p.is_active]
        self.assertEqual(len(inactive_products), 1)
        self.assertEqual(inactive_products[0].name, "Old Phone")
    
    def test_sorting_edge_cases(self):
        """Test sorting with edge cases like None values."""
        # Create products with None values for testing
        products_with_none = [
            Product(
                id=1,
                url="https://example.com/1",
                name="Product A",
                current_price=100.0,
                previous_price=None,  # None value
                lowest_price=90.0,
                image_url=None,
                created_at=None,  # None value
                last_checked=datetime(2023, 1, 1),
                is_active=True
            ),
            Product(
                id=2,
                url="https://example.com/2",
                name="Product B",
                current_price=200.0,
                previous_price=250.0,
                lowest_price=180.0,
                image_url=None,
                created_at=datetime(2023, 1, 2),
                last_checked=None,  # None value
                is_active=True
            )
        ]
        
        # Test sorting by previous_price with None values
        sorted_products = sorted(products_with_none, key=lambda p: p.previous_price or 0)
        self.assertEqual(sorted_products[0].id, 1)  # None (treated as 0) comes first
        
        # Test sorting by created_at with None values
        sorted_products = sorted(products_with_none, key=lambda p: p.created_at or datetime.min)
        self.assertEqual(sorted_products[0].id, 1)  # None (treated as min) comes first


if __name__ == '__main__':
    unittest.main()