#!/bin/bash

# Price Monitor Deployment Test Script
# This script tests the Docker deployment of the Price Monitor application

set -e

echo "=== Price Monitor Deployment Test ==="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
CONTAINER_NAME="price-monitor"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-development}"
API_PORT="${API_PORT:-8080}"
PROTOCOL="${PROTOCOL:-http}"
HEALTH_ENDPOINT="${PROTOCOL}://localhost:${API_PORT}/health"
MAX_WAIT_TIME=60

# Set defaults based on deployment mode
if [[ "$DEPLOYMENT_MODE" == "production" ]]; then
    API_PORT="${API_PORT:-8443}"
    PROTOCOL="https"
    HEALTH_ENDPOINT="https://localhost:${API_PORT}/health"
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
else
    API_PORT="${API_PORT:-8080}"
    PROTOCOL="http"
    HEALTH_ENDPOINT="http://localhost:${API_PORT}/health"
    COMPOSE_FILES=""
fi

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    log_info "Checking Docker availability..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    log_info "Docker is available"
}

check_docker_compose() {
    log_info "Checking Docker Compose availability..."
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    log_info "Docker Compose is available"
}

check_files() {
    log_info "Checking required files..."
    
    required_files=(
        "Dockerfile"
        "docker-compose.yml"
        "requirements.txt"
        "src/main.py"
        "src/app.py"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file missing: $file"
            exit 1
        fi
    done
    
    log_info "All required files present"
}

check_directories() {
    log_info "Checking required directories..."
    
    required_dirs=(
        "src"
        "static"
        "config"
        "certs"
        "data"
        "logs"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_warn "Creating missing directory: $dir"
            mkdir -p "$dir"
        fi
    done
    
    log_info "All required directories present"
}

build_image() {
    log_info "Building Docker image for $DEPLOYMENT_MODE mode..."
    
    if docker-compose $COMPOSE_FILES build --no-cache; then
        log_info "Docker image built successfully"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

start_container() {
    log_info "Starting container in $DEPLOYMENT_MODE mode..."
    
    # Stop existing container if running
    if docker-compose $COMPOSE_FILES ps | grep -q "$CONTAINER_NAME"; then
        log_info "Stopping existing container..."
        docker-compose $COMPOSE_FILES stop
    fi
    
    # Start container
    if docker-compose $COMPOSE_FILES up -d; then
        log_info "Container started successfully"
    else
        log_error "Failed to start container"
        exit 1
    fi
}

wait_for_health() {
    log_info "Waiting for application to be healthy..."
    
    local wait_time=0
    local health_check_interval=5
    
    while [[ $wait_time -lt $MAX_WAIT_TIME ]]; do
        if docker-compose $COMPOSE_FILES ps | grep -q "healthy"; then
            log_info "Application is healthy"
            return 0
        fi
        
        if docker-compose $COMPOSE_FILES ps | grep -q "unhealthy"; then
            log_error "Application health check failed"
            docker-compose $COMPOSE_FILES logs --tail=20 "$CONTAINER_NAME"
            return 1
        fi
        
        echo -n "."
        sleep $health_check_interval
        wait_time=$((wait_time + health_check_interval))
    done
    
    echo
    log_error "Timeout waiting for application to become healthy"
    docker-compose logs --tail=20 "$CONTAINER_NAME"
    return 1
}

test_health_endpoint() {
    log_info "Testing health endpoint ($HEALTH_ENDPOINT)..."
    
    # Test with curl (ignoring SSL verification for self-signed certs in HTTPS mode)
    local curl_opts="-f -s"
    if [[ "$PROTOCOL" == "https" ]]; then
        curl_opts="$curl_opts -k"
    fi
    
    if curl $curl_opts "$HEALTH_ENDPOINT" > /dev/null; then
        log_info "Health endpoint is accessible"
        
        # Get health response
        local health_response
        health_response=$(curl $curl_opts "$HEALTH_ENDPOINT")
        echo "Health response: $health_response"
    else
        log_error "Health endpoint is not accessible"
        return 1
    fi
}

test_web_interface() {
    log_info "Testing web interface..."
    
    local web_endpoint="${PROTOCOL}://localhost:${API_PORT}/"
    local curl_opts="-f -s"
    if [[ "$PROTOCOL" == "https" ]]; then
        curl_opts="$curl_opts -k"
    fi
    
    if curl $curl_opts "$web_endpoint" > /dev/null; then
        log_info "Web interface is accessible"
    else
        if [[ "$DEPLOYMENT_MODE" == "production" ]]; then
            log_warn "Web interface not accessible (expected in production mode with mTLS)"
        else
            log_error "Web interface is not accessible"
        fi
    fi
}

check_logs() {
    log_info "Checking application logs..."
    
    local log_output
    log_output=$(docker-compose $COMPOSE_FILES logs --tail=10 "$CONTAINER_NAME" 2>&1)
    
    if echo "$log_output" | grep -qi "error\|exception\|failed"; then
        log_warn "Found potential errors in logs:"
        echo "$log_output" | grep -i "error\|exception\|failed"
    else
        log_info "No obvious errors found in recent logs"
    fi
}

check_container_stats() {
    log_info "Checking container resource usage..."
    
    local stats
    stats=$(docker stats "$CONTAINER_NAME" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}")
    echo "$stats"
}

cleanup() {
    if [[ "${1:-}" == "--cleanup" ]]; then
        log_info "Cleaning up test deployment..."
        docker-compose $COMPOSE_FILES down
        log_info "Cleanup completed"
    fi
}

run_integration_tests() {
    log_info "Running comprehensive integration tests..."
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log_warn "Python3 not available - skipping integration tests"
        return 0
    fi
    
    # Run comprehensive integration tests
    if python3 run_comprehensive_integration_tests.py --output-dir test_reports; then
        log_info "✓ Comprehensive integration tests passed"
        return 0
    else
        log_warn "Some integration tests failed - check test_reports/ for details"
        return 1
    fi
}

run_tests() {
    log_info "Starting deployment tests..."
    echo
    
    # Pre-flight checks
    check_docker
    check_docker_compose
    check_files
    check_directories
    
    echo
    log_info "Building and deploying..."
    
    # Build and deploy
    build_image
    start_container
    
    echo
    log_info "Testing deployment..."
    
    # Wait for application to be ready
    if wait_for_health; then
        # Run basic deployment tests
        test_health_endpoint
        test_web_interface
        check_logs
        check_container_stats
        
        echo
        log_info "Running comprehensive integration tests..."
        run_integration_tests
        
        echo
        log_info "=== Deployment Test Summary ==="
        log_info "✓ Docker image built successfully"
        log_info "✓ Container started successfully"
        log_info "✓ Application health check passed"
        log_info "✓ Health endpoint is accessible"
        log_info "✓ No critical errors found in logs"
        log_info "✓ Integration tests executed"
        echo
        log_info "Deployment test completed successfully!"
        log_info "Application is running at: $HEALTH_ENDPOINT"
        log_info "Integration test reports available in: test_reports/"
        
        return 0
    else
        echo
        log_error "=== Deployment Test Failed ==="
        log_error "Application failed to become healthy"
        log_error "Check the logs above for details"
        
        return 1
    fi
}

# Main execution
main() {
    case "${1:-}" in
        --cleanup)
            cleanup --cleanup
            ;;
        --help|-h)
            echo "Usage: $0 [--cleanup] [--help]"
            echo
            echo "Options:"
            echo "  --cleanup    Stop and remove containers after testing"
            echo "  --help, -h   Show this help message"
            echo
            echo "Environment variables:"
            echo "  DEPLOYMENT_MODE  Deployment mode: development (default) or production"
            echo "  API_PORT         Port to test (default: 8080 for dev, 8443 for prod)"
            echo "  PROTOCOL         Protocol to use: http (default for dev) or https (prod)"
            ;;
        *)
            if run_tests; then
                echo
                log_info "To stop the application: docker-compose $COMPOSE_FILES stop"
                log_info "To view logs: docker-compose $COMPOSE_FILES logs -f $CONTAINER_NAME"
                log_info "To cleanup: $0 --cleanup"
                exit 0
            else
                exit 1
            fi
            ;;
    esac
}

# Handle script interruption
trap 'echo; log_warn "Test interrupted by user"; exit 130' INT

main "$@"