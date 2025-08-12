# Price Monitor - Integration Tests

This directory contains comprehensive integration tests for the Price Monitor application, covering all user requirements and end-to-end workflows.

## Test Coverage

### 1. Complete Workflows (`test_end_to_end_integration.py`)
- **Product Monitoring Workflow**: Add product → Parse → Monitor → Price drop → Email notification
- **Manual Price Update Workflow**: Manual price updates with email notifications
- **Multiple Products Monitoring**: Concurrent monitoring of multiple products
- **Error Handling**: Graceful handling of failures and recovery

### 2. Docker Deployment (`test_docker_integration.py`)
- **Container Build Process**: Docker image building and validation
- **Container Lifecycle**: Start, health checks, graceful shutdown
- **Configuration Mounting**: External config file mounting and validation
- **Volume Mounting**: Data and log volume persistence
- **Resource Usage**: Container resource monitoring and limits
- **Docker Compose**: Multi-service deployment validation

### 3. mTLS Security (`test_mtls_integration.py`)
- **Certificate Management**: Loading and validation of certificates
- **SSL Context Creation**: Proper SSL/TLS configuration
- **Client Authentication**: Certificate-based client authentication
- **Security Headers**: HTTPS enforcement and security headers

### 4. Static Web Interface (`test_static_web_functionality.py`)
- **HTML Structure**: Page structure and required elements
- **Form Functionality**: Add product, update price, delete product forms
- **JavaScript Integration**: API calls and dynamic content updates
- **Responsive Design**: Mobile and desktop compatibility
- **Accessibility**: ARIA labels, keyboard navigation, screen reader support
- **Error Handling**: User-friendly error messages and validation

### 5. User Requirements Validation
All 9 user requirements are comprehensively tested:

1. **Add Product URLs**: URL validation, parsing, and storage
2. **Automatic Daily Checks**: Scheduled monitoring and price comparison
3. **Email Notifications**: Price drop notifications with product details
4. **Configuration Management**: Property file loading and validation
5. **Docker Deployment**: Containerized deployment and configuration
6. **Product Management**: View, update, and delete monitored products
7. **Manual Price Updates**: Manual price entry with validation
8. **Price History Tracking**: Historical price data and trends
9. **AI/Parsing Tools**: Multiple parsing strategies and fallback handling

## Running the Tests

### Quick Start
```bash
# Run all integration tests
python3 run_comprehensive_integration_tests.py

# Run with custom output directory
python3 run_comprehensive_integration_tests.py --output-dir my_reports

# Skip Docker tests (if Docker not available)
python3 run_comprehensive_integration_tests.py --skip-docker

# Skip browser tests (if Selenium not available)
python3 run_comprehensive_integration_tests.py --skip-selenium
```

### Individual Test Modules
```bash
# Run specific test module
python3 tests/run_integration_tests.py --modules test_end_to_end_integration

# Run with verbose output
python3 tests/run_integration_tests.py --verbose

# Generate custom report
python3 tests/run_integration_tests.py --output custom_report.json
```

### Docker Deployment Testing
```bash
# Run deployment tests (includes integration tests)
./test-deployment.sh

# Run in production mode
DEPLOYMENT_MODE=production ./test-deployment.sh

# Cleanup after testing
./test-deployment.sh --cleanup
```

## Test Dependencies

### Required Python Packages
```bash
pip install requests selenium docker
```

### Optional Dependencies
- **Docker**: Required for container deployment tests
- **Docker Compose**: Required for multi-service deployment tests
- **Chrome/Chromium**: Required for Selenium browser tests
- **ChromeDriver**: Required for Selenium WebDriver

### Installing ChromeDriver
```bash
# macOS with Homebrew
brew install chromedriver

# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# Or download from: https://chromedriver.chromium.org/
```

## Test Configuration

### Environment Variables
- `SKIP_DOCKER_TESTS=1`: Skip Docker-related tests
- `SKIP_SELENIUM_TESTS=1`: Skip browser-based tests
- `TEST_TIMEOUT=300`: Set test timeout in seconds
- `API_PORT=8080`: Override API port for testing

