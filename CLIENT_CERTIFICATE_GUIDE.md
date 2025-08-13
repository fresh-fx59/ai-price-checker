# Client Certificate Setup Guide for Price Monitor

This guide explains how to issue and manage client certificates for mTLS authentication in your Price Monitor application running on price-monitor.flowvian.com.

## 🔐 Overview

Your Price Monitor application supports a hybrid SSL/TLS setup:

1. **Server Certificates**: Let's Encrypt certificates for public HTTPS (price-monitor.flowvian.com)
2. **Client Certificates**: Self-signed certificates for mTLS authentication
3. **Nginx Proxy**: Handles public SSL termination and proxies to mTLS backend on port 8443

## 🚀 Quick Start

### Production Setup (price-monitor.flowvian.com)

The production setup uses Let's Encrypt for public SSL and self-signed certificates for mTLS:

```bash
# 1. Generate client certificates for mTLS authentication
./generate-client-certs.sh admin-client 365
./generate-client-certs.sh api-client 30
./generate-client-certs.sh nginx-client 365  # For nginx proxy

# 2. Configure nginx with mTLS proxy
sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com

# 3. Import certificates on macOS (optional)
sudo ./import-certs-macos.sh
```

### Development Setup

For local development with self-signed certificates:

```bash
# Generate all certificates locally
./generate-client-certs.sh admin-client 365

# Configure nginx for local development
sudo DOMAIN_NAME=localhost USE_LETSENCRYPT=false ./setup-nginx-mtls.sh
```

## 📋 Detailed Setup Instructions

### 1. Server Certificate Setup (Let's Encrypt)

The production domain price-monitor.flowvian.com uses Let's Encrypt certificates:

```bash
# Using the nginx mTLS setup script (recommended)
sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com

# Or manually with certbot
sudo certbot --nginx -d price-monitor.flowvian.com \
     --email admin@flowvian.com \
     --agree-tos --non-interactive

# Or using the Ubuntu server setup script
sudo DOMAIN_NAME=price-monitor.flowvian.com \
     EMAIL_ADDRESS=admin@flowvian.com \
     SETUP_SSL=true \
     ./setup-ubuntu-server.sh
```

### 2. Client Certificate Generation

#### Generate CA and Client Certificates

```bash
# Generate your first client certificate
./generate-client-certs.sh admin-client

# This creates:
# - ./certs/ca.crt (Certificate Authority)
# - ./certs/ca.key (CA private key)
# - ./certs/server.crt (Server certificate)
# - ./certs/server.key (Server private key)
# - ./certs/admin-client.crt (Client certificate)
# - ./certs/admin-client.key (Client private key)
```

#### Generate Additional Client Certificates

```bash
# Generate certificates for different users/systems
./generate-client-certs.sh api-user 365
./generate-client-certs.sh monitoring-system 30
./generate-client-certs.sh backup-service 90

# Generate nginx client certificate for proxy mTLS
./generate-client-certs.sh nginx-client 365
```

### 3. Application Configuration

#### Configure mTLS in your application

Edit `./config/default.properties`:

```properties
# Enable mTLS
enable_mtls=true
api_port=8443

# Certificate paths
server_cert_path=/app/certs/server.crt
server_key_path=/app/certs/server.key
ca_cert_path=/app/certs/ca.crt
client_cert_required=true

# Security settings
request_timeout_seconds=30
max_retry_attempts=3
```

#### Configure Docker environment

Edit `.env` file:

```bash
# API Configuration
API_PORT=8443
FLASK_ENV=production

# Enable mTLS
ENABLE_MTLS=true

# Logging
LOG_LEVEL=INFO
```

### 4. Deploy with mTLS

```bash
# Deploy in production mode with mTLS
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check deployment
docker-compose ps
docker-compose logs -f price-monitor

# Verify nginx configuration
sudo nginx -t
sudo systemctl status nginx
```

## 🧪 Testing Client Certificates

### Test with curl

```bash
# Test production domain with client certificate
curl --cert ./certs/admin-client.crt \
     --key ./certs/admin-client.key \
     https://price-monitor.flowvian.com/health

# Test API endpoints
curl --cert ./certs/api-user.crt \
     --key ./certs/api-user.key \
     https://price-monitor.flowvian.com/api/products

# Test without certificate (should fail with 400 Bad Request)
curl https://price-monitor.flowvian.com/health

# Test local development
curl -k --cert ./certs/admin-client.crt \
       --key ./certs/admin-client.key \
       https://localhost:8443/health
```

### Test with browser

Convert certificate to PKCS#12 format for browser import:

```bash
# Create PKCS#12 certificate for browser
openssl pkcs12 -export -in ./certs/admin-client.crt \
               -inkey ./certs/admin-client.key \
               -out ./certs/admin-client.p12 \
               -name "Price Monitor Admin Client"

# Import admin-client.p12 into your browser's certificate store
```

## 🔄 Certificate Management

### Certificate Information

```bash
# View certificate details
openssl x509 -in ./certs/admin-client.crt -text -noout

# Check certificate expiration
openssl x509 -in ./certs/admin-client.crt -noout -dates

# Verify certificate chain
openssl verify -CAfile ./certs/ca.crt ./certs/admin-client.crt
```

### Certificate Renewal

#### Renew Client Certificates

