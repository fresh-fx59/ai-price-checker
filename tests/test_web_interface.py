"""
Tests for the static web interface.
"""
import unittest
from unittest.mock import Mock, patch
from src.app import SecureFlaskApp
from src.services.config_service import ConfigService


class TestWebInterface(unittest.TestCase):
    """Test cases for the static web interface."""
    
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
    
    def test_index_page_serves(self):
        """Test that the index page is served correctly."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/')
                
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Price Monitor Dashboard', response.data)
                self.assertIn(b'<!DOCTYPE html>', response.data)
    
    def test_static_css_serves(self):
        """Test that CSS files are served correctly."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/static/styles.css')
                
                self.assertEqual(response.status_code, 200)
                # Check that it's actually CSS content
                self.assertIn(b'font-family:', response.data)
    
    def test_static_js_serves(self):
        """Test that JavaScript files are served correctly."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/static/app.js')
                
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'PriceMonitorApp', response.data)
                self.assertIn(b'class PriceMonitorApp', response.data)
    
    def test_static_files_have_correct_content_type(self):
        """Test that static files have correct content types."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                # Test CSS content type
                response = client.get('/static/styles.css')
                self.assertEqual(response.status_code, 200)
                self.assertIn('text/css', response.content_type)
                
                # Test JS content type
                response = client.get('/static/app.js')
                self.assertEqual(response.status_code, 200)
                # Note: Flask might serve JS as text/plain or application/javascript
                self.assertTrue(
                    'javascript' in response.content_type or 
                    'text/plain' in response.content_type
                )
    
    def test_html_contains_required_elements(self):
        """Test that the HTML contains required elements for functionality."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/')
                html_content = response.data.decode('utf-8')
                
                # Check for essential elements
                required_elements = [
                    'id="product-url"',           # URL input field
                    'id="add-product-btn"',       # Add product button
                    'id="products-container"',    # Products container
                    'id="product-modal"',         # Product detail modal
                    'id="manual-price"',          # Manual price input
                    'id="update-price-btn"',      # Update price button
                    'id="delete-product-btn"',    # Delete product button
                    'href="styles.css"',          # CSS link
                    'src="app.js"'                # JavaScript link
                ]
                
                for element in required_elements:
                    self.assertIn(element, html_content, 
                                f"Required element '{element}' not found in HTML")
    
    def test_responsive_design_meta_tag(self):
        """Test that responsive design meta tag is present."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/')
                html_content = response.data.decode('utf-8')
                
                self.assertIn('name="viewport"', html_content)
                self.assertIn('width=device-width', html_content)
    
    def test_font_awesome_integration(self):
        """Test that Font Awesome is integrated for icons."""
        with patch('src.app.DatabaseManager'), \
             patch('src.app.SecurityService'), \
             patch('src.app.setup_mtls_authentication'):
            
            app = SecureFlaskApp(self.mock_config_service)
            app.app.config['TESTING'] = True
            
            with app.app.test_client() as client:
                response = client.get('/')
                html_content = response.data.decode('utf-8')
                
                self.assertIn('font-awesome', html_content)
                self.assertIn('fas fa-', html_content)


if __name__ == '__main__':
    unittest.main()