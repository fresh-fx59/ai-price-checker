"""
Authentication middleware for mTLS client certificate validation.
"""
import logging
from flask import request, g, jsonify
from typing import Optional, Callable, Any
from werkzeug.wrappers import Response

from .security_service import SecurityService


class MTLSAuthMiddleware:
    """Middleware for mTLS client certificate authentication."""
    
    def __init__(self, app, security_service: SecurityService, config):
        """Initialize the authentication middleware."""
        self.app = app
        self.security_service = security_service
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Wrap the Flask app
        self.wsgi_app = app.wsgi_app
        app.wsgi_app = self
    
    def __call__(self, environ, start_response):
        """WSGI application call."""
        # Extract client certificate from environment
        client_cert_pem = self._extract_client_certificate(environ)
        
        # Store certificate in environment for Flask to access
        environ['mtls.client_cert'] = client_cert_pem
        environ['mtls.authenticated'] = False
        environ['mtls.client_id'] = None
        environ['mtls.error'] = None
        
        if self.config.enable_mtls and client_cert_pem:
            # Validate the certificate
            auth_result = self.security_service.validate_client_certificate(client_cert_pem)
            
            environ['mtls.authenticated'] = auth_result.is_authenticated
            environ['mtls.client_id'] = auth_result.client_id
            environ['mtls.error'] = auth_result.error_message
            
            if auth_result.is_authenticated:
                self.logger.info(f"Client authenticated: {auth_result.client_id}")
            else:
                self.logger.warning(f"Client authentication failed: {auth_result.error_message}")
        
        return self.wsgi_app(environ, start_response)
    
    def _extract_client_certificate(self, environ) -> Optional[str]:
        """Extract client certificate from WSGI environment."""
        # Try different ways to get the client certificate depending on the server
        
        # Method 1: Standard SSL_CLIENT_CERT (Apache, nginx)
        client_cert = environ.get('SSL_CLIENT_CERT')
        if client_cert:
            return client_cert
        
        # Method 2: HTTP_SSL_CLIENT_CERT (some reverse proxies)
        client_cert = environ.get('HTTP_SSL_CLIENT_CERT')
        if client_cert:
            # URL decode if necessary
            import urllib.parse
            return urllib.parse.unquote(client_cert)
        
        # Method 3: X-SSL-CERT header (nginx with proxy_set_header)
        client_cert = environ.get('HTTP_X_SSL_CERT')
        if client_cert:
            # Replace spaces with newlines and add PEM headers if missing
            cert_content = client_cert.replace(' ', '\n')
            if not cert_content.startswith('-----BEGIN CERTIFICATE-----'):
                cert_content = f"-----BEGIN CERTIFICATE-----\n{cert_content}\n-----END CERTIFICATE-----"
            return cert_content
        
        # Method 4: Check if running with werkzeug development server
        if 'werkzeug' in environ.get('SERVER_SOFTWARE', '').lower():
            # For development, we might not have real certificates
            return None
        
        return None


def setup_mtls_authentication(app, security_service: SecurityService, config):
    """Set up mTLS authentication for Flask app."""
    
    # Add the middleware
    MTLSAuthMiddleware(app, security_service, config)
    
    @app.before_request
    def authenticate_request():
        """Authenticate the request using client certificate."""
        # Skip authentication for health check
        if request.endpoint == 'health_check':
            g.client_id = 'anonymous'
            g.authenticated = True
            return
        
        if not config.enable_mtls:
            # mTLS disabled, allow all requests
            g.client_id = 'anonymous'
            g.authenticated = True
            return
        
        # Get authentication info from environment
        authenticated = request.environ.get('mtls.authenticated', False)
        client_id = request.environ.get('mtls.client_id')
        error_message = request.environ.get('mtls.error')
        
        if not authenticated:
            if not request.environ.get('mtls.client_cert'):
                return jsonify({
                    'error': 'Client certificate required',
                    'message': 'mTLS authentication requires a valid client certificate'
                }), 401
            else:
                return jsonify({
                    'error': 'Authentication failed',
                    'message': error_message or 'Invalid client certificate'
                }), 401
        
        # Store authentication info in Flask's g object
        g.client_id = client_id
        g.authenticated = True
    
    return app


def require_authentication(f):
    """Decorator to require authentication for specific endpoints."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not getattr(g, 'authenticated', False):
            return jsonify({
                'error': 'Authentication required',
                'message': 'This endpoint requires client certificate authentication'
            }), 401
        return f(*args, **kwargs)
    return decorated_function