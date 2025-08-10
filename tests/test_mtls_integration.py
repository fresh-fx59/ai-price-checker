"""
Integration tests for mTLS security functionality.
"""
import unittest
from unittest.mock import Mock, patch
import tempfile
import os
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.security_service import SecurityService
from src.security.models import CertificateBundle


class TestMTLSIntegration(unittest.TestCase):
    """Integration tests for mTLS functionality."""
    
    def setUp(self):
        """Set up test fixtures with real certificate files."""
        # Create temporary directory for certificates
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test certificates
        self.ca_cert, self.ca_key = self._create_test_ca()
        self.server_cert, self.server_key = self._create_test_cert(self.ca_cert, self.ca_key, "server")
        self.client_cert, self.client_key = self._create_test_cert(self.ca_cert, self.ca_key, "client")
        
        # Write certificates to files
        self.ca_cert_path = os.path.join(self.temp_dir, 'ca.crt')
        self.server_cert_path = os.path.join(self.temp_dir, 'server.crt')
        self.server_key_path = os.path.join(self.temp_dir, 'server.key')
        
        with open(self.ca_cert_path, 'wb') as f:
            f.write(self.ca_cert.public_bytes(serialization.Encoding.PEM))
        
        with open(self.server_cert_path, 'wb') as f:
            f.write(self.server_cert.public_bytes(serialization.Encoding.PEM))
        
        with open(self.server_key_path, 'wb') as f:
            f.write(self.server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Create config
        self.config = Mock()
        self.config.enable_mtls = True
        self.config.server_cert_path = self.server_cert_path
        self.config.server_key_path = self.server_key_path
        self.config.ca_cert_path = self.ca_cert_path
        self.config.client_cert_required = True
        
        # Get client certificate PEM
        self.client_cert_pem = self.client_cert.public_bytes(serialization.Encoding.PEM).decode()
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
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
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=365)
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
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=30)
        ).sign(ca_key, hashes.SHA256(), default_backend())
        
        return cert, private_key
    
    def test_complete_certificate_workflow(self):
        """Test complete certificate loading and validation workflow."""
        # Create security service
        security_service = SecurityService(self.config)
        
        # Load certificates
        bundle = security_service.load_certificates()
        
        # Verify bundle contents
        self.assertIsInstance(bundle, CertificateBundle)
        self.assertIn("-----BEGIN CERTIFICATE-----", bundle.server_cert)
        self.assertIn("-----BEGIN PRIVATE KEY-----", bundle.server_key)
        self.assertIn("-----BEGIN CERTIFICATE-----", bundle.ca_cert)
        
        # Validate client certificate
        auth_result = security_service.validate_client_certificate(self.client_cert_pem)
        
        self.assertTrue(auth_result.is_authenticated)
        self.assertEqual(auth_result.client_id, "client")
        self.assertIsNone(auth_result.error_message)
    
    def test_ssl_context_creation(self):
        """Test SSL context creation with real certificates."""
        security_service = SecurityService(self.config)
        security_service.load_certificates()
        
        # Create SSL context
        ssl_context = security_service.setup_mtls_context()
        
        # Verify SSL context properties
        import ssl
        self.assertIsInstance(ssl_context, ssl.SSLContext)
        self.assertEqual(ssl_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(ssl_context.minimum_version, ssl.TLSVersion.TLSv1_2)
    
    def test_certificate_info_extraction(self):
        """Test certificate information extraction."""
        security_service = SecurityService(self.config)
        
        cert_info = security_service.get_certificate_info(self.client_cert_pem)
        
        self.assertIn("client", cert_info.subject)
        self.assertIn("Test CA", cert_info.issuer)
        self.assertTrue(cert_info.is_valid)
        self.assertIsNotNone(cert_info.fingerprint)
        self.assertIsNotNone(cert_info.serial_number)
    
    def test_invalid_certificate_rejection(self):
        """Test that invalid certificates are properly rejected."""
        security_service = SecurityService(self.config)
        security_service.load_certificates()
        
        # Test with completely invalid certificate
        auth_result = security_service.validate_client_certificate("invalid certificate")
        
        self.assertFalse(auth_result.is_authenticated)
        self.assertIsNone(auth_result.client_id)
        self.assertIsNotNone(auth_result.error_message)
    
    def test_certificate_validation_without_ca(self):
        """Test certificate validation when CA bundle is not loaded."""
        security_service = SecurityService(self.config)
        # Don't load certificates
        
        auth_result = security_service.validate_client_certificate(self.client_cert_pem)
        
        self.assertFalse(auth_result.is_authenticated)
        self.assertIsNone(auth_result.client_id)
        self.assertIsNotNone(auth_result.error_message)


if __name__ == '__main__':
    unittest.main()