### Test Data
Tests use temporary directories and mock data to avoid affecting production systems:
- Temporary SQLite databases
- Mock SMTP servers
- Sample HTML content for parsing tests
- Dummy certificates for mTLS testing

## Test Reports

### Report Types
1. **JSON Report**: Detailed machine-readable test results
2. **Summary Report**: Human-readable test summary
3. **Coverage Report**: Test coverage analysis
4. **Performance Report**: Resource usage and timing data

### Report Contents
- **Environment Information**: OS, Python version, Docker availability
- **Test Results**: Pass/fail status for each test
- **Failure Details**: Stack traces and error messages
- **Performance Metrics**: Execution times and resource usage
- **Requirements Validation**: Mapping of tests to user requirements

### Sample Report Structure
```json
{
  "start_time": "2023-12-01T10:00:00",
  "end_time": "2023-12-01T10:15:00",
  "duration": 900.5,
  "total_tests": 45,
  "passed_tests": 43,
  "failed_tests": 2,
  "skipped_tests": 0,
  "success_rate": 95.6,
  "environment_info": {
    "python_version": "3.9.7",
    "os": "Darwin",
    "docker_available": true,
    "selenium_available": true
  },
  "test_results": [...]
}
```

## Troubleshooting

### Common Issues

#### Docker Tests Failing
```bash
# Check Docker daemon
docker info

# Check Docker Compose
docker-compose --version

# Clean up Docker resources
docker system prune -f
```

#### Selenium Tests Failing
```bash
# Check ChromeDriver
chromedriver --version

# Update ChromeDriver
brew upgrade chromedriver  # macOS
```

#### Port Conflicts
```bash
# Check port usage
lsof -i :8080

# Use different port
API_PORT=8081 python3 run_comprehensive_integration_tests.py
```

#### Permission Issues
```bash
# Fix script permissions
chmod +x run_comprehensive_integration_tests.py
chmod +x tests/run_integration_tests.py
chmod +x test-deployment.sh
```

### Debug Mode
```bash
# Run with maximum verbosity
python3 tests/run_integration_tests.py --verbose

# Keep containers running for debugging
./test-deployment.sh
# (Don't use --cleanup flag)

# Check application logs
docker logs price-monitor
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests
on: [push, pull_request]
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install requests selenium docker
      - name: Run integration tests
        run: python3 run_comprehensive_integration_tests.py
      - name: Upload test reports
        uses: actions/upload-artifact@v2
        with:
          name: test-reports
          path: test_reports/
```

### Jenkins Pipeline Example
```groovy
pipeline {
    agent any
    stages {
        stage('Integration Tests') {
            steps {
                sh 'python3 run_comprehensive_integration_tests.py'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_reports/**/*'
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'test_reports',
                        reportFiles: '*_summary.txt',
                        reportName: 'Integration Test Report'
                    ])
                }
            }
        }
    }
}
```

## Contributing

### Adding New Tests
1. Create test file in appropriate category
2. Follow naming convention: `test_<feature>_integration.py`
3. Include docstrings and test descriptions
4. Add to test runner module list
5. Update this README

### Test Guidelines
- Use descriptive test names
- Include setup and teardown methods
- Mock external dependencies
- Test both success and failure scenarios
- Validate all user-facing functionality
- Include performance and resource usage checks

### Code Coverage
```bash
# Install coverage tool
pip install coverage

# Run tests with coverage
coverage run tests/run_integration_tests.py
coverage report
coverage html
```

## Support

For issues with integration tests:
1. Check the troubleshooting section above
2. Review test reports in `test_reports/` directory
3. Run individual test modules for isolation
4. Check application logs for runtime issues
5. Verify all dependencies are installed correctly

The integration tests are designed to be comprehensive and reliable, providing confidence that all user requirements are properly implemented and the application functions correctly in real-world scenarios.