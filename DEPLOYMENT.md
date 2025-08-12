# Price Monitor Deployment Guide

This guide covers deploying the Price Monitor application using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10 or later
- Docker Compose 2.0 or later
- SSL/TLS certificates for mTLS authentication (if enabled)

## Quick Start

### Development Deployment (No mTLS)

1. **Clone and prepare the environment:**
   ```bash
   git clone <repository-url>
   cd price-monitor
   cp .env.example .env
   ```

2. **Start development environment:**
   ```bash
   # Uses docker-compose.override.yml automatically
   docker-compose up -d
   ```

3. **Access the application:**
   - Web interface: http://localhost:8080
   - Health check: http://localhost:8080/health

### Production Deployment (With mTLS)

1. **Prepare certificates:**
   ```bash
   # Place your SSL certificates in ./certs/
   mkdir -p certs
   # Copy server.crt, server.key, ca.crt, and client certificates
   ```

2. **Configure for production:**
   ```bash
   cp .env.example .env
   # Edit .env with production settings
   ```

3. **Deploy with production configuration:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

4. **Verify deployment:**
   ```bash
   docker-compose ps
   docker-compose logs -f price-monitor
   ```

## Directory Structure

```
price-monitor/
├── config/                 # Configuration files (mounted read-only)
│   ├── default.properties  # Main configuration file
│   └── example.properties  # Example configuration
├── certs/                  # SSL/TLS certificates (mounted read-only)
│   ├── server.crt         # Server certificate
│   ├── server.key         # Server private key
│   ├── ca.crt             # Certificate Authority
│   └── client-certs/      # Client certificates directory
├── data/                   # Persistent data (database)
│   └── price_monitor.db   # SQLite database file
├── logs/                   # Application logs
│   └── price_monitor.log  # Main log file
├── static/                 # Web interface files (mounted read-only)
│   ├── index.html         # Main dashboard
│   ├── styles.css         # Stylesheet
│   └── app.js             # JavaScript application
├── docker-compose.yml      # Docker Compose configuration
├── .env                    # Environment variables (create from .env.example)
└── .env.example           # Environment variables template
```

## Configuration

### Environment Variables

The application supports configuration through environment variables. Copy `.env.example` to `.env` and customize:

```bash
# API Configuration
API_PORT=8443
FLASK_ENV=production

# Application Settings
LOG_LEVEL=INFO
CHECK_FREQUENCY_HOURS=24
CHECK_TIME=09:00
ENABLE_MTLS=true

# Email Settings (optional overrides)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
RECIPIENT_EMAIL=notifications@example.com
```

### Configuration File

Create `./config/default.properties` with your application settings:

```properties
# Database configuration
database_path=/app/data/price_monitor.db

# Email configuration
smtp_server=smtp.gmail.com
smtp_port=587
smtp_username=your-email@gmail.com
smtp_password=your-app-password
recipient_email=notifications@example.com

# Monitoring configuration
check_frequency_hours=24
check_time=09:00
request_timeout_seconds=30
max_retry_attempts=3

# Security configuration
enable_mtls=true
api_port=8443
server_cert_path=/app/certs/server.crt
server_key_path=/app/certs/server.key
ca_cert_path=/app/certs/ca.crt
client_cert_required=true

# Logging configuration
log_level=INFO
log_file_path=/app/logs/price_monitor.log

# AI/Parsing configuration (optional)
enable_ai_parsing=false
ai_api_key=
ai_api_endpoint=
```

### SSL/TLS Certificates (mTLS)

If using mTLS authentication, place certificates in `./certs/`:

```bash
./certs/
├── server.crt      # Server certificate
├── server.key      # Server private key
├── ca.crt          # Certificate Authority
└── client-certs/   # Client certificates
    ├── client1.crt
    ├── client1.key
    └── ...
```

**Certificate permissions:**
```bash
chmod 600 ./certs/*.key
chmod 644 ./certs/*.crt
```

## Deployment Modes

The application supports three deployment modes:

### 1. Development Mode (Default)
- **Configuration**: `docker-compose.yml` + `docker-compose.override.yml`
- **Features**: HTTP only, debug logging, no mTLS, relaxed security
- **Usage**: `docker-compose up -d`
- **Access**: http://localhost:8080

### 2. Production Mode
- **Configuration**: `docker-compose.yml` + `docker-compose.prod.yml`
- **Features**: HTTPS with mTLS, production logging, enhanced security
- **Usage**: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- **Access**: https://localhost:8443 (requires client certificate)

### 3. Custom Mode
- **Configuration**: Custom docker-compose files or environment variables
- **Features**: Fully customizable through .env file and volume mounts
- **Usage**: Modify .env and use standard docker-compose commands

## Deployment Commands

