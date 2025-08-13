#!/bin/bash

# Price Monitor Application - Ubuntu 24.04 Server Setup Script
# This script prepares a fresh Ubuntu 24.04 server to run the Price Monitor application
# Default Python version: 3.13 (latest stable release)
#
# SSL Certificate Features:
# - Automatic SSL certificate issuance with Let's Encrypt
# - Multiple certificate methods: nginx, webroot, standalone, dns
# - Interactive SSL management tools
# - Automatic certificate renewal
# - Certificate monitoring and alerting
# - Full IPv6 support for IPv6-only domains
#
# Network Features:
# - IPv4 and IPv6 dual-stack support
# - IPv6-only domain support
# - Nginx configured for both IPv4 and IPv6
# - Firewall rules for both protocols
#
# SSL Management Commands (available after setup):
# - ssl-manager: Interactive SSL certificate management
# - issue-ssl-cert <domain> <email> [method]: Issue new certificates
# - monitor-ssl-certs: Monitor certificate expiration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration variables (can be overridden via environment variables)
APP_USER="${APP_USER:-price-monitor}"
APP_DIR="${APP_DIR:-/opt/price-monitor}"
APP_PORT="${APP_PORT:-8080}"
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
NODE_VERSION="${NODE_VERSION:-20}"
INSTALL_DOCKER="${INSTALL_DOCKER:-true}"
INSTALL_NGINX="${INSTALL_NGINX:-true}"
SETUP_FIREWALL="${SETUP_FIREWALL:-true}"
SETUP_SSL="${SETUP_SSL:-false}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
EMAIL_ADDRESS="${EMAIL_ADDRESS:-}"
SSL_METHOD="${SSL_METHOD:-nginx}"

# Logging
LOG_FILE="/var/log/price-monitor-setup.log"
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
        build-essential \
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
        supervisor
    
    print_success "System updated successfully"
}

# Function to install Python and dependencies
install_python() {
    print_header "Installing Python ${PYTHON_VERSION} and dependencies..."
    
    # Add deadsnakes PPA for latest Python versions (required for Python 3.13)
    if [[ "$OFFLINE_MODE" != "true" ]]; then
        print_status "Adding deadsnakes PPA for Python ${PYTHON_VERSION}..."
        add-apt-repository ppa:deadsnakes/ppa -y
        apt-get update -y
    else
        print_status "Offline mode: Skipping deadsnakes PPA, using available packages"
        apt-get update -y
    fi
    
    # For Python 3.13, we might need additional repositories
    if [[ "$PYTHON_VERSION" == "3.13" ]]; then
        print_status "Python 3.13 detected - ensuring latest package information..."
        # Refresh package cache to get the latest Python 3.13 packages
        apt-get update -y
    fi
    
    # Detect Ubuntu version and adjust Python version if needed
    ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "24.04")
    print_status "Detected Ubuntu version: $ubuntu_version"
    
    # Check if the requested Python version is available
    if ! apt-cache show python${PYTHON_VERSION} > /dev/null 2>&1; then
        print_warning "Python ${PYTHON_VERSION} not available, checking for alternatives..."
        
        # Adjust Python version based on Ubuntu version
        case "$ubuntu_version" in
            "24.04"|"23.10"|"23.04")
                # Ubuntu 24.04+ - prioritize Python 3.13
                available_versions="3.13 3.12 3.11 3.10 3.9"
                ;;
            "22.04"|"22.10")
                # Ubuntu 22.04 - Python 3.13 available via deadsnakes
                available_versions="3.13 3.12 3.11 3.10 3.9 3.8"
                ;;
            "20.04"|"20.10")
                # Ubuntu 20.04 - Python 3.13 available via deadsnakes
                available_versions="3.13 3.12 3.11 3.10 3.9 3.8"
                ;;
            *)
                # Default fallback - prioritize Python 3.13
                available_versions="3.13 3.12 3.11 3.10 3.9 3.8"
                ;;
        esac
        
        # Try versions in order of preference
        for version in $available_versions; do
            if apt-cache show python${version} > /dev/null 2>&1; then
                print_status "Using Python ${version} instead"
                PYTHON_VERSION=$version
                break
            fi
        done
        
        # If no specific version found, use system default
        if ! apt-cache show python${PYTHON_VERSION} > /dev/null 2>&1; then
            print_status "Using system default Python 3"
            PYTHON_VERSION="3"
        fi
    fi
    
    print_status "Selected Python version: ${PYTHON_VERSION}"
    
    # Install Python and related packages (without version-specific pip first)
    apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-dev \
        python${PYTHON_VERSION}-venv \
        python3-pip \
        python3-setuptools \
        python3-wheel \
        curl \
        wget
    
    # Try to install version-specific pip, but don't fail if not available
    if apt-cache show python${PYTHON_VERSION}-pip > /dev/null 2>&1; then
        apt-get install -y python${PYTHON_VERSION}-pip
        print_status "Installed python${PYTHON_VERSION}-pip from package"
    else
        print_warning "python${PYTHON_VERSION}-pip package not available, using alternative method"
        
        # Install additional dependencies if available (don't fail if not found)
        print_status "Installing additional Python ${PYTHON_VERSION} packages..."
        
        # Try to install distutils (not available for Python 3.12+)
        case "$PYTHON_VERSION" in
            "3.8"|"3.9"|"3.10"|"3.11")
                print_status "Installing distutils for Python ${PYTHON_VERSION}..."
                apt-get install -y python${PYTHON_VERSION}-distutils || true
                ;;
            *)
                print_status "Distutils not needed for Python ${PYTHON_VERSION} (built-in or deprecated)"
                ;;
        esac
        
        # Try to install other useful packages if available
        for package in lib2to3 gdbm tk; do
            if apt-cache show python${PYTHON_VERSION}-${package} > /dev/null 2>&1; then
                print_status "Installing python${PYTHON_VERSION}-${package}..."
                apt-get install -y python${PYTHON_VERSION}-${package} || true
            else
                print_status "Package python${PYTHON_VERSION}-${package} not available (may be built-in)"
            fi
        done
        
        # Download and install pip for the specific Python version
        if ! python${PYTHON_VERSION} -m pip --version > /dev/null 2>&1; then
            print_status "Installing pip for Python ${PYTHON_VERSION} using get-pip.py..."
            
            # Check network connectivity first
            if check_network_connectivity "https://bootstrap.pypa.io" 10; then
                # Download get-pip.py with timeout and retries
                if curl -sS --connect-timeout 10 --retry 3 https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py; then
                    # Install pip without upgrading system packages
                    python${PYTHON_VERSION} /tmp/get-pip.py --user
                    
                    # Clean up
                    rm -f /tmp/get-pip.py
                else
                    print_error "Failed to download get-pip.py"
                    return 1
                fi
            else
                print_error "Cannot reach bootstrap.pypa.io - check network connectivity"
                return 1
            fi
        fi
    fi
    
    # Create symlinks for easier access
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/local/bin/python3
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/local/bin/python
    
    # Add user pip packages to PATH if they were installed
    if [[ -d "/root/.local/bin" ]]; then
        export PATH="/root/.local/bin:$PATH"
        echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc
        print_status "Added user pip packages to PATH"
    fi
    
    # Ensure pip is available and upgrade it safely
    if python${PYTHON_VERSION} -m pip --version > /dev/null 2>&1; then
        print_status "Using pip with Python ${PYTHON_VERSION}"
        # Upgrade pip in user space to avoid conflicts with system packages
        python${PYTHON_VERSION} -m pip install --user --upgrade pip
        pip_command="python${PYTHON_VERSION} -m pip"
    elif python3 -m pip --version > /dev/null 2>&1; then
        print_status "Using pip with system Python 3"
        # Upgrade pip in user space to avoid conflicts with system packages
        python3 -m pip install --user --upgrade pip
        pip_command="python3 -m pip"
    else
        print_error "Could not find a working pip installation"
        return 1
    fi
    
    # Install common Python packages in user space to avoid system conflicts
    print_status "Installing common Python packages..."
    $pip_command install --user \
        virtualenv \
        pipenv \
        poetry \
        gunicorn \
        supervisor || {
        print_warning "Some packages failed to install, trying without --user flag..."
        # Fallback: try installing without --user but with --break-system-packages for newer pip
        $pip_command install --break-system-packages \
            virtualenv \
            pipenv \
            poetry \
            gunicorn \
            supervisor || {
            print_warning "Package installation failed, will install in virtual environment later"
        }
    }
    
    # Verify installation
    print_status "Python installation verification:"
    
    if python${PYTHON_VERSION} --version; then
        print_status "✓ Python ${PYTHON_VERSION} is working"
    else
        print_error "✗ Python ${PYTHON_VERSION} installation failed"
        return 1
    fi
    
    if $pip_command --version; then
        print_status "✓ pip is working"
    else
        print_error "✗ pip installation failed"
        return 1
    fi
    
    # Test virtual environment creation
    if python${PYTHON_VERSION} -m venv /tmp/test_venv; then
        print_status "✓ Virtual environment creation works"
        rm -rf /tmp/test_venv
    else
        print_warning "✗ Virtual environment creation failed - may need manual intervention"
    fi
    
    print_success "Python ${PYTHON_VERSION} installed and verified successfully"
}

