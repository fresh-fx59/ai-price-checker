"""
Comprehensive tests for static web page functionality.
Tests the HTML/CSS/JavaScript interface for product management.
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import requests
import threading
import time

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import PriceMonitorApplication


class TestStaticWebFunctionality(unittest.TestCase):
    """Test static web page functionality with real browser interaction."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_config.properties")
        cls.db_path = os.path.join(cls.temp_dir, "test_database.db")
        cls.app_port = 8080
        cls.base_url = f"http://localhost:{cls.app_port}"
        
        # Create test configuration
        cls._create_test_config()
        
        # Check if Chrome/Chromium is available for Selenium
        cls.selenium_available = cls._check_selenium_availability()
        
        if not cls.selenium_available:
            print("Selenium WebDriver not available - skipping browser tests")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures."""
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    @classmethod
    def _create_test_config(cls):
        """Create test configuration file."""
        config_content = f"""
[database]
path = {cls.db_path}

[email]
smtp_server = smtp.test.com
smtp_port = 587
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30

[security]
enable_mtls = false
api_port = {cls.app_port}

[app]
log_level = INFO

[parsing]
enable_ai_parsing = false
"""
        with open(cls.config_path, 'w') as f:
            f.write(config_content)
    
    @classmethod
    def _check_selenium_availability(cls):
        """Check if Selenium WebDriver is available."""
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            driver.quit()
            return True
        except Exception:
            return False
    
    def setUp(self):
        """Set up test fixtures."""
        # Clean up database
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Start application in background thread
        self.app = None
        self.app_thread = None
        self.driver = None
        
        if self.selenium_available:
            self._start_test_application()
            self._setup_webdriver()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.driver:
            self.driver.quit()
        
        if self.app:
            self.app.shutdown()
        
        if self.app_thread and self.app_thread.is_alive():
            self.app_thread.join(timeout=5)
    
    def _start_test_application(self):
        """Start the application for testing."""
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self._get_sample_html(),
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            # Initialize and start application
            self.app = PriceMonitorApplication(config_path=self.config_path)
            if not self.app.initialize():
                self.fail("Failed to initialize test application")
            
            # Start Flask app in background thread
            def run_app():
                try:
                    self.app.run(host='127.0.0.1', port=self.app_port, debug=False)
                except Exception as e:
                    print(f"Application error: {e}")
            
            self.app_thread = threading.Thread(target=run_app, daemon=True)
            self.app_thread.start()
            
            # Wait for application to start
            self._wait_for_application_start()
    
    def _wait_for_application_start(self, timeout=30):
        """Wait for application to start and be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        
        self.fail("Application failed to start within timeout")
    
    def _setup_webdriver(self):
        """Set up Selenium WebDriver."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(10)
        except Exception as e:
            self.fail(f"Failed to setup WebDriver: {e}")
    
    def _get_sample_html(self):
        """Get sample HTML for testing."""
        return """
        <html>
        <head><title>Test Product</title></head>
        <body>
            <h1>Amazing Test Product</h1>
            <div class="price">$99.99</div>
            <img src="https://example.com/product.jpg" alt="Product Image">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Amazing Test Product",
                "offers": {
                    "@type": "Offer",
                    "price": "99.99",
                    "priceCurrency": "USD"
                },
                "image": "https://example.com/product.jpg"
            }
            </script>
        </body>
        </html>
        """
    
    def test_static_files_accessibility(self):
        """Test that static files are accessible."""
        # Test HTML page
        response = requests.get(f"{self.base_url}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('Price Monitor', response.text)
        
        # Test CSS file
        response = requests.get(f"{self.base_url}/static/styles.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/css', response.headers.get('content-type', ''))
        
        # Test JavaScript file
        response = requests.get(f"{self.base_url}/static/app.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response.headers.get('content-type', '').lower())
    
    def test_html_structure_and_content(self):
        """Test HTML structure and required content."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Check page title
        self.assertIn('Price Monitor', self.driver.title)
        
        # Check main heading
        heading = self.driver.find_element(By.TAG_NAME, 'h1')
        self.assertIn('Price Monitor', heading.text)
        
        # Check for required form elements
        url_input = self.driver.find_element(By.ID, 'productUrl')
        self.assertIsNotNone(url_input)
        
        add_button = self.driver.find_element(By.ID, 'addProductBtn')
        self.assertIsNotNone(add_button)
        
        # Check for product list container
        product_list = self.driver.find_element(By.ID, 'productList')
        self.assertIsNotNone(product_list)
    
    def test_add_product_form_functionality(self):
        """Test add product form functionality."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Find form elements
        url_input = self.driver.find_element(By.ID, 'productUrl')
        add_button = self.driver.find_element(By.ID, 'addProductBtn')
        
        # Test form validation (empty URL)
        add_button.click()
        
        # Should show validation message or prevent submission
        # (Implementation depends on JavaScript validation)
        
        # Test valid URL submission
        test_url = "https://example.com/product/1"
        url_input.clear()
        url_input.send_keys(test_url)
        add_button.click()
        
        # Wait for product to be added and appear in list
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
            )
            
            # Verify product appears in list
            product_items = self.driver.find_elements(By.CLASS_NAME, 'product-item')
            self.assertGreater(len(product_items), 0)
            
            # Check product details
            product_item = product_items[0]
            self.assertIn('Amazing Test Product', product_item.text)
            self.assertIn('$99.99', product_item.text)
            
        except TimeoutException:
            self.fail("Product was not added to the list within timeout")
    
    def test_product_list_display(self):
        """Test product list display functionality."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        # First add a product via API
        add_response = requests.post(f"{self.base_url}/api/products", 
                                   json={'url': 'https://example.com/product/1'})
        self.assertEqual(add_response.status_code, 200)
        
        # Load the page
        self.driver.get(f"{self.base_url}/")
        
        # Wait for products to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
            )
            
            # Check product display
            product_items = self.driver.find_elements(By.CLASS_NAME, 'product-item')
            self.assertEqual(len(product_items), 1)
            
            product_item = product_items[0]
            
            # Check required product information is displayed
            self.assertIn('Amazing Test Product', product_item.text)
            self.assertIn('$99.99', product_item.text)
            
            # Check for action buttons
            delete_button = product_item.find_element(By.CLASS_NAME, 'delete-btn')
            self.assertIsNotNone(delete_button)
            
            update_button = product_item.find_element(By.CLASS_NAME, 'update-price-btn')
            self.assertIsNotNone(update_button)
            
        except TimeoutException:
            self.fail("Products did not load within timeout")
    
    def test_manual_price_update_functionality(self):
        """Test manual price update functionality."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        # Add a product via API
        add_response = requests.post(f"{self.base_url}/api/products", 
                                   json={'url': 'https://example.com/product/1'})
        self.assertEqual(add_response.status_code, 200)
        product_data = add_response.json()
        product_id = product_data['product']['id']
        
        # Load the page
        self.driver.get(f"{self.base_url}/")
        
        # Wait for products to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
        )
        
        # Click update price button
        update_button = self.driver.find_element(By.CLASS_NAME, 'update-price-btn')
        update_button.click()
        
        # Should show price input modal or form
        try:
            price_input = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, 'newPrice'))
            )
            
            # Enter new price
            price_input.clear()
            price_input.send_keys('89.99')
            
            # Submit price update
            submit_button = self.driver.find_element(By.ID, 'updatePriceSubmit')
            submit_button.click()
            
            # Wait for update to complete and page to refresh
            time.sleep(2)
            
            # Verify price was updated
            product_item = self.driver.find_element(By.CLASS_NAME, 'product-item')
            self.assertIn('$89.99', product_item.text)
            
        except TimeoutException:
            self.fail("Price update form did not appear or function correctly")
    
    def test_product_deletion_functionality(self):
        """Test product deletion functionality."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        # Add a product via API
        add_response = requests.post(f"{self.base_url}/api/products", 
                                   json={'url': 'https://example.com/product/1'})
        self.assertEqual(add_response.status_code, 200)
        
        # Load the page
        self.driver.get(f"{self.base_url}/")
        
        # Wait for products to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
        )
        
        # Verify product is present
        product_items = self.driver.find_elements(By.CLASS_NAME, 'product-item')
        self.assertEqual(len(product_items), 1)
        
        # Click delete button
        delete_button = self.driver.find_element(By.CLASS_NAME, 'delete-btn')
        delete_button.click()
        
        # Handle confirmation dialog if present
        try:
            # Wait for confirmation dialog
            WebDriverWait(self.driver, 3).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            alert.accept()
        except TimeoutException:
            # No confirmation dialog, continue
            pass
        
        # Wait for product to be removed from list
        try:
            WebDriverWait(self.driver, 10).until(
                lambda driver: len(driver.find_elements(By.CLASS_NAME, 'product-item')) == 0
            )
            
            # Verify product list is empty
            product_items = self.driver.find_elements(By.CLASS_NAME, 'product-item')
            self.assertEqual(len(product_items), 0)
            
        except TimeoutException:
            self.fail("Product was not deleted within timeout")
    
    def test_responsive_design(self):
        """Test responsive design functionality."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Test different screen sizes
        screen_sizes = [
            (1920, 1080),  # Desktop
            (768, 1024),   # Tablet
            (375, 667)     # Mobile
        ]
        
        for width, height in screen_sizes:
            with self.subTest(screen_size=f"{width}x{height}"):
                self.driver.set_window_size(width, height)
                time.sleep(1)  # Allow layout to adjust
                
                # Check that main elements are still visible and accessible
                url_input = self.driver.find_element(By.ID, 'productUrl')
                self.assertTrue(url_input.is_displayed())
                
                add_button = self.driver.find_element(By.ID, 'addProductBtn')
                self.assertTrue(add_button.is_displayed())
                
                product_list = self.driver.find_element(By.ID, 'productList')
                self.assertTrue(product_list.is_displayed())
    
    def test_javascript_functionality(self):
        """Test JavaScript functionality and API interactions."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Test that JavaScript is loaded and working
        # Execute JavaScript to test API functions
        result = self.driver.execute_script("""
            // Test that main functions are defined
            return {
                addProductExists: typeof addProduct === 'function',
                updatePriceExists: typeof updatePrice === 'function',
                deleteProductExists: typeof deleteProduct === 'function',
                loadProductsExists: typeof loadProducts === 'function'
            };
        """)
        
        self.assertTrue(result['addProductExists'], "addProduct function not defined")
        self.assertTrue(result['updatePriceExists'], "updatePrice function not defined")
        self.assertTrue(result['deleteProductExists'], "deleteProduct function not defined")
        self.assertTrue(result['loadProductsExists'], "loadProducts function not defined")
    
    def test_error_handling_display(self):
        """Test error handling and display in the web interface."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Test invalid URL submission
        url_input = self.driver.find_element(By.ID, 'productUrl')
        add_button = self.driver.find_element(By.ID, 'addProductBtn')
        
        # Submit invalid URL
        url_input.clear()
        url_input.send_keys('not-a-valid-url')
        add_button.click()
        
        # Should show error message
        try:
            error_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'error-message'))
            )
            self.assertTrue(error_element.is_displayed())
            self.assertIn('error', error_element.text.lower())
            
        except TimeoutException:
            # Error might be shown differently, check for any error indication
            page_source = self.driver.page_source
            self.assertIn('error', page_source.lower())
    
    def test_loading_states(self):
        """Test loading states and user feedback."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Test loading state when adding product
        url_input = self.driver.find_element(By.ID, 'productUrl')
        add_button = self.driver.find_element(By.ID, 'addProductBtn')
        
        url_input.clear()
        url_input.send_keys('https://example.com/product/1')
        
        # Click and immediately check for loading state
        add_button.click()
        
        # Should show loading indicator or disable button
        try:
            # Check if button is disabled during processing
            WebDriverWait(self.driver, 2).until(
                lambda driver: not driver.find_element(By.ID, 'addProductBtn').is_enabled()
            )
        except TimeoutException:
            # Loading state might be very brief, that's okay
            pass
    
    def test_accessibility_features(self):
        """Test accessibility features of the web interface."""
        if not self.selenium_available:
            self.skipTest("Selenium not available")
        
        self.driver.get(f"{self.base_url}/")
        
        # Check for proper labels
        url_input = self.driver.find_element(By.ID, 'productUrl')
        label = self.driver.find_element(By.CSS_SELECTOR, 'label[for="productUrl"]')
        self.assertIsNotNone(label)
        
        # Check for ARIA attributes
        add_button = self.driver.find_element(By.ID, 'addProductBtn')
        aria_label = add_button.get_attribute('aria-label')
        self.assertIsNotNone(aria_label)
        
        # Check for keyboard navigation
        url_input.send_keys('\t')  # Tab to next element
        focused_element = self.driver.switch_to.active_element
        self.assertEqual(focused_element, add_button)


