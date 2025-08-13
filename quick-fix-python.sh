#!/bin/bash

# Quick fix for Python 3.13 -> 3.12 downgrade
# Run this to immediately fix the SQLAlchemy issue

set -e

APP_DIR="/opt/price-monitor"
APP_USER="price-monitor"

echo "🔧 Quick Python 3.13 -> 3.12 Fix"
echo "================================="

# Stop the service first
echo "Stopping price-monitor service..."
sudo systemctl stop price-monitor || true

# Install Python 3.12 if not present
if ! command -v python3.12 >/dev/null 2>&1; then
    echo "Installing Python 3.12..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y python3.12 python3.12-dev python3.12-venv python3.12-distutils
fi

# Backup current virtual environment
echo "Backing up current virtual environment..."
sudo -u $APP_USER mv $APP_DIR/venv $APP_DIR/venv.backup.$(date +%Y%m%d_%H%M%S) || true

# Create new virtual environment with Python 3.12
echo "Creating new virtual environment with Python 3.12..."
sudo -u $APP_USER python3.12 -m venv $APP_DIR/venv

# Upgrade pip
echo "Upgrading pip..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip wheel setuptools

# Install compatible SQLAlchemy version first
echo "Installing compatible SQLAlchemy..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install "sqlalchemy>=1.4.0,<2.0.0"

# Install other requirements
if [ -f "$APP_DIR/requirements.txt" ]; then
    echo "Installing requirements..."
    # Install everything except SQLAlchemy (already installed)
    grep -v "^sqlalchemy" $APP_DIR/requirements.txt > /tmp/requirements_no_sqlalchemy.txt || true
    if [ -s /tmp/requirements_no_sqlalchemy.txt ]; then
        sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r /tmp/requirements_no_sqlalchemy.txt
    fi
    rm -f /tmp/requirements_no_sqlalchemy.txt
fi

# Test the installation
echo "Testing Python and SQLAlchemy..."
sudo -u $APP_USER $APP_DIR/venv/bin/python --version
sudo -u $APP_USER $APP_DIR/venv/bin/python -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__} works!')"

# Start the service
echo "Starting price-monitor service..."
sudo systemctl start price-monitor

# Check status
sleep 3
if sudo systemctl is-active --quiet price-monitor; then
    echo "✅ Service started successfully!"
    echo "Check status: sudo systemctl status price-monitor"
else
    echo "❌ Service failed to start. Check logs: sudo journalctl -u price-monitor -f"
fi

echo "Done! 🎉"