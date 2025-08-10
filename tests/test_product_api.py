"""
Tests for product management API endpoints.
"""
import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.app import SecureFlaskApp
from src.services.config_service import ConfigService
from src.models.database import Product, PriceHistory
from src.models.web_scraping import PageContent, ProductInfo
from src.services.parser_service import ParsingServiceResult
from src.services.web_scraping_service import ScrapingResult
from src.services.price_monitor_service import PriceCheckResult


class TestProductAPI(unittest.TestCase):
    """Test cases for product management API endpoints."""
    
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
        
        # Create sample product
        self.sample_product = Product(
            id=1,
            url="https://example.com/product/1",
            name="Test Product",
            current_price=99.99,
            previous_price=109.99,
            lowest_price=89.99,
            image_url="https://example.com/image.jpg",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            last_checked=datetime(2023, 1, 2, 12, 0, 0),
            is_active=True
        )
        
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
            
            # Mock the authentication to always pass
            client = app.app.test_client()
            
            # Mock the g.client_id for authentication
            with app.app.app_context():
                from flask import g
                g.client_id = 'test_client'
                return client, app
    
    def test_get_products_empty(self):
        """Test getting products when none exist."""
        client, app = self._create_app_client()
        
        with patch.object(app.product_service, 'get_all_products', return_value=[]):
            response = client.get('/api/products')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['products'], [])
            self.assertEqual(data['count'], 0)
            self.assertIn('client_id', data)
    
    def test_get_products_with_data(self, app_client, sample_product):
        """Test getting products with data."""
        with patch.object(app_client.application.product_service, 'get_all_products', return_value=[sample_product]):
            response = app_client.get('/api/products')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['products']) == 1
            assert data['count'] == 1
            
            product = data['products'][0]
            assert product['id'] == 1
            assert product['name'] == "Test Product"
            assert product['current_price'] == 99.99
            assert product['url'] == "https://example.com/product/1"
    
    def test_get_products_active_only_filter(self, app_client):
        """Test getting products with active_only filter."""
        with patch.object(app_client.application.product_service, 'get_all_products') as mock_get:
            # Test active_only=true (default)
            app_client.get('/api/products')
            mock_get.assert_called_with(active_only=True)
            
            # Test active_only=false
            app_client.get('/api/products?active_only=false')
            mock_get.assert_called_with(active_only=False)
    
    def test_get_products_error(self, app_client):
        """Test error handling in get products."""
        with patch.object(app_client.application.product_service, 'get_all_products', side_effect=Exception("Database error")):
            response = app_client.get('/api/products')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['error'] == 'Internal server error'
    
    def test_add_product_success(self, app_client, sample_product):
        """Test successfully adding a product."""
        # Mock the services
        mock_scraping_result = ScrapingResult(
            success=True,
            page_content=PageContent(html="<html>Test</html>", url="https://example.com/product/1")
        )
        
        mock_product_info = ProductInfo(
            name="Test Product",
            price=99.99,
            image_url="https://example.com/image.jpg"
        )
        
        mock_parsing_result = ParsingServiceResult.success_result(
            mock_product_info, "test_parser", 0.9, []
        )
        
        with patch.object(app_client.application.product_service, 'get_product_by_url', return_value=None), \
             patch.object(app_client.application.web_scraping_service, 'fetch_page_content', return_value=mock_scraping_result), \
             patch.object(app_client.application.parser_service, 'parse_product', return_value=mock_parsing_result), \
             patch.object(app_client.application.product_service, 'add_product', return_value=sample_product):
            
            response = app_client.post('/api/products', 
                                     json={'url': 'https://example.com/product/1'},
                                     content_type='application/json')
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['message'] == 'Product added successfully'
            assert data['product']['name'] == 'Test Product'
            assert data['product']['current_price'] == 99.99
    
    def test_add_product_missing_url(self, app_client):
        """Test adding product without URL."""
        response = app_client.post('/api/products', 
                                 json={},
                                 content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Invalid request'
        assert 'URL is required' in data['message']
    
    def test_add_product_empty_url(self, app_client):
        """Test adding product with empty URL."""
        response = app_client.post('/api/products', 
                                 json={'url': '   '},
                                 content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Invalid request'
        assert 'URL cannot be empty' in data['message']
    
    def test_add_product_already_exists(self, app_client, sample_product):
        """Test adding product that already exists."""
        with patch.object(app_client.application.product_service, 'get_product_by_url', return_value=sample_product):
            response = app_client.post('/api/products', 
                                     json={'url': 'https://example.com/product/1'},
                                     content_type='application/json')
            
            assert response.status_code == 409
            data = json.loads(response.data)
            assert data['error'] == 'Product already exists'
            assert data['product_id'] == 1
    
    def test_add_product_scraping_failed(self, app_client):
        """Test adding product when scraping fails."""
        mock_scraping_result = ScrapingResult(
            success=False,
            error_message="Failed to fetch page"
        )
        
        with patch.object(app_client.application.product_service, 'get_product_by_url', return_value=None), \
             patch.object(app_client.application.web_scraping_service, 'fetch_page_content', return_value=mock_scraping_result):
            
            response = app_client.post('/api/products', 
                                     json={'url': 'https://example.com/product/1'},
                                     content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error'] == 'Failed to fetch product page'
    
    def test_add_product_parsing_failed(self, app_client):
        """Test adding product when parsing fails."""
        mock_scraping_result = ScrapingResult(
            success=True,
            page_content=PageContent(html="<html>Test</html>", url="https://example.com/product/1")
        )
        
        mock_parsing_result = ParsingServiceResult.error_result("Failed to parse", [])
        
        with patch.object(app_client.application.product_service, 'get_product_by_url', return_value=None), \
             patch.object(app_client.application.web_scraping_service, 'fetch_page_content', return_value=mock_scraping_result), \
             patch.object(app_client.application.parser_service, 'parse_product', return_value=mock_parsing_result):
            
            response = app_client.post('/api/products', 
                                     json={'url': 'https://example.com/product/1'},
                                     content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error'] == 'Failed to parse product information'
    
    def test_delete_product_success(self, app_client, sample_product):
        """Test successfully deleting a product."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=sample_product), \
             patch.object(app_client.application.product_service, 'delete_product', return_value=True):
            
            response = app_client.delete('/api/products/1')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == 'Product deleted successfully'
            assert data['product_id'] == 1
            assert data['product_name'] == 'Test Product'
    
    def test_delete_product_not_found(self, app_client):
        """Test deleting non-existent product."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=None):
            response = app_client.delete('/api/products/999')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Product not found'
    
    def test_delete_product_database_error(self, app_client, sample_product):
        """Test deleting product with database error."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=sample_product), \
             patch.object(app_client.application.product_service, 'delete_product', return_value=False):
            
            response = app_client.delete('/api/products/1')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['error'] == 'Failed to delete product'
    
    def test_update_product_price_success(self, app_client, sample_product):
        """Test successfully updating product price."""
        mock_result = PriceCheckResult.success_result(
            1, "Test Product", "https://example.com/product/1",
            99.99, 89.99, True, True, True, None
        )
        
        updated_product = Product(
            id=1,
            url="https://example.com/product/1",
            name="Test Product",
            current_price=89.99,
            previous_price=99.99,
            lowest_price=89.99,
            image_url="https://example.com/image.jpg",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            last_checked=datetime(2023, 1, 2, 12, 0, 0),
            is_active=True
        )
        
        with patch.object(app_client.application.product_service, 'get_product', side_effect=[sample_product, updated_product]), \
             patch.object(app_client.application.price_monitor_service, 'update_product_price_manually', return_value=mock_result):
            
            response = app_client.put('/api/products/1/price', 
                                    json={'price': 89.99},
                                    content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == 'Price updated successfully'
            assert data['product']['current_price'] == 89.99
            assert data['price_change']['price_dropped'] == True
            assert data['price_change']['is_new_lowest'] == True
    
    def test_update_product_price_missing_price(self, app_client):
        """Test updating product price without price."""
        response = app_client.put('/api/products/1/price', 
                                json={},
                                content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Invalid request'
        assert 'Price is required' in data['message']
    
    def test_update_product_price_invalid_price(self, app_client):
        """Test updating product price with invalid price."""
        response = app_client.put('/api/products/1/price', 
                                json={'price': -10.0},
                                content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Invalid price'
    
    def test_update_product_price_not_found(self, app_client):
        """Test updating price for non-existent product."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=None):
            response = app_client.put('/api/products/999/price', 
                                    json={'price': 89.99},
                                    content_type='application/json')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Product not found'
    
    def test_get_price_history_success(self, app_client, sample_product, sample_price_history):
        """Test successfully getting price history."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=sample_product), \
             patch.object(app_client.application.product_service, 'get_price_history', return_value=sample_price_history):
            
            response = app_client.get('/api/products/1/history')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['product']['id'] == 1
            assert data['product']['name'] == 'Test Product'
            assert len(data['history']) == 2
            assert data['count'] == 2
            assert data['history'][0]['price'] == 99.99
            assert data['history'][0]['source'] == 'automatic'
    
    def test_get_price_history_with_limit(self, app_client, sample_product):
        """Test getting price history with limit parameter."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=sample_product), \
             patch.object(app_client.application.product_service, 'get_price_history') as mock_get_history:
            
            app_client.get('/api/products/1/history?limit=5')
            mock_get_history.assert_called_with(1, limit=5)
    
    def test_get_price_history_invalid_limit(self, app_client):
        """Test getting price history with invalid limit."""
        response = app_client.get('/api/products/1/history?limit=-1')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Invalid limit'
    
    def test_get_price_history_not_found(self, app_client):
        """Test getting price history for non-existent product."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=None):
            response = app_client.get('/api/products/999/history')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Product not found'
    
    def test_get_product_details_success(self, app_client, sample_product, sample_price_history):
        """Test successfully getting product details."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=sample_product), \
             patch.object(app_client.application.product_service, 'get_price_history', return_value=sample_price_history):
            
            response = app_client.get('/api/products/1')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['product']['id'] == 1
            assert data['product']['name'] == 'Test Product'
            assert len(data['recent_history']) == 2
    
    def test_get_product_details_not_found(self, app_client):
        """Test getting details for non-existent product."""
        with patch.object(app_client.application.product_service, 'get_product', return_value=None):
            response = app_client.get('/api/products/999')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Product not found'
    
    def test_get_statistics_success(self, app_client):
        """Test successfully getting system statistics."""
        mock_product_stats = {
            'total_products': 5,
            'active_products': 4,
            'inactive_products': 1,
            'recent_price_drops': 2
        }
        
        mock_monitoring_stats = {
            'total_runs': 10,
            'total_price_drops': 15,
            'scheduler_running': True,
            'last_run': {
                'timestamp': '2023-01-01T12:00:00',
                'successful_checks': 4,
                'failed_checks': 0
            }
        }
        
        next_run = datetime(2023, 1, 2, 9, 0, 0)
        
        with patch.object(app_client.application.product_service, 'get_product_statistics', return_value=mock_product_stats), \
             patch.object(app_client.application.price_monitor_service, 'get_monitoring_stats', return_value=mock_monitoring_stats), \
             patch.object(app_client.application.price_monitor_service, 'get_next_scheduled_run', return_value=next_run):
            
            response = app_client.get('/api/stats')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['products']['total_products'] == 5
            assert data['monitoring']['total_runs'] == 10
            assert data['next_scheduled_run'] == '2023-01-02T09:00:00'
    
    def test_health_check(self, app_client):
        """Test health check endpoint."""
        response = app_client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'price-monitor'
        assert 'client_id' in data
    
    def test_error_handlers(self, app_client):
        """Test error handlers."""
        # Test 404
        response = app_client.get('/api/nonexistent')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Not found'
        
        # Test 405
        response = app_client.patch('/api/products')
        assert response.status_code == 405
        data = json.loads(response.data)
        assert data['error'] == 'Method not allowed'


if __name__ == '__main__':
    pytest.main([__file__])