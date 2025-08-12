#!/bin/bash

# User Data Script for Price Monitor Application
# This script sets up the server environment and deploys the application

set -e

# Variables from Terraform
APP_PORT="${app_port}"
ENVIRONMENT="${environment}"
DB_HOST="${db_host}"
DB_NAME="${db_name}"
DB_USERNAME="${db_username}"
DB_PASSWORD="${db_password}"
SMTP_SERVER="${smtp_server}"
SMTP_PORT="${smtp_port}"
SMTP_USERNAME="${smtp_username}"
SMTP_PASSWORD="${smtp_password}"
RECIPIENT_EMAIL="${recipient_email}"
ENABLE_MTLS="${enable_mtls}"
DOMAIN_NAME="${domain_name}"

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting Price Monitor application setup..."
echo "Environment: $ENVIRONMENT"
echo "App Port: $APP_PORT"

# Update system
apt-get update -y
apt-get upgrade -y

# Install required packages
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    supervisor \
    postgresql-client \
    docker.io \
    docker-compose \
    awscli \
    curl \
    wget \
    unzip \
    htop \
    tree \
    jq

# Enable and start Docker
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# Install Docker Compose (latest version)
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create application directory
mkdir -p /opt/price-monitor
cd /opt/price-monitor

# Clone the application (assuming it's in a git repository)
# Note: In production, you would typically deploy from a CI/CD pipeline
# For now, we'll create the directory structure and copy files

# Create application user
useradd -r -s /bin/false price-monitor
chown -R price-monitor:price-monitor /opt/price-monitor

# Create configuration directory
mkdir -p /opt/price-monitor/config
mkdir -p /opt/price-monitor/logs
mkdir -p /opt/price-monitor/data
mkdir -p /opt/price-monitor/certs

# Create application configuration
cat > /opt/price-monitor/config/production.properties << EOF
[database]
path = /opt/price-monitor/data/price_monitor.db
host = $DB_HOST
port = 5432
name = $DB_NAME
username = $DB_USERNAME
password = $DB_PASSWORD

[email]
smtp_server = $SMTP_SERVER
smtp_port = $SMTP_PORT
username = $SMTP_USERNAME
password = $SMTP_PASSWORD
recipient = $RECIPIENT_EMAIL

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30
check_time = 09:00

[security]
enable_mtls = $ENABLE_MTLS
api_port = $APP_PORT
server_cert_path = /opt/price-monitor/certs/server.crt
server_key_path = /opt/price-monitor/certs/server.key
ca_cert_path = /opt/price-monitor/certs/ca.crt
client_cert_required = $ENABLE_MTLS

[app]
log_level = INFO
log_file = /opt/price-monitor/logs/price_monitor.log
environment = $ENVIRONMENT

[parsing]
enable_ai_parsing = true
EOF

# Create Docker Compose file for the application
cat > /opt/price-monitor/docker-compose.yml << EOF
version: '3.8'

services:
  price-monitor:
    image: price-monitor:latest
    container_name: price-monitor-app
    ports:
      - "$APP_PORT:$APP_PORT"
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./logs:/app/logs
      - ./certs:/app/certs:ro
    environment:
      - CONFIG_FILE=/app/config/production.properties
      - ENVIRONMENT=$ENVIRONMENT
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:$APP_PORT/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    container_name: price-monitor-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - price-monitor
    restart: unless-stopped
EOF