# Function to install Node.js
install_nodejs() {
    print_header "Installing Node.js ${NODE_VERSION}..."
    
    # Install Node.js using NodeSource repository
    print_status "Adding NodeSource repository for Node.js ${NODE_VERSION}..."
    
    if check_network_connectivity "https://deb.nodesource.com" 10; then
        if curl -fsSL --connect-timeout 10 --retry 3 https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash -; then
            print_status "NodeSource repository added successfully"
            apt-get install -y nodejs
        else
            print_warning "Failed to add NodeSource repository, trying alternative method..."
            # Fallback: try installing from Ubuntu repositories
            apt-get install -y nodejs npm || {
                print_error "Failed to install Node.js"
                return 1
            }
        fi
    else
        print_warning "Cannot reach NodeSource repository, installing from Ubuntu packages..."
        apt-get install -y nodejs npm || {
            print_error "Failed to install Node.js"
            return 1
        }
    fi
    
    # Install global packages
    npm install -g \
        pm2 \
        yarn \
        typescript \
        @types/node
    
    print_success "Node.js ${NODE_VERSION} installed successfully"
}

# Function to install Docker
install_docker() {
    if [[ "$INSTALL_DOCKER" != "true" ]]; then
        print_status "Skipping Docker installation"
        return
    fi
    
    print_header "Installing Docker..."
    
    # Remove old versions
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Add Docker's official GPG key
    print_status "Adding Docker GPG key..."
    
    if check_network_connectivity "https://download.docker.com" 10; then
        if curl -fsSL --connect-timeout 10 --retry 3 https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg; then
            print_status "Docker GPG key added successfully"
        else
            print_error "Failed to download Docker GPG key"
            return 1
        fi
    else
        print_error "Cannot reach Docker repository - check network connectivity"
        return 1
    fi
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Install Docker Compose (multiple methods)
    print_status "Installing Docker Compose..."
    
    # Method 1: Check if docker-compose-plugin is already installed (preferred)
    if docker compose version > /dev/null 2>&1; then
        print_success "Docker Compose plugin already available via 'docker compose'"
        # Create a symlink for backward compatibility
        if [[ ! -f /usr/local/bin/docker-compose ]]; then
            cat > /usr/local/bin/docker-compose << 'EOF'
#!/bin/bash
# Docker Compose wrapper script
exec docker compose "$@"
EOF
            chmod +x /usr/local/bin/docker-compose
            print_status "Created docker-compose wrapper script"
        fi
    else
        # Method 2: Try to download standalone Docker Compose
        print_status "Downloading standalone Docker Compose..."
        
        # Try with timeout and retries
        compose_url="https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)"
        
        if curl -L --connect-timeout 10 --retry 3 "$compose_url" -o /usr/local/bin/docker-compose; then
            chmod +x /usr/local/bin/docker-compose
            print_success "Docker Compose standalone installed successfully"
        else
            print_warning "Failed to download Docker Compose from GitHub"
            
            # Method 3: Try alternative installation via pip
            if command -v pip3 > /dev/null 2>&1; then
                print_status "Trying to install Docker Compose via pip..."
                pip3 install docker-compose || {
                    print_warning "Failed to install Docker Compose via pip"
                }
            fi
            
            # Method 4: Install via apt (older version but works)
            print_status "Trying to install Docker Compose via apt..."
            apt-get install -y docker-compose || {
                print_warning "Failed to install Docker Compose via apt"
            }
        fi
    fi
    
    # Verify Docker Compose installation
    if docker compose version > /dev/null 2>&1; then
        print_success "✓ Docker Compose available via 'docker compose'"
        docker_compose_version=$(docker compose version --short 2>/dev/null || echo "unknown")
        print_status "Docker Compose version: $docker_compose_version"
    elif command -v docker-compose > /dev/null 2>&1; then
        print_success "✓ Docker Compose available via 'docker-compose'"
        docker_compose_version=$(docker-compose --version 2>/dev/null || echo "unknown")
        print_status "Docker Compose version: $docker_compose_version"
    else
        print_warning "Docker Compose installation could not be verified"
    fi
    
    # Enable and start Docker
    systemctl enable docker
    systemctl start docker
    
    # Add app user to docker group (will be created later)
    print_success "Docker installed successfully"
}

# Function to install Nginx
install_nginx() {
    if [[ "$INSTALL_NGINX" != "true" ]]; then
        print_status "Skipping Nginx installation"
        return
    fi
    
    print_header "Installing Nginx..."
    
    # Install Nginx
    apt-get install -y nginx
    
    # Enable and start Nginx
    systemctl enable nginx
    systemctl start nginx
    
    # Backup existing nginx configuration
    backup_nginx_config
    
    # Create enhanced log format for IPv6 support
    cat >> /etc/nginx/nginx.conf << 'EOF'

# Enhanced log format for IPv4/IPv6 dual-stack
log_format dual_stack '$remote_addr - $remote_user [$time_local] '
                      '"$request" $status $body_bytes_sent '
                      '"$http_referer" "$http_user_agent" '
                      'rt=$request_time uct="$upstream_connect_time" '
                      'uht="$upstream_header_time" urt="$upstream_response_time" '
                      'client_ip="$http_x_forwarded_for" '
                      'protocol="$server_protocol" scheme="$scheme"';
EOF
    
    # Create basic configuration
    cat > /etc/nginx/sites-available/price-monitor << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # IPv6 and dual-stack support headers
    add_header X-Served-By \$hostname always;
    add_header X-Client-IP \$remote_addr always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # IPv6 support headers
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Original-URI $request_uri;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Support for both IPv4 and IPv6 clients
        proxy_bind $server_addr transparent;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        access_log off;
    }
    
    location /static/ {
        alias /opt/price-monitor/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    
    # Enable the site
    ln -sf /etc/nginx/sites-available/price-monitor /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    if validate_nginx_config; then
        systemctl reload nginx
    else
        print_error "Nginx configuration validation failed"
        return 1
    fi
    
    print_success "Nginx installed and configured successfully"
}

# Function to setup firewall
setup_firewall() {
    if [[ "$SETUP_FIREWALL" != "true" ]]; then
        print_status "Skipping firewall setup"
        return
    fi
    
    print_header "Setting up UFW firewall with IPv4 and IPv6 support..."
    
    # Reset UFW to defaults
    ufw --force reset
    
    # Enable IPv6 support
    sed -i 's/IPV6=no/IPV6=yes/' /etc/default/ufw
    
    # Set default policies for both IPv4 and IPv6
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (be careful not to lock yourself out)
    ufw allow ssh
    ufw allow 22/tcp
    
    # Allow HTTP and HTTPS for both IPv4 and IPv6
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow from any to any port 80 proto tcp
    ufw allow from any to any port 443 proto tcp
    
    # Allow application port (for direct access if needed)
    ufw allow ${APP_PORT}/tcp
    
    # Enable UFW
    ufw --force enable
    
    print_success "Firewall configured successfully"
}

# Function to setup fail2ban
setup_fail2ban() {
    print_header "Configuring Fail2ban..."
    
    # Create custom jail configuration
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

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
    
    print_success "Fail2ban configured successfully"
}

# Function to create application user
create_app_user() {
    print_header "Creating application user: ${APP_USER}..."
    
    # Create user if it doesn't exist
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash -d /home/$APP_USER $APP_USER
        print_success "User $APP_USER created"
    else
        print_status "User $APP_USER already exists"
    fi
    
    # Add user to necessary groups
    usermod -aG sudo $APP_USER
    if [[ "$INSTALL_DOCKER" == "true" ]]; then
        usermod -aG docker $APP_USER
    fi
    
    # Create application directory
    mkdir -p $APP_DIR
    mkdir -p $APP_DIR/{config,logs,data,certs,backups,static}
    
    # Set ownership
    chown -R $APP_USER:$APP_USER $APP_DIR
    chmod -R 755 $APP_DIR
    chmod -R 700 $APP_DIR/certs
    
    print_success "Application user and directories created"
}

# Function to check network connectivity
check_network_connectivity() {
    local test_url="${1:-https://google.com}"
    local timeout="${2:-10}"
    
    print_status "Checking network connectivity to $test_url..."
    
    if curl -s --connect-timeout "$timeout" --max-time "$timeout" "$test_url" > /dev/null 2>&1; then
        print_success "✓ Network connectivity OK"
        return 0
    else
        print_warning "✗ Network connectivity issue to $test_url"
        return 1
    fi
}

# Function to backup nginx configuration
backup_nginx_config() {
    local backup_dir="/etc/nginx/backup"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    print_status "Creating nginx configuration backup..."
    
    # Create backup directory
    mkdir -p "$backup_dir"
    
    # Backup main configuration
    cp /etc/nginx/nginx.conf "$backup_dir/nginx.conf.$timestamp" 2>/dev/null || true
    
    # Backup sites-available
    if [[ -d /etc/nginx/sites-available ]]; then
        cp -r /etc/nginx/sites-available "$backup_dir/sites-available.$timestamp" 2>/dev/null || true
    fi
    
    print_status "Nginx configuration backed up to $backup_dir"
}

