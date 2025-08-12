#!/bin/bash

# Price Monitor Deployment Script
# This script helps deploy the Price Monitor application using Terraform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
AWS_REGION="us-west-2"
ACTION="plan"
AUTO_APPROVE=false
TERRAFORM_DIR="terraform"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Price Monitor Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV    Environment (dev, staging, production) [default: dev]
    -r, --region REGION      AWS region [default: us-west-2]
    -a, --action ACTION      Terraform action (plan, apply, destroy) [default: plan]
    -y, --auto-approve       Auto approve terraform apply/destroy
    -h, --help              Show this help message

EXAMPLES:
    # Plan deployment for dev environment
    $0 --environment dev --action plan

    # Deploy to production with auto-approve
    $0 --environment production --action apply --auto-approve

    # Destroy staging environment
    $0 --environment staging --action destroy

PREREQUISITES:
    1. AWS CLI configured with appropriate credentials
    2. Terraform >= 1.0 installed
    3. terraform.tfvars file configured in terraform/ directory

EOF
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check if AWS CLI is installed and configured
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi

    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install it first."
        exit 1
    fi

    # Check Terraform version
    TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
    print_status "Using Terraform version: $TERRAFORM_VERSION"

    # Check if terraform directory exists
    if [ ! -d "$TERRAFORM_DIR" ]; then
        print_error "Terraform directory '$TERRAFORM_DIR' not found."
        exit 1
    fi

    # Check if terraform.tfvars exists
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        print_warning "terraform.tfvars not found. Creating from example..."
        if [ -f "$TERRAFORM_DIR/terraform.tfvars.example" ]; then
            cp "$TERRAFORM_DIR/terraform.tfvars.example" "$TERRAFORM_DIR/terraform.tfvars"
            print_warning "Please edit $TERRAFORM_DIR/terraform.tfvars with your configuration before proceeding."
            exit 1
        else
            print_error "terraform.tfvars.example not found. Cannot create configuration file."
            exit 1
        fi
    fi

    print_success "Prerequisites check passed!"
}

# Function to validate environment
validate_environment() {
    case $ENVIRONMENT in
        dev|staging|production)
            print_status "Environment: $ENVIRONMENT"
            ;;
        *)
            print_error "Invalid environment: $ENVIRONMENT. Must be one of: dev, staging, production"
            exit 1
            ;;
    esac
}

# Function to initialize Terraform
terraform_init() {
    print_status "Initializing Terraform..."
    cd "$TERRAFORM_DIR"
    
    terraform init -upgrade
    
    if [ $? -eq 0 ]; then
        print_success "Terraform initialized successfully!"
    else
        print_error "Terraform initialization failed!"
        exit 1
    fi
    
    cd ..
}

# Function to run terraform plan
terraform_plan() {
    print_status "Running Terraform plan..."
    cd "$TERRAFORM_DIR"
    
    terraform plan \
        -var="environment=$ENVIRONMENT" \
        -var="aws_region=$AWS_REGION" \
        -out=tfplan
    
    if [ $? -eq 0 ]; then
        print_success "Terraform plan completed successfully!"
        print_status "Plan saved to: $TERRAFORM_DIR/tfplan"
    else
        print_error "Terraform plan failed!"
        exit 1
    fi
    
    cd ..
}

# Function to run terraform apply
terraform_apply() {
    print_status "Running Terraform apply..."
    cd "$TERRAFORM_DIR"
    
    if [ "$AUTO_APPROVE" = true ]; then
        terraform apply -auto-approve tfplan
    else
        terraform apply tfplan
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Terraform apply completed successfully!"
        print_status "Getting deployment information..."
        
        # Save outputs to file
        terraform output > ../deployment-outputs.txt
        
        # Save private key
        terraform output -raw private_key_pem > ../private_key.pem
        chmod 600 ../private_key.pem
        
        print_success "Deployment completed!"
        print_status "Application URL: $(terraform output -raw application_url)"
        print_status "Private key saved to: private_key.pem"
        print_status "Full outputs saved to: deployment-outputs.txt"
        
        # Show deployment instructions
        echo ""
        print_status "Deployment Instructions:"
        terraform output -raw deployment_instructions
        
    else
        print_error "Terraform apply failed!"
        exit 1
    fi
    
    cd ..
}

# Function to run terraform destroy
terraform_destroy() {
    print_warning "This will destroy all infrastructure for environment: $ENVIRONMENT"
    
    if [ "$AUTO_APPROVE" = false ]; then
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            print_status "Destroy cancelled."
            exit 0
        fi
    fi
    
    print_status "Running Terraform destroy..."
    cd "$TERRAFORM_DIR"
    
    if [ "$AUTO_APPROVE" = true ]; then
        terraform destroy -auto-approve \
            -var="environment=$ENVIRONMENT" \
            -var="aws_region=$AWS_REGION"
    else
        terraform destroy \
            -var="environment=$ENVIRONMENT" \
            -var="aws_region=$AWS_REGION"
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Infrastructure destroyed successfully!"
        
        # Clean up local files
        rm -f ../deployment-outputs.txt
        rm -f ../private_key.pem
        rm -f tfplan
        
    else
        print_error "Terraform destroy failed!"
        exit 1
    fi
    
    cd ..
}

# Function to show current status
show_status() {
    print_status "Current deployment status for environment: $ENVIRONMENT"
    
    cd "$TERRAFORM_DIR"
    
    if [ -f "terraform.tfstate" ]; then
        print_status "Terraform state exists. Checking resources..."
        terraform show -json | jq -r '.values.root_module.resources[].address' 2>/dev/null || print_warning "No resources found or jq not installed"
    else
        print_warning "No Terraform state found. Infrastructure not deployed."
    fi
    
    cd ..
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -y|--auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_status "Price Monitor Deployment Script"
    print_status "Environment: $ENVIRONMENT"
    print_status "AWS Region: $AWS_REGION"
    print_status "Action: $ACTION"
    echo ""
    
    # Validate inputs
    validate_environment
    
    # Check prerequisites
    check_prerequisites
    
    # Initialize Terraform
    terraform_init
    
    # Execute requested action
    case $ACTION in
        plan)
            terraform_plan
            ;;
        apply)
            terraform_plan
            terraform_apply
            ;;
        destroy)
            terraform_destroy
            ;;
        status)
            show_status
            ;;
        *)
            print_error "Invalid action: $ACTION. Must be one of: plan, apply, destroy, status"
            exit 1
            ;;
    esac
    
    print_success "Script completed successfully!"
}

# Run main function
main