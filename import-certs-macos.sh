#!/bin/bash

# Price Monitor mTLS Certificate Import Script for macOS
# Credits: https://victoronsoftware.com/posts/mtls-with-apple-keychain/
# This script imports mTLS certificates and keys into the Apple Keychain for price-monitor.flowvian.com
# Run as root: sudo ./import-certs-macos.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Configuration
CERT_DIR="${CERT_DIR:-certs}"
DOMAIN="price-monitor.flowvian.com"
CLIENT_CERT_NAME="${CLIENT_CERT_NAME:-admin-client}"

print_status "Price Monitor mTLS Certificate Import for macOS"
print_status "Domain: $DOMAIN"
print_status "Certificate directory: $CERT_DIR"
print_status "Client certificate: $CLIENT_CERT_NAME"
echo ""

# Check if certificate files exist
if [[ ! -f "$CERT_DIR/ca.crt" ]]; then
    print_error "CA certificate not found: $CERT_DIR/ca.crt"
    print_status "Please run ./generate-client-certs.sh first to generate certificates"
    exit 1
fi

if [[ ! -f "$CERT_DIR/${CLIENT_CERT_NAME}.crt" ]]; then
    print_error "Client certificate not found: $CERT_DIR/${CLIENT_CERT_NAME}.crt"
    print_status "Please run ./generate-client-certs.sh $CLIENT_CERT_NAME first"
    exit 1
fi

if [[ ! -f "$CERT_DIR/${CLIENT_CERT_NAME}.key" ]]; then
    print_error "Client private key not found: $CERT_DIR/${CLIENT_CERT_NAME}.key"
    exit 1
fi

# Import the Certificate Authority (CA) certificate
print_status "Importing CA certificate to System Keychain..."
if security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CERT_DIR/ca.crt"; then
    print_success "CA certificate imported successfully"
else
    print_warning "CA certificate import failed (may already exist)"
fi

# Import the server certificate if it exists (for local development)
if [[ -f "$CERT_DIR/server.crt" ]]; then
    print_status "Importing server certificate to System Keychain..."
    if security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CERT_DIR/server.crt"; then
        print_success "Server certificate imported successfully"
    else
        print_warning "Server certificate import failed (may already exist)"
    fi
fi

# Import the client certificate and private key
print_status "Importing client certificate: $CLIENT_CERT_NAME"
if security import "$CERT_DIR/${CLIENT_CERT_NAME}.crt" -k /Library/Keychains/System.keychain; then
    print_success "Client certificate imported successfully"
else
    print_warning "Client certificate import failed (may already exist)"
fi

print_status "Importing client private key: $CLIENT_CERT_NAME"
# Import with access for common applications
if security import "$CERT_DIR/${CLIENT_CERT_NAME}.key" -k /Library/Keychains/System.keychain -x \
    -T /usr/bin/curl \
    -T /Applications/Safari.app \
    -T '/Applications/Google Chrome.app' \
    -T '/Applications/Firefox.app' \
    -T '/Applications/Postman.app' \
    -T '/Applications/Insomnia.app'; then
    print_success "Client private key imported successfully"
else
    print_warning "Client private key import failed (may already exist)"
fi

# Create PKCS#12 bundle for easier browser import
print_status "Creating PKCS#12 bundle for browser import..."
if openssl pkcs12 -export -in "$CERT_DIR/${CLIENT_CERT_NAME}.crt" \
    -inkey "$CERT_DIR/${CLIENT_CERT_NAME}.key" \
    -out "$CERT_DIR/${CLIENT_CERT_NAME}.p12" \
    -name "Price Monitor Client ($CLIENT_CERT_NAME)" \
    -passout pass:; then
    print_success "PKCS#12 bundle created: $CERT_DIR/${CLIENT_CERT_NAME}.p12"
    print_status "You can import this .p12 file directly into browsers"
else
    print_warning "PKCS#12 bundle creation failed"
fi

echo ""
print_success "Certificate import completed!"
echo ""
print_status "Testing certificate access:"

# Test with curl
print_status "Testing with curl..."
if curl -k --cert "$CERT_DIR/${CLIENT_CERT_NAME}.crt" \
    --key "$CERT_DIR/${CLIENT_CERT_NAME}.key" \
    "https://$DOMAIN/health" 2>/dev/null; then
    print_success "✓ curl test successful"
else
    print_warning "✗ curl test failed (application may not be running)"
fi

echo ""
print_status "Usage Instructions:"
print_status "1. For curl: curl --cert $CERT_DIR/${CLIENT_CERT_NAME}.crt --key $CERT_DIR/${CLIENT_CERT_NAME}.key https://$DOMAIN/"
print_status "2. For browsers: Import $CERT_DIR/${CLIENT_CERT_NAME}.p12 into your browser's certificate store"
print_status "3. For applications: The certificates are now available in the System Keychain"

echo ""
print_status "Browser Import Instructions:"
print_status "Safari: Preferences → Advanced → Certificates → Manage Certificates"
print_status "Chrome: Settings → Privacy and Security → Security → Manage Certificates"
print_status "Firefox: Settings → Privacy & Security → Certificates → View Certificates → Import"

echo ""
print_status "To remove certificates later:"
print_status "security delete-certificate -c 'Price Monitor CA' /Library/Keychains/System.keychain"
print_status "security delete-certificate -c '$CLIENT_CERT_NAME' /Library/Keychains/System.keychain"