# Function to validate nginx configuration
validate_nginx_config() {
    local config_file="${1:-}"
    
    if [[ -n "$config_file" && -f "$config_file" ]]; then
        print_status "Validating nginx configuration: $config_file"
        if nginx -t -c /etc/nginx/nginx.conf; then
            print_success "✓ Nginx configuration is valid"
            return 0
        else
            print_error "✗ Nginx configuration has errors"
            return 1
        fi
    else
        print_status "Validating nginx configuration..."
        if nginx -t; then
            print_success "✓ Nginx configuration is valid"
            return 0
        else
            print_error "✗ Nginx configuration has errors"
            return 1
        fi
    fi
}

# Function to test dual-stack connectivity
test_dual_stack_connectivity() {
    local domain="${1:-google.com}"
    
    print_header "Testing dual-stack connectivity..."
    
    # Test IPv4 connectivity
    if ping -4 -c 1 -W 5 "$domain" > /dev/null 2>&1; then
        print_success "✓ IPv4 connectivity working"
        ipv4_working=true
    else
        print_warning "✗ IPv4 connectivity failed"
        ipv4_working=false
    fi
    
    # Test IPv6 connectivity
    if ping6 -c 1 -W 5 "$domain" > /dev/null 2>&1; then
        print_success "✓ IPv6 connectivity working"
        ipv6_working=true
    else
        print_warning "✗ IPv6 connectivity failed or not available"
        ipv6_working=false
    fi
    
    # Summary
    if [[ "$ipv4_working" == "true" && "$ipv6_working" == "true" ]]; then
        print_success "Dual-stack connectivity confirmed"
        return 0
    elif [[ "$ipv4_working" == "true" ]]; then
        print_status "IPv4-only connectivity available"
        return 0
    elif [[ "$ipv6_working" == "true" ]]; then
        print_status "IPv6-only connectivity available"
        return 0
    else
        print_error "No network connectivity detected"
        return 1
    fi
}

# Function to handle offline installation scenarios
handle_offline_mode() {
    print_header "Offline Mode Detected"
    print_status "The script will attempt to use only local packages and repositories"
    print_warning "Some features may be limited without internet access:"
    print_status "  - Latest Python versions may not be available"
    print_status "  - Docker Compose standalone may not be installed"
    print_status "  - Node.js will use Ubuntu repository version"
    print_status "  - SSL certificates cannot be issued without internet"
    echo ""
}

# Function to configure IPv6 support
configure_ipv6_support() {
    print_header "Configuring IPv6 support..."
    
    # Check if IPv6 is available
    if [[ ! -f /proc/net/if_inet6 ]]; then
        print_warning "IPv6 is not available on this system"
        return 1
    fi
    
    # Enable IPv6 forwarding if needed
    echo 'net.ipv6.conf.all.forwarding=1' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.default.forwarding=1' >> /etc/sysctl.conf
    
    # Disable IPv6 privacy extensions for servers (optional)
    echo 'net.ipv6.conf.all.use_tempaddr=0' >> /etc/sysctl.conf
    echo 'net.ipv6.conf.default.use_tempaddr=0' >> /etc/sysctl.conf
    
    # Apply sysctl settings
    sysctl -p
    
    # Test IPv6 connectivity
    if ping6 -c 1 google.com > /dev/null 2>&1; then
        print_success "IPv6 connectivity test passed"
    else
        print_warning "IPv6 connectivity test failed - check network configuration"
    fi
    
    # Show IPv6 addresses
    print_status "Current IPv6 addresses:"
    ip -6 addr show | grep inet6 | grep -v "::1/128" | grep -v "fe80::" | head -5
    
    print_success "IPv6 support configured"
}

# Function to check snap connectivity
check_snap_connectivity() {
    print_status "Checking snap store connectivity..."
    
    if timeout 10 snap find hello-world > /dev/null 2>&1; then
        print_success "✓ Snap store is accessible"
        return 0
    else
        print_warning "✗ Snap store is not accessible"
        return 1
    fi
}

# Function to install and setup certbot
install_certbot() {
    print_header "Installing Certbot (Let's Encrypt client)..."
    
    # Multiple installation methods for certbot
    local certbot_installed=false
    
    # Method 1: Try snap installation (recommended but requires internet)
    if [[ "$OFFLINE_MODE" != "true" ]] && check_snap_connectivity; then
        print_status "Attempting certbot installation via snap..."
        
        # Install snapd if not already installed
        apt-get install -y snapd
        systemctl enable snapd
        systemctl start snapd
        
        # Wait for snapd to be ready
        sleep 5
        
        # Try snap installation with timeout and better error handling
        print_status "Installing snap core..."
        if timeout 60 snap install core 2>/dev/null; then
            print_status "✓ Snap core installed"
        else
            print_warning "Snap core installation failed or timed out"
        fi
        
        print_status "Refreshing snap core..."
        if timeout 60 snap refresh core 2>/dev/null; then
            print_status "✓ Snap core refreshed"
        else
            print_status "Snap core refresh failed (may be already up to date)"
        fi
        
        print_status "Installing certbot via snap..."
        if timeout 120 snap install --classic certbot 2>/dev/null; then
            print_success "✓ Certbot installed via snap"
            
            # Create symlink for certbot command
            ln -sf /snap/bin/certbot /usr/bin/certbot
            
            # Install additional certbot plugins (optional)
            timeout 30 snap install certbot-dns-cloudflare || print_status "Cloudflare plugin not installed"
            timeout 30 snap install certbot-dns-route53 || print_status "Route53 plugin not installed"
            
            certbot_installed=true
        else
            print_warning "Snap installation failed or timed out"
        fi
    else
        print_status "Skipping snap installation (offline mode or connectivity issues)"
    fi
    
    # Method 2: Install via apt packages (fallback)
    if [[ "$certbot_installed" != "true" ]]; then
        print_status "Installing certbot via apt packages..."
        
        if apt-get install -y python3-certbot-nginx certbot; then
            print_success "✓ Certbot installed via apt"
            certbot_installed=true
        else
            print_error "Failed to install certbot via apt"
        fi
    fi
    
    # Method 3: Install via pip (last resort)
    if [[ "$certbot_installed" != "true" ]]; then
        print_status "Installing certbot via pip (last resort)..."
        
        if python3 -m pip install certbot certbot-nginx; then
            print_success "✓ Certbot installed via pip"
            certbot_installed=true
        else
            print_error "Failed to install certbot via pip"
        fi
    fi
    
    # Verify installation
    if [[ "$certbot_installed" != "true" ]]; then
        print_error "All certbot installation methods failed"
        return 1
    fi
    
    # Create certbot configuration directory
    mkdir -p /etc/letsencrypt
    mkdir -p /var/lib/letsencrypt
    mkdir -p /var/log/letsencrypt
    
    # Set proper permissions
    chmod 755 /etc/letsencrypt
    chmod 755 /var/lib/letsencrypt
    chmod 755 /var/log/letsencrypt
    
    # Verify certbot installation and show version
    print_status "Verifying certbot installation..."
    
    if command -v certbot > /dev/null 2>&1; then
        certbot_version=$(certbot --version 2>&1 | head -1)
        print_success "✓ Certbot is working: $certbot_version"
        
        # Test certbot functionality
        if certbot --help > /dev/null 2>&1; then
            print_success "✓ Certbot functionality verified"
        else
            print_warning "Certbot installed but may have issues"
        fi
    else
        print_error "Certbot command not found after installation"
        return 1
    fi
    
    # Show installation method used
    if [[ -f /snap/bin/certbot ]]; then
        print_status "Certbot installation method: Snap (recommended)"
    elif command -v certbot > /dev/null && dpkg -l | grep -q certbot; then
        print_status "Certbot installation method: APT package"
    elif python3 -m pip show certbot > /dev/null 2>&1; then
        print_status "Certbot installation method: Python pip"
    else
        print_status "Certbot installation method: Unknown"
    fi
    
    print_success "Certbot installed and verified successfully"
}

