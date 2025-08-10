"""
Integration tests for the product management API.
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


class TestProductAPIIntegration(unittest.TestCase):
    """Integration tests for product management API endpoints."""
    
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
    
    def test_health_endpoint(self):
        """Test the health check endpoint."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                with app.app.app_context():
                    from flask import g
                    g.client_id = 'test_client'
                    
                    response = client.get('/health')
                    
                    self.assertEqual(response.status_code, 200)
                    data = json.loads(response.data)
                    self.assertEqual(data['status'], 'healthy')
                    self.assertEqual(data['service'], 'price-monitor')
                    self.assertIn('client_id', data)
    
    def test_get_products_endpoint_structure(self):
        """Test the structure of the get products endpoint response."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            # Mock the product service
            sample_product = Product(
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
            
            with app.app.test_client() as client:
                with app.app.app_context():
                    from flask import g
                    g.client_id = 'test_client'
                    
                    with patch.object(app.product_service, 'get_all_products', return_value=[sample_product]):
                        response = client.get('/api/products')
                        
                        self.assertEqual(response.status_code, 200)
                        data = json.loads(response.data)
                        
                        # Check response structure
                        self.assertIn('products', data)
                        self.assertIn('count', data)
                        self.assertIn('client_id', data)
                        
                        # Check product data structure
                        self.assertEqual(len(data['products']), 1)
                        product = data['products'][0]
                        
                        required_fields = ['id', 'url', 'name', 'current_price', 'previous_price', 
                                         'lowest_price', 'image_url', 'created_at', 'last_checked', 'is_active']
                        for field in required_fields:
                            self.assertIn(field, product)
    
    def test_add_product_validation(self):
        """Test input validation for adding products."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                with app.app.app_context():
                    from flask import g
                    g.client_id = 'test_client'
                    
                    # Test missing URL
                    response = client.post('/api/products', 
                                         json={},
                                         content_type='application/json')
                    
                    self.assertEqual(response.status_code, 400)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Invalid request')
                    self.assertIn('URL is required', data['message'])
                    
                    # Test empty URL
                    response = client.post('/api/products', 
                                         json={'url': '   '},
                                         content_type='application/json')
                    
                    self.assertEqual(response.status_code, 400)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Invalid request')
                    self.assertIn('URL cannot be empty', data['message'])
    
    def test_price_update_validation(self):
        """Test input validation for price updates."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                with app.app.app_context():
                    from flask import g
                    g.client_id = 'test_client'
                    
                    # Test missing price
                    response = client.put('/api/products/1/price', 
                                        json={},
                                        content_type='application/json')
                    
                    self.assertEqual(response.status_code, 400)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Invalid request')
                    self.assertIn('Price is required', data['message'])
                    
                    # Test negative price
                    response = client.put('/api/products/1/price', 
                                        json={'price': -10.0},
                                        content_type='application/json')
                    
                    self.assertEqual(response.status_code, 400)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Invalid price')
                    
                    # Test invalid price format
                    response = client.put('/api/products/1/price', 
                                        json={'price': 'invalid'},
                                        content_type='application/json')
                    
                    self.assertEqual(response.status_code, 400)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Invalid price')
    
    def test_error_handlers(self):
        """Test error handlers."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                with app.app.app_context():
                    from flask import g
                    g.client_id = 'test_client'
                    
                    # Test 404
                    response = client.get('/api/nonexistent')
                    self.assertEqual(response.status_code, 404)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Not found')
                    
                    # Test 405
                    response = client.patch('/api/products')
                    self.assertEqual(response.status_code, 405)
                    data = json.loads(response.data)
                    self.assertEqual(data['error'], 'Method not allowed')
    
    def test_api_endpoints_exist(self):
        """Test that all required API endpoints exist."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            
            # Get all routes
            routes = []
            for rule in app.app.url_map.iter_rules():
                routes.append((rule.rule, list(rule.methods)))
            
            # Check required endpoints exist
            required_endpoints = [
                ('/health', ['GET']),
                ('/api/products', ['GET', 'POST']),
                ('/api/products/<int:product_id>', ['GET', 'DELETE']),
                ('/api/products/<int:product_id>/price', ['PUT']),
                ('/api/products/<int:product_id>/history', ['GET']),
                ('/api/stats', ['GET'])
            ]
            
            for endpoint, methods in required_endpoints:
                # Find matching route
                found = False
                for route, route_methods in routes:
                    if route == endpoint:
                        for method in methods:
                            self.assertIn(method, route_methods, 
                                        f"Method {method} not found for endpoint {endpoint}")
                        found = True
                        break
                
                self.assertTrue(found, f"Endpoint {endpoint} not found")


if __name__ == '__main__':
    unittest.main()