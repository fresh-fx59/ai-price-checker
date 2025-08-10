"""
Tests for the mTLS authentication middleware.
"""
import unittest
from unittest.mock import Mock, patch
import urllib.parse

from src.security.auth_middleware import MTLSAuthMiddleware, setup_mtls_authentication, require_authentication
from src.security.models import AuthenticationResult
from flask import Flask, g, jsonify


class TestMTLSAuthMiddleware(unittest.TestCase):
    """Test cases for MTLSAuthMiddleware."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.config = Mock()
        self.config.enable_mtls = True
        
        self.security_service = Mock()
        self.test_cert_pem = "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
    
    def test_extract_client_certificate_ssl_client_cert(self):
        """Test certificate extraction from SSL_CLIENT_CERT."""
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        environ = {'SSL_CLIENT_CERT': self.test_cert_pem}
        cert = middleware._extract_client_certificate(environ)
        
        self.assertEqual(cert, self.test_cert_pem)
    
    def test_extract_client_certificate_http_ssl_client_cert(self):
        """Test certificate extraction from HTTP_SSL_CLIENT_CERT."""
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        encoded_cert = urllib.parse.quote(self.test_cert_pem)
        environ = {'HTTP_SSL_CLIENT_CERT': encoded_cert}
        cert = middleware._extract_client_certificate(environ)
        
        self.assertEqual(cert, self.test_cert_pem)
    
    def test_extract_client_certificate_x_ssl_cert(self):
        """Test certificate extraction from X-SSL-CERT header."""
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        # Simulate nginx format with spaces instead of newlines
        cert_with_spaces = "MIICertificateData"
        environ = {'HTTP_X_SSL_CERT': cert_with_spaces}
        cert = middleware._extract_client_certificate(environ)
        
        expected = "-----BEGIN CERTIFICATE-----\nMIICertificateData\n-----END CERTIFICATE-----"
        self.assertEqual(cert, expected)
    
    def test_extract_client_certificate_none_found(self):
        """Test certificate extraction when no certificate is found."""
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        environ = {}
        cert = middleware._extract_client_certificate(environ)
        
        self.assertIsNone(cert)
    
    def test_wsgi_call_with_valid_certificate(self):
        """Test WSGI call with valid client certificate."""
        self.security_service.validate_client_certificate.return_value = AuthenticationResult(
            is_authenticated=True,
            client_id="test-client",
            error_message=None
        )
        
        # Mock the original WSGI app
        original_app = Mock()
        original_app.return_value = ['response']
        self.app.wsgi_app = original_app
        
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        environ = {'SSL_CLIENT_CERT': self.test_cert_pem}
        start_response = Mock()
        
        result = middleware(environ, start_response)
        
        # Check that authentication info was added to environ
        self.assertEqual(environ['mtls.client_cert'], self.test_cert_pem)
        self.assertTrue(environ['mtls.authenticated'])
        self.assertEqual(environ['mtls.client_id'], "test-client")
        self.assertIsNone(environ['mtls.error'])
        
        # Check that original app was called
        original_app.assert_called_once_with(environ, start_response)
        self.assertEqual(result, ['response'])
    
    def test_wsgi_call_with_invalid_certificate(self):
        """Test WSGI call with invalid client certificate."""
        self.security_service.validate_client_certificate.return_value = AuthenticationResult(
            is_authenticated=False,
            client_id=None,
            error_message="Certificate expired"
        )
        
        # Mock the original WSGI app
        original_app = Mock()
        original_app.return_value = ['response']
        self.app.wsgi_app = original_app
        
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        environ = {'SSL_CLIENT_CERT': self.test_cert_pem}
        start_response = Mock()
        
        result = middleware(environ, start_response)
        
        # Check that authentication info was added to environ
        self.assertEqual(environ['mtls.client_cert'], self.test_cert_pem)
        self.assertFalse(environ['mtls.authenticated'])
        self.assertIsNone(environ['mtls.client_id'])
        self.assertEqual(environ['mtls.error'], "Certificate expired")
        
        # Check that original app was still called
        original_app.assert_called_once_with(environ, start_response)
    
    def test_wsgi_call_mtls_disabled(self):
        """Test WSGI call when mTLS is disabled."""
        self.config.enable_mtls = False
        
        # Mock the original WSGI app
        original_app = Mock()
        original_app.return_value = ['response']
        self.app.wsgi_app = original_app
        
        middleware = MTLSAuthMiddleware(self.app, self.security_service, self.config)
        
        environ = {'SSL_CLIENT_CERT': self.test_cert_pem}
        start_response = Mock()
        
        result = middleware(environ, start_response)
        
        # Check that authentication was not performed
        self.assertEqual(environ['mtls.client_cert'], self.test_cert_pem)
        self.assertFalse(environ['mtls.authenticated'])
        self.assertIsNone(environ['mtls.client_id'])
        
        # Validation should not have been called
        self.security_service.validate_client_certificate.assert_not_called()


class TestSetupMTLSAuthentication(unittest.TestCase):
    """Test cases for setup_mtls_authentication function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.config = Mock()
        self.config.enable_mtls = True
        self.security_service = Mock()
    
    def test_setup_mtls_authentication(self):
        """Test mTLS authentication setup."""
        # Add a test route
        @self.app.route('/test')
        def test_route():
            return jsonify({'client_id': g.client_id, 'authenticated': g.authenticated})
        
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        # Test with authenticated request
        with self.app.test_client() as client:
            with client.application.test_request_context(
                '/test',
                environ_base={
                    'mtls.authenticated': True,
                    'mtls.client_id': 'test-client',
                    'mtls.client_cert': 'cert-data'
                }
            ):
                response = client.get('/test')
                self.assertEqual(response.status_code, 200)
    
    def test_health_check_bypass(self):
        """Test that health check bypasses authentication."""
        @self.app.route('/health')
        def health_check():
            return jsonify({'client_id': g.client_id, 'authenticated': g.authenticated})
        
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        with self.app.test_client() as client:
            response = client.get('/health')
            self.assertEqual(response.status_code, 200)
    
    def test_mtls_disabled(self):
        """Test authentication when mTLS is disabled."""
        self.config.enable_mtls = False
        
        @self.app.route('/test')
        def test_route():
            return jsonify({'client_id': g.client_id, 'authenticated': g.authenticated})
        
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        with self.app.test_client() as client:
            response = client.get('/test')
            self.assertEqual(response.status_code, 200)
    
    def test_missing_client_certificate(self):
        """Test request without client certificate."""
        @self.app.route('/test')
        def test_route():
            return jsonify({'message': 'success'})
        
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        with self.app.test_client() as client:
            with client.application.test_request_context(
                '/test',
                environ_base={'mtls.authenticated': False}
            ):
                response = client.get('/test')
                self.assertEqual(response.status_code, 401)
    
    def test_authentication_failed(self):
        """Test request with failed authentication."""
        @self.app.route('/test')
        def test_route():
            return jsonify({'message': 'success'})
        
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        with self.app.test_client() as client:
            with client.application.test_request_context(
                '/test',
                environ_base={
                    'mtls.authenticated': False,
                    'mtls.client_cert': 'invalid-cert',
                    'mtls.error': 'Certificate expired'
                }
            ):
                response = client.get('/test')
                self.assertEqual(response.status_code, 401)


