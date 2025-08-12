# Price Monitor - Ubuntu 24.04 Server Setup Guide

## Overview

The `setup-ubuntu-server.sh` script provides a comprehensive, automated setup for preparing a fresh Ubuntu 24.04 server to run the Price Monitor application. This script handles all necessary dependencies, security configurations, and application environment setup.

## 🚀 Quick Start

### Basic Setup
```bash
# Download and run the setup script
wget https://raw.githubusercontent.com/your-repo/price-monitor/main/setup-ubuntu-server.sh
chmod +x setup-ubuntu-server.sh
sudo ./setup-ubuntu-server.sh
```

### Custom Configuration
```bash
# Setup with custom domain and SSL
sudo DOMAIN_NAME=monitor.example.com \
     EMAIL_ADDRESS=admin@example.com \
     SETUP_SSL=true \
     ./setup-ubuntu-server.sh

# Setup without Docker (for lightweight deployment)
sudo INSTALL_DOCKER=false ./setup-ubuntu-server.sh
```

## 📋 What the Script Does

### System Updates & Dependencies
- ✅ Updates Ubuntu 24.04 to latest packages
- ✅ Installs essential system tools (curl, wget, git, etc.)
- ✅ Installs Python 3.12 with pip and virtual environment support
- ✅ Installs Node.js 20 with npm and global packages
- ✅ Installs Docker and Docker Compose (optional)
- ✅ Installs Nginx web server (optional)

### Security Configuration
- ✅ Configures UFW firewall with secure defaults
- ✅ Sets up Fail2ban for intrusion prevention
- ✅ Creates dedicated application user with limited privileges
- ✅ Configures SSL/TLS with Let's Encrypt (optional)
- ✅ Applies security-focused system optimizations

### Application Environment
- ✅ Creates application directory structure
- ✅ Sets up Python virtual environment with dependencies
- ✅ Creates systemd service for application management
- ✅ Configures Nginx reverse proxy
- ✅ Sets up log rotation and monitoring
- ✅ Creates backup system with automated scheduling

### Monitoring & Maintenance
- ✅ Health check scripts with automatic restart
- ✅ System monitoring for disk, memory, and load
- ✅ Automated daily backups
- ✅ Log rotation for application and system logs
- ✅ Performance optimizations for production use

## 🔧 Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_USER` | `price-monitor` | Application user name |
| `APP_DIR` | `/opt/price-monitor` | Application directory |
| `APP_PORT` | `8080` | Application port |
| `PYTHON_VERSION` | `3.12` | Python version to install |
| `NODE_VERSION` | `20` | Node.js version to install |
| `INSTALL_DOCKER` | `true` | Install Docker and Docker Compose |
| `INSTALL_NGINX` | `true` | Install and configure Nginx |
| `SETUP_FIREWALL` | `true` | Configure UFW firewall |
| `SETUP_SSL` | `false` | Setup SSL with Let's Encrypt |
| `DOMAIN_NAME` | `""` | Domain name for SSL certificate |
| `EMAIL_ADDRESS` | `""` | Email for SSL certificate registration |

### Usage Examples

#### Development Server
```bash
sudo APP_PORT=3000 \
     INSTALL_DOCKER=false \
     SETUP_FIREWALL=false \
     ./setup-ubuntu-server.sh
```

#### Production Server with SSL
```bash
sudo DOMAIN_NAME=monitor.yourdomain.com \
     EMAIL_ADDRESS=admin@yourdomain.com \
     SETUP_SSL=true \
     ./setup-ubuntu-server.sh
```

#### Minimal Setup (No Docker/Nginx)
```bash
sudo INSTALL_DOCKER=false \
     INSTALL_NGINX=false \
     SETUP_FIREWALL=false \
     ./setup-ubuntu-server.sh
```

## 📁 Directory Structure Created

```
/opt/price-monitor/
├── config/
│   └── production.properties    # Application configuration
├── logs/                        # Application logs
├── data/                        # Database and application data
├── certs/                       # SSL certificates (if mTLS enabled)
├── backups/                     # Automated backups
├── static/                      # Static web assets
├── venv/                        # Python virtual environment
├── src/                         # Application source code (after deployment)
├── requirements.txt             # Python dependencies
├── health-check.sh             # Health monitoring script
├── backup.sh                   # Backup script
└── deploy-app.sh               # Application deployment script
```

## 🔐 Security Features

### Firewall Configuration
- **SSH (22)**: Restricted access
- **HTTP (80)**: Web traffic
- **HTTPS (443)**: Secure web traffic
- **Application Port**: Direct application access
- **Default Policy**: Deny incoming, allow outgoing

### Fail2ban Protection
- **SSH Protection**: Blocks brute force attempts
- **Nginx Protection**: Blocks malicious web requests
- **Rate Limiting**: Prevents abuse and DoS attacks

### User Security
- **Non-root Execution**: Application runs as dedicated user
- **Limited Privileges**: Minimal required permissions
- **Secure File Permissions**: Proper ownership and access controls

### SSL/TLS Support
- **Let's Encrypt Integration**: Free SSL certificates
- **Automatic Renewal**: Certificates auto-renew before expiration
- **HTTPS Redirect**: Automatic HTTP to HTTPS redirection
- **Security Headers**: Modern security headers configured

## 📊 Monitoring & Logging

