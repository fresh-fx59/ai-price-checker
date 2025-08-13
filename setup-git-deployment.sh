#!/bin/bash

# Price Monitor Git Deployment Setup Script
# This script sets up git deployment for the first time

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
APP_DIR="${APP_DIR:-/opt/price-monitor}"
SERVICE_NAME="${SERVICE_NAME:-price-monitor}"


# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

print_header "Price Monitor Git Deployment Setup"

# Navigate to application directory
cd "$APP_DIR"

# Fix git ownership issues when running as root
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

# Check if git is installed
if ! command -v git &> /dev/null; then
    print_status "Installing git..."
    apt-get update
    apt-get install -y git
    print_success "Git installed"
fi

# Configuration - set default repository URL
GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/fresh-fx59/ai-price-checker.git}"

# Get repository URL (allow override)
if [[ -z "$GIT_REPO_URL" ]]; then
    echo ""
    print_status "Please provide your git repository URL"
    echo "Examples:"
    echo "  https://github.com/username/price-monitor.git"
    echo "  git@github.com:username/price-monitor.git"
    echo ""
    echo -n "Repository URL: "
    read GIT_REPO_URL
else
    print_status "Using repository: $GIT_REPO_URL"
    echo -n "Use this repository? (Y/n): "
    read CONFIRM_REPO
    if [[ "$CONFIRM_REPO" =~ ^[Nn]$ ]]; then
        echo -n "Enter repository URL: "
        read GIT_REPO_URL
    fi
fi

# Validate URL
if [[ -z "$GIT_REPO_URL" ]]; then
    print_error "Repository URL is required"
    exit 1
fi

# Initialize git repository if not already done
if [[ ! -d ".git" ]]; then
    print_status "Initializing git repository..."
    git init
    git remote add origin "$GIT_REPO_URL"
    print_success "Git repository initialized"
else
    print_status "Git repository already exists"
    
    # Check if remote exists
    if git remote get-url origin >/dev/null 2>&1; then
        CURRENT_REMOTE=$(git remote get-url origin)
        if [[ "$CURRENT_REMOTE" != "$GIT_REPO_URL" ]]; then
            print_warning "Current remote: $CURRENT_REMOTE"
            print_warning "New remote: $GIT_REPO_URL"
            echo -n "Update remote URL? (y/N): "
            read UPDATE_REMOTE
            if [[ "$UPDATE_REMOTE" =~ ^[Yy]$ ]]; then
                git remote set-url origin "$GIT_REPO_URL"
                print_success "Remote URL updated"
            fi
        else
            print_success "Remote URL already correct"
        fi
    else
        git remote add origin "$GIT_REPO_URL"
        print_success "Remote added"
    fi
fi

# Test git connectivity
print_status "Testing git connectivity..."
if git ls-remote origin HEAD >/dev/null 2>&1; then
    print_success "Git connectivity test passed"
else
    print_error "Failed to connect to git repository"
    print_status "Please check:"
    print_status "1. Repository URL is correct"
    print_status "2. You have access to the repository"
    print_status "3. SSH keys are set up (if using SSH URL)"
    exit 1
fi

# Fetch and checkout main branch
print_status "Fetching latest changes..."
git fetch origin

# Check if main branch exists remotely
if git ls-remote --heads origin main | grep -q main; then
    MAIN_BRANCH="main"
elif git ls-remote --heads origin master | grep -q master; then
    MAIN_BRANCH="master"
    print_warning "Using 'master' branch (consider renaming to 'main')"
else
    print_error "Neither 'main' nor 'master' branch found in remote repository"
    exit 1
fi

# Checkout the main branch
print_status "Checking out $MAIN_BRANCH branch..."
git checkout -B "$MAIN_BRANCH" "origin/$MAIN_BRANCH" 2>/dev/null || git checkout -b "$MAIN_BRANCH"

# Ensure price-monitor user exists
if ! id "price-monitor" &>/dev/null; then
    print_status "Creating price-monitor user..."
    useradd -r -s /bin/false -d "$APP_DIR" price-monitor
    print_success "price-monitor user created"
fi

# Set proper permissions
print_status "Setting proper file permissions..."
chown -R price-monitor:price-monitor "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod -R 750 "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/certs" 2>/dev/null || true

# Make deployment script executable
if [[ -f "deploy.sh" ]]; then
    chmod +x deploy.sh
    print_success "Deployment script made executable"
fi

print_header "Setup Complete"
print_success "Git deployment is now configured"
print_status "Repository: $GIT_REPO_URL"
print_status "Branch: $MAIN_BRANCH"
print_status "Application directory: $APP_DIR"

echo ""
print_status "Next steps:"
print_status "1. Run your first deployment: sudo ./deploy.sh"
print_status "2. For future updates: commit changes locally, push to git, then run sudo ./deploy.sh"

echo ""
print_status "Useful commands:"
print_status "  Deploy latest changes: sudo ./deploy.sh"
print_status "  Check service status: sudo systemctl status $SERVICE_NAME"
print_status "  View service logs: sudo journalctl -u $SERVICE_NAME -f"
print_status "  Check git status: git status"
print_status "  View recent commits: git log --oneline -5"