class TestRequireAuthentication(unittest.TestCase):
    """Test cases for require_authentication decorator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
    
    def test_require_authentication_success(self):
        """Test successful authentication with decorator."""
        @self.app.route('/test')
        @require_authentication
        def test_route():
            return jsonify({'message': 'success', 'client_id': g.client_id})
        
        with self.app.test_client() as client:
            with client.application.test_request_context('/test'):
                # Simulate authenticated request
                g.authenticated = True
                g.client_id = 'test-client'
                
                response = client.get('/test')
                self.assertEqual(response.status_code, 200)
    
    def test_require_authentication_failure(self):
        """Test failed authentication with decorator."""
        @self.app.route('/test')
        @require_authentication
        def test_route():
            return jsonify({'message': 'success'})
        
        with self.app.test_client() as client:
            with client.application.test_request_context('/test'):
                # Simulate unauthenticated request
                g.authenticated = False
                
                response = client.get('/test')
                self.assertEqual(response.status_code, 401)
    
    def test_require_authentication_no_auth_info(self):
        """Test decorator when no authentication info is available."""
        @self.app.route('/test')
        @require_authentication
        def test_route():
            return jsonify({'message': 'success'})
        
        with self.app.test_client() as client:
            with client.application.test_request_context('/test'):
                # No authentication info set
                response = client.get('/test')
                self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()