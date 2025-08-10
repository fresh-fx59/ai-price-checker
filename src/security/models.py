"""
Security models for mTLS certificate management.
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class CertificateBundle:
    """Bundle containing all certificates needed for mTLS."""
    server_cert: str
    server_key: str
    ca_cert: str
    client_certs: List[str]


@dataclass
class AuthenticationResult:
    """Result of client certificate authentication."""
    is_authenticated: bool
    client_id: Optional[str]
    error_message: Optional[str]


@dataclass
class CertificateInfo:
    """Information about a certificate."""
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    is_valid: bool
    fingerprint: str