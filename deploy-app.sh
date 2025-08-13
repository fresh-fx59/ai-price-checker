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

# Function to check system dependencies for lxml
check_system_dependencies() {
    print_status "Checking system dependencies for lxml..."
    
    missing_deps=()
    
    # Check for required development packages
    if ! dpkg -l | grep -q libxml2-dev; then
        missing_deps+=("libxml2-dev")
    fi
    
    if ! dpkg -l | grep -q libxslt1-dev; then
        missing_deps+=("libxslt1-dev")
    fi
    
    if ! dpkg -l | grep -q python3-dev; then
        missing_deps+=("python3-dev")
    fi
    
    if ! dpkg -l | grep -q build-essential; then
        missing_deps+=("build-essential")
    fi
    
    if ! dpkg -l | grep -q " bc "; then
        missing_deps+=("bc")
    fi
    
    if ! dpkg -l | grep -q pkg-config; then
        missing_deps+=("pkg-config")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing system dependencies: ${missing_deps[*]}"
        print_status "Please install them with: sudo apt-get install -y ${missing_deps[*]}"
        exit 1
    fi
    
    print_status "✓ All system dependencies are installed"
}

# Function to suggest Python version downgrade
suggest_python_downgrade() {
    print_error "Python 3.13 compatibility issues detected!"
    echo
    print_status "Python 3.13 is very new and many packages haven't been updated yet."
    print_status "For better compatibility, consider using Python 3.11 or 3.12:"
    echo
    print_status "1. Install Python 3.12:"
    print_status "   sudo apt update"
    print_status "   sudo apt install python3.12 python3.12-venv python3.12-dev"
    echo
    print_status "2. Recreate virtual environment:"
    print_status "   rm -rf $APP_DIR/venv"
    print_status "   python3.12 -m venv $APP_DIR/venv"
    echo
    print_status "3. Re-run deployment:"
    print_status "   ./deploy-app.sh"
    echo
}

print_status "Starting deployment..."

# Check system dependencies
check_system_dependencies

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