### Development Deployment
```bash
# Build and start in development mode
docker-compose up -d --build

# View logs
docker-compose logs -f price-monitor

# Check container status
docker-compose ps
```

### Production Deployment
```bash
# Build and start in production mode
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f price-monitor

# Check container status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Management Commands
```bash
# Stop the application
docker-compose stop

# Restart the application
docker-compose restart

# Update and restart
docker-compose pull
docker-compose up -d

# Remove containers and volumes
docker-compose down -v
```

### Health Checks
```bash
# Check container health
docker-compose ps

# Manual health check
curl -k https://localhost:8443/health

# View health check logs
docker inspect price-monitor | grep -A 10 Health
```

## Monitoring and Maintenance

### Log Management
- Logs are automatically rotated (max 10MB, 3 files)
- Application logs: `./logs/price_monitor.log`
- Container logs: `docker-compose logs price-monitor`

### Database Backup
```bash
# Backup database
docker-compose exec price-monitor cp /app/data/price_monitor.db /app/data/backup_$(date +%Y%m%d_%H%M%S).db

# Copy backup to host
docker cp price-monitor:/app/data/backup_*.db ./backups/
```

### Resource Monitoring
```bash
# Monitor resource usage
docker stats price-monitor

# View container processes
docker-compose exec price-monitor ps aux
```

## Security Considerations

### Container Security
- Runs as non-root user (`appuser`)
- Read-only root filesystem with specific writable directories
- No new privileges allowed
- Resource limits enforced

### Network Security
- Only exposes necessary port (8443)
- mTLS authentication for API access
- Security headers enabled
- HTTPS-only communication

### File Permissions
```bash
# Set proper permissions
chmod -R 755 ./config ./static
chmod -R 750 ./data ./logs ./certs
chmod 600 ./certs/*.key
```

## Troubleshooting

### Common Issues

1. **Container won't start:**
   ```bash
   # Check logs
   docker-compose logs price-monitor
   
   # Check configuration
   docker-compose config
   ```

2. **Health check failing:**
   ```bash
   # Test health endpoint manually
   curl -k https://localhost:8443/health
   
   # Check certificate configuration
   openssl s_client -connect localhost:8443 -cert ./certs/client.crt -key ./certs/client.key
   ```

3. **Permission errors:**
   ```bash
   # Fix file permissions
   sudo chown -R $(id -u):$(id -g) ./data ./logs
   chmod -R 755 ./data ./logs
   ```

4. **Email notifications not working:**
   ```bash
   # Test email configuration
   docker-compose exec price-monitor python -c "
   from src.services.email_service import EmailService
   from src.services.config_service import ConfigService
   config = ConfigService().load_config('/app/config/default.properties')
   email_service = EmailService(config)
   result = email_service.test_email_connection()
   print(f'Email test: {result.success}, {result.message}')
   "
   ```

### Performance Tuning

1. **Adjust resource limits in docker-compose.yml:**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '1.0'
   ```

2. **Optimize check frequency:**
   - Reduce `CHECK_FREQUENCY_HOURS` for more frequent checks
   - Adjust `REQUEST_TIMEOUT_SECONDS` based on network conditions

3. **Database optimization:**
   - Regular database cleanup of old price history
   - Monitor database size growth

## Production Deployment

### Additional Considerations

1. **Use external secrets management:**
   ```yaml
   # docker-compose.yml
   secrets:
     smtp_password:
       external: true
   ```

2. **Set up log aggregation:**
   ```yaml
   logging:
     driver: "syslog"
     options:
       syslog-address: "tcp://logserver:514"
   ```

3. **Configure reverse proxy:**
   ```nginx
   # nginx.conf
   upstream price-monitor {
       server localhost:8443;
   }
   
   server {
       listen 443 ssl;
       server_name price-monitor.example.com;
       
       location / {
           proxy_pass https://price-monitor;
           proxy_ssl_verify off;
       }
   }
   ```

4. **Set up monitoring:**
   - Container health monitoring
   - Application metrics collection
   - Alert configuration for failures

## Testing the Deployment

### Basic Functionality Test
```bash
# 1. Check container is running
docker-compose ps

# 2. Test health endpoint
curl -k https://localhost:8443/health

# 3. Test web interface (if mTLS disabled for testing)
curl -k https://localhost:8443/

# 4. Test API endpoints (with client certificate)
curl -k --cert ./certs/client.crt --key ./certs/client.key \
     https://localhost:8443/api/products

# 5. Check logs for errors
docker-compose logs price-monitor | grep -i error
```

### Load Testing
```bash
# Simple load test
for i in {1..10}; do
  curl -k --cert ./certs/client.crt --key ./certs/client.key \
       https://localhost:8443/health &
done
wait
```

This deployment guide provides comprehensive instructions for deploying and managing the Price Monitor application in a production environment.