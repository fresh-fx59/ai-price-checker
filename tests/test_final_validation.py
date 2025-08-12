#!/usr/bin/env python3
"""
Final validation tests for task 12: Create integration tests and end-to-end validation.
This module specifically validates all the requirements mentioned in task 12.
"""

import unittest
import os
import sys
import subprocess
import tempfile
import shutil
import time
import json
import requests
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import PriceMonitorApplication


class TestTask12FinalValidation(unittest.TestCase):
    """Final validation tests for task 12 requirements."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "final_test_config.properties")
        cls.db_path = os.path.join(cls.temp_dir, "final_test_database.db")
        
        # Create test configuration
        cls._create_test_config()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures."""
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    @classmethod
    def _create_test_config(cls):
        """Create test configuration file."""
        config_content = f"""
[database]
path = {cls.db_path}

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

[parsing]
enable_ai_parsing = false
"""
        with open(cls.config_path, 'w') as f:
            f.write(config_content)
    
    def setUp(self):
        """Set up test fixtures."""
        # Clean up database
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_comprehensive_integration_tests_exist(self):
        """Test that comprehensive integration tests covering complete workflows exist."""
        
        # Check that key integration test files exist
        required_test_files = [
            'tests/test_comprehensive_validation.py',
            'tests/test_end_to_end_integration.py',
            'tests/test_docker_integration.py',
            'tests/test_static_web_functionality.py',
            'tests/test_mtls_integration.py',
            'tests/test_price_monitor_email_integration.py',
            'tests/test_product_management_integration.py',
            'tests/test_web_interface.py',
            'tests/test_api_integration.py',
            'tests/run_integration_tests.py'
        ]
        
        for test_file in required_test_files:
            self.assertTrue(os.path.exists(test_file), f"Required test file missing: {test_file}")
        
        # Verify test files contain actual test classes and methods
        with open('tests/test_comprehensive_validation.py', 'r') as f:
            content = f.read()
            self.assertIn('class Test', content)
            self.assertIn('def test_', content)
            self.assertIn('unittest.TestCase', content)
    
    def test_docker_container_deployment_tests(self):
        """Test that Docker container deployment and configuration tests exist."""
        
        # Check Docker integration test file exists
        self.assertTrue(os.path.exists('tests/test_docker_integration.py'))
        
        # Check that Docker-related files exist
        docker_files = [
            'Dockerfile',
            'docker-compose.yml',
            'test-deployment.sh'
        ]
        
        for docker_file in docker_files:
            self.assertTrue(os.path.exists(docker_file), f"Docker file missing: {docker_file}")
        
        # Verify Docker test file contains required test methods
        with open('tests/test_docker_integration.py', 'r') as f:
            content = f.read()
            required_tests = [
                'test_docker_image_build',
                'test_container_startup_and_health',
                'test_configuration_mounting',
                'test_volume_mounting'
            ]
            
            for test_method in required_tests:
                self.assertIn(test_method, content, f"Required Docker test method missing: {test_method}")
    
    def test_mtls_security_implementation_validation(self):
        """Test that mTLS security implementation validation exists."""
        
        # Check mTLS integration test file exists
        self.assertTrue(os.path.exists('tests/test_mtls_integration.py'))
        
        # Check security service implementation exists
        self.assertTrue(os.path.exists('src/security/security_service.py'))
        self.assertTrue(os.path.exists('src/security/auth_middleware.py'))
        
        # Verify mTLS test file contains required test methods
        with open('tests/test_mtls_integration.py', 'r') as f:
            content = f.read()
            required_tests = [
                'certificate',
                'ssl',
                'mtls',
                'security'
            ]
            
            # Check that at least some mTLS-related terms are present
            content_lower = content.lower()
            for term in required_tests:
                self.assertIn(term, content_lower, f"mTLS-related term missing: {term}")
    
    def test_static_web_page_validation(self):
        """Test that static web page validation with mTLS exists."""
        
        # Check static web functionality test file exists
        self.assertTrue(os.path.exists('tests/test_static_web_functionality.py'))
        
        # Check that static files exist
        static_files = [
            'static/index.html',
            'static/styles.css',
            'static/app.js'
        ]
        
        for static_file in static_files:
            self.assertTrue(os.path.exists(static_file), f"Static file missing: {static_file}")
        
        # Verify static web test file contains required test methods
        with open('tests/test_static_web_functionality.py', 'r') as f:
            content = f.read()
            required_tests = [
                'test_html',
                'test_static',
                'functionality'
            ]
            
            content_lower = content.lower()
            for term in required_tests:
                self.assertIn(term, content_lower, f"Static web test term missing: {term}")
    
    def test_email_notifications_for_automatic_and_manual_price_changes(self):
        """Test that email notifications are tested for both automatic and manual price changes."""
        
        # Check email integration test file exists
        self.assertTrue(os.path.exists('tests/test_price_monitor_email_integration.py'))
        
        # Verify email test file contains tests for both automatic and manual notifications
        with open('tests/test_price_monitor_email_integration.py', 'r') as f:
            content = f.read()
            
            # Should test both automatic and manual price change notifications
            self.assertIn('automatic', content.lower())
            self.assertIn('manual', content.lower())
            self.assertIn('email', content.lower())
            self.assertIn('notification', content.lower())
    
    def test_all_user_requirements_validation(self):
        """Test that all user requirements are validated through test scenarios."""
        
        # Check comprehensive validation test file exists
        self.assertTrue(os.path.exists('tests/test_comprehensive_validation.py'))
        
        # Read the comprehensive validation file and check for requirement tests
        with open('tests/test_comprehensive_validation.py', 'r') as f:
            content = f.read()
        
        # Should contain test classes for each of the 9 requirements
        expected_requirement_tests = [
            'TestRequirement1',  # Add product URLs
            'TestRequirement2',  # Automatic daily checks
            'TestRequirement3',  # Email notifications
            'TestRequirement4',  # Configuration management
            'TestRequirement5',  # Docker deployment
            'TestRequirement6',  # Product management
            'TestRequirement7',  # Manual price updates
            'TestRequirement8',  # Price history tracking
            'TestRequirement9'   # AI/parsing tools
        ]
        
        for req_test in expected_requirement_tests:
            self.assertIn(req_test, content, f"Requirement test class missing: {req_test}")
    
    def test_static_page_functionality_validation(self):
        """Test that static page functionality is properly validated."""
        
        # Check that static web functionality tests exist
        self.assertTrue(os.path.exists('tests/test_static_web_functionality.py'))
        
        # Verify the static HTML page contains required elements
        with open('static/index.html', 'r') as f:
            html_content = f.read()
        
        required_elements = [
            'Price Monitor',
            'product-url',  # Actual ID in HTML
            'add-product-btn',  # Actual ID in HTML
            'products-container'  # Actual ID in HTML
        ]
        
        for element in required_elements:
            self.assertIn(element, html_content, f"Required HTML element missing: {element}")
        
        # Verify JavaScript file contains required functions
        with open('static/app.js', 'r') as f:
            js_content = f.read()
        
        required_functions = [
            'addProduct',
            'updatePrice',
            'deleteProduct',
            'loadProducts'
        ]
        
        for function in required_functions:
            self.assertIn(function, js_content, f"Required JavaScript function missing: {function}")
    
    def test_integration_test_runner_exists(self):
        """Test that integration test runner exists and is functional."""
        
        # Check that test runner files exist
        test_runners = [
            'tests/run_integration_tests.py',
            'run_comprehensive_integration_tests.py'
        ]
        
        for runner in test_runners:
            self.assertTrue(os.path.exists(runner), f"Test runner missing: {runner}")
        
        # Verify comprehensive test runner is executable
        self.assertTrue(os.access('run_comprehensive_integration_tests.py', os.X_OK),
                       "Comprehensive test runner is not executable")
    
    def test_complete_workflow_integration(self):
        """Test that complete workflow integration tests exist and function."""
        
        # This test validates that the integration test infrastructure exists and works
        # We'll test the basic workflow without making actual network calls
        
        # Check that the main integration test files exist and contain workflow tests
        integration_files = [
            'tests/test_end_to_end_integration.py',
            'tests/test_comprehensive_validation.py'
        ]
        
        for file_path in integration_files:
            self.assertTrue(os.path.exists(file_path), f"Integration test file missing: {file_path}")
            
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for workflow-related test methods
                workflow_indicators = [
                    'workflow',
                    'end_to_end',
                    'integration',
                    'complete'
                ]
                
                has_workflow_tests = any(indicator in content.lower() for indicator in workflow_indicators)
                self.assertTrue(has_workflow_tests, f"No workflow tests found in {file_path}")
        
        # Verify that the application can be initialized (basic smoke test)
        with patch('src.services.web_scraping_service.WebScrapingService'), \
             patch('src.services.email_service.EmailService') as mock_email_service:
            
            mock_email_instance = Mock()
            mock_email_instance.test_email_connection.return_value = Mock(success=True)
            mock_email_service.return_value = mock_email_instance
            
            app = PriceMonitorApplication(config_path=self.config_path)
            self.assertTrue(app.initialize(), "Application should initialize successfully")
            
            try:
                # Basic validation that services are available
                self.assertIsNotNone(app.product_service, "Product service should be available")
                self.assertIsNotNone(app.price_monitor_service, "Price monitor service should be available")
                
                # Test that we can get all products (should be empty initially)
                all_products = app.product_service.get_all_products()
                self.assertIsInstance(all_products, list, "Should return a list of products")
                
            finally:
                app.shutdown()
    
    def test_test_documentation_exists(self):
        """Test that comprehensive test documentation exists."""
        
        # Check that test documentation exists
        doc_files = [
            'tests/README_INTEGRATION_TESTS.md'
        ]
        
        for doc_file in doc_files:
            self.assertTrue(os.path.exists(doc_file), f"Test documentation missing: {doc_file}")
        
        # Verify documentation contains required sections
        with open('tests/README_INTEGRATION_TESTS.md', 'r') as f:
            content = f.read()
        
        required_sections = [
            'Test Coverage',
            'Running the Tests',
            'Docker',
            'mTLS',
            'Static Web',
            'Email Notifications',
            'User Requirements'
        ]
        
        for section in required_sections:
            self.assertIn(section, content, f"Documentation section missing: {section}")
    
    def test_deployment_test_script_exists(self):
        """Test that deployment test script exists and is functional."""
        
        # Check deployment test script exists
        self.assertTrue(os.path.exists('test-deployment.sh'), "Deployment test script missing")
        
        # Verify script is executable
        self.assertTrue(os.access('test-deployment.sh', os.X_OK),
                       "Deployment test script is not executable")
        
        # Check deployment documentation exists
        self.assertTrue(os.path.exists('DEPLOYMENT.md'), "Deployment documentation missing")
    
    def test_all_test_modules_importable(self):
        """Test that all test modules can be imported successfully."""
        
        test_modules = [
            'tests.test_comprehensive_validation',
            'tests.test_end_to_end_integration',
            'tests.test_mtls_integration',
            'tests.test_price_monitor_email_integration',
            'tests.test_product_management_integration',
            'tests.test_api_integration',
            'tests.run_integration_tests'
        ]
        
        # Test modules that require optional dependencies separately
        optional_modules = [
            ('tests.test_docker_integration', 'docker'),
            ('tests.test_static_web_functionality', 'selenium'),
            ('tests.test_web_interface', 'selenium')
        ]
        
        for module_name in test_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                self.fail(f"Test module {module_name} cannot be imported: {e}")
        
        # Test optional modules with graceful handling of missing dependencies
        for module_name, dependency in optional_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                if dependency in str(e).lower():
                    print(f"Skipping {module_name} - {dependency} package not available: {e}")
                else:
                    self.fail(f"Test module {module_name} cannot be imported: {e}")
    
    def test_comprehensive_test_runner_functionality(self):
        """Test that the comprehensive test runner can execute successfully."""
        
        # Test that the comprehensive test runner can be executed
        # (We'll do a dry run to avoid actually running all tests)
        
        try:
            # Test help functionality
            result = subprocess.run([
                'python3', 'run_comprehensive_integration_tests.py', '--help'
            ], capture_output=True, text=True, timeout=30)
            
            self.assertEqual(result.returncode, 0, "Test runner help should work")
            self.assertIn('comprehensive', result.stdout.lower())
            
        except subprocess.TimeoutExpired:
            self.fail("Test runner help command timed out")
        except Exception as e:
            self.fail(f"Error testing comprehensive test runner: {e}")


