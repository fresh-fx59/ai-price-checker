# Price Monitor Application

A comprehensive price monitoring application that tracks product prices and sends notifications when prices change. The application features a secure mTLS-enabled web interface and automated price checking capabilities.

## 🌐 Production Deployment

**Live Application**: https://price-monitor.flowvian.com

The application is deployed with enterprise-grade security:
- ✅ Let's Encrypt SSL certificates for public access
- ✅ mTLS (mutual TLS) authentication for secure API access
- ✅ Nginx reverse proxy with SSL termination
- ✅ Automated certificate management and renewal

## 🚀 Quick Start

### For Users (Client Certificate Required)

1. **Request Access**: Contact the administrator for client certificates
2. **Install Certificate**: Import the provided `.p12` certificate into your browser
3. **Access Application**: Navigate to https://price-monitor.flowvian.com
4. **API Access**: Use client certificates for programmatic access

### For Administrators

1. **Generate Client Certificates**:
   ```bash
   ./generate-client-certs.sh admin-client 365
   ```

2. **Configure mTLS Proxy**:
   ```bash
   sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com
   ```

3. **Import Certificates (macOS)**:
   ```bash
   sudo ./import-certs-macos.sh
   ```

## 📋 Documentation

- **[Production Deployment Summary](PRODUCTION_DEPLOYMENT_SUMMARY.md)** - Current production configuration
- **[Client Certificate Guide](CLIENT_CERTIFICATE_GUIDE.md)** - Complete mTLS setup guide
- **[Server Setup Guide](SERVER_SETUP_GUIDE.md)** - Ubuntu server installation
- **[Infrastructure Summary](INFRASTRUCTURE_SUMMARY.md)** - Terraform deployment guide

## 🔐 Security Features

- **mTLS Authentication**: Client certificates required for all access
- **Let's Encrypt SSL**: Automated public SSL certificate management
- **Nginx Security**: Modern security headers and configurations
- **Certificate Management**: Automated renewal and monitoring
