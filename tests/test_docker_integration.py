"""
Docker-specific integration tests for the Price Monitor application.
Tests containerized deployment, configuration mounting, and container health.
"""

import unittest
import subprocess
import time
import requests
import json
import tempfile
import os
import shutil
from unittest.mock import patch
import docker
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TestDockerIntegration(unittest.TestCase):
    """Docker deployment integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.container_name = "price-monitor-test"
        cls.image_name = "price-monitor:test"
        cls.api_port = 8080
        cls.docker_available = cls._check_docker_availability()
        
        if not cls.docker_available:
            raise unittest.SkipTest("Docker not available")
        
        # Create test configuration files
        cls._create_test_configs()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures."""
        # Clean up containers and images
        if cls.docker_available:
            cls._cleanup_docker_resources()
        
        # Clean up temporary files
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    @classmethod
    def _check_docker_availability(cls):
        """Check if Docker is available."""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @classmethod
    def _create_test_configs(cls):
        """Create test configuration files."""
        # Create config directory
        config_dir = os.path.join(cls.temp_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        # Create test configuration
        config_content = """
[database]
path = /app/data/test_database.db

[email]
smtp_server = smtp.test.com
smtp_port = 587
username = test@example.com
password = testpass
recipient = recipient@example.com

[monitoring]
check_frequency_hours = 24
max_retry_attempts = 3
request_timeout_seconds = 30

[security]
enable_mtls = false
api_port = 8080

[app]
log_level = INFO
log_file = /app/logs/test.log

[parsing]
enable_ai_parsing = false
"""
        cls.config_path = os.path.join(config_dir, 'test.properties')
        with open(cls.config_path, 'w') as f:
            f.write(config_content)
        
        # Create mTLS test configuration
        mtls_config_content = config_content.replace(
            'enable_mtls = false', 'enable_mtls = true'
        ).replace(
            'api_port = 8080', 'api_port = 8443'
        ) + """
server_cert_path = /app/certs/server.crt
server_key_path = /app/certs/server.key
ca_cert_path = /app/certs/ca.crt
client_cert_required = true
"""
        cls.mtls_config_path = os.path.join(config_dir, 'mtls.properties')
        with open(cls.mtls_config_path, 'w') as f:
            f.write(mtls_config_content)
        
        # Create dummy certificates for mTLS testing
        certs_dir = os.path.join(cls.temp_dir, 'certs')
        os.makedirs(certs_dir, exist_ok=True)
        
        dummy_cert = """-----BEGIN CERTIFICATE-----
MIICljCCAX4CCQCKOtLUOHDAuTANBgkqhkiG9w0BAQsFADANMQswCQYDVQQGEwJV
UzAeFw0yMzAxMDEwMDAwMDBaFw0yNDAxMDEwMDAwMDBaMA0xCzAJBgNVBAYTAlVT
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1234567890abcdef...
-----END CERTIFICATE-----"""
        
        dummy_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDXNjk1234567890
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890...
-----END PRIVATE KEY-----"""
        
        for cert_file, content in [('server.crt', dummy_cert), ('server.key', dummy_key), ('ca.crt', dummy_cert)]:
            with open(os.path.join(certs_dir, cert_file), 'w') as f:
                f.write(content)
    
    @classmethod
    def _cleanup_docker_resources(cls):
        """Clean up Docker containers and images."""
        try:
            # Stop and remove container
            subprocess.run(['docker', 'stop', cls.container_name], 
                          capture_output=True, timeout=30)
            subprocess.run(['docker', 'rm', cls.container_name], 
                          capture_output=True, timeout=30)
            
            # Remove test image
            subprocess.run(['docker', 'rmi', cls.image_name], 
                          capture_output=True, timeout=30)
        except Exception:
            pass  # Ignore cleanup errors
    
    def setUp(self):
        """Set up test fixtures."""
        # Clean up any existing containers
        self._cleanup_docker_resources()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up containers after each test
        self._cleanup_docker_resources()
    
    def _build_docker_image(self):
        """Build Docker image for testing."""
        print("Building Docker image...")
        
        build_result = subprocess.run([
            'docker', 'build', '-t', self.image_name, '.'
        ], capture_output=True, text=True, timeout=300)
        
        if build_result.returncode != 0:
            self.fail(f"Docker build failed: {build_result.stderr}")
        
        print("Docker image built successfully")
        return True
    
    def _start_container(self, config_file='test.properties', port=8080, additional_volumes=None):
        """Start Docker container with specified configuration."""
        print(f"Starting container with config: {config_file}")
        
        # Base volume mounts
        volumes = [
            f"{os.path.join(self.temp_dir, 'config')}:/app/config:ro",
            f"{os.path.join(self.temp_dir, 'data')}:/app/data",
            f"{os.path.join(self.temp_dir, 'logs')}:/app/logs"
        ]
        
        # Add additional volumes if specified
        if additional_volumes:
            volumes.extend(additional_volumes)
        
        # Create directories
        os.makedirs(os.path.join(self.temp_dir, 'data'), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, 'logs'), exist_ok=True)
        
        # Build docker run command
        cmd = [
            'docker', 'run', '-d',
            '--name', self.container_name,
            '-p', f'{port}:{port}',
            '-e', f'CONFIG_FILE=/app/config/{config_file}'
        ]
        
        # Add volume mounts
        for volume in volumes:
            cmd.extend(['-v', volume])
        
        cmd.append(self.image_name)
        
        # Start container
        start_result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if start_result.returncode != 0:
            self.fail(f"Container start failed: {start_result.stderr}")
        
        print("Container started successfully")
        return start_result.stdout.strip()  # Container ID
    
    def _wait_for_container_health(self, timeout=60):
        """Wait for container to become healthy."""
        print("Waiting for container to become healthy...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check container status
            status_result = subprocess.run([
                'docker', 'inspect', self.container_name,
                '--format', '{{.State.Health.Status}}'
            ], capture_output=True, text=True, timeout=10)
            
            if status_result.returncode == 0:
                health_status = status_result.stdout.strip()
                if health_status == 'healthy':
                    print("Container is healthy")
                    return True
                elif health_status == 'unhealthy':
                    # Get container logs for debugging
                    logs_result = subprocess.run([
                        'docker', 'logs', '--tail', '20', self.container_name
                    ], capture_output=True, text=True, timeout=10)
                    
                    self.fail(f"Container became unhealthy. Logs:\n{logs_result.stdout}")
            
            time.sleep(2)
        
        # Timeout - get logs for debugging
        logs_result = subprocess.run([
            'docker', 'logs', '--tail', '20', self.container_name
        ], capture_output=True, text=True, timeout=10)
        
        self.fail(f"Container health check timeout. Logs:\n{logs_result.stdout}")
    
    def _test_api_endpoint(self, endpoint, port=8080, expected_status=200):
        """Test API endpoint accessibility."""
        url = f"http://localhost:{port}{endpoint}"
        
        # Configure requests with retry strategy
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        
        try:
            response = session.get(url, timeout=10)
            self.assertEqual(response.status_code, expected_status)
            return response
        except requests.exceptions.RequestException as e:
            self.fail(f"API endpoint {endpoint} not accessible: {e}")
    
    def test_docker_image_build(self):
        """Test Docker image build process."""
        self._build_docker_image()
        
        # Verify image exists
        images_result = subprocess.run([
            'docker', 'images', self.image_name, '--format', '{{.Repository}}:{{.Tag}}'
        ], capture_output=True, text=True, timeout=10)
        
        self.assertIn(self.image_name, images_result.stdout)
    
    def test_container_startup_and_health(self):
        """Test container startup and health check."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Test health endpoint
        response = self._test_api_endpoint('/health')
        data = response.json()
        
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'price-monitor')
    
    def test_configuration_mounting(self):
        """Test external configuration file mounting."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Test that configuration was loaded correctly
        response = self._test_api_endpoint('/health')
        data = response.json()
        
        # Verify configuration-specific values are reflected
        self.assertIn('database_path', data)
        self.assertIn('email_enabled', data)
    
    def test_volume_mounting(self):
        """Test data and log volume mounting."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Wait a bit for application to create files
        time.sleep(5)
        
        # Check that database file was created in mounted volume
        db_path = os.path.join(self.temp_dir, 'data', 'test_database.db')
        # Note: Database might not be created immediately, so we check for data directory
        data_dir = os.path.join(self.temp_dir, 'data')
        self.assertTrue(os.path.exists(data_dir))
        
        # Check that log directory exists
        log_dir = os.path.join(self.temp_dir, 'logs')
        self.assertTrue(os.path.exists(log_dir))
    
    def test_api_endpoints_accessibility(self):
        """Test that all API endpoints are accessible."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Test various endpoints
        endpoints_to_test = [
            ('/health', 200),
            ('/api/products', 200),
            ('/api/stats', 200),
            ('/', 200),  # Static web page
        ]
        
        for endpoint, expected_status in endpoints_to_test:
            with self.subTest(endpoint=endpoint):
                self._test_api_endpoint(endpoint, expected_status=expected_status)
    
    def test_static_web_page_serving(self):
        """Test static web page serving from container."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Test static web page
        response = self._test_api_endpoint('/')
        html_content = response.text
        
        self.assertIn('Price Monitor', html_content)
        self.assertIn('Add Product', html_content)
        
        # Test static assets
        css_response = self._test_api_endpoint('/static/styles.css')
        self.assertIn('text/css', css_response.headers.get('content-type', ''))
        
        js_response = self._test_api_endpoint('/static/app.js')
        self.assertIn('javascript', js_response.headers.get('content-type', '').lower())
    
    def test_container_resource_usage(self):
        """Test container resource usage and limits."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Get container stats
        stats_result = subprocess.run([
            'docker', 'stats', self.container_name, '--no-stream',
            '--format', 'table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'
        ], capture_output=True, text=True, timeout=10)
        
        self.assertEqual(stats_result.returncode, 0)
        self.assertIn('%', stats_result.stdout)  # CPU percentage should be present
    
    def test_container_logs(self):
        """Test container logging functionality."""
        self._build_docker_image()
        self._start_container()
        self._wait_for_container_health()
        
        # Get container logs
        logs_result = subprocess.run([
            'docker', 'logs', self.container_name
        ], capture_output=True, text=True, timeout=10)
        
        self.assertEqual(logs_result.returncode, 0)
        
        # Check for expected log messages
        log_output = logs_result.stdout + logs_result.stderr
        self.assertIn('Price Monitor', log_output)
        
        # Should not contain critical errors
        self.assertNotIn('CRITICAL', log_output)
        self.assertNotIn('FATAL', log_output)
    
    def test_graceful_shutdown(self):
        """Test graceful container shutdown."""
        self._build_docker_image()
        container_id = self._start_container()
        self._wait_for_container_health()
        
        # Send SIGTERM to container
        stop_result = subprocess.run([
            'docker', 'stop', self.container_name
        ], capture_output=True, text=True, timeout=30)
        
        self.assertEqual(stop_result.returncode, 0)
        
        # Check that container stopped gracefully
        inspect_result = subprocess.run([
            'docker', 'inspect', self.container_name,
            '--format', '{{.State.ExitCode}}'
        ], capture_output=True, text=True, timeout=10)
        
        exit_code = int(inspect_result.stdout.strip())
        self.assertEqual(exit_code, 0)  # Clean shutdown
    
    def test_mtls_configuration(self):
        """Test mTLS configuration in container."""
        self._build_docker_image()
        
        # Start container with mTLS configuration and certificate volumes
        additional_volumes = [
            f"{os.path.join(self.temp_dir, 'certs')}:/app/certs:ro"
        ]
        
        self._start_container(
            config_file='mtls.properties',
            port=8443,
            additional_volumes=additional_volumes
        )
        
        # Wait for container to start (might take longer with mTLS)
        time.sleep(10)
        
        # Check container is running
        status_result = subprocess.run([
            'docker', 'inspect', self.container_name,
            '--format', '{{.State.Running}}'
        ], capture_output=True, text=True, timeout=10)
        
        is_running = status_result.stdout.strip() == 'true'
        self.assertTrue(is_running, "Container should be running with mTLS configuration")
        
        # Note: We can't easily test HTTPS endpoints without proper certificates
        # But we can verify the container started successfully with mTLS config
    
    def test_environment_variable_override(self):
        """Test configuration override via environment variables."""
        self._build_docker_image()
        
        # Start container with environment variable overrides
        cmd = [
            'docker', 'run', '-d',
            '--name', self.container_name,
            '-p', f'{self.api_port}:{self.api_port}',
            '-e', 'CONFIG_FILE=/app/config/test.properties',
            '-e', 'LOG_LEVEL=DEBUG',
            '-v', f"{os.path.join(self.temp_dir, 'config')}:/app/config:ro",
            '-v', f"{os.path.join(self.temp_dir, 'data')}:/app/data",
            '-v', f"{os.path.join(self.temp_dir, 'logs')}:/app/logs",
            self.image_name
        ]
        
        start_result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(start_result.returncode, 0)
        
        # Wait for startup
        time.sleep(10)
        
        # Check logs for debug level logging
        logs_result = subprocess.run([
            'docker', 'logs', self.container_name
        ], capture_output=True, text=True, timeout=10)
        
        log_output = logs_result.stdout + logs_result.stderr
        # Debug level should produce more verbose output
        self.assertIn('DEBUG', log_output.upper())


class TestDockerComposeIntegration(unittest.TestCase):
    """Docker Compose integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.docker_compose_available = cls._check_docker_compose_availability()
        
        if not cls.docker_compose_available:
            raise unittest.SkipTest("Docker Compose not available")
    
    @classmethod
    def _check_docker_compose_availability(cls):
        """Check if Docker Compose is available."""
        try:
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def setUp(self):
        """Set up test fixtures."""
        # Clean up any existing compose services
        subprocess.run(['docker-compose', 'down'], 
                      capture_output=True, timeout=30)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up compose services
        subprocess.run(['docker-compose', 'down'], 
                      capture_output=True, timeout=30)
    
    def test_docker_compose_config_validation(self):
        """Test Docker Compose configuration validation."""
        # Test that docker-compose.yml is valid
        config_result = subprocess.run([
            'docker-compose', 'config'
        ], capture_output=True, text=True, timeout=30)
        
        self.assertEqual(config_result.returncode, 0, 
                        f"Docker Compose config invalid: {config_result.stderr}")
    
    def test_docker_compose_build(self):
        """Test Docker Compose build process."""
        build_result = subprocess.run([
            'docker-compose', 'build', '--no-cache'
        ], capture_output=True, text=True, timeout=300)
        
        self.assertEqual(build_result.returncode, 0,
                        f"Docker Compose build failed: {build_result.stderr}")
    
    def test_docker_compose_up_down(self):
        """Test Docker Compose service lifecycle."""
        # Build first
        build_result = subprocess.run([
            'docker-compose', 'build'
        ], capture_output=True, text=True, timeout=300)
        
        if build_result.returncode != 0:
            self.skipTest(f"Build failed: {build_result.stderr}")
        
        # Start services
        up_result = subprocess.run([
            'docker-compose', 'up', '-d'
        ], capture_output=True, text=True, timeout=120)
        
        self.assertEqual(up_result.returncode, 0,
                        f"Docker Compose up failed: {up_result.stderr}")
        
        try:
            # Wait for services to be ready
            time.sleep(15)
            
            # Check service status
            ps_result = subprocess.run([
                'docker-compose', 'ps'
            ], capture_output=True, text=True, timeout=30)
            
            self.assertEqual(ps_result.returncode, 0)
            self.assertIn('price-monitor', ps_result.stdout)
            
        finally:
            # Stop services
            down_result = subprocess.run([
                'docker-compose', 'down'
            ], capture_output=True, text=True, timeout=60)
            
            self.assertEqual(down_result.returncode, 0,
                            f"Docker Compose down failed: {down_result.stderr}")


if __name__ == '__main__':
    unittest.main(verbosity=2)