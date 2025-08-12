"""
Security service for mTLS certificate management and validation.
"""
import ssl
import os
import logging
from typing import Optional, List
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import NameOID
from datetime import datetime, timezone

from .models import CertificateBundle, AuthenticationResult, CertificateInfo


class SecurityService:
    """Service for handling mTLS authentication and certificate management."""
    
    def __init__(self, config):
        """Initialize the security service with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._certificate_bundle: Optional[CertificateBundle] = None
        
    def load_certificates(self) -> CertificateBundle:
        """Load certificates from configured paths."""
        # Skip certificate loading if mTLS is disabled
        if not getattr(self.config, 'enable_mtls', False):
            self.logger.info("mTLS disabled, skipping certificate loading")
            self._certificate_bundle = CertificateBundle(
                server_cert="",
                server_key="",
                ca_cert="",
                client_certs=[]
            )
            return self._certificate_bundle
        
        try:
            # Load server certificate
            server_cert = self._load_certificate_file(self.config.server_cert_path)
            
            # Load server private key
            server_key = self._load_certificate_file(self.config.server_key_path)
            
            # Load CA certificate
            ca_cert = self._load_certificate_file(self.config.ca_cert_path)
            
            # Load client certificates (if directory exists)
            client_certs = self._load_client_certificates()
            
            self._certificate_bundle = CertificateBundle(
                server_cert=server_cert,
                server_key=server_key,
                ca_cert=ca_cert,
                client_certs=client_certs
            )
            
            self.logger.info("Successfully loaded certificate bundle")
            return self._certificate_bundle
            
        except Exception as e:
            self.logger.error(f"Failed to load certificates: {e}")
            raise
    
    def _load_certificate_file(self, file_path: str) -> str:
        """Load certificate content from file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Certificate file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        if not content.strip():
            raise ValueError(f"Certificate file is empty: {file_path}")
        
        return content
    
    def _load_client_certificates(self) -> List[str]:
        """Load all client certificates from the client certificates directory."""
        client_certs = []
        
        # Check if there's a client-certs directory
        cert_dir = os.path.dirname(self.config.server_cert_path)
        client_cert_dir = os.path.join(cert_dir, 'client-certs')
        
        if os.path.exists(client_cert_dir) and os.path.isdir(client_cert_dir):
            for filename in os.listdir(client_cert_dir):
                if filename.endswith(('.crt', '.pem')):
                    cert_path = os.path.join(client_cert_dir, filename)
                    try:
                        cert_content = self._load_certificate_file(cert_path)
                        client_certs.append(cert_content)
                        self.logger.info(f"Loaded client certificate: {filename}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load client certificate {filename}: {e}")
        
        return client_certs
    
    def validate_client_certificate(self, cert_pem: str) -> AuthenticationResult:
        """Validate a client certificate against the CA."""
        try:
            # Parse the client certificate
            cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
            
            # Get certificate info
            cert_info = self._get_certificate_info(cert)
            
            # Check if certificate is expired
            if not cert_info.is_valid:
                return AuthenticationResult(
                    is_authenticated=False,
                    client_id=None,
                    error_message="Certificate has expired"
                )
            
            # Validate against CA
            if not self._validate_against_ca(cert):
                return AuthenticationResult(
                    is_authenticated=False,
                    client_id=None,
                    error_message="Certificate not signed by trusted CA"
                )
            
            # Extract client ID from certificate subject
            client_id = self._extract_client_id(cert)
            
            self.logger.info(f"Successfully authenticated client: {client_id}")
            return AuthenticationResult(
                is_authenticated=True,
                client_id=client_id,
                error_message=None
            )
            
        except Exception as e:
            self.logger.error(f"Certificate validation failed: {e}")
            return AuthenticationResult(
                is_authenticated=False,
                client_id=None,
                error_message=f"Certificate validation error: {str(e)}"
            )
    
    def _get_certificate_info(self, cert: x509.Certificate) -> CertificateInfo:
        """Extract information from a certificate."""
        now = datetime.now(timezone.utc)
        
        # Get subject and issuer
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        
        # Get validity period
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
        
        # Check if certificate is currently valid
        is_valid = not_before <= now <= not_after
        
        # Get fingerprint
        fingerprint = cert.fingerprint(cert.signature_hash_algorithm).hex()
        
        return CertificateInfo(
            subject=subject,
            issuer=issuer,
            serial_number=str(cert.serial_number),
            not_before=not_before,
            not_after=not_after,
            is_valid=is_valid,
            fingerprint=fingerprint
        )
    
    def _validate_against_ca(self, cert: x509.Certificate) -> bool:
        """Validate certificate against the CA certificate."""
        try:
            if not self._certificate_bundle:
                raise ValueError("Certificate bundle not loaded")
            
            # Load CA certificate
            ca_cert = x509.load_pem_x509_certificate(
                self._certificate_bundle.ca_cert.encode(), 
                default_backend()
            )
            
            # Check if the certificate was issued by the CA
            # Compare issuer of the cert with subject of the CA
            if cert.issuer != ca_cert.subject:
                return False
            
            # Verify the certificate signature using CA's public key
            try:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.asymmetric import padding
                
                # Get the signature algorithm
                signature_algorithm = cert.signature_algorithm_oid._name
                
                if 'sha256' in signature_algorithm.lower():
                    hash_algorithm = hashes.SHA256()
                elif 'sha1' in signature_algorithm.lower():
                    hash_algorithm = hashes.SHA1()
                else:
                    # Default to SHA256
                    hash_algorithm = hashes.SHA256()
                
                # For RSA signatures, we need to use the appropriate padding
                ca_public_key = ca_cert.public_key()
                
                # Try to verify the signature
                if hasattr(ca_public_key, 'verify'):
                    # For RSA keys
                    ca_public_key.verify(
                        cert.signature,
                        cert.tbs_certificate_bytes,
                        padding.PKCS1v15(),
                        hash_algorithm
                    )
                    return True
                else:
                    # For other key types, use the generic verify method
                    ca_public_key.verify(
                        cert.signature,
                        cert.tbs_certificate_bytes,
                        hash_algorithm
                    )
                    return True
                    
            except Exception as verify_error:
                self.logger.debug(f"Signature verification failed: {verify_error}")
                return False
                
        except Exception as e:
            self.logger.error(f"CA validation failed: {e}")
            return False
    
    def _extract_client_id(self, cert: x509.Certificate) -> str:
        """Extract client ID from certificate subject."""
        try:
            # Try to get Common Name (CN) from subject
            for attribute in cert.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    return attribute.value
            
            # Fallback to serial number if CN not found
            return str(cert.serial_number)
            
        except Exception:
            return "unknown"
    
    def setup_mtls_context(self) -> ssl.SSLContext:
        """Create SSL context configured for mTLS."""
        if not self._certificate_bundle:
            raise ValueError("Certificate bundle not loaded. Call load_certificates() first.")
        
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Load server certificate and key
        context.load_cert_chain(
            certfile=self.config.server_cert_path,
            keyfile=self.config.server_key_path
        )
        
        # Load CA certificate for client verification
        context.load_verify_locations(cafile=self.config.ca_cert_path)
        
        # Require client certificates
        if self.config.client_cert_required:
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_OPTIONAL
        
        # Set protocol and cipher options
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        self.logger.info("SSL context configured for mTLS")
        return context
    
    def get_certificate_info(self, cert_pem: str) -> CertificateInfo:
        """Get detailed information about a certificate."""
        cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
        return self._get_certificate_info(cert)
    
    def is_certificate_valid(self, cert_pem: str) -> bool:
        """Check if a certificate is currently valid (not expired)."""
        try:
            cert_info = self.get_certificate_info(cert_pem)
            return cert_info.is_valid
        except Exception:
            return False