# Function to issue SSL certificates for users
issue_ssl_certificate() {
    local domain="$1"
    local email="$2"
    local method="${3:-nginx}"  # nginx, webroot, standalone, or dns
    
    if [[ -z "$domain" ]] || [[ -z "$email" ]]; then
        print_error "Domain name and email address are required for SSL certificate issuance"
        print_status "Usage: issue_ssl_certificate <domain> <email> [method]"
        print_status "Methods: nginx (default), webroot, standalone, dns"
        return 1
    fi
    
    print_header "Issuing SSL certificate for $domain using $method method..."
    
    # Validate email format
    if [[ ! "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        print_error "Invalid email format: $email"
        return 1
    fi
    
    # Check if certificate already exists
    if [[ -d "/etc/letsencrypt/live/$domain" ]]; then
        print_warning "Certificate for $domain already exists"
        read -p "Do you want to renew/replace it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Certificate issuance cancelled"
            return 0
        fi
    fi
    
    # Pre-flight checks
    print_status "Performing pre-flight checks..."
    
    # Check DNS resolution (IPv4 and IPv6)
    local ipv4_check=false
    local ipv6_check=false
    
    if nslookup "$domain" > /dev/null 2>&1; then
        ipv4_check=true
        print_status "IPv4 (A record) resolution: ✓"
    else
        print_warning "IPv4 (A record) resolution: ✗"
    fi
    
    if nslookup -type=AAAA "$domain" > /dev/null 2>&1; then
        ipv6_check=true
        print_status "IPv6 (AAAA record) resolution: ✓"
    else
        print_warning "IPv6 (AAAA record) resolution: ✗"
    fi
    
    if [[ "$ipv4_check" == "false" && "$ipv6_check" == "false" ]]; then
        print_error "DNS resolution failed for $domain (both IPv4 and IPv6)"
        print_status "Please ensure the domain has A and/or AAAA records pointing to this server"
        return 1
    elif [[ "$ipv6_check" == "true" && "$ipv4_check" == "false" ]]; then
        print_status "IPv6-only domain detected - this is supported!"
    fi
    
    # Check if ports are accessible (for non-DNS methods)
    if [[ "$method" != "dns" ]]; then
        # Test IPv4 connectivity
        if nc -4 -z -w5 "$domain" 80 2>/dev/null; then
            print_status "Port 80 accessible via IPv4: ✓"
        else
            print_warning "Port 80 not accessible via IPv4: ✗"
        fi
        
        # Test IPv6 connectivity
        if nc -6 -z -w5 "$domain" 80 2>/dev/null; then
            print_status "Port 80 accessible via IPv6: ✓"
        else
            print_warning "Port 80 not accessible via IPv6: ✗"
        fi
    fi
    
    # Issue certificate based on method
    case "$method" in
        "nginx")
            issue_certificate_nginx "$domain" "$email"
            ;;
        "webroot")
            issue_certificate_webroot "$domain" "$email"
            ;;
        "standalone")
            issue_certificate_standalone "$domain" "$email"
            ;;
        "dns")
            issue_certificate_dns "$domain" "$email"
            ;;
        *)
            print_error "Unknown method: $method"
            print_status "Available methods: nginx, webroot, standalone, dns"
            return 1
            ;;
    esac
}

# Function to issue certificate using nginx plugin
issue_certificate_nginx() {
    local domain="$1"
    local email="$2"
    
    print_status "Using nginx plugin to issue certificate..."
    
    # Ensure nginx is running
    if ! systemctl is-active --quiet nginx; then
        print_status "Starting nginx..."
        systemctl start nginx
    fi
    
    # Test nginx configuration
    if ! nginx -t; then
        print_error "Nginx configuration test failed"
        return 1
    fi
    
    # Issue certificate
    if certbot --nginx -d "$domain" --email "$email" --agree-tos --non-interactive --redirect; then
        print_success "SSL certificate issued successfully for $domain"
        return 0
    else
        print_error "Failed to issue certificate using nginx plugin"
        return 1
    fi
}

# Function to issue certificate using webroot method
issue_certificate_webroot() {
    local domain="$1"
    local email="$2"
    local webroot_path="/var/www/html"
    
    print_status "Using webroot method to issue certificate..."
    
    # Create webroot directory
    mkdir -p "$webroot_path/.well-known/acme-challenge"
    chown -R www-data:www-data "$webroot_path"
    
    # Ensure nginx is configured for webroot
    setup_nginx_webroot_config "$domain"
    
    # Issue certificate
    if certbot certonly --webroot -w "$webroot_path" -d "$domain" --email "$email" --agree-tos --non-interactive; then
        print_success "SSL certificate issued successfully for $domain"
        
        # Update nginx configuration with SSL
        update_nginx_ssl_config "$domain"
        return 0
    else
        print_error "Failed to issue certificate using webroot method"
        return 1
    fi
}

# Function to issue certificate using standalone method
issue_certificate_standalone() {
    local domain="$1"
    local email="$2"
    
    print_status "Using standalone method to issue certificate..."
    
    # Stop nginx temporarily
    if systemctl is-active --quiet nginx; then
        print_status "Stopping nginx temporarily..."
        systemctl stop nginx
        nginx_was_running=true
    fi
    
    # Issue certificate
    if certbot certonly --standalone -d "$domain" --email "$email" --agree-tos --non-interactive; then
        print_success "SSL certificate issued successfully for $domain"
        
        # Restart nginx if it was running
        if [[ "$nginx_was_running" == "true" ]]; then
            print_status "Restarting nginx..."
            systemctl start nginx
        fi
        
        # Update nginx configuration with SSL
        update_nginx_ssl_config "$domain"
        return 0
    else
        print_error "Failed to issue certificate using standalone method"
        
        # Restart nginx if it was running
        if [[ "$nginx_was_running" == "true" ]]; then
            systemctl start nginx
        fi
        return 1
    fi
}

# Function to issue certificate using DNS challenge
issue_certificate_dns() {
    local domain="$1"
    local email="$2"
    
    print_status "Using DNS challenge method to issue certificate..."
    print_status "This method requires manual DNS record creation or DNS provider API access"
    
    # Issue certificate with manual DNS challenge
    if certbot certonly --manual --preferred-challenges dns -d "$domain" --email "$email" --agree-tos; then
        print_success "SSL certificate issued successfully for $domain"
        
        # Update nginx configuration with SSL
        update_nginx_ssl_config "$domain"
        return 0
    else
        print_error "Failed to issue certificate using DNS method"
        return 1
    fi
}

# Function to setup nginx webroot configuration
setup_nginx_webroot_config() {
    local domain="$1"
    
    cat > "/etc/nginx/sites-available/$domain-temp" << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $domain;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files \$uri =404;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF
    
    # Enable temporary configuration
    ln -sf "/etc/nginx/sites-available/$domain-temp" "/etc/nginx/sites-enabled/$domain-temp"
    
    # Test and reload nginx
    if nginx -t; then
        systemctl reload nginx
    else
        print_error "Nginx configuration test failed"
        return 1
    fi
}