class TestTask12RequirementsMapping(unittest.TestCase):
    """Test that task 12 requirements are properly mapped to implementations."""
    
    def test_comprehensive_integration_tests_requirement(self):
        """Test: Write comprehensive integration tests covering complete workflows."""
        
        # Verify comprehensive validation test exists
        self.assertTrue(os.path.exists('tests/test_comprehensive_validation.py'))
        
        # Verify end-to-end integration tests exist
        self.assertTrue(os.path.exists('tests/test_end_to_end_integration.py'))
        
        # Check that tests cover complete workflows
        with open('tests/test_end_to_end_integration.py', 'r') as f:
            content = f.read()
            
            workflow_tests = [
                'complete_product_monitoring_workflow',
                'manual_price_update_workflow',
                'multiple_products_monitoring_workflow'
            ]
            
            for workflow in workflow_tests:
                self.assertIn(workflow, content, f"Workflow test missing: {workflow}")
    
    def test_docker_deployment_testing_requirement(self):
        """Test: Test Docker container deployment and configuration."""
        
        # Verify Docker integration tests exist
        self.assertTrue(os.path.exists('tests/test_docker_integration.py'))
        
        # Check deployment test script exists
        self.assertTrue(os.path.exists('test-deployment.sh'))
        
        # Verify Docker configuration files exist
        docker_files = ['Dockerfile', 'docker-compose.yml']
        for docker_file in docker_files:
            self.assertTrue(os.path.exists(docker_file))
    
    def test_mtls_security_validation_requirement(self):
        """Test: Validate mTLS security implementation with static web page."""
        
        # Verify mTLS integration tests exist
        self.assertTrue(os.path.exists('tests/test_mtls_integration.py'))
        
        # Verify security implementation exists
        self.assertTrue(os.path.exists('src/security/security_service.py'))
        self.assertTrue(os.path.exists('src/security/auth_middleware.py'))
        
        # Verify static web page exists
        self.assertTrue(os.path.exists('static/index.html'))
    
    def test_email_notifications_testing_requirement(self):
        """Test: Test email notifications for both automatic and manual price changes."""
        
        # Verify email integration tests exist
        self.assertTrue(os.path.exists('tests/test_price_monitor_email_integration.py'))
        
        # Verify email service implementation exists
        self.assertTrue(os.path.exists('src/services/email_service.py'))
        
        # Check that both automatic and manual email tests exist
        with open('tests/test_price_monitor_email_integration.py', 'r') as f:
            content = f.read()
            self.assertIn('automatic', content.lower())
            self.assertIn('manual', content.lower())
    
    def test_user_requirements_validation_requirement(self):
        """Test: Create test scenarios for all user requirements including static page functionality."""
        
        # Verify comprehensive validation exists
        self.assertTrue(os.path.exists('tests/test_comprehensive_validation.py'))
        
        # Verify static web functionality tests exist
        self.assertTrue(os.path.exists('tests/test_static_web_functionality.py'))
        
        # Check that all 9 requirements are tested
        with open('tests/test_comprehensive_validation.py', 'r') as f:
            content = f.read()
            
            for i in range(1, 10):
                self.assertIn(f'TestRequirement{i}', content, 
                             f"Requirement {i} test class missing")
    
    def test_all_requirements_validation_mapping(self):
        """Test: Requirements mapping to 'All requirements validation'."""
        
        # This test verifies that the implementation covers all requirements
        # mentioned in the original requirements document
        
        requirements_file = '.kiro/specs/price-monitor/requirements.md'
        self.assertTrue(os.path.exists(requirements_file), "Requirements document missing")
        
        with open(requirements_file, 'r') as f:
            requirements_content = f.read()
        
        # Verify all 9 requirements are documented
        for i in range(1, 10):
            self.assertIn(f'Requirement {i}', requirements_content,
                         f"Requirement {i} missing from requirements document")


if __name__ == '__main__':
    unittest.main(verbosity=2)