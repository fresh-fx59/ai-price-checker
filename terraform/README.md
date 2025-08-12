# Price Monitor Infrastructure - Terraform

This Terraform configuration creates a complete AWS infrastructure for deploying the Price Monitor application with high availability, security, and scalability.

## Architecture Overview

The infrastructure includes:

- **VPC** with public and private subnets across multiple AZs
- **Application Load Balancer** for high availability and SSL termination
- **Auto Scaling Group** with EC2 instances running the application
- **RDS PostgreSQL** database (optional, can use local SQLite)
- **S3 bucket** for backups and static assets
- **CloudWatch** for logging and monitoring
- **Route53** and **ACM** for custom domain and SSL (optional)
- **Security Groups** with least-privilege access
- **IAM roles** for secure AWS service access

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** >= 1.0 installed
3. **Domain name** (optional, for SSL/custom domain)
4. **Email credentials** for SMTP notifications

## Quick Start

### 1. Clone and Navigate

```bash
cd terraform/
```

### 2. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your specific values:

```hcl
# Basic Configuration
aws_region   = "us-west-2"
environment  = "production"
project_name = "price-monitor"

# Security - IMPORTANT: Restrict SSH access
admin_cidr_blocks = ["YOUR_IP_ADDRESS/32"]

# Database
db_password = "your_secure_password_here"

# Email Configuration
smtp_username   = "your_email@gmail.com"
smtp_password   = "your_app_password"
recipient_email = "alerts@yourdomain.com"

# Optional: Custom Domain
domain_name = "monitor.yourdomain.com"
```

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

### 4. Get Connection Details

```bash
# Get the application URL
terraform output application_url

# Save the SSH private key
terraform output -raw private_key_pem > private_key.pem
chmod 600 private_key.pem

# Get deployment instructions
terraform output deployment_instructions
```

## Configuration Options

### Environment Types

- **dev**: Single instance, minimal resources, no deletion protection
- **staging**: 2 instances, moderate resources, basic monitoring
- **production**: 2+ instances, full resources, deletion protection, enhanced monitoring

### Database Options

```hcl
# Use RDS PostgreSQL (recommended for production)
use_rds = true
db_instance_class = "db.t3.micro"

# Use local SQLite (for development/testing)
use_rds = false
```

### SSL/TLS Options

```hcl
# No SSL (HTTP only)
domain_name = ""
enable_mtls = false

# SSL with custom domain
domain_name = "monitor.yourdomain.com"
enable_mtls = false

# mTLS with self-signed certificates
domain_name = ""
enable_mtls = true
```

### Scaling Configuration

```hcl
# Auto Scaling Group settings
asg_min_size         = 1
asg_max_size         = 5
asg_desired_capacity = 2

# Instance type
instance_type = "t3.medium"  # or t3.large for higher load
```

## Security Features

### Network Security
- VPC with isolated subnets
- Security groups with minimal required access
- NAT Gateway for private subnet internet access
- No direct internet access to database

### Application Security
- Optional mTLS support
- SSL/TLS termination at load balancer
- Encrypted storage (EBS, S3, RDS)
- IAM roles with least-privilege access

### Access Control
- SSH access restricted to admin IP addresses
- Database access only from application security group
- S3 bucket with public access blocked

## Monitoring and Logging

### CloudWatch Integration
- Application logs automatically sent to CloudWatch
- Custom log groups for different components
- Configurable log retention periods

### Health Checks
- Load balancer health checks on `/health` endpoint
- Auto Scaling Group health checks
- Automatic instance replacement on failure

### Monitoring Endpoints
- Application: `http://your-domain/health`
- Load balancer: AWS Console → EC2 → Load Balancers
- Logs: AWS Console → CloudWatch → Log Groups

## Backup and Recovery

### Database Backups
- Automated RDS backups (configurable retention)
- Point-in-time recovery available
- Cross-AZ backup storage

### Application Data
- S3 bucket for application backups
- Versioning enabled on S3 bucket
- Server-side encryption enabled

## Cost Optimization

### Development Environment
```hcl
environment = "dev"
instance_type = "t3.micro"
asg_desired_capacity = 1
use_rds = false
```

### Production Environment
```hcl
environment = "production"
instance_type = "t3.medium"
asg_desired_capacity = 2
use_rds = true
db_instance_class = "db.t3.micro"
```

## Deployment Process

### Initial Deployment
1. Infrastructure provisioning (5-10 minutes)
2. EC2 instance initialization (5-10 minutes)
3. Application container startup (2-5 minutes)
4. Health check validation (1-2 minutes)

### Application Updates
The infrastructure supports blue-green deployments:

```bash
# Update launch template with new AMI/user data
terraform apply

# Trigger instance refresh
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name $(terraform output -raw auto_scaling_group_name)
```

## Troubleshooting

### Common Issues

#### Application Not Starting
```bash
# SSH to instance
ssh -i private_key.pem ubuntu@<instance-ip>

# Check application logs
sudo docker-compose -f /opt/price-monitor/docker-compose.yml logs

# Check system logs
sudo journalctl -u price-monitor -f
```

#### Database Connection Issues
```bash
# Test database connectivity
psql -h <db-endpoint> -U <username> -d <database>

# Check security group rules
aws ec2 describe-security-groups --group-ids <sg-id>
```

#### SSL Certificate Issues
```bash
# Check certificate status
aws acm describe-certificate --certificate-arn <cert-arn>

# Verify DNS validation
dig <domain-name>
```

### Health Check Endpoints

- **Application Health**: `GET /health`
- **Load Balancer Health**: AWS Console
- **Database Health**: Connection test from application

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Warning**: This will permanently delete all resources including databases and S3 data. Make sure to backup any important data first.

## Advanced Configuration

### Custom AMI
To use a custom AMI with pre-installed application:

```hcl
# In variables.tf, add:
variable "custom_ami_id" {
  description = "Custom AMI ID for application instances"
  type        = string
  default     = ""
}

# In main.tf, modify launch template:
image_id = var.custom_ami_id != "" ? var.custom_ami_id : data.aws_ami.ubuntu.id
```

### Multi-Region Deployment
For multi-region deployment, create separate Terraform configurations for each region and use Route53 for DNS failover.

### Container Registry
For production deployments, consider using ECR:

```bash
# Build and push to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-west-2.amazonaws.com
docker build -t price-monitor .
docker tag price-monitor:latest <account>.dkr.ecr.us-west-2.amazonaws.com/price-monitor:latest
docker push <account>.dkr.ecr.us-west-2.amazonaws.com/price-monitor:latest
```

## Support

For issues with the infrastructure:

1. Check AWS CloudWatch logs
2. Review Terraform state and outputs
3. Verify security group and network configuration
4. Test connectivity between components

## License

This Terraform configuration is provided as-is for the Price Monitor application deployment.