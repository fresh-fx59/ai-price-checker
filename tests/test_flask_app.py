"""
Tests for the Flask application with mTLS authentication.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import ssl
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.app import SecureFlaskApp
from src.security.models import CertificateBundle, AuthenticationResult


class TestSecureFlaskApp(unittest.TestCase):
    """Test cases for SecureFlaskApp."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.enable_mtls = True
        self.mock_config.api_port = 8443
        self.mock_config.server_cert_path = '/certs/server.crt'
        self.mock_config.server_key_path = '/certs/server.key'
        self.mock_config.ca_cert_path = '/certs/ca.crt'
        self.mock_config.client_cert_required = True
        
        # Mock config service
        self.mock_config_service = Mock()
        self.mock_config_service.get_config.return_value = self.mock_config
        
        # Create test certificates
        self.ca_cert, self.ca_key = self._create_test_ca()
        self.client_cert, self.client_key = self._create_test_cert(self.ca_cert, self.ca_key, "test-client")
        self.client_cert_pem = self.client_cert.public_bytes(serialization.Encoding.PEM).decode()
    
    def _create_test_ca(self):
        """Create a test CA certificate and key."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        return cert, private_key
    
    def _create_test_cert(self, ca_cert, ca_key, common_name):
        """Create a test certificate signed by the CA."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=30)
        ).sign(ca_key, hashes.SHA256(), default_backend())
        
        return cert, private_key
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_app_initialization(self, mock_load_certs):
        """Test Flask app initialization."""
        mock_load_certs.return_value = Mock()
        
        app = SecureFlaskApp(self.mock_config_service)
        
        self.assertIsNotNone(app.app)
        self.assertEqual(app.config, self.mock_config)
        mock_load_certs.assert_called_once()
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_health_endpoint_without_mtls(self, mock_load_certs):
        """Test health endpoint when mTLS is disabled."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        response = client.get('/health')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'price-monitor')
        self.assertFalse(data['mtls_enabled'])
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    @patch('src.security.security_service.SecurityService.validate_client_certificate')
    def test_health_endpoint_with_mtls(self, mock_validate, mock_load_certs):
        """Test health endpoint when mTLS is enabled."""
        mock_load_certs.return_value = Mock()
        mock_validate.return_value = AuthenticationResult(
            is_authenticated=True,
            client_id="test-client",
            error_message=None
        )
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        # Simulate client certificate in environment
        with client.application.test_request_context(
            '/health',
            environ_base={'mtls.client_cert': self.client_cert_pem}
        ):
            response = client.get('/health')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertTrue(data['mtls_enabled'])
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_api_endpoint_without_authentication(self, mock_load_certs):
        """Test API endpoint access without authentication."""
        mock_load_certs.return_value = Mock()
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        response = client.get('/api/products')
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    @patch('src.security.security_service.SecurityService.validate_client_certificate')
    def test_api_endpoint_with_valid_authentication(self, mock_validate, mock_load_certs):
        """Test API endpoint access with valid authentication."""
        mock_load_certs.return_value = Mock()
        mock_validate.return_value = AuthenticationResult(
            is_authenticated=True,
            client_id="test-client",
            error_message=None
        )
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        # Mock the environment to simulate successful authentication
        with patch.dict('os.environ', {'mtls.authenticated': 'True', 'mtls.client_id': 'test-client'}):
            with client.application.test_request_context(
                '/api/products',
                environ_base={
                    'mtls.client_cert': self.client_cert_pem,
                    'mtls.authenticated': True,
                    'mtls.client_id': 'test-client'
                }
            ):
                response = client.get('/api/products')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('products', data)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    @patch('src.security.security_service.SecurityService.validate_client_certificate')
    def test_add_product_endpoint(self, mock_validate, mock_load_certs):
        """Test add product endpoint."""
        mock_load_certs.return_value = Mock()
        mock_validate.return_value = AuthenticationResult(
            is_authenticated=True,
            client_id="test-client",
            error_message=None
        )
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        product_data = {'url': 'https://example.com/product'}
        
        with client.application.test_request_context(
            '/api/products',
            method='POST',
            json=product_data,
            environ_base={
                'mtls.client_cert': self.client_cert_pem,
                'mtls.authenticated': True,
                'mtls.client_id': 'test-client'
            }
        ):
            response = client.post('/api/products', json=product_data)
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['url'], 'https://example.com/product')
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_add_product_invalid_data(self, mock_load_certs):
        """Test add product endpoint with invalid data."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        # Test with missing URL
        response = client.post('/api/products', json={})
        self.assertEqual(response.status_code, 400)
        
        # Test with no JSON data
        response = client.post('/api/products')
        self.assertEqual(response.status_code, 400)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_update_price_endpoint(self, mock_load_certs):
        """Test manual price update endpoint."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        price_data = {'price': 29.99}
        response = client.put('/api/products/1/price', json=price_data)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['price'], 29.99)
        self.assertEqual(data['product_id'], 1)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_update_price_invalid_data(self, mock_load_certs):
        """Test price update with invalid data."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        # Test with missing price
        response = client.put('/api/products/1/price', json={})
        self.assertEqual(response.status_code, 400)
        
        # Test with invalid price
        response = client.put('/api/products/1/price', json={'price': 'invalid'})
        self.assertEqual(response.status_code, 400)
        
        # Test with negative price
        response = client.put('/api/products/1/price', json={'price': -10})
        self.assertEqual(response.status_code, 400)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_delete_product_endpoint(self, mock_load_certs):
        """Test delete product endpoint."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        response = client.delete('/api/products/1')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['product_id'], 1)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_price_history_endpoint(self, mock_load_certs):
        """Test price history endpoint."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        response = client.get('/api/products/1/history')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['product_id'], 1)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_error_handlers(self, mock_load_certs):
        """Test error handlers."""
        mock_load_certs.return_value = Mock()
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        # Test 404
        response = client.get('/nonexistent')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)
        
        # Test 405
        response = client.patch('/health')
        self.assertEqual(response.status_code, 405)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    def test_security_headers(self, mock_load_certs):
        """Test security headers are added to responses."""
        mock_load_certs.return_value = Mock()
        self.mock_config.enable_mtls = False
        
        app = SecureFlaskApp(self.mock_config_service)
        client = app.app.test_client()
        
        response = client.get('/health')
        
        # Check security headers
        self.assertIn('Strict-Transport-Security', response.headers)
        self.assertIn('Content-Security-Policy', response.headers)
        self.assertIn('X-Content-Type-Options', response.headers)
        self.assertIn('X-Frame-Options', response.headers)
        self.assertIn('X-XSS-Protection', response.headers)
        self.assertIn('Referrer-Policy', response.headers)
        
        # Check that Server header is removed
        self.assertNotIn('Server', response.headers)
    
    @patch('src.security.security_service.SecurityService.load_certificates')
    @patch('src.security.security_service.SecurityService.setup_mtls_context')
    def test_create_ssl_context(self, mock_setup_context, mock_load_certs):
        """Test SSL context creation."""
        mock_load_certs.return_value = Mock()
        mock_context = Mock()
        mock_setup_context.return_value = mock_context
        
        app = SecureFlaskApp(self.mock_config_service)
        context = app.create_ssl_context()
        
        self.assertEqual(context, mock_context)
        mock_setup_context.assert_called_once()


if __name__ == '__main__':
    unittest.main()