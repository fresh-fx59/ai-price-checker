# Price Monitor Application Infrastructure
# Terraform configuration for deploying the Price Monitor application

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "price-monitor"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# VPC Configuration
resource "aws_vpc" "price_monitor_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "price_monitor_igw" {
  vpc_id = aws_vpc.price_monitor_vpc.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# Public Subnet
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.price_monitor_vpc.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
    Type = "public"
  }
}

# Private Subnet
resource "aws_subnet" "private_subnet" {
  vpc_id            = aws_vpc.price_monitor_vpc.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = {
    Name = "${var.project_name}-private-subnet"
    Type = "private"
  }
}

# Route Table for Public Subnet
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.price_monitor_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.price_monitor_igw.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

# Route Table Association for Public Subnet
resource "aws_route_table_association" "public_rta" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

# NAT Gateway for Private Subnet
resource "aws_eip" "nat_eip" {
  domain = "vpc"
  
  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

resource "aws_nat_gateway" "price_monitor_nat" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id     = aws_subnet.public_subnet.id

  tags = {
    Name = "${var.project_name}-nat-gateway"
  }

  depends_on = [aws_internet_gateway.price_monitor_igw]
}

# Route Table for Private Subnet
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.price_monitor_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.price_monitor_nat.id
  }

  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

# Route Table Association for Private Subnet
resource "aws_route_table_association" "private_rta" {
  subnet_id      = aws_subnet.private_subnet.id
  route_table_id = aws_route_table.private_rt.id
}

# Security Groups
resource "aws_security_group" "price_monitor_app_sg" {
  name_prefix = "${var.project_name}-app-"
  vpc_id      = aws_vpc.price_monitor_vpc.id
  description = "Security group for Price Monitor application"

  # HTTP access
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP access"
  }

  # HTTPS access
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS access"
  }

  # Application port (configurable)
  ingress {
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Application port"
  }

  # SSH access (restricted to admin IPs)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.admin_cidr_blocks
    description = "SSH access"
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "${var.project_name}-app-sg"
  }
}

resource "aws_security_group" "price_monitor_db_sg" {
  name_prefix = "${var.project_name}-db-"
  vpc_id      = aws_vpc.price_monitor_vpc.id
  description = "Security group for Price Monitor database"

  # Database access from application
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.price_monitor_app_sg.id]
    description     = "PostgreSQL access from application"
  }

  tags = {
    Name = "${var.project_name}-db-sg"
  }
}

# Key Pair for EC2 instances
resource "tls_private_key" "price_monitor_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "price_monitor_key_pair" {
  key_name   = "${var.project_name}-key"
  public_key = tls_private_key.price_monitor_key.public_key_openssh

  tags = {
    Name = "${var.project_name}-key-pair"
  }
}

# Application Load Balancer
resource "aws_lb" "price_monitor_alb" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.price_monitor_app_sg.id]
  subnets           = [aws_subnet.public_subnet.id, aws_subnet.private_subnet.id]

  enable_deletion_protection = var.enable_deletion_protection

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# Target Group for Application
resource "aws_lb_target_group" "price_monitor_tg" {
  name     = "${var.project_name}-tg"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = aws_vpc.price_monitor_vpc.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  tags = {
    Name = "${var.project_name}-tg"
  }
}

# ALB Listener
resource "aws_lb_listener" "price_monitor_listener" {
  load_balancer_arn = aws_lb.price_monitor_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.price_monitor_tg.arn
  }
}

# RDS Subnet Group
resource "aws_db_subnet_group" "price_monitor_db_subnet_group" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_subnet.id, aws_subnet.public_subnet.id]

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "price_monitor_db" {
  count = var.use_rds ? 1 : 0

  identifier = "${var.project_name}-db"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class
  
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.price_monitor_db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.price_monitor_db_subnet_group.name
  
  backup_retention_period = var.db_backup_retention_period
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  skip_final_snapshot = var.environment != "production"
  deletion_protection = var.environment == "production"
  
  tags = {
    Name = "${var.project_name}-db"
  }
}