# Function to create SSL certificate management tools
create_ssl_management_tools() {
    print_header "Creating SSL certificate management tools..."
    
    # Create certificate issuance script
    cat > /usr/local/bin/issue-ssl-cert << 'EOF'
#!/bin/bash
# SSL Certificate Issuance Tool
# Usage: issue-ssl-cert <domain> <email> [method]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Parse arguments
DOMAIN="$1"
EMAIL="$2"
METHOD="${3:-nginx}"

if [[ -z "$DOMAIN" ]] || [[ -z "$EMAIL" ]]; then
    echo "Usage: $0 <domain> <email> [method]"
    echo "Methods: nginx (default), webroot, standalone, dns"
    exit 1
fi

# Source the main setup script functions
source /usr/local/bin/ssl-functions.sh

# Issue certificate
issue_ssl_certificate "$DOMAIN" "$EMAIL" "$METHOD"
EOF
    
    # Create SSL functions library
    cat > /usr/local/bin/ssl-functions.sh << 'EOF'
#!/bin/bash
# SSL Functions Library

# Function to list all certificates
list_certificates() {
    echo "=== SSL Certificates ==="
    certbot certificates
}

# Function to check certificate expiration
check_certificate_expiration() {
    local domain="$1"
    
    if [[ -z "$domain" ]]; then
        echo "Usage: check_certificate_expiration <domain>"
        return 1
    fi
    
    local cert_path="/etc/letsencrypt/live/$domain/fullchain.pem"
    
    if [[ -f "$cert_path" ]]; then
        echo "Certificate expiration for $domain:"
        openssl x509 -in "$cert_path" -noout -enddate
        
        # Calculate days remaining
        local exp_date=$(openssl x509 -in "$cert_path" -noout -enddate | cut -d= -f2)
        local exp_epoch=$(date -d "$exp_date" +%s)
        local now_epoch=$(date +%s)
        local days_remaining=$(( (exp_epoch - now_epoch) / 86400 ))
        
        echo "Days remaining: $days_remaining"
        
        if [[ $days_remaining -lt 30 ]]; then
            echo "WARNING: Certificate expires in less than 30 days!"
        fi
    else
        echo "Certificate not found for $domain"
        return 1
    fi
}

# Function to revoke certificate
revoke_certificate() {
    local domain="$1"
    
    if [[ -z "$domain" ]]; then
        echo "Usage: revoke_certificate <domain>"
        return 1
    fi
    
    echo "Revoking certificate for $domain..."
    
    if certbot revoke --cert-path "/etc/letsencrypt/live/$domain/fullchain.pem"; then
        echo "Certificate revoked successfully"
        
        # Clean up nginx configuration
        rm -f "/etc/nginx/sites-enabled/$domain"*
        rm -f "/etc/nginx/sites-available/$domain"*
        
        # Reload nginx
        nginx -t && systemctl reload nginx
    else
        echo "Failed to revoke certificate"
        return 1
    fi
}

# Function to test certificate
test_certificate() {
    local domain="$1"
    
    if [[ -z "$domain" ]]; then
        echo "Usage: test_certificate <domain>"
        return 1
    fi
    
    echo "Testing SSL certificate for $domain..."
    
    # Test with openssl
    echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -text | grep -E "(Subject|Issuer|Not Before|Not After)"
    
    # Test with curl
    if curl -I -s "https://$domain" > /dev/null; then
        echo "HTTPS connection successful"
    else
        echo "HTTPS connection failed"
    fi
}
EOF
    
    # Create certificate monitoring script
    cat > /usr/local/bin/monitor-ssl-certs << 'EOF'
#!/bin/bash
# SSL Certificate Monitoring Script

LOG_FILE="/var/log/ssl-monitor.log"
ALERT_DAYS=30

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_message "Starting SSL certificate monitoring..."

# Check all certificates
for cert_dir in /etc/letsencrypt/live/*/; do
    if [[ -d "$cert_dir" ]]; then
        domain=$(basename "$cert_dir")
        cert_file="$cert_dir/fullchain.pem"
        
        if [[ -f "$cert_file" ]]; then
            # Get expiration date
            exp_date=$(openssl x509 -in "$cert_file" -noout -enddate | cut -d= -f2)
            exp_epoch=$(date -d "$exp_date" +%s)
            now_epoch=$(date +%s)
            days_remaining=$(( (exp_epoch - now_epoch) / 86400 ))
            
            log_message "Certificate for $domain expires in $days_remaining days"
            
            if [[ $days_remaining -lt $ALERT_DAYS ]]; then
                log_message "ALERT: Certificate for $domain expires in $days_remaining days!"
                
                # Send alert (customize as needed)
                echo "SSL Certificate Alert: $domain expires in $days_remaining days" | logger -t ssl-monitor
            fi
        fi
    fi
done

log_message "SSL certificate monitoring completed"
EOF
    
    # Make scripts executable
    chmod +x /usr/local/bin/issue-ssl-cert
    chmod +x /usr/local/bin/ssl-functions.sh
    chmod +x /usr/local/bin/monitor-ssl-certs
    
    # Create SSL management menu script
    cat > /usr/local/bin/ssl-manager << 'EOF'
#!/bin/bash
# Interactive SSL Certificate Manager

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

print_header() { echo -e "${PURPLE}=== $1 ===${NC}"; }
print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Source SSL functions
source /usr/local/bin/ssl-functions.sh

# Main menu
while true; do
    clear
    print_header "SSL Certificate Manager"
    echo ""
    echo "1. Issue new SSL certificate"
    echo "2. List all certificates"
    echo "3. Check certificate expiration"
    echo "4. Renew certificates"
    echo "5. Test certificate"
    echo "6. Revoke certificate"
    echo "7. Monitor certificate status"
    echo "8. Exit"
    echo ""
    read -p "Select an option (1-8): " choice
    
    case $choice in
        1)
            echo ""
            read -p "Enter domain name: " domain
            read -p "Enter email address: " email
            echo "Select method:"
            echo "1. Nginx (recommended)"
            echo "2. Webroot"
            echo "3. Standalone"
            echo "4. DNS"
            read -p "Select method (1-4): " method_choice
            
            case $method_choice in
                1) method="nginx" ;;
                2) method="webroot" ;;
                3) method="standalone" ;;
                4) method="dns" ;;
                *) method="nginx" ;;
            esac
            
            issue_ssl_certificate "$domain" "$email" "$method"
            read -p "Press Enter to continue..."
            ;;
        2)
            echo ""
            list_certificates
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            read -p "Enter domain name: " domain
            check_certificate_expiration "$domain"
            read -p "Press Enter to continue..."
            ;;
        4)
            echo ""
            print_status "Renewing all certificates..."
            certbot renew
            systemctl reload nginx
            print_success "Certificate renewal completed"
            read -p "Press Enter to continue..."
            ;;
        5)
            echo ""
            read -p "Enter domain name: " domain
            test_certificate "$domain"
            read -p "Press Enter to continue..."
            ;;
        6)
            echo ""
            read -p "Enter domain name to revoke: " domain
            read -p "Are you sure you want to revoke the certificate for $domain? (y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                revoke_certificate "$domain"
            else
                print_status "Certificate revocation cancelled"
            fi
            read -p "Press Enter to continue..."
            ;;
        7)
            echo ""
            /usr/local/bin/monitor-ssl-certs
            read -p "Press Enter to continue..."
            ;;
        8)
            print_status "Exiting SSL Certificate Manager"
            exit 0
            ;;
        *)
            print_error "Invalid option. Please select 1-8."
            sleep 2
            ;;
    esac
done
EOF
    
    chmod +x /usr/local/bin/ssl-manager
    
    # Add SSL monitoring to cron
    cat > /etc/cron.d/ssl-monitoring << 'EOF'
# SSL Certificate Monitoring - check daily at 6 AM
0 6 * * * root /usr/local/bin/monitor-ssl-certs
EOF
    
    print_success "SSL certificate management tools created successfully"
    print_status "Available commands:"
    print_status "  - ssl-manager: Interactive SSL management menu"
    print_status "  - issue-ssl-cert <domain> <email> [method]: Issue new certificate"
    print_status "  - monitor-ssl-certs: Check certificate expiration status"
}

# Function to install SSL certificates with Let's Encrypt
setup_ssl() {
    if [[ "$SETUP_SSL" != "true" ]] || [[ -z "$DOMAIN_NAME" ]] || [[ -z "$EMAIL_ADDRESS" ]]; then
        print_status "Skipping SSL setup (requires SETUP_SSL=true, DOMAIN_NAME, and EMAIL_ADDRESS)"
        return
    fi
    
    print_header "Setting up SSL with Let's Encrypt..."
    
    # Install certbot if not already done
    install_certbot
    
    # Verify Nginx is running and configured
    if ! systemctl is-active --quiet nginx; then
        print_error "Nginx is not running. Starting Nginx..."
        systemctl start nginx
    fi
    
    # Test Nginx configuration
    if ! nginx -t; then
        print_error "Nginx configuration test failed. Please check configuration."
        return 1
    fi
    
    # Create a temporary basic Nginx configuration for domain verification
    cat > /etc/nginx/sites-available/temp-ssl-setup << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF
    
    # Enable temporary configuration
    ln -sf /etc/nginx/sites-available/temp-ssl-setup /etc/nginx/sites-enabled/temp-ssl-setup
    systemctl reload nginx
    
    # Wait for DNS propagation check (IPv4 and IPv6)
    print_status "Checking DNS resolution for $DOMAIN_NAME..."
    local dns_check_attempts=0
    local max_dns_attempts=30
    local ipv4_resolved=false
    local ipv6_resolved=false
    
    while [ $dns_check_attempts -lt $max_dns_attempts ]; do
        # Check IPv4 (A record)
        if nslookup $DOMAIN_NAME > /dev/null 2>&1; then
            ipv4_resolved=true
        fi
        
        # Check IPv6 (AAAA record)
        if nslookup -type=AAAA $DOMAIN_NAME > /dev/null 2>&1; then
            ipv6_resolved=true
        fi
        
        if [[ "$ipv4_resolved" == "true" || "$ipv6_resolved" == "true" ]]; then
            if [[ "$ipv4_resolved" == "true" && "$ipv6_resolved" == "true" ]]; then
                print_success "DNS resolution successful for $DOMAIN_NAME (IPv4 and IPv6)"
            elif [[ "$ipv4_resolved" == "true" ]]; then
                print_success "DNS resolution successful for $DOMAIN_NAME (IPv4 only)"
            else
                print_success "DNS resolution successful for $DOMAIN_NAME (IPv6 only)"
            fi
            break
        else
            print_status "Waiting for DNS propagation... (attempt $((dns_check_attempts + 1))/$max_dns_attempts)"
            sleep 10
            dns_check_attempts=$((dns_check_attempts + 1))
        fi
    done
    
    if [ $dns_check_attempts -eq $max_dns_attempts ]; then
        print_warning "DNS resolution check timed out. Proceeding anyway..."
    fi
    
    # Issue SSL certificate using the specified method
    print_status "Issuing SSL certificate for $DOMAIN_NAME using $SSL_METHOD method..."
    
    if issue_ssl_certificate "$DOMAIN_NAME" "$EMAIL_ADDRESS" "$SSL_METHOD"; then
        ssl_success=true
    else
        print_error "SSL certificate issuance failed"
        ssl_success=false
    fi
    
    # Remove temporary configuration
    rm -f /etc/nginx/sites-enabled/temp-ssl-setup
    rm -f /etc/nginx/sites-available/temp-ssl-setup
    
    if [ "$ssl_success" = true ]; then
        # Setup auto-renewal
        setup_ssl_renewal
        
        # Test certificate
        test_ssl_certificate
        
        # Create SSL management scripts
        create_ssl_management_scripts
        
        print_success "SSL setup completed successfully for $DOMAIN_NAME"
    else
        print_error "SSL setup failed. Please check domain DNS settings and try again."
        return 1
    fi
}

# Function to update Nginx SSL configuration manually
update_nginx_ssl_config() {
    print_status "Updating Nginx SSL configuration..."
    
    cat > /etc/nginx/sites-available/price-monitor << EOF
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;
    
    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # Application proxy
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Enhanced IPv6 support headers
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Original-URI \$request_uri;
        proxy_set_header X-Client-IP \$remote_addr;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Support for both IPv4 and IPv6 clients
        proxy_bind \$server_addr transparent;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:$APP_PORT/health;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        access_log off;
    }
    
    # Static files
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Security headers for static files
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
    }
    
    # Favicon
    location = /favicon.ico {
        alias $APP_DIR/static/favicon.ico;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
    
    # Robots.txt
    location = /robots.txt {
        alias $APP_DIR/static/robots.txt;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
EOF
    
    # Test and reload Nginx configuration
    if nginx -t; then
        systemctl reload nginx
        print_success "Nginx SSL configuration updated successfully"
    else
        print_error "Nginx SSL configuration test failed"
        return 1
    fi
}

# Function to setup SSL certificate auto-renewal
setup_ssl_renewal() {
    print_status "Setting up SSL certificate auto-renewal..."
    
    # Enable and start certbot timer
    systemctl enable certbot.timer
    systemctl start certbot.timer
    
    # Create custom renewal script with Nginx reload
    cat > /usr/local/bin/certbot-renewal.sh << 'EOF'
#!/bin/bash
# Custom certbot renewal script with Nginx reload

LOG_FILE="/var/log/certbot-renewal.log"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log_message "Starting certificate renewal check..."

# Run certbot renewal
if /usr/bin/certbot renew --quiet --no-self-upgrade; then
    log_message "Certificate renewal check completed successfully"
    
    # Test Nginx configuration
    if nginx -t; then
        # Reload Nginx to use new certificates
        systemctl reload nginx
        log_message "Nginx reloaded successfully with renewed certificates"
    else
        log_message "ERROR: Nginx configuration test failed after renewal"
    fi
else
    log_message "ERROR: Certificate renewal failed"
fi

log_message "Certificate renewal process completed"
EOF
    
    chmod +x /usr/local/bin/certbot-renewal.sh
    
    # Create systemd service for renewal
    cat > /etc/systemd/system/certbot-renewal.service << 'EOF'
[Unit]
Description=Certbot Renewal with Nginx Reload
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/certbot-renewal.sh
EOF
    
    # Create systemd timer for renewal (twice daily)
    cat > /etc/systemd/system/certbot-renewal.timer << 'EOF'
[Unit]
Description=Run certbot renewal twice daily
Requires=certbot-renewal.service

[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # Enable and start the custom renewal timer
    systemctl daemon-reload
    systemctl enable certbot-renewal.timer
    systemctl start certbot-renewal.timer
    
    # Add cron job as backup
    cat > /etc/cron.d/certbot-renewal << 'EOF'
# Certbot renewal backup cron job
0 */12 * * * root /usr/local/bin/certbot-renewal.sh
EOF
    
    print_success "SSL auto-renewal configured successfully"
}

