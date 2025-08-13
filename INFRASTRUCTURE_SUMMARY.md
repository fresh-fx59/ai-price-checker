# Price Monitor Infrastructure - Terraform Deployment

## Overview

I've created a comprehensive Terraform infrastructure setup for deploying the Price Monitor application on AWS. This infrastructure provides a production-ready, scalable, and secure environment with high availability and automated deployment capabilities.

## 🏗️ Infrastructure Components

### Core Infrastructure
- **VPC** with public and private subnets across multiple AZs
- **Application Load Balancer** for high availability and SSL termination
- **Auto Scaling Group** with EC2 instances running the application
- **RDS PostgreSQL** database (optional, can use local SQLite)
- **S3 bucket** for backups and static assets
- **CloudWatch** for logging and monitoring
- **Route53** and **ACM** for custom domain and SSL (optional)

### Security Features
- **Security Groups** with least-privilege access
- **IAM roles** for secure AWS service access
- **VPC isolation** with private subnets for database
- **Optional mTLS** support for enhanced security
- **Encrypted storage** (EBS, S3, RDS)

### Monitoring & Operations
- **CloudWatch integration** for logs and metrics
- **Health checks** at load balancer and application level
- **Auto Scaling** based on demand
- **Automated backups** for database and application data

## 📁 File Structure

```
terraform/
├── main.tf                    # Main infrastructure configuration
├── variables.tf               # Input variables and validation
├── outputs.tf                 # Output values and deployment info
├── locals.tf                  # Local values and environment configs
├── versions.tf                # Terraform and provider versions
├── user_data.sh              # EC2 initialization script
├── terraform.tfvars.example  # Example configuration file
└── README.md                 # Detailed documentation

deploy.sh                     # Deployment automation script
```

## 🚀 Quick Start

### 1. Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform >= 1.0 installed
- Domain name (optional, for SSL/custom domain)
- Email credentials for SMTP notifications

### 2. Configuration
```bash
# Copy and customize configuration
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# Edit with your specific values
vim terraform/terraform.tfvars
```

### 3. Deploy
```bash
# Plan deployment
./deploy.sh --environment dev --action plan

# Deploy infrastructure
./deploy.sh --environment production --action apply --auto-approve

# Get deployment info
terraform output deployment_instructions
```

### 4. Cloudflare: Remove proxy and set Encryption mode to Full

**Note**: Used this option to fix redirect loop

1. **Disable Cloudflare Proxy**
   - Just remove the "Proxy" setting from your domain in Cloudflare

2. **Set SSL Mode to Full**
   - Go to SSL/TLS → Overview
   - Set SSL mode to "Full" or "Full (strict)"

## 🔧 Configuration Options

### Environment Types

#### Development
```hcl
environment = "dev"
instance_type = "t3.micro"
asg_desired_capacity = 1
use_rds = false  # Uses local SQLite
domain_name = ""  # No custom domain
```

#### Staging
```hcl
environment = "staging"
instance_type = "t3.small"
asg_desired_capacity = 2
use_rds = true
domain_name = "staging-monitor.flowvian.com"
```

#### Production (Current: price-monitor.flowvian.com)
```hcl
environment = "production"
instance_type = "t3.medium"
asg_desired_capacity = 2
use_rds = true
db_backup_retention_period = 30
enable_deletion_protection = true
domain_name = "price-monitor.flowvian.com"
enable_mtls = true
```

### SSL/TLS Options

#### HTTP Only (Development)
```hcl
domain_name = ""
enable_mtls = false
```

#### HTTPS with Let's Encrypt (Production)
```hcl
domain_name = "price-monitor.flowvian.com"
enable_mtls = false
ssl_certificate_source = "letsencrypt"
```

#### Hybrid: Let's Encrypt + mTLS (Current Production)
```hcl
domain_name = "price-monitor.flowvian.com"
enable_mtls = true
ssl_certificate_source = "letsencrypt"
mtls_proxy_enabled = true
app_port = 8443
```

#### mTLS with Self-Signed Certificates (Development)
```hcl
domain_name = ""
enable_mtls = true
ssl_certificate_source = "self-signed"
```

## 🔐 Security Features

### Network Security
- **VPC Isolation**: Separate public/private subnets
- **Security Groups**: Minimal required access only
- **NAT Gateway**: Private subnet internet access
- **No Direct DB Access**: Database isolated in private subnet

### Application Security
- **mTLS Support**: Optional mutual TLS authentication
- **SSL Termination**: At load balancer level
- **Encrypted Storage**: All data encrypted at rest
- **IAM Roles**: Least-privilege access to AWS services

### Access Control
- **SSH Restrictions**: Limited to admin IP addresses
- **Database Access**: Only from application security group
- **S3 Security**: Public access blocked, versioning enabled

## 📊 Monitoring & Logging

### CloudWatch Integration
- **Application Logs**: Automatically sent to CloudWatch
- **System Logs**: EC2 and Docker container logs
- **Custom Metrics**: Application performance metrics
- **Log Retention**: Configurable retention periods

### Health Monitoring
- **Load Balancer Health Checks**: `/health` endpoint
- **Auto Scaling Health Checks**: Instance-level monitoring
- **Application Health**: Container health checks
- **Database Monitoring**: RDS performance insights

