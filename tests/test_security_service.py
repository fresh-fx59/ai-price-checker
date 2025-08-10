"""
Tests for the SecurityService certificate management functionality.
"""
import unittest
from unittest.mock import Mock, patch, mock_open
import ssl
import os
from datetime import datetime, timezone, timedelta
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.security_service import SecurityService
from src.security.models import CertificateBundle, AuthenticationResult, CertificateInfo


class TestSecurityService(unittest.TestCase):
    """Test cases for SecurityService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.config.server_cert_path = '/certs/server.crt'
        self.config.server_key_path = '/certs/server.key'
        self.config.ca_cert_path = '/certs/ca.crt'
        self.config.client_cert_required = True
        
        self.security_service = SecurityService(self.config)
        
        # Create test certificates
        self.ca_cert, self.ca_key = self._create_test_ca()
        self.server_cert, self.server_key = self._create_test_cert(self.ca_cert, self.ca_key, "server")
        self.client_cert, self.client_key = self._create_test_cert(self.ca_cert, self.ca_key, "client")
        
        # Convert to PEM format
        self.ca_cert_pem = self.ca_cert.public_bytes(serialization.Encoding.PEM).decode()
        self.server_cert_pem = self.server_cert.public_bytes(serialization.Encoding.PEM).decode()
        self.client_cert_pem = self.client_cert.public_bytes(serialization.Encoding.PEM).decode()
        self.server_key_pem = self.server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
    
    def _create_test_ca(self):
        """Create a test CA certificate and key."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
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
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Create certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
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
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('os.path.isdir')
    @patch('os.listdir')
    def test_load_certificates_success(self, mock_listdir, mock_isdir, mock_exists, mock_file):
        """Test successful certificate loading."""
        # Mock file system
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_listdir.return_value = ['client1.crt', 'client2.crt']
        
        # Mock file contents
        file_contents = {
            '/certs/server.crt': self.server_cert_pem,
            '/certs/server.key': self.server_key_pem,
            '/certs/ca.crt': self.ca_cert_pem,
            '/certs/client-certs/client1.crt': self.client_cert_pem,
            '/certs/client-certs/client2.crt': self.client_cert_pem,
        }
        
        def mock_open_side_effect(filename, mode='r'):
            return mock_open(read_data=file_contents.get(filename, ''))()
        
        mock_file.side_effect = mock_open_side_effect
        
        # Test certificate loading
        bundle = self.security_service.load_certificates()
        
        self.assertIsInstance(bundle, CertificateBundle)
        self.assertEqual(bundle.server_cert, self.server_cert_pem)
        self.assertEqual(bundle.server_key, self.server_key_pem)
        self.assertEqual(bundle.ca_cert, self.ca_cert_pem)
        self.assertEqual(len(bundle.client_certs), 2)
    
    @patch('os.path.exists')
    def test_load_certificates_file_not_found(self, mock_exists):
        """Test certificate loading when file doesn't exist."""
        mock_exists.return_value = False
        
        with self.assertRaises(FileNotFoundError):
            self.security_service.load_certificates()
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_load_certificates_empty_file(self, mock_exists, mock_file):
        """Test certificate loading with empty file."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = ''
        
        with self.assertRaises(ValueError):
            self.security_service.load_certificates()
    
    def test_validate_client_certificate_success(self):
        """Test successful client certificate validation."""
        # Load certificates first
        self.security_service._certificate_bundle = CertificateBundle(
            server_cert=self.server_cert_pem,
            server_key=self.server_key_pem,
            ca_cert=self.ca_cert_pem,
            client_certs=[self.client_cert_pem]
        )
        
        result = self.security_service.validate_client_certificate(self.client_cert_pem)
        
        self.assertIsInstance(result, AuthenticationResult)
        self.assertTrue(result.is_authenticated)
        self.assertEqual(result.client_id, "client")
        self.assertIsNone(result.error_message)
    
    def test_validate_client_certificate_expired(self):
        """Test validation of expired certificate."""
        # Create expired certificate
        expired_cert, _ = self._create_expired_cert()
        expired_cert_pem = expired_cert.public_bytes(serialization.Encoding.PEM).decode()
        
        self.security_service._certificate_bundle = CertificateBundle(
            server_cert=self.server_cert_pem,
            server_key=self.server_key_pem,
            ca_cert=self.ca_cert_pem,
            client_certs=[]
        )
        
        result = self.security_service.validate_client_certificate(expired_cert_pem)
        
        self.assertFalse(result.is_authenticated)
        self.assertIsNone(result.client_id)
        self.assertIn("expired", result.error_message.lower())
    
    def _create_expired_cert(self):
        """Create an expired test certificate."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "expired"),
        ])
        
        # Create certificate that expired yesterday
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            self.ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow() - timedelta(days=2)
        ).not_valid_after(
            datetime.utcnow() - timedelta(days=1)
        ).sign(self.ca_key, hashes.SHA256(), default_backend())
        
        return cert, private_key
    
    def test_validate_client_certificate_invalid_format(self):
        """Test validation with invalid certificate format."""
        result = self.security_service.validate_client_certificate("invalid certificate")
        
        self.assertFalse(result.is_authenticated)
        self.assertIsNone(result.client_id)
        self.assertIn("validation error", result.error_message.lower())
    
    @patch('ssl.create_default_context')
    def test_setup_mtls_context_success(self, mock_create_context):
        """Test successful SSL context setup."""
        mock_context = Mock()
        mock_create_context.return_value = mock_context
        
        # Load certificates first
        self.security_service._certificate_bundle = CertificateBundle(
            server_cert=self.server_cert_pem,
            server_key=self.server_key_pem,
            ca_cert=self.ca_cert_pem,
            client_certs=[]
        )
        
        context = self.security_service.setup_mtls_context()
        
        self.assertEqual(context, mock_context)
        mock_context.load_cert_chain.assert_called_once_with(
            certfile='/certs/server.crt',
            keyfile='/certs/server.key'
        )
        mock_context.load_verify_locations.assert_called_once_with(
            cafile='/certs/ca.crt'
        )
        self.assertEqual(mock_context.verify_mode, ssl.CERT_REQUIRED)
    
    def test_setup_mtls_context_no_bundle(self):
        """Test SSL context setup without loaded certificate bundle."""
        with self.assertRaises(ValueError):
            self.security_service.setup_mtls_context()
    
    def test_get_certificate_info(self):
        """Test certificate information extraction."""
        info = self.security_service.get_certificate_info(self.client_cert_pem)
        
        self.assertIsInstance(info, CertificateInfo)
        self.assertIn("client", info.subject)
        self.assertIn("Test CA", info.issuer)
        self.assertTrue(info.is_valid)
        self.assertIsNotNone(info.fingerprint)
        self.assertIsNotNone(info.serial_number)
    
    def test_is_certificate_valid_true(self):
        """Test certificate validity check for valid certificate."""
        is_valid = self.security_service.is_certificate_valid(self.client_cert_pem)
        self.assertTrue(is_valid)
    
    def test_is_certificate_valid_false(self):
        """Test certificate validity check for invalid certificate."""
        is_valid = self.security_service.is_certificate_valid("invalid certificate")
        self.assertFalse(is_valid)
    
    def test_extract_client_id_from_common_name(self):
        """Test client ID extraction from certificate common name."""
        client_id = self.security_service._extract_client_id(self.client_cert)
        self.assertEqual(client_id, "client")
    
    def test_extract_client_id_fallback_to_serial(self):
        """Test client ID extraction fallback to serial number."""
        # Create certificate without common name
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            self.ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            12345
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=30)
        ).sign(self.ca_key, hashes.SHA256(), default_backend())
        
        client_id = self.security_service._extract_client_id(cert)
        self.assertEqual(client_id, "12345")


if __name__ == '__main__':
    unittest.main()