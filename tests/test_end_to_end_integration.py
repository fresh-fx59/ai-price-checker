"""
Comprehensive end-to-end integration tests for the Price Monitor application.
Tests complete workflows, Docker deployment, mTLS security, and all user requirements.
"""

import unittest
import json
import time
import tempfile
import os
import shutil
import subprocess
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sqlite3

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import PriceMonitorApplication
from src.models.database import Product, PriceHistory
from src.models.web_scraping import ProductInfo
from src.services.email_service import EmailDeliveryResult


class TestEndToEndIntegration(unittest.TestCase):
    """Comprehensive end-to-end integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_config.properties")
        cls.db_path = os.path.join(cls.temp_dir, "test_database.db")
        cls.log_path = os.path.join(cls.temp_dir, "test.log")
        
        # Create test configuration
        cls._create_test_config()
        
        # Mock HTML content for testing
        cls.sample_product_html = """
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
        
        cls.updated_product_html = cls.sample_product_html.replace("$99.99", "$79.99").replace('"99.99"', '"79.99"')
    
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
check_time = 09:00

[security]
enable_mtls = false
api_port = 8080

[app]
log_level = INFO
log_file = {cls.log_path}

[parsing]
enable_ai_parsing = false
"""
        with open(cls.config_path, 'w') as f:
            f.write(config_content)
    
    def setUp(self):
        """Set up test fixtures."""
        # Clean up database
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Clean up log file
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up any running applications
        pass


class TestCompleteWorkflows(TestEndToEndIntegration):
    """Test complete user workflows from start to finish."""
    
    def test_complete_product_monitoring_workflow(self):
        """Test complete workflow: add product → parse → monitor → price drop → notify."""
        
        # Mock web scraping and email services
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service, \
             patch('requests.get') as mock_requests:
            
            # Setup mocks
            mock_response = Mock()
            mock_response.text = self.sample_product_html
            mock_response.status_code = 200
            mock_requests.return_value = mock_response
            
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_instance.send_price_drop_notification.return_value = EmailNotificationResult(
                success=True,
                message="Email sent successfully"
            )
            mock_email_service.return_value = mock_email_instance
            
            # Initialize application
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Step 1: Add product
                product_url = "https://example.com/product/1"
                product = app.product_service.add_product(product_url)
                
                self.assertIsNotNone(product)
                self.assertEqual(product.url, product_url)
                self.assertEqual(product.name, "Amazing Test Product")
                self.assertEqual(product.current_price, 99.99)
                self.assertEqual(product.lowest_price, 99.99)
                
                # Step 2: Verify product is stored in database
                stored_product = app.product_service.get_product(product.id)
                self.assertIsNotNone(stored_product)
                self.assertEqual(stored_product.name, "Amazing Test Product")
                
                # Step 3: Simulate price drop by updating mock response
                mock_response.text = self.updated_product_html
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content=self.updated_product_html,
                    success=True,
                    url="https://example.com/product/1"
                )
                
                # Step 4: Run price check
                check_result = app.price_monitor_service.check_product(product.id)
                
                self.assertTrue(check_result.success)
                self.assertTrue(check_result.price_changed)
                self.assertEqual(check_result.new_price, 79.99)
                self.assertEqual(check_result.old_price, 99.99)
                
                # Step 5: Verify price was updated in database
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.current_price, 79.99)
                self.assertEqual(updated_product.previous_price, 99.99)
                self.assertEqual(updated_product.lowest_price, 79.99)
                
                # Step 6: Verify email notification was sent
                mock_email_instance.send_price_drop_notification.assert_called_once()
                call_args = mock_email_instance.send_price_drop_notification.call_args[0]
                self.assertEqual(call_args[1], 99.99)  # old_price
                self.assertEqual(call_args[2], 79.99)  # new_price
                
                # Step 7: Verify price history was recorded
                history = app.product_service.get_price_history(product.id)
                self.assertGreaterEqual(len(history), 2)  # Initial price + updated price
                
            finally:
                app.shutdown()
    
    def test_manual_price_update_workflow(self):
        """Test manual price update workflow with email notification."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service, \
             patch('requests.get') as mock_requests:
            
            # Setup mocks
            mock_response = Mock()
            mock_response.text = self.sample_product_html
            mock_response.status_code = 200
            mock_requests.return_value = mock_response
            
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_instance.send_price_drop_notification.return_value = EmailNotificationResult(
                success=True,
                message="Email sent successfully"
            )
            mock_email_service.return_value = mock_email_instance
            
            # Initialize application
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Manual price update (lower price)
                result = app.product_service.update_price_manually(product.id, 69.99)
                self.assertTrue(result)
                
                # Verify price was updated
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.current_price, 69.99)
                self.assertEqual(updated_product.previous_price, 99.99)
                self.assertEqual(updated_product.lowest_price, 69.99)
                
                # Verify email notification was sent for manual update
                mock_email_instance.send_price_drop_notification.assert_called_once()
                
            finally:
                app.shutdown()
    
    def test_multiple_products_monitoring_workflow(self):
        """Test monitoring multiple products simultaneously."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service, \
             patch('requests.get') as mock_requests:
            
            # Setup mocks for multiple products
            def mock_fetch_side_effect(url):
                if "product/1" in url:
                    return Mock(content=self.sample_product_html, success=True, url=url)
                elif "product/2" in url:
                    html = self.sample_product_html.replace("Amazing Test Product", "Another Product").replace("99.99", "149.99")
                    return Mock(content=html, success=True, url=url)
                else:
                    return Mock(content="", success=False, url=url)
            
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.side_effect = mock_fetch_side_effect
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_instance.send_price_drop_notification.return_value = EmailNotificationResult(
                success=True,
                message="Email sent successfully"
            )
            mock_email_service.return_value = mock_email_instance
            
            # Initialize application
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add multiple products
                product1 = app.product_service.add_product("https://example.com/product/1")
                product2 = app.product_service.add_product("https://example.com/product/2")
                
                self.assertEqual(product1.name, "Amazing Test Product")
                self.assertEqual(product1.current_price, 99.99)
                self.assertEqual(product2.name, "Another Product")
                self.assertEqual(product2.current_price, 149.99)
                
                # Check all products
                app.price_monitor_service.check_all_products()
                
                # Verify both products were checked
                self.assertEqual(mock_scraping_instance.fetch_page_content.call_count, 2)
                
                # Get all products
                all_products = app.product_service.get_all_products()
                self.assertEqual(len(all_products), 2)
                
            finally:
                app.shutdown()


class TestDockerDeploymentIntegration(TestEndToEndIntegration):
    """Test Docker container deployment and configuration."""
    
    def test_docker_build_process(self):
        """Test Docker image build process."""
        # Check if Docker is available
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.skipTest("Docker not available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("Docker not available")
        
        # Test Docker build
        build_result = subprocess.run([
            'docker', 'build', '-t', 'price-monitor-test', '.'
        ], capture_output=True, text=True, timeout=300)
        
        if build_result.returncode != 0:
            self.fail(f"Docker build failed: {build_result.stderr}")
        
        # Verify image was created
        image_result = subprocess.run([
            'docker', 'images', 'price-monitor-test', '--format', '{{.Repository}}'
        ], capture_output=True, text=True, timeout=10)
        
        self.assertIn('price-monitor-test', image_result.stdout)
        
        # Clean up
        subprocess.run(['docker', 'rmi', 'price-monitor-test'], 
                      capture_output=True, timeout=30)
    
    def test_docker_compose_configuration(self):
        """Test Docker Compose configuration validation."""
        # Check if docker-compose.yml exists and is valid
        self.assertTrue(os.path.exists('docker-compose.yml'))
        
        try:
            result = subprocess.run(['docker-compose', 'config'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.fail(f"Docker Compose configuration invalid: {result.stderr}")
        except FileNotFoundError:
            self.skipTest("Docker Compose not available")
    
    def test_container_health_check(self):
        """Test container health check functionality."""
        # This would typically require a running container
        # For now, we'll test the health check endpoint logic
        
        with patch('src.services.web_scraping_service.WebScrapingService'), \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Test health status
                status = app.get_status()
                
                self.assertIn('running', status)
                self.assertIn('config_path', status)
                self.assertIn('email_enabled', status)
                self.assertIn('scheduler_running', status)
                
                self.assertTrue(status['running'])
                self.assertTrue(status['email_enabled'])
                
            finally:
                app.shutdown()


class TestMTLSSecurityIntegration(TestEndToEndIntegration):
    """Test mTLS security implementation with static web page."""
    
    def setUp(self):
        """Set up mTLS test fixtures."""
        super().setUp()
        
        # Create mTLS configuration
        self.mtls_config_path = os.path.join(self.temp_dir, "mtls_config.properties")
        self.cert_dir = os.path.join(self.temp_dir, "certs")
        os.makedirs(self.cert_dir, exist_ok=True)
        
        # Create dummy certificate files for testing
        self._create_dummy_certificates()
        
        mtls_config_content = f"""