## 💾 Backup & Recovery

### Automated Backups
- **RDS Backups**: Point-in-time recovery available
- **S3 Versioning**: Application data versioning
- **Cross-AZ Storage**: High availability backup storage
- **Configurable Retention**: Environment-specific retention policies

### Disaster Recovery
- **Multi-AZ Deployment**: High availability across zones
- **Auto Scaling**: Automatic instance replacement
- **Database Failover**: RDS Multi-AZ support
- **Infrastructure as Code**: Complete environment recreation

## 💰 Cost Optimization

### Development Environment
- **t3.micro instances**: Minimal compute costs
- **Single instance**: Reduced infrastructure overhead
- **Local SQLite**: No RDS costs
- **Short log retention**: Reduced storage costs

### Production Environment
- **Right-sized instances**: Balanced performance/cost
- **Auto Scaling**: Pay only for needed capacity
- **Reserved instances**: Long-term cost savings
- **Optimized storage**: GP3 for better price/performance

## 🔄 Deployment Process

### Infrastructure Deployment
1. **Terraform Plan**: Review changes before applying
2. **Resource Creation**: VPC, subnets, security groups, etc.
3. **Application Deployment**: EC2 instances with Docker containers
4. **Health Validation**: Automated health checks
5. **DNS Configuration**: Route53 and SSL certificate setup

### Application Updates
- **Blue-Green Deployment**: Zero-downtime updates
- **Rolling Updates**: Gradual instance replacement
- **Health Check Validation**: Ensure new instances are healthy
- **Rollback Capability**: Quick rollback if issues occur

## 🛠️ Operations

### Daily Operations
```bash
# Check application status
curl https://your-domain.com/health

# View application logs
aws logs tail /aws/ec2/price-monitor --follow

# Scale application
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name price-monitor-asg \
  --desired-capacity 3
```

### Maintenance Tasks
```bash
# Update application
./deploy.sh --environment production --action apply

# Backup database
aws rds create-db-snapshot \
  --db-instance-identifier price-monitor-db \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)

# Rotate logs
aws logs put-retention-policy \
  --log-group-name /aws/ec2/price-monitor \
  --retention-in-days 30
```

## 🚨 Troubleshooting

### Common Issues

#### Application Not Starting
```bash
# SSH to instance
ssh -i private_key.pem ubuntu@<instance-ip>

# Check Docker containers
sudo docker-compose -f /opt/price-monitor/docker-compose.yml ps

# View application logs
sudo docker-compose -f /opt/price-monitor/docker-compose.yml logs -f
```

#### Database Connection Issues
```bash
# Test database connectivity
psql -h <db-endpoint> -U <username> -d <database>

# Check security groups
aws ec2 describe-security-groups --group-ids <sg-id>
```

#### SSL Certificate Problems
```bash
# Check certificate status
aws acm describe-certificate --certificate-arn <cert-arn>

# Verify DNS validation
dig <domain-name>
```

## 📈 Scaling Considerations

### Horizontal Scaling
- **Auto Scaling Group**: Automatic instance scaling
- **Load Balancer**: Distributes traffic across instances
- **Database Read Replicas**: Scale database reads
- **CDN Integration**: CloudFront for static assets

### Vertical Scaling
- **Instance Types**: Upgrade to larger instances
- **Database Scaling**: Increase RDS instance size
- **Storage Scaling**: Auto-scaling storage for RDS
- **Memory Optimization**: Tune application memory usage

## 🔮 Future Enhancements

### Planned Improvements
- **Multi-Region Deployment**: Cross-region disaster recovery
- **Container Orchestration**: EKS for advanced container management
- **Serverless Components**: Lambda for background tasks
- **Advanced Monitoring**: Custom dashboards and alerting

### Integration Options
- **CI/CD Pipeline**: GitHub Actions or AWS CodePipeline
- **Container Registry**: ECR for container image management
- **Secrets Management**: AWS Secrets Manager integration
- **API Gateway**: Advanced API management and throttling

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] AWS credentials configured
- [ ] Terraform installed and configured
- [ ] Domain name registered (if using custom domain)
- [ ] Email credentials obtained
- [ ] terraform.tfvars configured
- [ ] Admin IP addresses identified

### Post-Deployment
- [ ] Application health check passes
- [ ] SSL certificate validated (if applicable)
- [ ] Email notifications working
- [ ] Database connectivity verified
- [ ] Monitoring and logging configured
- [ ] Backup strategy implemented

## 📞 Support

For infrastructure issues:
1. Check AWS CloudWatch logs
2. Review Terraform state and outputs
3. Verify security group configurations
4. Test network connectivity
5. Validate SSL certificates and DNS

The infrastructure is designed to be self-healing and highly available, with comprehensive monitoring and automated recovery capabilities.

## 🎯 Summary

This Terraform infrastructure provides:

✅ **Production-Ready**: Scalable, secure, and highly available
✅ **Cost-Optimized**: Environment-specific resource sizing
✅ **Security-First**: Multiple layers of security controls
✅ **Monitoring**: Comprehensive logging and health checks
✅ **Automation**: Fully automated deployment and scaling
✅ **Documentation**: Complete setup and operations guide

The infrastructure supports the Price Monitor application's requirements for reliability, security, and scalability while maintaining cost efficiency across different environments.