# Create Nginx configuration
cat > /opt/price-monitor/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    upstream price_monitor {
        server price-monitor-app:$APP_PORT;
    }

    server {
        listen 80;
        server_name $DOMAIN_NAME;

        # Redirect HTTP to HTTPS if domain is configured
        if (\$host = $DOMAIN_NAME) {
            return 301 https://\$server_name\$request_uri;
        }

        # Health check endpoint
        location /health {
            proxy_pass http://price_monitor;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        # Main application
        location / {
            proxy_pass http://price_monitor;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }

    server {
        listen 443 ssl http2;
        server_name $DOMAIN_NAME;

        ssl_certificate /etc/nginx/certs/server.crt;
        ssl_certificate_key /etc/nginx/certs/server.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        location / {
            proxy_pass http://price_monitor;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
EOF

# Create systemd service for the application
cat > /etc/systemd/system/price-monitor.service << EOF
[Unit]
Description=Price Monitor Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/price-monitor
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=root

[Install]
WantedBy=multi-user.target
EOF

# Create log rotation configuration
cat > /etc/logrotate.d/price-monitor << EOF
/opt/price-monitor/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 price-monitor price-monitor
    postrotate
        /usr/local/bin/docker-compose -f /opt/price-monitor/docker-compose.yml restart price-monitor
    endscript
}
EOF

# Set up CloudWatch agent (optional)
if [ "$ENVIRONMENT" = "production" ]; then
    wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
    dpkg -i amazon-cloudwatch-agent.deb

    # Create CloudWatch agent configuration
    cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/opt/price-monitor/logs/price_monitor.log",
                        "log_group_name": "/aws/ec2/price-monitor",
                        "log_stream_name": "{instance_id}/application.log"
                    },
                    {
                        "file_path": "/var/log/user-data.log",
                        "log_group_name": "/aws/ec2/price-monitor",
                        "log_stream_name": "{instance_id}/user-data.log"
                    }
                ]
            }
        }
    }
}
EOF

    # Start CloudWatch agent
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
        -a fetch-config \
        -m ec2 \
        -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
        -s
fi

# Generate self-signed certificates if mTLS is enabled and no domain is provided
if [ "$ENABLE_MTLS" = "true" ] && [ -z "$DOMAIN_NAME" ]; then
    echo "Generating self-signed certificates for mTLS..."
    
    # Generate CA private key
    openssl genrsa -out /opt/price-monitor/certs/ca.key 4096
    
    # Generate CA certificate
    openssl req -new -x509 -days 365 -key /opt/price-monitor/certs/ca.key \
        -out /opt/price-monitor/certs/ca.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=Price Monitor CA"
    
    # Generate server private key
    openssl genrsa -out /opt/price-monitor/certs/server.key 4096
    
    # Generate server certificate signing request
    openssl req -new -key /opt/price-monitor/certs/server.key \
        -out /opt/price-monitor/certs/server.csr \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    
    # Generate server certificate
    openssl x509 -req -days 365 -in /opt/price-monitor/certs/server.csr \
        -CA /opt/price-monitor/certs/ca.crt \
        -CAkey /opt/price-monitor/certs/ca.key \
        -CAcreateserial \
        -out /opt/price-monitor/certs/server.crt
    
    # Clean up CSR
    rm /opt/price-monitor/certs/server.csr
fi

# Set proper permissions
chown -R price-monitor:price-monitor /opt/price-monitor
chmod -R 755 /opt/price-monitor
chmod -R 600 /opt/price-monitor/certs/*
chmod 644 /opt/price-monitor/config/production.properties

# Enable and start services
systemctl daemon-reload
systemctl enable price-monitor
systemctl start price-monitor

# Create a simple health check script
cat > /opt/price-monitor/health-check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost:$APP_PORT/health || exit 1
EOF

chmod +x /opt/price-monitor/health-check.sh

# Set up cron job for health monitoring
echo "*/5 * * * * root /opt/price-monitor/health-check.sh || systemctl restart price-monitor" >> /etc/crontab

# Create deployment info file
cat > /opt/price-monitor/deployment-info.txt << EOF
Price Monitor Application Deployment
====================================

Deployment Date: $(date)
Environment: $ENVIRONMENT
Application Port: $APP_PORT
Database Host: $DB_HOST
Domain: $DOMAIN_NAME
mTLS Enabled: $ENABLE_MTLS

Configuration File: /opt/price-monitor/config/production.properties
Log Files: /opt/price-monitor/logs/
Data Directory: /opt/price-monitor/data/
Certificates: /opt/price-monitor/certs/

Services:
- price-monitor.service (systemd)
- Docker containers managed by docker-compose

Health Check: curl http://localhost:$APP_PORT/health

To view logs:
- Application logs: tail -f /opt/price-monitor/logs/price_monitor.log
- Docker logs: docker-compose -f /opt/price-monitor/docker-compose.yml logs -f
- System logs: journalctl -u price-monitor -f

To restart application:
- systemctl restart price-monitor
- Or: docker-compose -f /opt/price-monitor/docker-compose.yml restart
EOF

echo "Price Monitor application setup completed successfully!"
echo "Application should be available at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):$APP_PORT"
echo "Check deployment info at: /opt/price-monitor/deployment-info.txt"