#!/bin/bash

# Client Certificate Generation Script for Price Monitor mTLS
# This script generates client certificates for mTLS authentication

set -e

# Configuration
CERT_DIR="${CERT_DIR:-certs}"
CA_DIR="${CA_DIR:-$CERT_DIR}"
CA_KEY="$CA_DIR/ca.key"
CA_CERT="$CA_DIR/ca.crt"
CLIENT_NAME="${1:-client1}"
DAYS_VALID="${2:-365}"

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

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Function to create CA if it doesn't exist
create_ca() {
    print_header "Creating Certificate Authority (CA)"
    
    # Create CA and certs directories
    mkdir -p "$CA_DIR"
    mkdir -p "$CERT_DIR"
    
    # Generate CA private key
    print_status "Generating CA private key..."
    openssl genrsa -out "$CA_KEY" 4096
    
    # Generate CA certificate
    print_status "Generating CA certificate..."
    openssl req -new -x509 -days 3650 -key "$CA_KEY" -out "$CA_CERT" \
        -subj "/C=US/ST=State/L=City/O=Price Monitor/OU=IT Department/CN=Price Monitor CA"
    
    # Set proper permissions
    chmod 600 "$CA_KEY"
    chmod 644 "$CA_CERT"
    
    print_success "CA created successfully"
    print_status "CA Directory: $CA_DIR"
}

# Function to generate client certificate
generate_client_cert() {
    local client_name="$1"
    local client_key="$CERT_DIR/${client_name}.key"
    local client_csr="$CERT_DIR/${client_name}.csr"
    local client_cert="$CERT_DIR/${client_name}.crt"
    
    print_header "Generating Client Certificate for: $client_name"
    
    # Generate client private key
    print_status "Generating client private key..."
    openssl genrsa -out "$client_key" 2048
    
    # Generate client certificate signing request
    print_status "Generating certificate signing request..."
    openssl req -new -key "$client_key" -out "$client_csr" \
        -subj "/C=US/ST=State/L=City/O=Price Monitor/OU=Client/CN=$client_name"
    
    # Generate client certificate signed by CA
    print_status "Generating client certificate..."
    openssl x509 -req -in "$client_csr" -CA "$CA_CERT" -CAkey "$CA_KEY" \
        -CAcreateserial -out "$client_cert" -days "$DAYS_VALID" \
        -extensions v3_req -extfile <(cat <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment, keyAgreement
extendedKeyUsage = critical, clientAuth
EOF
)
    
    # Clean up CSR
    rm "$client_csr"
    
    # Set proper permissions
    chmod 600 "$client_key"
    chmod 644 "$client_cert"
    
    print_success "Client certificate generated: $client_cert"
    print_success "Client private key: $client_key"
}

# Function to generate server certificate (if needed)
generate_server_cert() {
    local server_key="$CERT_DIR/server.key"
    local server_csr="$CERT_DIR/server.csr"
    local server_cert="$CERT_DIR/server.crt"
    local server_name="${SERVER_NAME:-localhost}"
    
    print_header "Generating Server Certificate"
    
    # Generate server private key
    print_status "Generating server private key..."
    openssl genrsa -out "$server_key" 2048
    
    # Generate server certificate signing request
    print_status "Generating server certificate signing request..."
    openssl req -new -key "$server_key" -out "$server_csr" \
        -subj "/C=US/ST=State/L=City/O=Price Monitor/OU=Server/CN=$server_name"
    
    # Generate server certificate signed by CA
    print_status "Generating server certificate..."
    openssl x509 -req -in "$server_csr" -CA "$CA_CERT" -CAkey "$CA_KEY" \
        -CAcreateserial -out "$server_cert" -days "$DAYS_VALID" \
        -extensions v3_req -extfile <(cat <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment, keyAgreement
extendedKeyUsage = critical, serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = $server_name
DNS.3 = 127.0.0.1
DNS.4 = ::1
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
)
    
    # Clean up CSR
    rm "$server_csr"
    
    # Set proper permissions
    chmod 600 "$server_key"
    chmod 644 "$server_cert"
    
    print_success "Server certificate generated: $server_cert"
    print_success "Server private key: $server_key"
}