# Function to check Python version compatibility
check_python_version() {
    python_version=$($APP_DIR/venv/bin/python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_status "Detected Python version: $python_version"
    
    # Check if Python 3.13+ (which has lxml compatibility issues)
    if command -v bc >/dev/null 2>&1; then
        if [[ $(echo "$python_version >= 3.13" | bc -l) -eq 1 ]]; then
            print_status "Python 3.13+ detected - using compatibility mode for lxml"
            return 0
        else
            return 1
        fi
    else
        # Fallback comparison without bc
        major=$(echo "$python_version" | cut -d. -f1)
        minor=$(echo "$python_version" | cut -d. -f2)
        if [[ $major -gt 3 ]] || [[ $major -eq 3 && $minor -ge 13 ]]; then
            print_status "Python 3.13+ detected - using compatibility mode for lxml"
            return 0
        else
            return 1
        fi
    fi
}

# Function to install lxml with Python 3.13 compatibility
install_lxml_compatible() {
    print_status "Installing lxml with Python 3.13 compatibility..."
    
    # Try precompiled wheel first (fastest and most reliable)
    if $APP_DIR/venv/bin/pip install --only-binary=lxml lxml; then
        print_success "✓ lxml installed from precompiled wheel"
        return 0
    fi
    
    # If wheel fails, try older compatible version
    print_status "Precompiled wheel failed, trying compatible lxml version..."
    if $APP_DIR/venv/bin/pip install "lxml>=4.9.0,<5.0.0" --only-binary=lxml; then
        print_success "✓ Compatible lxml version installed"
        return 0
    fi
    
    # Last resort: try to build with relaxed constraints
    print_status "Trying to build lxml with relaxed constraints..."
    export CFLAGS="-Wno-error"
    if $APP_DIR/venv/bin/pip install lxml --no-binary=lxml; then
        print_success "✓ lxml built from source with relaxed constraints"
        unset CFLAGS
        return 0
    fi
    
    unset CFLAGS
    print_error "Failed to install lxml - Python 3.13 compatibility issue"
    return 1
}

# Function to install SQLAlchemy with Python 3.13 compatibility
install_sqlalchemy_compatible() {
    print_status "Installing SQLAlchemy with Python 3.13 compatibility..."
    
    # Try latest version first (may have been fixed)
    if $APP_DIR/venv/bin/pip install "sqlalchemy>=2.0.0"; then
        print_success "✓ Latest SQLAlchemy installed"
        return 0
    fi
    
    # Try a known working version for Python 3.13
    print_status "Latest version failed, trying compatible SQLAlchemy version..."
    if $APP_DIR/venv/bin/pip install "sqlalchemy>=1.4.0,<2.0.0"; then
        print_success "✓ Compatible SQLAlchemy version installed"
        return 0
    fi
    
    print_error "Failed to install compatible SQLAlchemy version"
    return 1
}

# Function to handle Python 3.13 incompatible packages
handle_python313_packages() {
    local temp_req_file="/tmp/requirements_python313_compat.txt"
    local incompatible_packages=("lxml" "sqlalchemy")
    
    # Create requirements file without incompatible packages
    cp requirements.txt "$temp_req_file"
    
    for package in "${incompatible_packages[@]}"; do
        if grep -q "^$package" requirements.txt; then
            print_status "Handling $package separately for Python 3.13 compatibility..."
            grep -v "^$package" "$temp_req_file" > "${temp_req_file}.tmp"
            mv "${temp_req_file}.tmp" "$temp_req_file"
            
            case $package in
                "lxml")
                    if ! install_lxml_compatible; then
                        rm -f "$temp_req_file"
                        return 1
                    fi
                    ;;
                "sqlalchemy")
                    if ! install_sqlalchemy_compatible; then
                        rm -f "$temp_req_file"
                        return 1
                    fi
                    ;;
            esac
        fi
    done
    
    # Install remaining packages
    if [ -s "$temp_req_file" ]; then
        print_status "Installing remaining dependencies..."
        $APP_DIR/venv/bin/pip install -r "$temp_req_file"
    fi
    
    rm -f "$temp_req_file"
    return 0
}

# Install/update dependencies
print_status "Installing dependencies..."

# Upgrade pip and install build tools
$APP_DIR/venv/bin/pip install --upgrade pip wheel setuptools

# Check if we need Python 3.13 compatibility mode
if check_python_version; then
    # Python 3.13+ detected - handle incompatible packages specially
    print_status "Python 3.13+ detected - handling incompatible packages..."
    
    if ! handle_python313_packages; then
        suggest_python_downgrade
        exit 1
    fi
else
    # Python < 3.13 - use standard installation with PEP 517 for lxml
    if grep -q "lxml" requirements.txt; then
        print_status "Installing lxml with PEP 517 support..."
        
        # Extract lxml version from requirements.txt
        lxml_version=$(grep "^lxml" requirements.txt | head -1)
        
        # Try PEP 517 first, then fallback
        if $APP_DIR/venv/bin/pip install --use-pep517 --no-build-isolation "$lxml_version"; then
            print_status "✓ lxml installed with PEP 517"
        else
            print_status "PEP 517 failed, using standard installation..."
            $APP_DIR/venv/bin/pip install "$lxml_version"
        fi
        
        # Install remaining dependencies
        grep -v "^lxml" requirements.txt > /tmp/requirements_no_lxml.txt
        if [ -s /tmp/requirements_no_lxml.txt ]; then
            $APP_DIR/venv/bin/pip install -r /tmp/requirements_no_lxml.txt
        fi
        rm -f /tmp/requirements_no_lxml.txt
    else
        # No lxml, install normally
        $APP_DIR/venv/bin/pip install -r requirements.txt
    fi
fi

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

# Health check
if curl -f -s http://localhost:8080/health > /dev/null; then
    print_success "Deployment completed successfully!"
    print_status "Application is running and healthy"
else
    print_error "Deployment may have failed - health check failed"
    print_status "Check logs: journalctl -u price-monitor -f"
    exit 1
fi