### Health Monitoring
- **Application Health**: Checks `/health` endpoint every 5 minutes
- **Automatic Restart**: Restarts service if health check fails
- **System Monitoring**: Tracks disk, memory, and CPU usage
- **Alert Logging**: Logs warnings for resource usage

### Log Management
- **Application Logs**: `/opt/price-monitor/logs/price_monitor.log`
- **System Logs**: `journalctl -u price-monitor`
- **Nginx Logs**: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`
- **Health Check Logs**: `/var/log/price-monitor-health.log`
- **Backup Logs**: `/opt/price-monitor/logs/backup.log`

### Log Rotation
- **Daily Rotation**: Logs rotated daily
- **Compression**: Old logs compressed to save space
- **Retention**: 14 days for application logs, 52 days for Nginx logs
- **Automatic Cleanup**: Old logs automatically removed

## 💾 Backup System

### Automated Backups
- **Daily Schedule**: Runs at 2 AM daily
- **Database Backup**: SQLite database files
- **Configuration Backup**: Application configuration files
- **Log Backup**: Recent log files (last 7 days)
- **Retention Policy**: 30 days retention for all backups

### Manual Backup
```bash
# Run backup manually
sudo -u price-monitor /opt/price-monitor/backup.sh

# Restore from backup
sudo -u price-monitor cp /opt/price-monitor/backups/database_YYYYMMDD_HHMMSS.db /opt/price-monitor/data/price_monitor.db
```

## 🚀 Application Deployment

### After Server Setup

1. **Configure Application**:
```bash
sudo nano /opt/price-monitor/config/production.properties
```

2. **Deploy Application Code**:
```bash
# Set repository URL
export REPO_URL=https://github.com/your-username/price-monitor.git

# Deploy application
sudo -u price-monitor /opt/price-monitor/deploy-app.sh
```

3. **Start Application**:
```bash
sudo systemctl start price-monitor
sudo systemctl enable price-monitor
```

4. **Verify Deployment**:
```bash
# Check service status
sudo systemctl status price-monitor

# Test health endpoint
curl http://localhost:8080/health

# Check logs
sudo journalctl -u price-monitor -f
```

### Application Management

```bash
# Start/Stop/Restart service
sudo systemctl start price-monitor
sudo systemctl stop price-monitor
sudo systemctl restart price-monitor

# View logs
sudo journalctl -u price-monitor -f
tail -f /opt/price-monitor/logs/price_monitor.log

# Check application status
curl http://localhost:8080/health

# Update application
sudo -u price-monitor /opt/price-monitor/deploy-app.sh
```

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status price-monitor

# Check logs for errors
sudo journalctl -u price-monitor -n 50

# Verify configuration
sudo -u price-monitor /opt/price-monitor/venv/bin/python -m src.main --check-config
```

#### Port Already in Use
```bash
# Check what's using the port
sudo netstat -tlnp | grep :8080

# Kill process using the port
sudo kill -9 $(sudo lsof -t -i:8080)
```

#### Permission Issues
```bash
# Fix ownership
sudo chown -R price-monitor:price-monitor /opt/price-monitor

# Fix permissions
sudo chmod -R 755 /opt/price-monitor
sudo chmod -R 700 /opt/price-monitor/certs
sudo chmod 600 /opt/price-monitor/config/production.properties
```

#### SSL Certificate Issues
```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew

# Test Nginx configuration
sudo nginx -t
```

### Log Locations

- **Setup Log**: `/var/log/price-monitor-setup.log`
- **Application Logs**: `/opt/price-monitor/logs/`
- **System Logs**: `journalctl -u price-monitor`
- **Nginx Logs**: `/var/log/nginx/`
- **Health Check Logs**: `/var/log/price-monitor-health.log`
- **System Monitor Logs**: `/var/log/system-monitor.log`

## 🔄 Updates and Maintenance

### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
sudo -u price-monitor /opt/price-monitor/venv/bin/pip install --upgrade -r /opt/price-monitor/requirements.txt

# Restart application after updates
sudo systemctl restart price-monitor
```

### Security Updates
```bash
# Update fail2ban rules
sudo fail2ban-client reload

# Update firewall rules
sudo ufw status
sudo ufw reload

# Check for security updates
sudo unattended-upgrades --dry-run
```

### Performance Monitoring
```bash
# Check system resources
htop
df -h
free -h

# Check application performance
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8080/health

# Monitor logs for errors
sudo journalctl -u price-monitor --since "1 hour ago" | grep ERROR
```

## 📞 Support

### Getting Help

1. **Check Logs**: Always start by checking the relevant log files
2. **Verify Configuration**: Ensure all configuration files are correct
3. **Test Connectivity**: Verify network connectivity and firewall rules
4. **Resource Usage**: Check system resources (disk, memory, CPU)
5. **Service Status**: Verify all services are running correctly

### Useful Commands

```bash
# Complete system status check
sudo systemctl status price-monitor nginx fail2ban ufw

# Check all logs
sudo journalctl -u price-monitor -n 100
tail -f /opt/price-monitor/logs/price_monitor.log
tail -f /var/log/nginx/error.log

# Test application
curl -I http://localhost:8080/health
curl -I http://localhost/health

# Check security
sudo fail2ban-client status
sudo ufw status verbose
```

The setup script provides a robust, production-ready environment for the Price Monitor application with comprehensive security, monitoring, and maintenance features built-in.