#!/bin/bash

# Python 3.13 to 3.12 Downgrade Script for Price Monitor
# This script helps downgrade from Python 3.13 to 3.12 for better compatibility

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="${APP_DIR:-/opt/price-monitor}"
APP_USER="${APP_USER:-price-monitor}"

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
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check current Python version
check_current_python() {
    print_header "Checking Current Python Installation"
    
    if command -v python3.13 >/dev/null 2>&1; then
        print_status "Python 3.13 found: $(python3.13 --version)"
        PYTHON_313_INSTALLED=true
    else
        print_status "Python 3.13 not found"
        PYTHON_313_INSTALLED=false
    fi
    
    if command -v python3.12 >/dev/null 2>&1; then
        print_status "Python 3.12 found: $(python3.12 --version)"
        PYTHON_312_INSTALLED=true
    else
        print_status "Python 3.12 not found"
        PYTHON_312_INSTALLED=false
    fi
    
    current_default=$(python3 --version 2>&1 | grep -o "3\.[0-9]\+")
    print_status "Current default python3 version: $current_default"
}

# Install Python 3.12
install_python312() {
    if [[ "$PYTHON_312_INSTALLED" == "true" ]]; then
        print_status "Python 3.12 already installed, skipping installation"
        return
    fi
    
    print_header "Installing Python 3.12"
    
    # Add deadsnakes PPA if not already added
    if ! grep -q "deadsnakes/ppa" /etc/apt/sources.list.d/*.list 2>/dev/null; then
        print_status "Adding deadsnakes PPA..."
        add-apt-repository ppa:deadsnakes/ppa -y
    fi
    
    # Update package list
    apt-get update -y
    
    # Install Python 3.12 and related packages
    print_status "Installing Python 3.12 packages..."
    apt-get install -y \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3.12-distutils
    
    print_success "Python 3.12 installed successfully"
}

# Update system default Python
update_default_python() {
    print_header "Updating System Default Python"
    
    # Update alternatives to prioritize Python 3.12
    print_status "Setting up Python alternatives..."
    
    # Remove existing alternatives
    update-alternatives --remove-all python3 2>/dev/null || true
    
    # Add Python 3.12 with higher priority
    if command -v python3.12 >/dev/null 2>&1; then
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 100
        print_status "Added Python 3.12 as default python3"
    fi
    
    # Add Python 3.13 with lower priority if it exists
    if command -v python3.13 >/dev/null 2>&1; then
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 50
        print_status "Added Python 3.13 as alternative python3"
    fi
    
    # Verify the change
    new_version=$(python3 --version 2>&1 | grep -o "3\.[0-9]\+")
    print_success "Default python3 is now version: $new_version"
}

# Recreate virtual environment
recreate_venv() {
    print_header "Recreating Virtual Environment"
    
    if [[ ! -d "$APP_DIR" ]]; then
        print_warning "Application directory $APP_DIR not found, skipping virtual environment recreation"
        return
    fi
    
    # Backup old virtual environment
    if [[ -d "$APP_DIR/venv" ]]; then
        print_status "Backing up existing virtual environment..."
        sudo -u $APP_USER mv "$APP_DIR/venv" "$APP_DIR/venv.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create new virtual environment with Python 3.12
    print_status "Creating new virtual environment with Python 3.12..."
    sudo -u $APP_USER python3.12 -m venv "$APP_DIR/venv"
    
    # Upgrade pip in the new environment
    print_status "Upgrading pip in virtual environment..."
    sudo -u $APP_USER "$APP_DIR/venv/bin/pip" install --upgrade pip wheel setuptools
    
    print_success "Virtual environment recreated successfully"
}

# Reinstall Python packages
reinstall_packages() {
    print_header "Reinstalling Python Packages"
    
    if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
        print_warning "requirements.txt not found, skipping package installation"
        return
    fi
    
    print_status "Installing packages from requirements.txt..."
    sudo -u $APP_USER "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    
    print_success "Python packages installed successfully"
}

# Test the installation
test_installation() {
    print_header "Testing Installation"
    
    # Test Python version
    python_version=$(python3 --version)
    print_status "System Python version: $python_version"
    
    if [[ -f "$APP_DIR/venv/bin/python" ]]; then
        venv_version=$("$APP_DIR/venv/bin/python" --version)
        print_status "Virtual environment Python version: $venv_version"
        
        # Test importing key packages
        print_status "Testing key package imports..."
        
        if sudo -u $APP_USER "$APP_DIR/venv/bin/python" -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__} imported successfully')" 2>/dev/null; then
            print_success "✓ SQLAlchemy import test passed"
        else
            print_error "✗ SQLAlchemy import test failed"
        fi
        
        if sudo -u $APP_USER "$APP_DIR/venv/bin/python" -c "import lxml; print(f'lxml {lxml.__version__} imported successfully')" 2>/dev/null; then
            print_success "✓ lxml import test passed"
        else
            print_warning "⚠ lxml import test failed (may not be in requirements)"
        fi
    else
        print_warning "Virtual environment not found, skipping venv tests"
    fi
}

# Cleanup Python 3.13 (optional)
cleanup_python313() {
    if [[ "$PYTHON_313_INSTALLED" != "true" ]]; then
        return
    fi
    
    print_header "Python 3.13 Cleanup (Optional)"
    
    read -p "Do you want to remove Python 3.13 packages? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Removing Python 3.13 packages..."
        apt-get remove -y python3.13 python3.13-dev python3.13-venv python3.13-distutils || true
        apt-get autoremove -y
        print_success "Python 3.13 packages removed"
    else
        print_status "Keeping Python 3.13 packages (they won't interfere)"
    fi
}

# Show summary
show_summary() {
    print_header "Downgrade Summary"
    
    echo
    print_success "Python downgrade completed successfully!"
    echo
    print_status "Current Configuration:"
    print_status "  • System Python: $(python3 --version)"
    if [[ -f "$APP_DIR/venv/bin/python" ]]; then
        print_status "  • Virtual Environment: $($APP_DIR/venv/bin/python --version)"
    fi
    print_status "  • Application Directory: $APP_DIR"
    echo
    print_status "Next Steps:"
    print_status "  1. Test your application: sudo -u $APP_USER $APP_DIR/deploy-app.sh"
    print_status "  2. Start the service: systemctl start price-monitor"
    print_status "  3. Check status: systemctl status price-monitor"
    echo
    print_status "If you encounter issues:"
    print_status "  • Check logs: journalctl -u price-monitor -f"
    print_status "  • Verify packages: $APP_DIR/venv/bin/pip list"
    echo
}

# Main execution
main() {
    print_header "Python 3.13 to 3.12 Downgrade for Price Monitor"
    echo
    
    # Check prerequisites
    check_root
    check_current_python
    
    # Perform downgrade steps
    install_python312
    update_default_python
    recreate_venv
    reinstall_packages
    test_installation
    cleanup_python313
    
    # Show summary
    show_summary
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-dir)
            APP_DIR="$2"
            shift 2
            ;;
        --app-user)
            APP_USER="$2"
            shift 2
            ;;
        --help)
            echo "Python 3.13 to 3.12 Downgrade Script"
            echo
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  --app-dir DIR    Application directory (default: /opt/price-monitor)"
            echo "  --app-user USER  Application user (default: price-monitor)"
            echo "  --help           Show this help message"
            echo
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main