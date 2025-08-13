#!/bin/bash

# Price Monitor Application - Ubuntu 24.04 IPv6-Only Docker Setup Script
# This script prepares a fresh Ubuntu 24.04 server with IPv6-only networking
# to run the Price Monitor application inside Docker containers
#
# Key Features:
# - IPv6-only network configuration
# - Docker and Docker Compose installation
# - Nginx reverse proxy with IPv6 support
# - SSL certificate support for IPv6 domains
# - Security hardening for IPv6 environments
# - Automated container deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration variables
APP_USER="${APP_USER:-price-monitor}"
APP_DIR="${APP_DIR:-/opt/price-monitor}"
APP_PORT="${APP_PORT:-8080}"
DOCKER_NETWORK="${DOCKER_NETWORK:-price-monitor-net}"
SETUP_FIREWALL="${SETUP_FIREWALL:-true}"
SETUP_SSL="${SETUP_SSL:-false}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
EMAIL_ADDRESS="${EMAIL_ADDRESS:-}"

# Logging
LOG_FILE="/var/log/price-monitor-ipv6-setup.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

# Function to print colored output
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
    echo -e "${PURPLE}[SETUP]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Function to check Ubuntu version
check_ubuntu_version() {
    if ! grep -q "Ubuntu 24.04" /etc/os-release; then
        print_warning "This script is designed for Ubuntu 24.04. Current version:"
        cat /etc/os-release | grep PRETTY_NAME
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to verify IPv6 connectivity
verify_ipv6() {
    print_header "Verifying IPv6 connectivity..."
    
    # Check if IPv6 is enabled
    if [[ ! -f /proc/net/if_inet6 ]]; then
        print_error "IPv6 is not available on this system"
        exit 1
    fi
    
    # Check for IPv6 addresses
    local ipv6_addresses=$(ip -6 addr show | grep "inet6" | grep -v "::1/128" | grep -v "fe80::" | wc -l)
    if [[ $ipv6_addresses -eq 0 ]]; then
        print_error "No IPv6 addresses found. This script requires IPv6 connectivity."
        exit 1
    fi
    
    print_status "Found $ipv6_addresses IPv6 address(es)"
    ip -6 addr show | grep "inet6" | grep -v "::1/128" | grep -v "fe80::" | head -3
    
    # Test IPv6 connectivity
    if ping6 -c 3 -W 5 google.com > /dev/null 2>&1; then
        print_success "IPv6 connectivity test passed"
    else
        print_warning "IPv6 connectivity test failed - continuing anyway"
    fi
}

# Function to configure IPv6 networking
configure_ipv6_networking() {
    print_header "Configuring IPv6 networking..."
    
    # Disable IPv4 forwarding (IPv6-only setup)
    echo 'net.ipv4.ip_forward=0' >> /etc/sysctl.conf
    
    # Enable IPv6 forwarding
    echo 'net.ipv6.conf.all.forwarding=1' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.default.forwarding=1' >> /etc/sysctl.conf
    
    # Optimize IPv6 settings for server use
    echo 'net.ipv6.conf.all.use_tempaddr=0' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.default.use_tempaddr=0' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.all.accept_ra=1' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.default.accept_ra=1' >> /etc/sysctl.conf
    
    # Apply sysctl settings
    sysctl -p
    
    print_success "IPv6 networking configured"
}

# Function to update system
update_system() {
    print_header "Updating system packages..."
    
    # Update package lists
    apt-get update -y
    
    # Upgrade existing packages
    apt-get upgrade -y
    
    # Install essential packages
    apt-get install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        htop \
        tree \
        jq \
        vim \
        nano \
        net-tools \
        ufw \
        fail2ban \
        logrotate \
        cron \
        netcat-openbsd \
        dnsutils \
        libxml2-dev \
        libxslt1-dev \
        python3-dev \
        build-essential \
        pkg-config
    
    print_success "System updated successfully"
}

# Function to install Docker with IPv6 support
install_docker() {
    print_header "Installing Docker with IPv6 support..."
    
    # Remove old versions
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Add Docker's official GPG key
    print_status "Adding Docker GPG key..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Configure Docker daemon for IPv6
    print_status "Configuring Docker daemon for IPv6..."
    mkdir -p /etc/docker
    
    cat > /etc/docker/daemon.json << 'EOF'
{
  "ipv6": true,
  "fixed-cidr-v6": "2001:db8:1::/64",
  "experimental": false,
  "ip6tables": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF
    
    # Enable and start Docker
    systemctl enable docker
    systemctl start docker
    
    # Create Docker network with IPv6 support
    print_status "Creating Docker network with IPv6 support..."
    docker network create \
        --driver bridge \
        --ipv6 \
        --subnet=172.20.0.0/16 \
        --subnet=2001:db8:2::/64 \
        $DOCKER_NETWORK || print_warning "Docker network may already exist"
    
    # Verify Docker installation
    if docker --version && docker compose version; then
        print_success "Docker installed and configured successfully"
    else
        print_error "Docker installation verification failed"
        exit 1
    fi
}

# Function to install Nginx with IPv6 configuration
install_nginx() {
    print_header "Installing Nginx with IPv6 configuration..."
    
    # Install Nginx
    apt-get install -y nginx
    
    # Create IPv6-optimized configuration
    cat > /etc/nginx/sites-available/price-monitor << 'EOF'
server {
    # IPv6-only configuration
    listen [::]:80 default_server;
    listen [::]:443 ssl http2 default_server;
    
    server_name _;
    
    # SSL configuration (will be updated by certbot)
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;
    
    # Redirect HTTP to HTTPS
    if ($scheme != "https") {
        return 301 https://$host$request_uri;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        access_log off;
    }
    
    location /static/ {
        alias /opt/price-monitor/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Security: deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF
    
    # Enable the site
    ln -sf /etc/nginx/sites-available/price-monitor /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test and reload Nginx
    if nginx -t; then
        systemctl enable nginx
        systemctl start nginx
        systemctl reload nginx
        print_success "Nginx installed and configured successfully"
    else
        print_error "Nginx configuration test failed"
        exit 1
    fi
}

# Function to setup IPv6 firewall
setup_ipv6_firewall() {
    if [[ "$SETUP_FIREWALL" != "true" ]]; then
        print_status "Skipping firewall setup"
        return
    fi
    
    print_header "Setting up IPv6-optimized UFW firewall..."
    
    # Reset UFW to defaults
    ufw --force reset
    
    # Enable IPv6 support
    sed -i 's/IPV6=no/IPV6=yes/' /etc/default/ufw
    
    # Set default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (IPv6)
    ufw allow from any to any port 22 proto tcp
    
    # Allow HTTP and HTTPS (IPv6)
    ufw allow from any to any port 80 proto tcp
    ufw allow from any to any port 443 proto tcp
    
    # Allow application port for direct access if needed
    ufw allow from any to any port ${APP_PORT} proto tcp
    
    # Rate limiting for SSH
    ufw limit ssh
    
    # Enable UFW
    ufw --force enable
    
    print_success "IPv6 firewall configured successfully"
}

# Function to setup fail2ban for IPv6
setup_fail2ban() {
    print_header "Configuring Fail2ban for IPv6..."
    
    # Create custom jail configuration with IPv6 support
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

# IPv6 support
banaction = ufw
banaction_allports = ufw

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10

[nginx-botsearch]
enabled = true
filter = nginx-botsearch
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
EOF
    
    # Enable and start fail2ban
    systemctl enable fail2ban
    systemctl start fail2ban
    
    print_success "Fail2ban configured for IPv6"
}

# Function to create application user and directories
create_app_user() {
    print_header "Creating application user: ${APP_USER}..."
    
    # Create user if it doesn't exist
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash -d /home/$APP_USER $APP_USER
        print_success "User $APP_USER created"
    else
        print_status "User $APP_USER already exists"
    fi
    
    # Add user to docker group
    usermod -aG docker $APP_USER
    
    # Create application directory structure
    mkdir -p $APP_DIR/{config,logs,data,certs,static}
    
    # Set ownership and permissions
    chown -R $APP_USER:$APP_USER $APP_DIR
    chmod -R 755 $APP_DIR
    chmod -R 700 $APP_DIR/certs
    
    print_success "Application user and directories created"
}

# Function to install certbot for IPv6 SSL certificates
install_certbot() {
    print_header "Installing Certbot for IPv6 SSL certificates..."
    
    # Install snapd
    apt-get install -y snapd
    systemctl enable snapd
    systemctl start snapd
    
    # Wait for snapd to be ready
    sleep 5
    
    # Install certbot via snap
    snap install core
    snap refresh core
    snap install --classic certbot
    
    # Create symlink
    ln -sf /snap/bin/certbot /usr/bin/certbot
    
    # Install nginx plugin
    apt-get install -y python3-certbot-nginx
    
    print_success "Certbot installed successfully"
}

# Function to create Docker Compose configuration
create_docker_compose() {
    print_header "Creating Docker Compose configuration..."
    
    cat > $APP_DIR/docker-compose.yml << 'EOF'
version: '3.8'

services:
  price-monitor:
    build: .
    container_name: price-monitor-app
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./logs:/app/logs
      - ./static:/app/static:ro
    environment:
      - PYTHONUNBUFFERED=1
      - CONFIG_PATH=/app/config
      - DATA_PATH=/app/data
      - LOG_PATH=/app/logs
    networks:
      - price-monitor-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  price-monitor-net:
    external: true
EOF
    
    # Create Dockerfile
    cat > $APP_DIR/Dockerfile << 'EOF'
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "src/main.py"]
EOF
    
    # Set ownership
    chown -R $APP_USER:$APP_USER $APP_DIR/docker-compose.yml $APP_DIR/Dockerfile
    
    print_success "Docker Compose configuration created"
}

# Function to create systemd service for Docker Compose
create_systemd_service() {
    print_header "Creating systemd service for Price Monitor..."
    
    cat > /etc/systemd/system/price-monitor.service << EOF
[Unit]
Description=Price Monitor Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0
User=$APP_USER
Group=$APP_USER

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable the service
    systemctl daemon-reload
    systemctl enable price-monitor.service
    
    print_success "Systemd service created and enabled"
}

# Function to create management scripts
create_management_scripts() {
    print_header "Creating management scripts..."
    
    # Create deployment script
    cat > /usr/local/bin/deploy-price-monitor << EOF
#!/bin/bash
# Price Monitor Deployment Script

set -e

APP_DIR="$APP_DIR"
APP_USER="$APP_USER"

print_status() {
    echo -e "\033[0;34m[INFO]\033[0m \$1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m \$1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m \$1"
}

# Change to app directory
cd \$APP_DIR

# Pull latest changes (if git repo)
if [[ -d .git ]]; then
    print_status "Pulling latest changes..."
    sudo -u \$APP_USER git pull
fi

# Build and deploy
print_status "Building and deploying containers..."
sudo -u \$APP_USER docker compose build --no-cache
sudo -u \$APP_USER docker compose up -d

# Check health
sleep 10
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    print_success "Deployment successful - application is healthy"
else
    print_error "Deployment may have issues - health check failed"
    exit 1
fi
EOF
    
    # Create log viewer script
    cat > /usr/local/bin/price-monitor-logs << EOF
#!/bin/bash
# Price Monitor Log Viewer

APP_DIR="$APP_DIR"
APP_USER="$APP_USER"

cd \$APP_DIR
sudo -u \$APP_USER docker compose logs -f
EOF
    
    # Create status script
    cat > /usr/local/bin/price-monitor-status << EOF
#!/bin/bash
# Price Monitor Status Script

APP_DIR="$APP_DIR"
APP_USER="$APP_USER"

echo "=== Price Monitor Status ==="
echo

echo "Docker Containers:"
cd \$APP_DIR
sudo -u \$APP_USER docker compose ps

echo
echo "Application Health:"
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ Application is healthy"
else
    echo "✗ Application health check failed"
fi

echo
echo "System Resources:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
EOF
    
    # Make scripts executable
    chmod +x /usr/local/bin/deploy-price-monitor
    chmod +x /usr/local/bin/price-monitor-logs
    chmod +x /usr/local/bin/price-monitor-status
    
    print_success "Management scripts created"
}

# Function to display setup summary
display_summary() {
    print_header "Setup Complete!"
    echo
    print_success "Ubuntu 24.04 IPv6-only Docker setup completed successfully"
    echo
    print_status "Configuration Summary:"
    print_status "  • Application User: $APP_USER"
    print_status "  • Application Directory: $APP_DIR"
    print_status "  • Application Port: $APP_PORT"
    print_status "  • Docker Network: $DOCKER_NETWORK"
    print_status "  • IPv6 Support: Enabled"
    print_status "  • Firewall: $([ "$SETUP_FIREWALL" == "true" ] && echo "Enabled" || echo "Disabled")"
    echo
    print_status "Available Commands:"
    print_status "  • deploy-price-monitor    - Deploy/update the application"
    print_status "  • price-monitor-logs      - View application logs"
    print_status "  • price-monitor-status    - Check application status"
    print_status "  • systemctl start price-monitor  - Start the service"
    print_status "  • systemctl stop price-monitor   - Stop the service"
    echo
    print_status "Next Steps:"
    print_status "  1. Copy your application code to $APP_DIR"
    print_status "  2. Update configuration files in $APP_DIR/config/"
    print_status "  3. Run: deploy-price-monitor"
    
    if [[ "$SETUP_SSL" == "true" && -n "$DOMAIN_NAME" ]]; then
        print_status "  4. SSL certificate will be issued for: $DOMAIN_NAME"
    else
        print_status "  4. Configure SSL: certbot --nginx -d your-domain.com"
    fi
    
    echo
    print_status "IPv6 Addresses:"
    ip -6 addr show | grep "inet6" | grep -v "::1/128" | grep -v "fe80::" | head -3
    echo
}

# Main execution
main() {
    print_header "Starting Ubuntu 24.04 IPv6-Only Docker Setup for Price Monitor"
    echo
    
    # Pre-flight checks
    check_root
    check_ubuntu_version
    verify_ipv6
    
    # System setup
    configure_ipv6_networking
    update_system
    
    # Install core components
    install_docker
    install_nginx
    
    # Security setup
    setup_ipv6_firewall
    setup_fail2ban
    
    # Application setup
    create_app_user
    create_docker_compose
    create_systemd_service
    create_management_scripts
    
    # SSL setup (optional)
    if [[ "$SETUP_SSL" == "true" ]]; then
        install_certbot
        if [[ -n "$DOMAIN_NAME" && -n "$EMAIL_ADDRESS" ]]; then
            print_status "Issuing SSL certificate for $DOMAIN_NAME..."
            certbot --nginx -d "$DOMAIN_NAME" --email "$EMAIL_ADDRESS" --agree-tos --non-interactive
        fi
    fi
    
    # Final summary
    display_summary
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN_NAME="$2"
            SETUP_SSL="true"
            shift 2
            ;;
        --email)
            EMAIL_ADDRESS="$2"
            shift 2
            ;;
        --no-firewall)
            SETUP_FIREWALL="false"
            shift
            ;;
        --app-port)
            APP_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --domain DOMAIN     Set domain name and enable SSL"
            echo "  --email EMAIL       Email for SSL certificate"
            echo "  --no-firewall       Skip firewall setup"
            echo "  --app-port PORT     Application port (default: 8080)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"