# Function to display certificate info
show_cert_info() {
    local cert_file="$1"
    
    if [[ -f "$cert_file" ]]; then
        print_header "Certificate Information: $(basename "$cert_file")"
        openssl x509 -in "$cert_file" -text -noout | grep -E "(Subject:|Issuer:|Not Before:|Not After:|DNS:|IP Address:)"
    fi
}

# Function to test certificate
test_certificate() {
    local client_cert="$CERT_DIR/${CLIENT_NAME}.crt"
    local client_key="$CERT_DIR/${CLIENT_NAME}.key"
    
    if [[ -f "$client_cert" && -f "$client_key" ]]; then
        print_header "Testing Client Certificate"
        print_status "Testing certificate with curl..."
        
        # Test against local application (if running)
        if curl -k --cert "$client_cert" --key "$client_key" \
           https://localhost:8443/health 2>/dev/null; then
            print_success "Client certificate test successful!"
        else
            print_warning "Could not test certificate (application may not be running)"
            print_status "Certificate files are ready for use"
        fi
    fi
}

# Main execution
main() {
    print_header "Price Monitor Client Certificate Generator"
    
    if [[ $# -eq 0 ]]; then
        print_status "Usage: $0 <client_name> [days_valid]"
        print_status "Example: $0 admin-client 365"
        print_status "Example: $0 api-client 30"
        print_status ""
        print_status "Environment Variables:"
        print_status "  CERT_DIR=<path>    Certificate output directory (default: ./certs)"
        print_status "  CA_DIR=<path>      CA certificate directory (default: same as CERT_DIR)"
        print_status ""
        print_status "Examples with custom directories:"
        print_status "  CERT_DIR=/etc/ssl/certs CA_DIR=/etc/ssl/ca $0 admin-client"
        print_status "  CA_DIR=/shared/ca $0 api-client 90"
        exit 1
    fi
    
    # Check if CA exists, create if not
    if [[ ! -f "$CA_CERT" || ! -f "$CA_KEY" ]]; then
        print_warning "CA not found, creating new CA..."
        create_ca
    else
        print_status "Using existing CA: $CA_CERT"
    fi
    
    # Generate server certificate if it doesn't exist
    if [[ ! -f "$CERT_DIR/server.crt" ]]; then
        print_warning "Server certificate not found, generating..."
        generate_server_cert
    fi
    
    # Generate client certificate
    generate_client_cert "$CLIENT_NAME"
    
    # Show certificate information
    show_cert_info "$CERT_DIR/${CLIENT_NAME}.crt"
    
    # Test certificate
    test_certificate
    
    print_header "Certificate Generation Complete"
    print_success "Certificate Directory: $CERT_DIR"
    print_success "CA Directory: $CA_DIR"
    print_status "CA Certificate: $CA_CERT"
    print_status "Client Certificate: $CERT_DIR/${CLIENT_NAME}.crt"
    print_status "Client Private Key: $CERT_DIR/${CLIENT_NAME}.key"
    
    echo ""
    print_status "To use this certificate with curl:"
    echo "curl -k --cert $CERT_DIR/${CLIENT_NAME}.crt --key $CERT_DIR/${CLIENT_NAME}.key https://localhost:8443/health"
    
    echo ""
    print_status "To use in browser, combine certificate and key:"
    echo "cat $CERT_DIR/${CLIENT_NAME}.crt $CERT_DIR/${CLIENT_NAME}.key > $CERT_DIR/${CLIENT_NAME}.p12"
    echo "openssl pkcs12 -export -in $CERT_DIR/${CLIENT_NAME}.crt -inkey $CERT_DIR/${CLIENT_NAME}.key -out $CERT_DIR/${CLIENT_NAME}.p12"
}

# Run main function
main "$@"