# Function to test SSL certificate
test_ssl_certificate() {
    print_status "Testing SSL certificate..."
    
    # Wait for Nginx to reload
    sleep 5
    
    # Test SSL certificate with openssl
    if echo | openssl s_client -servername $DOMAIN_NAME -connect $DOMAIN_NAME:443 2>/dev/null | openssl x509 -noout -dates; then
        print_success "SSL certificate test passed"
        
        # Test HTTPS connection
        if curl -I -s https://$DOMAIN_NAME/health > /dev/null 2>&1; then
            print_success "HTTPS connection test passed"
        else
            print_warning "HTTPS connection test failed - application may not be running yet"
        fi
    else
        print_warning "SSL certificate test failed - certificate may still be propagating"
    fi
}

# Function to create SSL management scripts
create_ssl_management_scripts() {
    print_status "Creating SSL management scripts..."
    
    # Create SSL status check script
    cat > $APP_DIR/ssl-status.sh << EOF
#!/bin/bash
# SSL Certificate Status Check Script

DOMAIN="$DOMAIN_NAME"
CERT_PATH="/etc/letsencrypt/live/\$DOMAIN"

echo "=== SSL Certificate Status for \$DOMAIN ==="
echo ""

# Check if certificate exists
if [ -f "\$CERT_PATH/fullchain.pem" ]; then
    echo "Certificate found: \$CERT_PATH/fullchain.pem"
    
    # Show certificate details
    echo ""
    echo "Certificate Details:"
    openssl x509 -in "\$CERT_PATH/fullchain.pem" -noout -subject -issuer -dates
    
    # Check expiration
    echo ""
    echo "Days until expiration:"
    openssl x509 -in "\$CERT_PATH/fullchain.pem" -noout -checkend 0 && echo "Certificate is valid" || echo "Certificate has expired"
    
    # Show days remaining
    exp_date=\$(openssl x509 -in "\$CERT_PATH/fullchain.pem" -noout -enddate | cut -d= -f2)
    exp_epoch=\$(date -d "\$exp_date" +%s)
    now_epoch=\$(date +%s)
    days_remaining=\$(( (exp_epoch - now_epoch) / 86400 ))
    echo "Days remaining: \$days_remaining"
    
else
    echo "Certificate not found at \$CERT_PATH"
fi

echo ""
echo "=== Certbot Status ==="
certbot certificates

echo ""
echo "=== Renewal Timer Status ==="
systemctl status certbot-renewal.timer --no-pager

echo ""
echo "=== Recent Renewal Logs ==="
tail -n 20 /var/log/certbot-renewal.log 2>/dev/null || echo "No renewal logs found"
EOF
    
    # Create SSL renewal script
    cat > $APP_DIR/ssl-renew.sh << EOF
#!/bin/bash
# Manual SSL Certificate Renewal Script

DOMAIN="$DOMAIN_NAME"

echo "=== Manual SSL Certificate Renewal for \$DOMAIN ==="
echo ""

# Test renewal (dry run)
echo "Testing renewal (dry run)..."
if certbot renew --dry-run; then
    echo "Dry run successful!"
    echo ""
    
    # Ask for confirmation
    read -p "Proceed with actual renewal? (y/N): " -n 1 -r
    echo
    
    if [[ \$REPLY =~ ^[Yy]\$ ]]; then
        echo "Performing actual renewal..."
        
        if certbot renew --force-renewal; then
            echo "Certificate renewed successfully!"
            
            # Test and reload Nginx
            if nginx -t; then
                systemctl reload nginx
                echo "Nginx reloaded successfully"
            else
                echo "ERROR: Nginx configuration test failed"
            fi
        else
            echo "ERROR: Certificate renewal failed"
        fi
    else
        echo "Renewal cancelled"
    fi
else
    echo "ERROR: Dry run failed - renewal would not succeed"
fi
EOF
    
    # Create SSL troubleshooting script
    cat > $APP_DIR/ssl-troubleshoot.sh << 'EOF'
#!/bin/bash
# SSL Troubleshooting Script

DOMAIN="$DOMAIN_NAME"

echo "=== SSL Troubleshooting for $DOMAIN ==="
echo ""

echo "1. DNS Resolution Check:"
echo "IPv4 (A record):"
nslookup $DOMAIN || echo "IPv4 DNS resolution failed"
echo "IPv6 (AAAA record):"
nslookup -type=AAAA $DOMAIN || echo "IPv6 DNS resolution failed"
echo ""

echo "2. Port 80 Accessibility:"
echo "IPv4:"
curl -4 -I -m 10 http://$DOMAIN/ 2>/dev/null && echo "Port 80 accessible via IPv4" || echo "Port 80 not accessible via IPv4"
echo "IPv6:"
curl -6 -I -m 10 http://$DOMAIN/ 2>/dev/null && echo "Port 80 accessible via IPv6" || echo "Port 80 not accessible via IPv6"
echo ""

echo "3. Port 443 Accessibility:"
echo "IPv4:"
curl -4 -I -m 10 https://$DOMAIN/ 2>/dev/null && echo "Port 443 accessible via IPv4" || echo "Port 443 not accessible via IPv4"
echo "IPv6:"
curl -6 -I -m 10 https://$DOMAIN/ 2>/dev/null && echo "Port 443 accessible via IPv6" || echo "Port 443 not accessible via IPv6"
echo ""

echo "4. Certificate Chain Test:"
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -text | grep -E "(Subject|Issuer|Not Before|Not After)"
echo ""

echo "5. Nginx Configuration Test:"
nginx -t && echo "Nginx config OK" || echo "Nginx config has errors"
echo ""

echo "6. Nginx Status:"
systemctl status nginx --no-pager
echo ""

echo "7. Certbot Status:"
certbot certificates
echo ""

echo "8. Let's Encrypt Rate Limits Check:"
echo "Check rate limits at: https://crt.sh/?q=$DOMAIN"
echo ""

echo "9. Firewall Status:"
ufw status
echo ""

echo "10. Recent Nginx Error Logs:"
tail -n 10 /var/log/nginx/error.log 2>/dev/null || echo "No Nginx error logs found"
EOF
    
    # Make scripts executable and set ownership
    chmod +x $APP_DIR/ssl-*.sh
    chown $APP_USER:$APP_USER $APP_DIR/ssl-*.sh
    
    print_success "SSL management scripts created in $APP_DIR/"
}

