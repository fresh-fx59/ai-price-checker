#!/bin/bash

# Price Monitor Nginx mTLS Configuration Script
# This script configures Nginx for the price-monitor.flowvian.com domain with mTLS proxy

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

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Configuration
DOMAIN_NAME="${DOMAIN_NAME:-price-monitor.flowvian.com}"
APP_PORT="${APP_PORT:-8443}"
CERT_DIR="${CERT_DIR:-/opt/price-monitor/certs}"
NGINX_SITES_DIR="/etc/nginx/sites-available"
NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
USE_LETSENCRYPT="${USE_LETSENCRYPT:-true}"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

print_header "Price Monitor Nginx mTLS Configuration"
print_status "Domain: $DOMAIN_NAME"
print_status "Application Port: $APP_PORT"
print_status "Certificate Directory: $CERT_DIR"
print_status "Use Let's Encrypt: $USE_LETSENCRYPT"

# Backup existing configuration
backup_nginx_config() {
    local backup_dir="/etc/nginx/backup"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    print_status "Creating nginx configuration backup..."
    mkdir -p "$backup_dir"
    
    if [[ -f "$NGINX_SITES_DIR/price-monitor" ]]; then
        cp "$NGINX_SITES_DIR/price-monitor" "$backup_dir/price-monitor.$timestamp"
        print_status "Existing configuration backed up"
    fi
}

# Generate nginx client certificate for mTLS proxy
generate_nginx_client_cert() {
    print_header "Generating Nginx Client Certificate for mTLS Proxy"
    
    if [[ ! -f "$CERT_DIR/ca.crt" || ! -f "$CERT_DIR/ca.key" ]]; then
        print_error "CA certificates not found. Please run ./generate-client-certs.sh first"
        exit 1
    fi
    
    local nginx_client_key="$CERT_DIR/nginx-client.key"
    local nginx_client_csr="$CERT_DIR/nginx-client.csr"
    local nginx_client_cert="$CERT_DIR/nginx-client.crt"
    
    if [[ -f "$nginx_client_cert" && -f "$nginx_client_key" ]]; then
        print_status "Nginx client certificate already exists"
        return 0
    fi
    
    print_status "Generating nginx client private key..."
    openssl genrsa -out "$nginx_client_key" 2048
    
    print_status "Generating nginx client certificate signing request..."
    openssl req -new -key "$nginx_client_key" -out "$nginx_client_csr" \
        -subj "/C=US/ST=State/L=City/O=Price Monitor/OU=Nginx Proxy/CN=nginx-client"
    
    print_status "Generating nginx client certificate..."
    openssl x509 -req -in "$nginx_client_csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
        -CAcreateserial -out "$nginx_client_cert" -days 365 \
        -extensions v3_req -extfile <(cat <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment, keyAgreement
extendedKeyUsage = critical, clientAuth
EOF
)
    
    # Clean up CSR
    rm "$nginx_client_csr"
    
    # Set proper permissions
    chmod 600 "$nginx_client_key"
    chmod 644 "$nginx_client_cert"
    chown www-data:www-data "$nginx_client_key" "$nginx_client_cert"
    
    print_success "Nginx client certificate generated successfully"
}

# Create nginx configuration
create_nginx_config() {
    print_header "Creating Nginx Configuration for $DOMAIN_NAME"
    
    local config_file="$NGINX_SITES_DIR/price-monitor"
    
    cat > "$config_file" << EOF
# Nginx configuration for mTLS proxy
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;
    
    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
EOF

    # Add SSL certificate configuration based on Let's Encrypt usage
    if [[ "$USE_LETSENCRYPT" == "true" ]]; then
        cat >> "$config_file" << EOF
    # SSL Configuration with Let's Encrypt
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    
EOF
    else
        cat >> "$config_file" << EOF
    # SSL Configuration with self-signed certificates
    ssl_certificate $CERT_DIR/server.crt;
    ssl_certificate_key $CERT_DIR/server.key;
    
EOF
    fi

    cat >> "$config_file" << EOF
    # Client certificate configuration (for end-to-end mTLS)
    ssl_client_certificate $CERT_DIR/ca.crt;
    ssl_verify_client on;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; script-src 'self' 'unsafe-inline'; img-src 'self' data: https: http:; connect-src 'self'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss;
    
    location / {
        # Proxy to HTTPS backend with client certificate
        proxy_pass https://127.0.0.1:$APP_PORT;
        
        # Pass client certificate to backend
        proxy_ssl_certificate $CERT_DIR/nginx-client.crt;
        proxy_ssl_certificate_key $CERT_DIR/nginx-client.key;
        proxy_ssl_trusted_certificate $CERT_DIR/ca.crt;
        proxy_ssl_verify on;
        proxy_ssl_verify_depth 2;
        
        # Standard proxy headers
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # SSL-specific headers
        proxy_set_header X-SSL-Client-Cert \$ssl_client_cert;
        proxy_set_header X-SSL-Client-Verify \$ssl_client_verify;
        proxy_set_header X-SSL-Client-S-DN \$ssl_client_s_dn;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health {
        proxy_pass https://127.0.0.1:$APP_PORT/health;
        
        # Use client certificate for health checks
        proxy_ssl_certificate $CERT_DIR/nginx-client.crt;
        proxy_ssl_certificate_key $CERT_DIR/nginx-client.key;
        proxy_ssl_trusted_certificate $CERT_DIR/ca.crt;
        proxy_ssl_verify on;
        
        access_log off;
    }
    
    location /static/ {
        alias /opt/price-monitor/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Fallback to try files if alias doesn't work
        try_files $uri $uri/ =404;
    }
}

# Note: Port $APP_PORT is used directly by the Python application
# Nginx handles public access on ports 80/443 and proxies to the app
EOF

    print_success "Nginx configuration created: $config_file"
}