# Launch Template for EC2 instances
resource "aws_launch_template" "price_monitor_lt" {
  name_prefix   = "${var.project_name}-lt-"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  key_name      = aws_key_pair.price_monitor_key_pair.key_name

  vpc_security_group_ids = [aws_security_group.price_monitor_app_sg.id]

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    app_port        = var.app_port
    environment     = var.environment
    db_host         = var.use_rds ? aws_db_instance.price_monitor_db[0].endpoint : "localhost"
    db_name         = var.db_name
    db_username     = var.db_username
    db_password     = var.db_password
    smtp_server     = var.smtp_server
    smtp_port       = var.smtp_port
    smtp_username   = var.smtp_username
    smtp_password   = var.smtp_password
    recipient_email = var.recipient_email
    enable_mtls     = var.enable_mtls
    domain_name     = var.domain_name
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-instance"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "price_monitor_asg" {
  name                = "${var.project_name}-asg"
  vpc_zone_identifier = [aws_subnet.public_subnet.id]
  target_group_arns   = [aws_lb_target_group.price_monitor_tg.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = var.asg_min_size
  max_size         = var.asg_max_size
  desired_capacity = var.asg_desired_capacity

  launch_template {
    id      = aws_launch_template.price_monitor_lt.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg"
    propagate_at_launch = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "price_monitor_logs" {
  name              = "/aws/ec2/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# S3 Bucket for application data and backups
resource "aws_s3_bucket" "price_monitor_bucket" {
  bucket = "${var.project_name}-${var.environment}-${random_id.bucket_suffix.hex}"

  tags = {
    Name = "${var.project_name}-bucket"
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "price_monitor_bucket_versioning" {
  bucket = aws_s3_bucket.price_monitor_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "price_monitor_bucket_encryption" {
  bucket = aws_s3_bucket.price_monitor_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "price_monitor_bucket_pab" {
  bucket = aws_s3_bucket.price_monitor_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM Role for EC2 instances
resource "aws_iam_role" "price_monitor_ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

# IAM Policy for EC2 instances
resource "aws_iam_role_policy" "price_monitor_ec2_policy" {
  name = "${var.project_name}-ec2-policy"
  role = aws_iam_role.price_monitor_ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.price_monitor_logs.arn}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.price_monitor_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.price_monitor_bucket.arn
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "price_monitor_profile" {
  name = "${var.project_name}-profile"
  role = aws_iam_role.price_monitor_ec2_role.name
}

# Route53 (optional, if domain is provided)
resource "aws_route53_zone" "price_monitor_zone" {
  count = var.domain_name != "" ? 1 : 0
  name  = var.domain_name

  tags = {
    Name = "${var.project_name}-zone"
  }
}

resource "aws_route53_record" "price_monitor_record" {
  count   = var.domain_name != "" ? 1 : 0
  zone_id = aws_route53_zone.price_monitor_zone[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.price_monitor_alb.dns_name
    zone_id                = aws_lb.price_monitor_alb.zone_id
    evaluate_target_health = true
  }
}

# SSL Certificate (if domain is provided)
resource "aws_acm_certificate" "price_monitor_cert" {
  count           = var.domain_name != "" ? 1 : 0
  domain_name     = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project_name}-cert"
  }
}

# Certificate validation
resource "aws_route53_record" "price_monitor_cert_validation" {
  count   = var.domain_name != "" ? 1 : 0
  name    = tolist(aws_acm_certificate.price_monitor_cert[0].domain_validation_options)[0].resource_record_name
  type    = tolist(aws_acm_certificate.price_monitor_cert[0].domain_validation_options)[0].resource_record_type
  zone_id = aws_route53_zone.price_monitor_zone[0].zone_id
  records = [tolist(aws_acm_certificate.price_monitor_cert[0].domain_validation_options)[0].resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "price_monitor_cert_validation" {
  count           = var.domain_name != "" ? 1 : 0
  certificate_arn = aws_acm_certificate.price_monitor_cert[0].arn
  validation_record_fqdns = [aws_route53_record.price_monitor_cert_validation[0].fqdn]
}

# HTTPS Listener (if SSL certificate is available)
resource "aws_lb_listener" "price_monitor_https_listener" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.price_monitor_alb.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate_validation.price_monitor_cert_validation[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.price_monitor_tg.arn
  }
}

# HTTP to HTTPS redirect (if SSL certificate is available)
resource "aws_lb_listener_rule" "price_monitor_redirect_http_to_https" {
  count        = var.domain_name != "" ? 1 : 0
  listener_arn = aws_lb_listener.price_monitor_listener.arn
  priority     = 100

  action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  condition {
    host_header {
      values = [var.domain_name]
    }
  }
}