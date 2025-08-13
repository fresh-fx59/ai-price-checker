# Production Deployment Summary - price-monitor.flowvian.com

## 🚀 Current Production Configuration

The Price Monitor application is successfully deployed at **price-monitor.flowvian.com** with a hybrid SSL/mTLS configuration.

### Architecture Overview

```
Internet → Nginx (443/SSL) → mTLS Proxy → Python App (8443/mTLS) → SQLite
```

### SSL/TLS Configuration

1. **Public SSL**: Let's Encrypt certificates for price-monitor.flowvian.com
2. **mTLS Backend**: Self-signed CA for client certificate authentication
3. **Nginx Proxy**: Handles SSL termination and mTLS proxy to backend

## 📋 Working Configuration Files

### Nginx Configuration (`/etc/nginx/sites-available/price-monitor`)

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name price-monitor.flowvian.com;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server with mTLS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name price-monitor.flowvian.com;
    
    # Let's Encrypt SSL certificates
    ssl_certificate /etc/letsencrypt/live/price-monitor.flowvian.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/price-monitor.flowvian.com/privkey.pem;
    
    # Client certificate validation
    ssl_client_certificate /opt/price-monitor/certs/ca.crt;
    ssl_verify_client on;
    
    # Proxy to mTLS backend
    location / {
        proxy_pass https://127.0.0.1:8443;
        proxy_ssl_certificate /opt/price-monitor/certs/nginx-client.crt;
        proxy_ssl_certificate_key /opt/price-monitor/certs/nginx-client.key;
        proxy_ssl_trusted_certificate /opt/price-monitor/certs/ca.crt;
        proxy_ssl_verify on;
        # ... additional proxy headers
    }
}
```

### Application Configuration

- **Domain**: price-monitor.flowvian.com
- **Public Port**: 443 (HTTPS)
- **Backend Port**: 8443 (mTLS)
- **SSL Certificates**: Let's Encrypt (auto-renewal enabled)
- **Client Certificates**: Self-signed CA for mTLS authentication

## 🔐 Certificate Management

### Certificate Types

1. **Let's Encrypt Certificates** (Public SSL)
   - Location: `/etc/letsencrypt/live/price-monitor.flowvian.com/`
   - Auto-renewal: Enabled via cron
   - Used for: Public HTTPS access

2. **Self-Signed CA** (mTLS)
   - Location: `/opt/price-monitor/certs/ca.crt`
   - Used for: Client certificate validation

3. **Client Certificates** (mTLS Authentication)
   - Location: `/opt/price-monitor/certs/`
   - Types: admin-client, api-client, nginx-client
   - Used for: Authenticated access to the application

### Certificate Generation

```bash
# Generate client certificates
./generate-client-certs.sh admin-client 365
./generate-client-certs.sh nginx-client 365

# Configure nginx with mTLS
sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com

# Import certificates on macOS
sudo ./import-certs-macos.sh
```

## 🧪 Testing the Configuration

### Health Check Tests

```bash
# Test with valid client certificate
curl --cert certs/admin-client.crt \
     --key certs/admin-client.key \
     https://price-monitor.flowvian.com/health

# Expected response: {"status": "healthy", ...}

# Test without certificate (should fail)
curl https://price-monitor.flowvian.com/health
# Expected: 400 Bad Request (No required SSL certificate was sent)
```

### Browser Access

1. Import `certs/admin-client.p12` into your browser
2. Navigate to https://price-monitor.flowvian.com
3. Browser will prompt for client certificate selection
4. Select the imported certificate to access the application

## 🔧 Deployment Scripts

### Updated Scripts

1. **`setup-nginx-mtls.sh`** - New script for nginx mTLS configuration
2. **`generate-client-certs.sh`** - Enhanced with nginx-client certificate generation
3. **`import-certs-macos.sh`** - Updated for production domain and PKCS#12 export

### Script Usage

```bash
# Complete production setup
sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com
./generate-client-certs.sh admin-client 365
sudo ./import-certs-macos.sh

