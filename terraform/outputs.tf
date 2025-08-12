# Outputs for Price Monitor Infrastructure

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.price_monitor_vpc.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public_subnet.id
}

output "private_subnet_id" {
  description = "ID of the private subnet"
  value       = aws_subnet.private_subnet.id
}

output "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.price_monitor_alb.dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.price_monitor_alb.zone_id
}

output "application_url" {
  description = "URL to access the application"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.price_monitor_alb.dns_name}"
}

output "database_endpoint" {
  description = "RDS instance endpoint"
  value       = var.use_rds ? aws_db_instance.price_monitor_db[0].endpoint : "N/A - Using local database"
  sensitive   = true
}

output "database_port" {
  description = "RDS instance port"
  value       = var.use_rds ? aws_db_instance.price_monitor_db[0].port : "N/A"
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.price_monitor_bucket.bucket
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.price_monitor_logs.name
}

output "private_key_pem" {
  description = "Private key for SSH access (keep secure!)"
  value       = tls_private_key.price_monitor_key.private_key_pem
  sensitive   = true
}

output "public_key_openssh" {
  description = "Public key for SSH access"
  value       = tls_private_key.price_monitor_key.public_key_openssh
}

output "security_group_app_id" {
  description = "ID of the application security group"
  value       = aws_security_group.price_monitor_app_sg.id
}

output "security_group_db_id" {
  description = "ID of the database security group"
  value       = aws_security_group.price_monitor_db_sg.id
}

output "auto_scaling_group_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.price_monitor_asg.name
}

output "launch_template_id" {
  description = "ID of the launch template"
  value       = aws_launch_template.price_monitor_lt.id
}

output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = var.domain_name != "" ? aws_route53_zone.price_monitor_zone[0].zone_id : "N/A - No domain configured"
}

output "ssl_certificate_arn" {
  description = "ARN of the SSL certificate"
  value       = var.domain_name != "" ? aws_acm_certificate.price_monitor_cert[0].arn : "N/A - No domain configured"
}

output "deployment_instructions" {
  description = "Instructions for deploying the application"
  value = <<-EOT
    Deployment Instructions:
    
    1. SSH to instances using:
       ssh -i private_key.pem ubuntu@<instance-ip>
    
    2. Application will be available at:
       ${var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.price_monitor_alb.dns_name}"}
    
    3. Database connection details:
       Host: ${var.use_rds ? aws_db_instance.price_monitor_db[0].endpoint : "localhost"}
       Port: ${var.use_rds ? aws_db_instance.price_monitor_db[0].port : "5432"}
       Database: ${var.db_name}
       Username: ${var.db_username}
    
    4. Logs are available in CloudWatch:
       Log Group: ${aws_cloudwatch_log_group.price_monitor_logs.name}
    
    5. S3 bucket for backups:
       Bucket: ${aws_s3_bucket.price_monitor_bucket.bucket}
    
    6. To save the private key:
       terraform output -raw private_key_pem > private_key.pem
       chmod 600 private_key.pem
  EOT
}