```bash
# Renew a client certificate (generates new certificate with same name)
./generate-client-certs.sh admin-client 365

# Restart application to reload certificates
docker-compose restart
```

#### Renew Server Certificates (Let's Encrypt)

```bash
# Manual renewal
sudo certbot renew

# Copy renewed certificates to application
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./certs/server.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./certs/server.key

# Restart application
docker-compose restart
```

### Revoke Client Certificates

```bash
# Remove client certificate files
rm ./certs/compromised-client.crt
rm ./certs/compromised-client.key

# Restart application to reload certificate list
docker-compose restart
```

## 🔧 Advanced Configuration

### Multiple Client CAs

For enterprise environments with multiple certificate authorities:

```bash
# Create separate CAs for different departments
./generate-client-certs.sh admin-dept-user 365
./generate-client-certs.sh api-dept-user 365

# Combine CA certificates
cat ./certs/ca.crt ./certs/dept-ca.crt > ./certs/combined-ca.crt
```

### Certificate Validation Levels

Configure different validation levels in `./config/default.properties`:

```properties
# Strict validation (default)
client_cert_required=true
verify_client_cert=true

# Optional client certificates
client_cert_required=false
verify_client_cert=true

# No client certificate validation (disable mTLS)
enable_mtls=false
```

### Custom Certificate Extensions

For advanced use cases, modify the certificate generation script:

```bash
# Add custom extensions to client certificates
# Edit generate-client-certs.sh and modify the v3_req section:

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = clientAuth
subjectAltName = @alt_names

[alt_names]
email.1 = user@company.com
URI.1 = https://company.com/users/admin
```

## 🚨 Troubleshooting

### Common Issues

#### Certificate Not Accepted

```bash
# Check certificate format
file ./certs/admin-client.crt

# Verify certificate chain
openssl verify -CAfile ./certs/ca.crt ./certs/admin-client.crt

# Check certificate purpose
openssl x509 -in ./certs/admin-client.crt -noout -purpose
```

#### Connection Refused

```bash
# Check if application is running
docker-compose ps

# Check application logs
docker-compose logs price-monitor

# Test without SSL
curl http://localhost:8080/health  # if HTTP port is exposed
```

#### Certificate Expired

```bash
# Check expiration date
openssl x509 -in ./certs/admin-client.crt -noout -dates

# Regenerate expired certificate
./generate-client-certs.sh admin-client 365
```

### Debug Commands

```bash
# Test SSL connection
openssl s_client -connect localhost:8443 \
                 -cert ./certs/admin-client.crt \
                 -key ./certs/admin-client.key

# Check certificate details
curl -k -v --cert ./certs/admin-client.crt \
           --key ./certs/admin-client.key \
           https://localhost:8443/health

# Monitor application logs
docker-compose logs -f price-monitor | grep -i ssl
```

## 📊 Certificate Monitoring

### Automated Monitoring

Create a monitoring script:

```bash
#!/bin/bash
# monitor-certificates.sh

CERT_DIR="./certs"
WARN_DAYS=30

for cert in "$CERT_DIR"/*.crt; do
    if [[ -f "$cert" ]]; then
        expiry=$(openssl x509 -in "$cert" -noout -enddate | cut -d= -f2)
        expiry_epoch=$(date -d "$expiry" +%s)
        current_epoch=$(date +%s)
        days_left=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [[ $days_left -lt $WARN_DAYS ]]; then
            echo "WARNING: Certificate $cert expires in $days_left days"
        fi
    fi
done
```

### Health Check Integration

Add certificate monitoring to your health checks:

```bash
# Add to health check endpoint
curl -k --cert ./certs/monitor-client.crt \
       --key ./certs/monitor-client.key \
       https://localhost:8443/health
```

## 🔒 Security Best Practices

### Certificate Security

1. **Protect Private Keys**: Set proper file permissions (600)
2. **Regular Rotation**: Rotate client certificates every 90-365 days
3. **Separate CAs**: Use different CAs for different environments
4. **Monitor Expiration**: Set up alerts for certificate expiration
5. **Secure Storage**: Store certificates in encrypted storage

### Access Control

```bash
# Set proper permissions
chmod 600 ./certs/*.key
chmod 644 ./certs/*.crt
chown app-user:app-group ./certs/*

# Restrict certificate directory access
chmod 750 ./certs
```

### Audit Trail

```bash
# Log certificate usage
tail -f ./logs/price_monitor.log | grep -i certificate

# Monitor certificate access
docker-compose logs price-monitor | grep -i "client certificate"
```

## 📞 Support

### Getting Help

1. **Check Logs**: `docker-compose logs price-monitor`
2. **Verify Certificates**: Use `openssl` commands to validate
3. **Test Connectivity**: Use `curl` with verbose output
4. **Check Configuration**: Verify `./config/default.properties`

### Useful Commands

```bash
# Complete certificate status
./generate-client-certs.sh --help
openssl x509 -in ./certs/ca.crt -text -noout
docker-compose exec price-monitor ls -la /app/certs/

# Application status
curl -k --cert ./certs/admin-client.crt \
       --key ./certs/admin-client.key \
       https://localhost:8443/health

# Certificate validation
openssl verify -CAfile ./certs/ca.crt ./certs/*.crt
```

This guide provides comprehensive instructions for managing client certificates in your Price Monitor application with both development and production scenarios covered.