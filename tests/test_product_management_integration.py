"""
Integration tests for complete product management workflow.
"""
import unittest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from src.app import SecureFlaskApp
from src.services.config_service import ConfigService
from src.models.database import Product, PriceHistory
from src.models.web_scraping import PageContent, ProductInfo
from src.services.parser_service import ParsingServiceResult
from src.services.web_scraping_service import ScrapingResult
from src.services.price_monitor_service import PriceCheckResult


class TestProductManagementIntegration(unittest.TestCase):
    """Integration tests for complete product management workflow."""
    
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
        
        # Create sample products
        self.sample_products = [
            Product(
                id=1,
                url="https://example.com/product/1",
                name="Test Product 1",
                current_price=99.99,
                previous_price=109.99,
                lowest_price=89.99,
                image_url="https://example.com/image1.jpg",
                created_at=datetime(2023, 1, 1, 12, 0, 0),
                last_checked=datetime(2023, 1, 2, 12, 0, 0),
                is_active=True
            ),
            Product(
                id=2,
                url="https://example.com/product/2",
                name="Another Product",
                current_price=49.99,
                previous_price=49.99,
                lowest_price=39.99,
                image_url=None,
                created_at=datetime(2023, 1, 1, 10, 0, 0),
                last_checked=datetime(2023, 1, 2, 10, 0, 0),
                is_active=True
            ),
            Product(
                id=3,
                url="https://example.com/product/3",
                name="Inactive Product",
                current_price=29.99,
                previous_price=34.99,
                lowest_price=25.99,
                image_url=None,
                created_at=datetime(2023, 1, 1, 8, 0, 0),
                last_checked=datetime(2023, 1, 1, 8, 0, 0),
                is_active=False
            )
        ]
        
        # Create sample price history
        self.sample_price_history = [
            PriceHistory(
                id=1,
                product_id=1,
                price=99.99,
                recorded_at=datetime(2023, 1, 2, 12, 0, 0),
                source='automatic'
            ),
            PriceHistory(
                id=2,
                product_id=1,
                price=109.99,
                recorded_at=datetime(2023, 1, 1, 12, 0, 0),
                source='manual'
            )
        ]
    
    def _create_app_client(self):
        """Create a test client for the Flask app."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            client = app.app.test_client()
            
            # Mock the g.client_id for authentication
            with app.app.app_context():
                from flask import g
                g.client_id = 'test_client'
                return client, app
    
    def test_product_listing_with_filtering_and_sorting(self):
        """Test product listing with various filtering and sorting options."""
        client, app = self._create_app_client()
        
        with patch.object(app.product_service, 'get_all_products', return_value=self.sample_products):
            # Test default listing (active only, sorted by created_at desc)
            response = client.get('/api/products')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            
            self.assertEqual(len(data['products']), 2)  # Only active products
            self.assertEqual(data['total_count'], 2)
            self.assertEqual(data['filters']['active_only'], True)
            self.assertEqual(data['filters']['sort_by'], 'created_at')
            self.assertEqual(data['filters']['sort_order'], 'desc')
            
            # Test including inactive products
            response = client.get('/api/products?active_only=false')
            data = json.loads(response.data)
            self.assertEqual(len(data['products']), 3)  # All products
            self.assertEqual(data['total_count'], 3)
            
            # Test sorting by name ascending
            response = client.get('/api/products?sort_by=name&sort_order=asc')
            data = json.loads(response.data)
            product_names = [p['name'] for p in data['products']]
            self.assertEqual(product_names, ['Another Product', 'Test Product 1'])
            
            # Test sorting by price descending
            response = client.get('/api/products?sort_by=current_price&sort_order=desc')
            data = json.loads(response.data)
            prices = [p['current_price'] for p in data['products']]
            self.assertEqual(prices, [99.99, 49.99])
            
            # Test search functionality
            response = client.get('/api/products?search=Another')
            data = json.loads(response.data)
            self.assertEqual(len(data['products']), 1)
            self.assertEqual(data['products'][0]['name'], 'Another Product')
            
            # Test pagination
            response = client.get('/api/products?limit=1&offset=0')
            data = json.loads(response.data)
            self.assertEqual(len(data['products']), 1)
            self.assertEqual(data['count'], 1)
            self.assertEqual(data['total_count'], 2)
            self.assertEqual(data['offset'], 0)
            self.assertEqual(data['limit'], 1)
    
    def test_product_listing_validation(self):
        """Test validation of product listing parameters."""
        client, app = self._create_app_client()
        
        # Test invalid sort field
        response = client.get('/api/products?sort_by=invalid_field')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid sort field')
        
        # Test invalid sort order
        response = client.get('/api/products?sort_order=invalid')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid sort order')
        
        # Test invalid limit
        response = client.get('/api/products?limit=-1')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid limit')
        
        # Test invalid offset
        response = client.get('/api/products?offset=-1')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid offset')
    
    def test_product_deletion_with_confirmation(self):
        """Test product deletion with confirmation workflow."""
        client, app = self._create_app_client()
        
        product = self.sample_products[0]
        
        with patch.object(app.product_service, 'get_product', return_value=product):
            # Test deletion without confirmation
            response = client.delete('/api/products/1')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            
            self.assertTrue(data['requires_confirmation'])
            self.assertEqual(data['product']['id'], 1)
            self.assertEqual(data['product']['name'], 'Test Product 1')
            self.assertIn('confirmation', data['message'])
            
            # Test deletion with confirmation
            with patch.object(app.product_service, 'delete_product', return_value=True):
                response = client.delete('/api/products/1?confirm=true')
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)
                
                self.assertEqual(data['message'], 'Product deleted successfully')
                self.assertEqual(data['product_id'], 1)
                self.assertEqual(data['product_name'], 'Test Product 1')
    
    def test_complete_product_workflow(self):
        """Test complete product management workflow from add to delete."""
        client, app = self._create_app_client()
        
        # Step 1: Add a new product
        mock_scraping_result = ScrapingResult(
            success=True,
            page_content=PageContent(html="<html>Test</html>", url="https://example.com/new-product")
        )
        
        mock_product_info = ProductInfo(
            name="New Test Product",
            price=79.99,
            image_url="https://example.com/new-image.jpg"
        )
        
        mock_parsing_result = ParsingServiceResult.success_result(
            mock_product_info, "test_parser", 0.9, []
        )
        
        new_product = Product(
            id=4,
            url="https://example.com/new-product",
            name="New Test Product",
            current_price=79.99,
            previous_price=None,
            lowest_price=79.99,
            image_url="https://example.com/new-image.jpg",
            created_at=datetime(2023, 1, 3, 12, 0, 0),
            last_checked=datetime(2023, 1, 3, 12, 0, 0),
            is_active=True
        )
        
        with patch.object(app.product_service, 'get_product_by_url', return_value=None), \
             patch.object(app.web_scraping_service, 'fetch_page_content', return_value=mock_scraping_result), \
             patch.object(app.parser_service, 'parse_product', return_value=mock_parsing_result), \
             patch.object(app.product_service, 'add_product', return_value=new_product):
            
            response = client.post('/api/products', 
                                 json={'url': 'https://example.com/new-product'},
                                 content_type='application/json')
            
            self.assertEqual(response.status_code, 201)
            data = json.loads(response.data)
            self.assertEqual(data['message'], 'Product added successfully')
            self.assertEqual(data['product']['name'], 'New Test Product')
        
        # Step 2: Get product details
        with patch.object(app.product_service, 'get_product', return_value=new_product), \
             patch.object(app.product_service, 'get_price_history', return_value=[]):
            
            response = client.get('/api/products/4')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['product']['name'], 'New Test Product')
        
        # Step 3: Update price manually
        mock_result = PriceCheckResult.success_result(
            4, "New Test Product", "https://example.com/new-product",
            79.99, 69.99, True, True, True, None
        )
        
        updated_product = Product(
            id=4,
            url="https://example.com/new-product",
            name="New Test Product",
            current_price=69.99,
            previous_price=79.99,
            lowest_price=69.99,
            image_url="https://example.com/new-image.jpg",
            created_at=datetime(2023, 1, 3, 12, 0, 0),
            last_checked=datetime(2023, 1, 3, 13, 0, 0),
            is_active=True
        )
        
        with patch.object(app.product_service, 'get_product', side_effect=[new_product, updated_product]), \
             patch.object(app.price_monitor_service, 'update_product_price_manually', return_value=mock_result):
            
            response = client.put('/api/products/4/price', 
                                json={'price': 69.99},
                                content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['message'], 'Price updated successfully')
            self.assertTrue(data['price_change']['price_dropped'])
        
        # Step 4: Get price history
        history = [
            PriceHistory(
                id=3,
                product_id=4,
                price=69.99,
                recorded_at=datetime(2023, 1, 3, 13, 0, 0),
                source='manual'
            ),
            PriceHistory(
                id=4,
                product_id=4,
                price=79.99,
                recorded_at=datetime(2023, 1, 3, 12, 0, 0),
                source='automatic'
            )
        ]
        
        with patch.object(app.product_service, 'get_product', return_value=updated_product), \
             patch.object(app.product_service, 'get_price_history', return_value=history):
            
            response = client.get('/api/products/4/history')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data['history']), 2)
            self.assertEqual(data['history'][0]['price'], 69.99)
            self.assertEqual(data['history'][0]['source'], 'manual')
        
        # Step 5: Delete the product
        with patch.object(app.product_service, 'get_product', return_value=updated_product), \
             patch.object(app.product_service, 'delete_product', return_value=True):
            
            # First call without confirmation
            response = client.delete('/api/products/4')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data['requires_confirmation'])
            
            # Second call with confirmation
            response = client.delete('/api/products/4?confirm=true')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['message'], 'Product deleted successfully')
    
    def test_price_change_calculation(self):
        """Test that price change information is calculated correctly."""
        client, app = self._create_app_client()
        
        with patch.object(app.product_service, 'get_all_products', return_value=self.sample_products):
            response = client.get('/api/products')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            
            # Find the product with price change
            product_with_change = next(p for p in data['products'] if p['id'] == 1)
            
            self.assertIsNotNone(product_with_change['price_change'])
            self.assertEqual(product_with_change['price_change']['direction'], 'drop')
            self.assertAlmostEqual(product_with_change['price_change']['amount'], -10.0, places=2)
            self.assertAlmostEqual(product_with_change['price_change']['percentage'], -9.09, places=1)
            
            # Find the product without price change
            product_without_change = next(p for p in data['products'] if p['id'] == 2)
            self.assertIsNone(product_without_change['price_change'])
    
    def test_error_handling_in_workflow(self):
        """Test error handling throughout the product management workflow."""
        client, app = self._create_app_client()
        
        # Test adding product with invalid URL
        response = client.post('/api/products', 
                             json={'url': ''},
                             content_type='application/json')
        self.assertEqual(response.status_code, 400)
        
        # Test getting non-existent product
        with patch.object(app.product_service, 'get_product', return_value=None):
            response = client.get('/api/products/999')
            self.assertEqual(response.status_code, 404)
        
        # Test updating price for non-existent product
        with patch.object(app.product_service, 'get_product', return_value=None):
            response = client.put('/api/products/999/price', 
                                json={'price': 50.0},
                                content_type='application/json')
            self.assertEqual(response.status_code, 404)
        
        # Test deleting non-existent product
        with patch.object(app.product_service, 'get_product', return_value=None):
            response = client.delete('/api/products/999')
            self.assertEqual(response.status_code, 404)
        
        # Test getting price history for non-existent product
        with patch.object(app.product_service, 'get_product', return_value=None):
            response = client.get('/api/products/999/history')
            self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()