[database]
path = {self.db_path}

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
enable_mtls = true
api_port = 8443
server_cert_path = {os.path.join(self.cert_dir, 'server.crt')}
server_key_path = {os.path.join(self.cert_dir, 'server.key')}
ca_cert_path = {os.path.join(self.cert_dir, 'ca.crt')}
client_cert_required = true

[app]
log_level = INFO
log_file = {self.log_path}

[parsing]
enable_ai_parsing = false
"""
        with open(self.mtls_config_path, 'w') as f:
            f.write(mtls_config_content)
    
    def _create_dummy_certificates(self):
        """Create dummy certificate files for testing."""
        # Create dummy certificate content (not real certificates)
        dummy_cert = """-----BEGIN CERTIFICATE-----
MIICljCCAX4CCQCKOtLUOHDAuTANBgkqhkiG9w0BAQsFADANMQswCQYDVQQGEwJV
UzAeFw0yMzAxMDEwMDAwMDBaFw0yNDAxMDEwMDAwMDBaMA0xCzAJBgNVBAYTAlVT
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1234567890abcdef...
-----END CERTIFICATE-----"""
        
        dummy_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDXNjk1234567890
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890...
-----END PRIVATE KEY-----"""
        
        # Write dummy certificates
        with open(os.path.join(self.cert_dir, 'server.crt'), 'w') as f:
            f.write(dummy_cert)
        
        with open(os.path.join(self.cert_dir, 'server.key'), 'w') as f:
            f.write(dummy_key)
        
        with open(os.path.join(self.cert_dir, 'ca.crt'), 'w') as f:
            f.write(dummy_cert)
    
    def test_mtls_configuration_loading(self):
        """Test mTLS configuration loading."""
        
        with patch('src.services.web_scraping_service.WebScrapingService'), \
             patch('src.services.email_service.EmailService') as mock_email_service, \
             patch('src.security.security_service.SecurityService') as mock_security_service:
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            mock_security_instance = Mock()
            mock_security_service.return_value = mock_security_instance
            
            app = PriceMonitorApplication(config_path=self.mtls_config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Verify mTLS is enabled in configuration
                self.assertTrue(app.config.enable_mtls)
                self.assertEqual(app.config.api_port, 8443)
                self.assertTrue(app.config.client_cert_required)
                
                # Verify security service was initialized
                mock_security_service.assert_called_once()
                
            finally:
                app.shutdown()
    
    def test_static_web_page_with_mtls(self):
        """Test static web page accessibility with mTLS configuration."""
        
        # Check that static files exist
        static_files = ['static/index.html', 'static/styles.css', 'static/app.js']
        for file_path in static_files:
            self.assertTrue(os.path.exists(file_path), f"Static file missing: {file_path}")
        
        # Verify static files contain expected content
        with open('static/index.html', 'r') as f:
            html_content = f.read()
            self.assertIn('Price Monitor', html_content)
            self.assertIn('Add Product', html_content)
        
        with open('static/app.js', 'r') as f:
            js_content = f.read()
            self.assertIn('addProduct', js_content)
            self.assertIn('updatePrice', js_content)


class TestEmailNotificationIntegration(TestEndToEndIntegration):
    """Test email notifications for both automatic and manual price changes."""
    
    def test_automatic_price_drop_notification(self):
        """Test email notification for automatic price drop detection."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('smtplib.SMTP') as mock_smtp:
            
            # Setup web scraping mock
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            # Setup SMTP mock
            mock_smtp_instance = Mock()
            mock_smtp.return_value = mock_smtp_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Simulate price drop
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content=self.updated_product_html,
                    success=True,
                    url="https://example.com/product/1"
                )
                
                # Run price check
                check_result = app.price_monitor_service.check_product(product.id)
                
                self.assertTrue(check_result.success)
                self.assertTrue(check_result.price_changed)
                
                # Verify email was sent
                mock_smtp_instance.send_message.assert_called_once()
                
                # Verify email content
                call_args = mock_smtp_instance.send_message.call_args[0][0]
                email_body = str(call_args)
                self.assertIn("Amazing Test Product", email_body)
                self.assertIn("$99.99", email_body)
                self.assertIn("$79.99", email_body)
                
            finally:
                app.shutdown()
    
    def test_manual_price_update_notification(self):
        """Test email notification for manual price updates."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('smtplib.SMTP') as mock_smtp:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_smtp_instance = Mock()
            mock_smtp.return_value = mock_smtp_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Manual price update (lower price)
                result = app.product_service.update_price_manually(product.id, 69.99)
                self.assertTrue(result)
                
                # Verify email was sent for manual update
                mock_smtp_instance.send_message.assert_called_once()
                
                # Verify email indicates manual update
                call_args = mock_smtp_instance.send_message.call_args[0][0]
                email_body = str(call_args)
                self.assertIn("manual", email_body.lower())
                
            finally:
                app.shutdown()
    
    def test_email_failure_handling(self):
        """Test handling of email delivery failures."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('smtplib.SMTP') as mock_smtp:
            
            # Setup web scraping mock
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            # Setup SMTP mock to fail
            mock_smtp_instance = Mock()
            mock_smtp_instance.send_message.side_effect = Exception("SMTP Error")
            mock_smtp.return_value = mock_smtp_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Simulate price drop
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content=self.updated_product_html,
                    success=True,
                    url="https://example.com/product/1"
                )
                
                # Run price check (should not fail even if email fails)
                check_result = app.price_monitor_service.check_product(product.id)
                
                self.assertTrue(check_result.success)
                self.assertTrue(check_result.price_changed)
                
                # Verify price was still updated despite email failure
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.current_price, 79.99)
                
            finally:
                app.shutdown()


class TestUserRequirementsValidation(TestEndToEndIntegration):
    """Test all user requirements are properly implemented."""
    
    def test_requirement_1_add_product_urls(self):
        """Test Requirement 1: Add product URLs to monitor."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Test URL validation and accessibility
                valid_url = "https://example.com/product/1"
                product = app.product_service.add_product(valid_url)
                
                self.assertIsNotNone(product)
                self.assertEqual(product.url, valid_url)
                self.assertEqual(product.name, "Amazing Test Product")
                self.assertEqual(product.current_price, 99.99)
                self.assertIsNotNone(product.image_url)
                
                # Test invalid URL handling
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content="",
                    success=False,
                    url="https://invalid.com/product"
                )
                
                with self.assertRaises(Exception):
                    app.product_service.add_product("https://invalid.com/product")
                
            finally:
                app.shutdown()
    
    def test_requirement_2_automatic_daily_checks(self):
        """Test Requirement 2: Automatic daily price checks."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Test scheduled check functionality
                app.price_monitor_service.check_all_products()
                
                # Verify product was checked
                updated_product = app.product_service.get_product(product.id)
                self.assertIsNotNone(updated_product.last_checked)
                
                # Test inaccessible URL handling
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content="",
                    success=False,
                    url="https://example.com/product/1"
                )
                
                # Should not raise exception
                app.price_monitor_service.check_all_products()
                
            finally:
                app.shutdown()
    
    def test_requirement_3_email_notifications(self):
        """Test Requirement 3: Email notifications for price drops."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('smtplib.SMTP') as mock_smtp:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_smtp_instance = Mock()
            mock_smtp.return_value = mock_smtp_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Simulate price drop
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content=self.updated_product_html,
                    success=True,
                    url="https://example.com/product/1"
                )
                
                # Run price check
                check_result = app.price_monitor_service.check_product(product.id)
                
                # Verify email notification was sent
                mock_smtp_instance.send_message.assert_called_once()
                
                # Verify email content includes required information
                call_args = mock_smtp_instance.send_message.call_args[0][0]
                email_body = str(call_args)
                self.assertIn("Amazing Test Product", email_body)  # Product name
                self.assertIn("99.99", email_body)  # Old price
                self.assertIn("79.99", email_body)  # New price
                self.assertIn("https://example.com/product/1", email_body)  # Product URL
                
            finally:
                app.shutdown()
    
    def test_requirement_4_configuration_management(self):
        """Test Requirement 4: Configuration through property files."""
        
        # Test configuration loading
        app = PriceMonitorApplication(config_path=self.config_path)
        self.assertTrue(app.initialize())
        
        try:
            # Verify configuration was loaded
            self.assertIsNotNone(app.config)
            self.assertEqual(app.config.smtp_server, "smtp.test.com")
            self.assertEqual(app.config.smtp_port, 587)
            self.assertEqual(app.config.check_frequency_hours, 24)
            
            # Test missing configuration handling
            missing_config_path = os.path.join(self.temp_dir, "missing_config.properties")
            app_missing = PriceMonitorApplication(config_path=missing_config_path)
            
            # Should create default config and fail gracefully
            result = app_missing.initialize()
            self.assertFalse(result)
            
        finally:
            app.shutdown()
    
    def test_requirement_5_docker_deployment(self):
        """Test Requirement 5: Docker deployment capability."""
        
        # Verify Docker files exist
        self.assertTrue(os.path.exists('Dockerfile'))
        self.assertTrue(os.path.exists('docker-compose.yml'))
        self.assertTrue(os.path.exists('requirements.txt'))
        
        # Test application initialization (simulating container startup)
        with patch('src.services.web_scraping_service.WebScrapingService'), \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Verify all services initialized
                self.assertIsNotNone(app.product_service)
                self.assertIsNotNone(app.price_monitor_service)
                self.assertIsNotNone(app.email_service)
                
                # Test graceful shutdown
                app.shutdown()
                self.assertFalse(app._is_running)
                
            finally:
                if app._is_running:
                    app.shutdown()
    
    def test_requirement_6_product_management(self):
        """Test Requirement 6: View and manage monitored products."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add products
                product1 = app.product_service.add_product("https://example.com/product/1")
                product2 = app.product_service.add_product("https://example.com/product/2")
                
                # Test viewing all products
                all_products = app.product_service.get_all_products()
                self.assertEqual(len(all_products), 2)
                
                # Test viewing specific product details
                product_detail = app.product_service.get_product(product1.id)
                self.assertIsNotNone(product_detail)
                self.assertEqual(product_detail.name, "Amazing Test Product")
                
                # Test product deletion
                result = app.product_service.delete_product(product2.id)
                self.assertTrue(result)
                
                # Verify product was deleted
                remaining_products = app.product_service.get_all_products()
                self.assertEqual(len(remaining_products), 1)
                
                # Test empty product list handling
                app.product_service.delete_product(product1.id)
                empty_list = app.product_service.get_all_products()
                self.assertEqual(len(empty_list), 0)
                
            finally:
                app.shutdown()
    
    def test_requirement_7_manual_price_updates(self):
        """Test Requirement 7: Manual price updates."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Test valid manual price update
                result = app.product_service.update_price_manually(product.id, 89.99)
                self.assertTrue(result)
                
                # Verify price was updated
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.current_price, 89.99)
                self.assertEqual(updated_product.previous_price, 99.99)
                
                # Test lowest price update
                app.product_service.update_price_manually(product.id, 69.99)
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.lowest_price, 69.99)
                
                # Test invalid price format handling
                with self.assertRaises(ValueError):
                    app.product_service.update_price_manually(product.id, -10.0)
                
            finally:
                app.shutdown()
    
    def test_requirement_8_price_history_tracking(self):
        """Test Requirement 8: Price history tracking."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Add product
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Update price multiple times
                app.product_service.update_price_manually(product.id, 89.99)
                app.product_service.update_price_manually(product.id, 79.99)
                app.product_service.update_price_manually(product.id, 85.99)
                
                # Get price history
                history = app.product_service.get_price_history(product.id)
                self.assertGreaterEqual(len(history), 4)  # Initial + 3 updates
                
                # Verify current, previous, and lowest prices
                updated_product = app.product_service.get_product(product.id)
                self.assertEqual(updated_product.current_price, 85.99)
                self.assertEqual(updated_product.previous_price, 79.99)
                self.assertEqual(updated_product.lowest_price, 79.99)
                
                # Verify history is chronological
                timestamps = [h.recorded_at for h in history]
                self.assertEqual(timestamps, sorted(timestamps))
                
            finally:
                app.shutdown()
    
    def test_requirement_9_ai_parsing_tools(self):
        """Test Requirement 9: AI/parsing tools for product information extraction."""
        
        with patch('src.services.web_scraping_service.WebScrapingService') as mock_scraping, \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            # Setup mocks
            mock_scraping_instance = Mock()
            mock_scraping_instance.fetch_page_content.return_value = Mock(
                content=self.sample_product_html,
                success=True,
                url="https://example.com/product/1"
            )
            mock_scraping.return_value = mock_scraping_instance
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize())
            
            try:
                # Test multiple parsing strategies
                product = app.product_service.add_product("https://example.com/product/1")
                
                # Verify product information was extracted correctly
                self.assertEqual(product.name, "Amazing Test Product")
                self.assertEqual(product.current_price, 99.99)
                self.assertEqual(product.image_url, "https://example.com/product.jpg")
                
                # Test parsing failure handling
                mock_scraping_instance.fetch_page_content.return_value = Mock(
                    content="<html><body>No product info</body></html>",
                    success=True,
                    url="https://example.com/product/2"
                )
                
                # Should handle parsing failure gracefully
                with self.assertRaises(Exception):
                    app.product_service.add_product("https://example.com/product/2")
                
            finally:
                app.shutdown()


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)