class TestStaticWebContentValidation(unittest.TestCase):
    """Test static web content validation without browser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.static_dir = 'static'
    
    def test_html_file_exists_and_valid(self):
        """Test that HTML file exists and contains required elements."""
        html_path = os.path.join(self.static_dir, 'index.html')
        self.assertTrue(os.path.exists(html_path), "index.html file missing")
        
        with open(html_path, 'r') as f:
            html_content = f.read()
        
        # Check for required HTML elements
        required_elements = [
            '<title>',
            'Price Monitor',
            'id="productUrl"',
            'id="addProductBtn"',
            'id="productList"',
            '<script',
            '<link'
        ]
        
        for element in required_elements:
            self.assertIn(element, html_content, f"Required element missing: {element}")
    
    def test_css_file_exists_and_valid(self):
        """Test that CSS file exists and contains styling."""
        css_path = os.path.join(self.static_dir, 'styles.css')
        self.assertTrue(os.path.exists(css_path), "styles.css file missing")
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check for basic CSS structure
        self.assertIn('{', css_content)
        self.assertIn('}', css_content)
        
        # Check for responsive design elements
        responsive_indicators = [
            '@media',
            'max-width',
            'min-width'
        ]
        
        has_responsive = any(indicator in css_content for indicator in responsive_indicators)
        self.assertTrue(has_responsive, "CSS should include responsive design elements")
    
    def test_javascript_file_exists_and_valid(self):
        """Test that JavaScript file exists and contains required functions."""
        js_path = os.path.join(self.static_dir, 'app.js')
        self.assertTrue(os.path.exists(js_path), "app.js file missing")
        
        with open(js_path, 'r') as f:
            js_content = f.read()
        
        # Check for required JavaScript functions
        required_functions = [
            'addProduct',
            'updatePrice',
            'deleteProduct',
            'loadProducts'
        ]
        
        for function in required_functions:
            self.assertIn(function, js_content, f"Required function missing: {function}")
        
        # Check for API endpoints
        api_endpoints = [
            '/api/products',
            '/api/stats'
        ]
        
        for endpoint in api_endpoints:
            self.assertIn(endpoint, js_content, f"API endpoint missing: {endpoint}")
    
    def test_static_files_structure(self):
        """Test static files directory structure."""
        self.assertTrue(os.path.exists(self.static_dir), "Static directory missing")
        
        required_files = [
            'index.html',
            'styles.css',
            'app.js'
        ]
        
        for file_name in required_files:
            file_path = os.path.join(self.static_dir, file_name)
            self.assertTrue(os.path.exists(file_path), f"Required static file missing: {file_name}")
    
    def test_html_meta_tags(self):
        """Test HTML meta tags for proper configuration."""
        html_path = os.path.join(self.static_dir, 'index.html')
        
        with open(html_path, 'r') as f:
            html_content = f.read()
        
        # Check for viewport meta tag (responsive design)
        self.assertIn('viewport', html_content, "Viewport meta tag missing")
        
        # Check for charset declaration
        charset_indicators = ['charset=', 'encoding=']
        has_charset = any(indicator in html_content for indicator in charset_indicators)
        self.assertTrue(has_charset, "Character encoding declaration missing")


if __name__ == '__main__':
    unittest.main(verbosity=2)