# Enable the site
enable_site() {
    print_header "Enabling Nginx Site"
    
    # Remove default site
    if [[ -f "$NGINX_ENABLED_DIR/default" ]]; then
        rm -f "$NGINX_ENABLED_DIR/default"
        print_status "Removed default nginx site"
    fi
    
    # Enable price-monitor site
    ln -sf "$NGINX_SITES_DIR/price-monitor" "$NGINX_ENABLED_DIR/price-monitor"
    print_success "Price Monitor site enabled"
}

# Test and reload nginx
test_and_reload() {
    print_header "Testing and Reloading Nginx"
    
    print_status "Testing nginx configuration..."
    if nginx -t; then
        print_success "Nginx configuration test passed"
        
        print_status "Reloading nginx..."
        systemctl reload nginx
        print_success "Nginx reloaded successfully"
    else
        print_error "Nginx configuration test failed"
        return 1
    fi
}

# Setup Let's Encrypt certificate
setup_letsencrypt() {
    if [[ "$USE_LETSENCRYPT" != "true" ]]; then
        print_status "Skipping Let's Encrypt setup"
        return 0
    fi
    
    print_header "Setting up Let's Encrypt Certificate"
    
    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        print_status "Installing certbot..."
        apt-get update
        apt-get install -y certbot python3-certbot-nginx
    fi
    
    # Check if certificate already exists
    if [[ -f "/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem" ]]; then
        print_status "Let's Encrypt certificate already exists for $DOMAIN_NAME"
        return 0
    fi
    
    print_status "Obtaining Let's Encrypt certificate for $DOMAIN_NAME..."
    
    # Temporarily disable mTLS for certificate issuance
    sed -i 's/ssl_verify_client on;/ssl_verify_client optional;/' "$NGINX_SITES_DIR/price-monitor"
    systemctl reload nginx
    
    # Obtain certificate
    if certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --email "admin@$DOMAIN_NAME"; then
        print_success "Let's Encrypt certificate obtained successfully"
        
        # Re-enable mTLS
        sed -i 's/ssl_verify_client optional;/ssl_verify_client on;/' "$NGINX_SITES_DIR/price-monitor"
        systemctl reload nginx
        
        # Setup auto-renewal
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        print_status "Auto-renewal configured"
    else
        print_error "Failed to obtain Let's Encrypt certificate"
        # Restore mTLS setting
        sed -i 's/ssl_verify_client optional;/ssl_verify_client on;/' "$NGINX_SITES_DIR/price-monitor"
        return 1
    fi
}

# Main execution
main() {
    print_header "Starting Nginx mTLS Configuration"
    
    # Check prerequisites
    if ! command -v nginx &> /dev/null; then
        print_error "Nginx is not installed. Please install nginx first."
        exit 1
    fi
    
    if [[ ! -d "$CERT_DIR" ]]; then
        print_error "Certificate directory not found: $CERT_DIR"
        print_status "Please run ./generate-client-certs.sh first to generate certificates"
        exit 1
    fi
    
    # Backup existing configuration
    backup_nginx_config
    
    # Generate nginx client certificate
    generate_nginx_client_cert
    
    # Create nginx configuration
    create_nginx_config
    
    # Enable the site
    enable_site
    
    # Setup Let's Encrypt if requested
    setup_letsencrypt
    
    # Test and reload nginx
    test_and_reload
    
    print_header "Configuration Complete"
    print_success "Nginx mTLS proxy configured successfully for $DOMAIN_NAME"
    print_status "Application should be accessible at: https://$DOMAIN_NAME"
    print_status "Health check: https://$DOMAIN_NAME/health"
    
    echo ""
    print_status "Next steps:"
    print_status "1. Ensure your application is running on port $APP_PORT with mTLS enabled"
    print_status "2. Generate client certificates: ./generate-client-certs.sh admin-client"
    print_status "3. Test the configuration: curl --cert certs/admin-client.crt --key certs/admin-client.key https://$DOMAIN_NAME/health"
    
    if [[ "$USE_LETSENCRYPT" == "true" ]]; then
        print_status "4. Let's Encrypt certificate will auto-renew"
    fi
}

# Show usage if no arguments
if [[ $# -eq 0 && -z "$DOMAIN_NAME" ]]; then
    echo "Usage: $0 [domain_name]"
    echo ""
    echo "Environment Variables:"
    echo "  DOMAIN_NAME=<domain>     Domain name (default: price-monitor.flowvian.com)"
    echo "  APP_PORT=<port>          Application port (default: 8443)"
    echo "  CERT_DIR=<path>          Certificate directory (default: /opt/price-monitor/certs)"
    echo "  USE_LETSENCRYPT=<bool>   Use Let's Encrypt certificates (default: true)"
    echo ""
    echo "Examples:"
    echo "  sudo ./setup-nginx-mtls.sh"
    echo "  sudo DOMAIN_NAME=monitor.example.com ./setup-nginx-mtls.sh"
    echo "  sudo USE_LETSENCRYPT=false ./setup-nginx-mtls.sh"
    exit 1
fi

# Override domain name if provided as argument
if [[ $# -gt 0 ]]; then
    DOMAIN_NAME="$1"
fi

# Run main function
main