#!/bin/bash

# Price Monitor Deployment Script
# This script pulls the latest changes and restarts the service

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
APP_DIR="/opt/price-monitor"
SERVICE_NAME="price-monitor"
BACKUP_DIR="/opt/price-monitor/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

print_header "Price Monitor Deployment"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Navigate to application directory
cd "$APP_DIR"

# Create backup of current version
print_status "Creating backup of current version..."
tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" \
    --exclude='.git' \
    --exclude='backups' \
    --exclude='logs' \
    --exclude='data' \
    --exclude='__pycache__' \
    .

print_success "Backup created: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"

# Stop the service
print_status "Stopping $SERVICE_NAME service..."
systemctl stop "$SERVICE_NAME" || print_warning "Service may not be running"

# Pull latest changes
print_status "Pulling latest changes from git..."
git fetch origin
git reset --hard origin/main

# Set proper permissions
print_status "Setting proper file permissions..."
chown -R www-data:www-data "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod -R 750 "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/certs" 2>/dev/null || true

# Install/update Python dependencies if requirements changed
if git diff HEAD~1 HEAD --name-only | grep -q "requirements.txt"; then
    print_status "Requirements.txt changed, updating Python dependencies..."
    pip install -r requirements.txt
fi

# Start the service
print_status "Starting $SERVICE_NAME service..."
systemctl start "$SERVICE_NAME"

# Wait a moment for service to start
sleep 3

# Check service status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_success "Service started successfully"
    
    # Test health endpoint
    print_status "Testing application health..."
    if curl -k -s --cert /opt/price-monitor/certs/admin-client.crt \
            --key /opt/price-monitor/certs/admin-client.key \
            https://localhost:8443/health > /dev/null; then
        print_success "Health check passed"
    else
        print_warning "Health check failed - application may still be starting"
    fi
else
    print_error "Failed to start service"
    print_status "Checking service logs..."
    journalctl -u "$SERVICE_NAME" --no-pager -n 20
    exit 1
fi

# Clean up old backups (keep last 5)
print_status "Cleaning up old backups..."
cd "$BACKUP_DIR"
ls -t backup_*.tar.gz | tail -n +6 | xargs rm -f 2>/dev/null || true

print_header "Deployment Complete"
print_success "Price Monitor has been updated successfully"
print_status "Service status: $(systemctl is-active $SERVICE_NAME)"
print_status "View logs: sudo journalctl -u $SERVICE_NAME -f"
print_status "Health check: curl -k --cert /opt/price-monitor/certs/admin-client.crt --key /opt/price-monitor/certs/admin-client.key https://price-monitor.flowvian.com/health"

echo ""
print_status "Recent commits:"
git log --oneline -5