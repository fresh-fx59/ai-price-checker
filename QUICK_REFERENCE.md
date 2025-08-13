# Price Monitor - Quick Reference

## 🌐 Production Access

**Domain**: price-monitor.flowvian.com  
**Protocol**: HTTPS with mTLS authentication  
**Health Check**: `curl --cert certs/admin-client.crt --key certs/admin-client.key https://price-monitor.flowvian.com/health`

## 🔐 Certificate Commands

### Generate Client Certificates
```bash
# Admin certificate (365 days)
./generate-client-certs.sh admin-client 365

# API client certificate (30 days)
./generate-client-certs.sh api-client 30

# Nginx proxy certificate
./generate-client-certs.sh nginx-client 365
```

### Import Certificates (macOS)
```bash
# Import all certificates to System Keychain
sudo ./import-certs-macos.sh

# Manual browser import
open certs/admin-client.p12
```

## 🔧 Nginx Configuration

### Setup mTLS Proxy
```bash
# Configure nginx for production domain
sudo ./setup-nginx-mtls.sh price-monitor.flowvian.com

# Test configuration
sudo nginx -t

# Reload configuration
sudo systemctl reload nginx
```

### Configuration File Location
```
/etc/nginx/sites-available/price-monitor
```

## 🧪 Testing Commands

### Health Check with Certificate
```bash
curl --cert certs/admin-client.crt \
     --key certs/admin-client.key \
     https://price-monitor.flowvian.com/health
```

### Test Without Certificate (Should Fail)
```bash
curl https://price-monitor.flowvian.com/health
# Expected: 400 Bad Request
```

### Test SSL Connection
```bash
openssl s_client -connect price-monitor.flowvian.com:443 \
    -cert certs/admin-client.crt \
    -key certs/admin-client.key
```

## 📁 File Locations

### Certificates
- **CA Certificate**: `/opt/price-monitor/certs/ca.crt`
- **Client Certificates**: `/opt/price-monitor/certs/*.crt`
- **Private Keys**: `/opt/price-monitor/certs/*.key`
- **Let's Encrypt**: `/etc/letsencrypt/live/price-monitor.flowvian.com/`

### Configuration
- **Nginx Config**: `/etc/nginx/sites-available/price-monitor`
- **App Config**: `/opt/price-monitor/config/production.properties`
- **SSL Certificates**: `/etc/letsencrypt/live/price-monitor.flowvian.com/`

### Logs
- **Application**: `/opt/price-monitor/logs/price_monitor.log`
- **Nginx Access**: `/var/log/nginx/access.log`
- **Nginx Error**: `/var/log/nginx/error.log`

## 🚨 Troubleshooting

### Certificate Issues
```bash
# Verify certificate chain
openssl verify -CAfile certs/ca.crt certs/admin-client.crt

# Check certificate expiration
openssl x509 -in certs/admin-client.crt -noout -dates

# View certificate details
openssl x509 -in certs/admin-client.crt -text -noout
```

### Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Check status
sudo systemctl status nginx

# View error logs
sudo tail -f /var/log/nginx/error.log
```

### Application Issues
```bash
# Check application status
sudo systemctl status price-monitor

# View application logs
sudo journalctl -u price-monitor -f

# Test local backend
curl -k --cert certs/admin-client.crt \
       --key certs/admin-client.key \
       https://localhost:8443/health
```

## 🔄 Maintenance

### Certificate Renewal
```bash
# Let's Encrypt (automatic)
sudo certbot renew

# Client certificates (manual)
./generate-client-certs.sh admin-client 365
```

### Service Management
```bash
# Restart application
sudo systemctl restart price-monitor

# Reload nginx
sudo systemctl reload nginx

# Check all services
sudo systemctl status price-monitor nginx
```

## 📞 Emergency Commands

### Disable mTLS Temporarily
```bash
sudo sed -i 's/ssl_verify_client on;/ssl_verify_client optional;/' \
    /etc/nginx/sites-available/price-monitor
sudo systemctl reload nginx
```

### Restore mTLS
```bash
sudo sed -i 's/ssl_verify_client optional;/ssl_verify_client on;/' \
    /etc/nginx/sites-available/price-monitor
sudo systemctl reload nginx
```

### Backup Configuration
```bash
sudo cp /etc/nginx/sites-available/price-monitor \
       /etc/nginx/backup/price-monitor.$(date +%Y%m%d_%H%M%S)
```