# Function to setup application environment
setup_app_environment() {
    print_header "Setting up application environment..."
    
    # Create Python virtual environment (using Python 3.13 by default)
    print_status "Creating virtual environment with Python $(python3 --version)..."
    sudo -u $APP_USER python3 -m venv $APP_DIR/venv
    
    # Verify virtual environment creation
    if [[ -f "$APP_DIR/venv/bin/python" ]]; then
        print_status "✓ Virtual environment created successfully"
        venv_python_version=$(sudo -u $APP_USER $APP_DIR/venv/bin/python --version)
        print_status "Virtual environment Python version: $venv_python_version"
    else
        print_error "✗ Virtual environment creation failed"
        return 1
    fi
    
    # Create requirements.txt if it doesn't exist (Python 3.13 compatible versions)
    if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
        cat > $APP_DIR/requirements.txt << 'EOF'
# Core web framework
flask>=3.0.0
gunicorn>=21.2.0

# HTTP and web scraping
requests>=2.31.0
beautifulsoup4>=4.12.2
lxml>=4.9.3

# Database
sqlalchemy>=2.0.23
psycopg2-binary>=2.9.9

# Configuration and environment
python-dotenv>=1.0.0

# Task scheduling
schedule>=1.2.0

# Security and cryptography
cryptography>=41.0.8

# Data validation
pydantic>=2.5.0

# Template engine (Flask dependency)
jinja2>=3.1.2
markupsafe>=2.1.3

# CLI and utilities
click>=8.1.7
itsdangerous>=2.1.2
werkzeug>=3.0.1

# HTTP client dependencies
urllib3>=2.1.0
certifi>=2023.11.17
charset-normalizer>=3.3.2
idna>=3.6

# Additional Python 3.13 compatibility packages
setuptools>=69.0.0
wheel>=0.42.0
EOF
        chown $APP_USER:$APP_USER $APP_DIR/requirements.txt
    fi
    
    # Install Python dependencies in virtual environment
    print_status "Installing Python dependencies in virtual environment..."
    
    # Upgrade pip in virtual environment (safe since it's isolated)
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
    
    # Install wheel and setuptools first for better compatibility
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade wheel setuptools
    
    # Install application dependencies
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
    
    print_success "Application environment setup completed"
}

# Function to create systemd service
create_systemd_service() {
    print_header "Creating systemd service..."
    
    cat > /etc/systemd/system/price-monitor.service << EOF
[Unit]
Description=Price Monitor Application
After=network.target postgresql.service
Wants=network.target

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
Environment=PYTHONPATH=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python -m src.main
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable price-monitor
    
    print_success "Systemd service created"
}

# Function to setup log rotation
setup_log_rotation() {
    print_header "Setting up log rotation..."
    
    cat > /etc/logrotate.d/price-monitor << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload price-monitor
    endscript
}

/var/log/nginx/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data adm
    postrotate
        systemctl reload nginx
    endscript
}
EOF
    
    print_success "Log rotation configured"
}

# Function to setup monitoring
setup_monitoring() {
    print_header "Setting up basic monitoring..."
    
    # Create health check script
    cat > $APP_DIR/health-check.sh << 'EOF'
#!/bin/bash
# Health check script for Price Monitor application

APP_PORT=${APP_PORT:-8080}
LOG_FILE="/var/log/price-monitor-health.log"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check if application is responding on both IPv4 and IPv6
ipv4_check=false
ipv6_check=false

# Test IPv4 connectivity
if curl -4 -f -s http://localhost:$APP_PORT/health > /dev/null 2>&1; then
    log_message "IPv4 health check PASSED"
    ipv4_check=true
else
    log_message "IPv4 health check FAILED"
fi

# Test IPv6 connectivity (if available)
if curl -6 -f -s http://localhost:$APP_PORT/health > /dev/null 2>&1; then
    log_message "IPv6 health check PASSED"
    ipv6_check=true
else
    log_message "IPv6 health check FAILED or not available"
fi

# Overall health check result
if [[ "$ipv4_check" == "true" || "$ipv6_check" == "true" ]]; then
    log_message "Overall health check PASSED (IPv4: $ipv4_check, IPv6: $ipv6_check)"
    exit 0
else
    log_message "Overall health check FAILED - Application not responding on any protocol"
    # Try to restart the service
    systemctl restart price-monitor
    log_message "Attempted to restart price-monitor service"
    exit 1
fi
EOF
    
    chmod +x $APP_DIR/health-check.sh
    chown $APP_USER:$APP_USER $APP_DIR/health-check.sh
    
    # Add cron job for health monitoring
    cat > /etc/cron.d/price-monitor-health << EOF
# Health check every 5 minutes
*/5 * * * * $APP_USER $APP_DIR/health-check.sh
EOF
    
    # Create system monitoring script
    cat > /usr/local/bin/system-monitor.sh << 'EOF'
#!/bin/bash
# System monitoring script

LOG_FILE="/var/log/system-monitor.log"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check disk usage
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    log_message "WARNING: Disk usage is ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEMORY_USAGE" -gt 80 ]; then
    log_message "WARNING: Memory usage is ${MEMORY_USAGE}%"
fi

# Check load average
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
if (( $(echo "$LOAD_AVG > 2.0" | bc -l) )); then
    log_message "WARNING: High load average: $LOAD_AVG"
fi

log_message "System check completed - Disk: ${DISK_USAGE}%, Memory: ${MEMORY_USAGE}%, Load: $LOAD_AVG"
EOF
    
    chmod +x /usr/local/bin/system-monitor.sh
    
    # Add cron job for system monitoring
    cat > /etc/cron.d/system-monitor << 'EOF'
# System monitoring every 15 minutes
*/15 * * * * root /usr/local/bin/system-monitor.sh
EOF
    
    print_success "Monitoring setup completed"
}

# Function to create configuration template
create_config_template() {
    print_header "Creating configuration template..."
    
    cat > $APP_DIR/config/production.properties << EOF
[database]
path = $APP_DIR/data/price_monitor.db
# For PostgreSQL, uncomment and configure:
# host = localhost
# port = 5432
# name = price_monitor
# username = price_monitor_user
# password = your_secure_password

[email]
smtp_server = smtp.gmail.com
smtp_port = 587
username = your_email@gmail.com
password = your_app_password
recipient = alerts@yourdomain.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30
check_time = 09:00

[security]
enable_mtls = false
api_port = $APP_PORT
server_cert_path = $APP_DIR/certs/server.crt
server_key_path = $APP_DIR/certs/server.key
ca_cert_path = $APP_DIR/certs/ca.crt
client_cert_required = false

[app]
log_level = INFO
log_file = $APP_DIR/logs/price_monitor.log
environment = production

[parsing]
enable_ai_parsing = true
EOF
    
    chown $APP_USER:$APP_USER $APP_DIR/config/production.properties
    chmod 600 $APP_DIR/config/production.properties
    
    print_success "Configuration template created"
}

# Function to setup backup script
setup_backup() {
    print_header "Setting up backup system..."
    
    cat > $APP_DIR/backup.sh << 'EOF'
#!/bin/bash
# Backup script for Price Monitor application

BACKUP_DIR="/opt/price-monitor/backups"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="/opt/price-monitor"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
if [ -f "$APP_DIR/data/price_monitor.db" ]; then
    cp "$APP_DIR/data/price_monitor.db" "$BACKUP_DIR/database_$DATE.db"
    echo "Database backup created: database_$DATE.db"
fi

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$APP_DIR" config/
echo "Configuration backup created: config_$DATE.tar.gz"

# Backup logs (last 7 days)
find "$APP_DIR/logs" -name "*.log" -mtime -7 -exec tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" {} +
echo "Logs backup created: logs_$DATE.tar.gz"

# Clean old backups (keep last 30 days)
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF
    
    chmod +x $APP_DIR/backup.sh
    chown $APP_USER:$APP_USER $APP_DIR/backup.sh
    
    # Add daily backup cron job
    cat > /etc/cron.d/price-monitor-backup << EOF
# Daily backup at 2 AM
0 2 * * * $APP_USER $APP_DIR/backup.sh >> $APP_DIR/logs/backup.log 2>&1
EOF
    
    print_success "Backup system configured"
}

# Function to optimize system performance
optimize_system() {
    print_header "Optimizing system performance..."
    
    # Update sysctl settings
    cat >> /etc/sysctl.conf << 'EOF'

# Price Monitor Application Optimizations
# Network optimizations
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_congestion_control = bbr

# File system optimizations
fs.file-max = 65536
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Security optimizations
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1
EOF
    
    # Apply sysctl settings
    sysctl -p
    
    # Update limits
    cat >> /etc/security/limits.conf << EOF

# Price Monitor Application Limits
$APP_USER soft nofile 65536
$APP_USER hard nofile 65536
$APP_USER soft nproc 4096
$APP_USER hard nproc 4096
EOF
    
    print_success "System performance optimized"
}

