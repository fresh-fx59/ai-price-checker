# Local values for Price Monitor Infrastructure

locals {
  # Common tags applied to all resources
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Application = "price-monitor"
    Owner       = "devops"
    CreatedDate = formatdate("YYYY-MM-DD", timestamp())
  }

  # Environment-specific configurations
  environment_config = {
    dev = {
      instance_type                = "t3.micro"
      asg_min_size                = 1
      asg_max_size                = 2
      asg_desired_capacity        = 1
      db_instance_class           = "db.t3.micro"
      db_allocated_storage        = 20
      db_backup_retention_period  = 1
      log_retention_days          = 7
      enable_deletion_protection  = false
    }
    staging = {
      instance_type                = "t3.small"
      asg_min_size                = 1
      asg_max_size                = 3
      asg_desired_capacity        = 2
      db_instance_class           = "db.t3.micro"
      db_allocated_storage        = 20
      db_backup_retention_period  = 7
      log_retention_days          = 14
      enable_deletion_protection  = false
    }
    production = {
      instance_type                = "t3.medium"
      asg_min_size                = 2
      asg_max_size                = 5
      asg_desired_capacity        = 2
      db_instance_class           = "db.t3.small"
      db_allocated_storage        = 50
      db_backup_retention_period  = 30
      log_retention_days          = 30
      enable_deletion_protection  = true
    }
  }

  # Use environment-specific config or fallback to variables
  current_config = lookup(local.environment_config, var.environment, {
    instance_type                = var.instance_type
    asg_min_size                = var.asg_min_size
    asg_max_size                = var.asg_max_size
    asg_desired_capacity        = var.asg_desired_capacity
    db_instance_class           = var.db_instance_class
    db_allocated_storage        = var.db_allocated_storage
    db_backup_retention_period  = var.db_backup_retention_period
    log_retention_days          = var.log_retention_days
    enable_deletion_protection  = var.enable_deletion_protection
  })

  # Naming conventions
  name_prefix = "${var.project_name}-${var.environment}"
  
  # SSL/TLS configuration
  enable_ssl = var.domain_name != ""
  
  # Database configuration
  db_port = 5432
  
  # Application configuration
  app_name = "price-monitor"
  
  # Availability zones (use first 2 available)
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
}