# Test the deployment
curl --cert certs/admin-client.crt \
     --key certs/admin-client.key \
     https://price-monitor.flowvian.com/health
```

## 📊 Monitoring and Maintenance

### Health Monitoring

- **Endpoint**: https://price-monitor.flowvian.com/health
- **Authentication**: Requires valid client certificate
- **Monitoring**: Automated health checks with client certificate

### Certificate Renewal

- **Let's Encrypt**: Auto-renewal via certbot cron job
- **Client Certificates**: Manual renewal (365-day validity)
- **Monitoring**: Certificate expiration alerts

### Log Locations

- **Application**: `/opt/price-monitor/logs/price_monitor.log`
- **Nginx Access**: `/var/log/nginx/access.log`
- **Nginx Error**: `/var/log/nginx/error.log`
- **SSL/TLS**: Included in nginx error log

## 🚨 Troubleshooting

### Common Issues

#### Certificate Not Accepted
```bash
# Verify certificate chain
openssl verify -CAfile certs/ca.crt certs/admin-client.crt

# Check certificate details
openssl x509 -in certs/admin-client.crt -text -noout
```

#### Nginx Configuration Issues
```bash
# Test nginx configuration
sudo nginx -t

# Check nginx status
sudo systemctl status nginx

# Reload nginx configuration
sudo systemctl reload nginx
```

#### SSL Certificate Issues
```bash
# Check Let's Encrypt certificate
sudo certbot certificates

# Test SSL configuration
openssl s_client -connect price-monitor.flowvian.com:443 -servername price-monitor.flowvian.com
```

### Debug Commands

```bash
# Test mTLS connection
openssl s_client -connect price-monitor.flowvian.com:443 \
    -cert certs/admin-client.crt \
    -key certs/admin-client.key

# Check certificate expiration
openssl x509 -in certs/admin-client.crt -noout -dates

# Monitor nginx logs
sudo tail -f /var/log/nginx/error.log
```

## 🔄 Updates and Maintenance

### Regular Maintenance Tasks

1. **Monitor Certificate Expiration**
   ```bash
   # Check Let's Encrypt certificates
   sudo certbot certificates
   
   # Check client certificates
   openssl x509 -in certs/admin-client.crt -noout -dates
   ```

2. **Update Client Certificates**
   ```bash
   # Renew client certificates before expiration
   ./generate-client-certs.sh admin-client 365
   ```

3. **Monitor Application Health**
   ```bash
   # Automated health check with client certificate
   curl --cert certs/admin-client.crt \
        --key certs/admin-client.key \
        https://price-monitor.flowvian.com/health
   ```

### Security Best Practices

- ✅ Let's Encrypt certificates for public SSL
- ✅ Self-signed CA for mTLS (not exposed to public)
- ✅ Client certificate authentication required
- ✅ Nginx security headers configured
- ✅ HTTP to HTTPS redirect enforced
- ✅ Certificate auto-renewal enabled

## 📞 Support

### Quick Reference

- **Domain**: price-monitor.flowvian.com
- **Public Port**: 443 (HTTPS)
- **Backend Port**: 8443 (mTLS)
- **Health Check**: `curl --cert certs/admin-client.crt --key certs/admin-client.key https://price-monitor.flowvian.com/health`
- **Configuration**: `/etc/nginx/sites-available/price-monitor`
- **Certificates**: `/opt/price-monitor/certs/`

### Emergency Procedures

1. **Disable mTLS temporarily**:
   ```bash
   sudo sed -i 's/ssl_verify_client on;/ssl_verify_client optional;/' /etc/nginx/sites-available/price-monitor
   sudo systemctl reload nginx
   ```

2. **Restore from backup**:
   ```bash
   sudo cp /etc/nginx/backup/price-monitor.* /etc/nginx/sites-available/price-monitor
   sudo systemctl reload nginx
   ```

The production deployment is stable and secure with proper SSL/mTLS configuration, automated certificate renewal, and comprehensive monitoring capabilities.