# Function to create deployment script
create_deployment_script() {
    print_header "Creating deployment script..."
    
    cat > $APP_DIR/deploy-app.sh << 'EOF'
#!/bin/bash
# Deployment script for Price Monitor application

set -e

APP_DIR="/opt/price-monitor"
APP_USER="price-monitor"
REPO_URL="${REPO_URL:-https://github.com/fresh-fx59/ai-price-checker.git}"
BRANCH="${BRANCH:-main}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as app user
if [[ $(whoami) != "$APP_USER" ]]; then
    print_error "This script must be run as $APP_USER user"
    exit 1
fi

print_status "Starting deployment..."

# Backup current version
if [ -d "$APP_DIR/src" ]; then
    print_status "Backing up current version..."
    tar -czf "$APP_DIR/backups/app_backup_$(date +%Y%m%d_%H%M%S).tar.gz" -C "$APP_DIR" src/ static/ || true
fi

# Clone or update repository
if [ -d "$APP_DIR/.git" ]; then
    print_status "Updating existing repository..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/$BRANCH
else
    print_status "Cloning repository..."
    cd /tmp
    git clone -b $BRANCH $REPO_URL price-monitor-temp
    cp -r price-monitor-temp/* "$APP_DIR/"
    rm -rf price-monitor-temp
    cd "$APP_DIR"
fi

# Install/update dependencies
print_status "Installing dependencies..."
$APP_DIR/venv/bin/pip install -r requirements.txt

# Run database migrations if needed
if [ -f "$APP_DIR/migrations.py" ]; then
    print_status "Running database migrations..."
    $APP_DIR/venv/bin/python migrations.py
fi

# Set proper permissions
chmod +x "$APP_DIR/src/main.py" || true
find "$APP_DIR" -name "*.py" -exec chmod 644 {} \;

# Restart application
print_status "Restarting application..."
sudo systemctl restart price-monitor

# Wait for application to start
sleep 5

# Health check for both IPv4 and IPv6
print_status "Performing dual-stack health check..."

ipv4_healthy=false
ipv6_healthy=false

# Test IPv4
if curl -4 -f -s http://localhost:8080/health > /dev/null 2>&1; then
    print_success "✓ IPv4 health check passed"
    ipv4_healthy=true
else
    print_warning "✗ IPv4 health check failed"
fi

# Test IPv6
if curl -6 -f -s http://localhost:8080/health > /dev/null 2>&1; then
    print_success "✓ IPv6 health check passed"
    ipv6_healthy=true
else
    print_status "IPv6 health check failed or not available"
fi

if [[ "$ipv4_healthy" == "true" || "$ipv6_healthy" == "true" ]]; then
    print_success "Deployment completed successfully!"
    print_status "Application is running and healthy (IPv4: $ipv4_healthy, IPv6: $ipv6_healthy)"
else
    print_error "Deployment may have failed - health check failed"
    print_status "Check logs: journalctl -u price-monitor -f"
    exit 1
fi
EOF
    
    chmod +x $APP_DIR/deploy-app.sh
    chown $APP_USER:$APP_USER $APP_DIR/deploy-app.sh
    
    print_success "Deployment script created"
}

# Function to display final information
display_final_info() {
    print_header "Setup completed successfully!"
    
    echo ""
    echo "=== Price Monitor Server Setup Summary ==="
    echo ""
    echo "Application User: $APP_USER"
    echo "Application Directory: $APP_DIR"
    echo "Application Port: $APP_PORT"
    echo "Python Version: $(python3 --version)"
    echo "Node.js Version: $(node --version 2>/dev/null || echo 'Not installed')"
    echo "Docker: $(docker --version 2>/dev/null || echo 'Not installed')"
    echo "Nginx: $(nginx -v 2>&1 || echo 'Not installed')"
    echo ""
    echo "=== Network Configuration ==="
    echo "IPv4 Support: $(ip -4 addr show | grep -q 'inet ' && echo 'Enabled' || echo 'Disabled')"
    echo "IPv6 Support: $(ip -6 addr show | grep -q 'inet6' && echo 'Enabled' || echo 'Disabled')"
    if ip -6 addr show | grep -q 'inet6.*global'; then
        echo "IPv6 Global Address: $(ip -6 addr show | grep 'inet6.*global' | head -1 | awk '{print $2}' | cut -d'/' -f1)"
    fi
    echo ""
    echo "=== Next Steps ==="
    echo ""
    echo "1. Configure the application:"
    echo "   sudo nano $APP_DIR/config/production.properties"
    echo ""
    echo "2. Deploy your application code:"
    echo "   sudo -u $APP_USER $APP_DIR/deploy-app.sh"
    echo ""
    echo "3. Start the application:"
    echo "   sudo systemctl start price-monitor"
    echo ""
    echo "4. Check application status:"
    echo "   sudo systemctl status price-monitor"
    if [[ "$SETUP_SSL" == "true" && -n "$DOMAIN_NAME" ]]; then
        echo "   curl https://$DOMAIN_NAME/health"
    else
        echo "   curl http://localhost:$APP_PORT/health"
    fi
    echo ""
    echo "5. View logs:"
    echo "   sudo journalctl -u price-monitor -f"
    echo "   tail -f $APP_DIR/logs/price_monitor.log"
    echo ""
    echo "6. SSL Certificate Management:"
    echo "   sudo ssl-manager                                  # Interactive SSL management"
    echo "   sudo issue-ssl-cert <domain> <email> [method]    # Issue new certificate"
    echo "   sudo monitor-ssl-certs                           # Check all certificates"
    echo "   sudo certbot certificates                        # List certificates"
    echo "   sudo certbot renew                               # Renew all certificates"
    echo ""
    if [[ "$SETUP_SSL" == "true" && -n "$DOMAIN_NAME" ]]; then
        echo "   Your SSL certificate for $DOMAIN_NAME:"
        echo "   sudo $APP_DIR/ssl-status.sh                   # Check certificate status"
        echo "   sudo $APP_DIR/ssl-renew.sh                    # Manual renewal"
        echo "   sudo $APP_DIR/ssl-troubleshoot.sh             # Troubleshooting"
        echo ""
    fi
    echo ""
    echo "=== Important Files ==="
    echo ""
    echo "Configuration: $APP_DIR/config/production.properties"
    echo "Logs: $APP_DIR/logs/"
    echo "Data: $APP_DIR/data/"
    echo "Backups: $APP_DIR/backups/"
    echo "Service: /etc/systemd/system/price-monitor.service"
    echo "Nginx Config: /etc/nginx/sites-available/price-monitor"
    echo ""
    echo "=== Security Notes ==="
    echo ""
    echo "- Firewall (UFW) is enabled with ports 22, 80, 443, $APP_PORT open"
    echo "- Fail2ban is configured for SSH and Nginx protection"
    echo "- Application runs as non-root user: $APP_USER"
    echo "- SSL/TLS: $([ "$SETUP_SSL" == "true" ] && echo "Configured for $DOMAIN_NAME" || echo "Not configured")"
    echo ""
    echo "Setup log saved to: $LOG_FILE"
    echo ""
    print_success "Server is ready for Price Monitor application deployment!"
}

# Main execution function
main() {
    print_header "Price Monitor - Ubuntu 24.04 Server Setup"
    print_status "Starting server preparation..."
    
    # Pre-flight checks
    check_root
    check_ubuntu_version
    
    # Check network connectivity
    print_header "Checking network connectivity..."
    
    # Test dual-stack connectivity first
    test_dual_stack_connectivity
    
    # Then test HTTPS connectivity
    if ! check_network_connectivity "https://google.com" 10; then
        handle_offline_mode
        read -p "Continue in offline mode? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Setup cancelled by user"
            exit 1
        fi
        export OFFLINE_MODE=true
    else
        export OFFLINE_MODE=false
    fi
    
    # System setup
    update_system
    configure_ipv6_support
    install_python
    install_nodejs
    install_docker
    install_nginx
    install_certbot
    
    # Security setup
    setup_firewall
    setup_fail2ban
    
    # Application setup
    create_app_user
    create_ssl_management_tools
    setup_ssl
    setup_app_environment
    create_systemd_service
    setup_log_rotation
    setup_monitoring
    create_config_template
    setup_backup
    
    # Optimization
    optimize_system
    create_deployment_script
    
    # Final steps
    display_final_info
}

# Show usage information
show_usage() {
    cat << EOF
Price Monitor - Ubuntu 24.04 Server Setup Script

Usage: sudo $0 [OPTIONS]

Environment Variables:
    APP_USER          Application user name (default: price-monitor)
    APP_DIR           Application directory (default: /opt/price-monitor)
    APP_PORT          Application port (default: 8080)
    PYTHON_VERSION    Python version to install (default: 3.13)
    NODE_VERSION      Node.js version to install (default: 20)
    INSTALL_DOCKER    Install Docker (default: true)
    INSTALL_NGINX     Install Nginx (default: true)
    SETUP_FIREWALL    Setup UFW firewall (default: true)
    SETUP_SSL         Setup SSL with Let's Encrypt (default: false)
    DOMAIN_NAME       Domain name for SSL certificate
    EMAIL_ADDRESS     Email address for SSL certificate
    SSL_METHOD        SSL certificate method: nginx, webroot, standalone, dns (default: nginx)

Examples:
    # Basic setup (uses Python 3.13 by default)
    sudo $0

    # Setup with custom Python version
    sudo PYTHON_VERSION=3.12 $0

    # Setup with custom domain and SSL (nginx method)
    sudo DOMAIN_NAME=monitor.example.com EMAIL_ADDRESS=admin@example.com SETUP_SSL=true $0

    # Setup with SSL using webroot method
    sudo DOMAIN_NAME=monitor.example.com EMAIL_ADDRESS=admin@example.com SETUP_SSL=true SSL_METHOD=webroot $0

    # Setup for IPv6-only domain
    sudo DOMAIN_NAME=price-checker.flowvian.com EMAIL_ADDRESS=admin@flowvian.com SETUP_SSL=true $0

    # Setup for dual-stack domain (IPv4 + IPv6)
    sudo DOMAIN_NAME=example.com EMAIL_ADDRESS=admin@example.com SETUP_SSL=true $0

    # Setup without Docker
    sudo INSTALL_DOCKER=false $0

    # Issue SSL certificate after setup
    sudo issue-ssl-cert monitor.example.com admin@example.com nginx
    
    # Issue SSL certificate for IPv6-only domain
    sudo issue-ssl-cert price-checker.flowvian.com admin@flowvian.com nginx
    
    # Issue SSL certificate for dual-stack domain
    sudo issue-ssl-cert example.com admin@example.com nginx

EOF
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_usage
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac