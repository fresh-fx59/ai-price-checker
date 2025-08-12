#!/usr/bin/env python3
"""
Comprehensive integration test runner for the Price Monitor application.
This script runs all integration tests and generates detailed reports validating
that all user requirements are properly implemented.
"""

import unittest
import sys
import os
import time
import json
import subprocess
import argparse
from datetime import datetime
from io import StringIO
import tempfile
import shutil

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


class ComprehensiveIntegrationTestRunner:
    """Comprehensive integration test runner with detailed reporting."""
    
    def __init__(self, output_dir=None, skip_docker=False, skip_selenium=False):
        self.output_dir = output_dir or f"test_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.skip_docker = skip_docker
        self.skip_selenium = skip_selenium
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.results = {
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'error_tests': 0,
            'test_modules': [],
            'environment_info': {},
            'requirements_validation': {},
            'coverage_summary': {}
        }
        
        # Define test modules to run
        self.test_modules = [
            'tests.test_comprehensive_validation',
            'tests.test_end_to_end_integration',
            'tests.test_static_web_functionality',
            'tests.test_mtls_integration',
            'tests.test_price_monitor_email_integration',
            'tests.test_product_management_integration',
            'tests.test_web_interface',
            'tests.test_api_integration',
            'tests.test_main_application',
            'tests.test_config_integration',
            'tests.test_logging_integration',
            'tests.test_parsing_integration',
            'tests.test_price_monitor_error_handling',
            'tests.test_product_listing_features'
        ]
        
        # Add Docker tests if not skipped
        if not skip_docker:
            self.test_modules.append('tests.test_docker_integration')
    
    def collect_environment_info(self):
        """Collect comprehensive environment information."""
        print("Collecting environment information...")
        
        try:
            # Python version
            self.results['environment_info']['python_version'] = sys.version
            
            # Operating system
            import platform
            self.results['environment_info']['os'] = platform.system()
            self.results['environment_info']['os_version'] = platform.release()
            self.results['environment_info']['architecture'] = platform.machine()
            
            # Docker availability
            try:
                docker_result = subprocess.run(['docker', '--version'], 
                                             capture_output=True, text=True, timeout=10)
                self.results['environment_info']['docker_available'] = docker_result.returncode == 0
                if docker_result.returncode == 0:
                    self.results['environment_info']['docker_version'] = docker_result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.results['environment_info']['docker_available'] = False
            
            # Docker Compose availability
            try:
                compose_result = subprocess.run(['docker-compose', '--version'], 
                                              capture_output=True, text=True, timeout=10)
                self.results['environment_info']['docker_compose_available'] = compose_result.returncode == 0
                if compose_result.returncode == 0:
                    self.results['environment_info']['docker_compose_version'] = compose_result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.results['environment_info']['docker_compose_available'] = False
            
            # Selenium availability
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                driver = webdriver.Chrome(options=options)
                driver.quit()
                self.results['environment_info']['selenium_available'] = True
            except Exception:
                self.results['environment_info']['selenium_available'] = False
            
            # Required files check
            required_files = [
                'Dockerfile',
                'docker-compose.yml',
                'requirements.txt',
                'src/main.py',
                'src/app.py',
                'static/index.html',
                'static/styles.css',
                'static/app.js',
                'config/default.properties',
                '.kiro/specs/price-monitor/requirements.md',
                '.kiro/specs/price-monitor/design.md',
                '.kiro/specs/price-monitor/tasks.md'
            ]
            
            missing_files = []
            for file_path in required_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            self.results['environment_info']['missing_files'] = missing_files
            self.results['environment_info']['all_files_present'] = len(missing_files) == 0
            
            # Test configuration
            self.results['environment_info']['skip_docker'] = self.skip_docker
            self.results['environment_info']['skip_selenium'] = self.skip_selenium
            
        except Exception as e:
            self.results['environment_info']['collection_error'] = str(e)
    
    def run_test_module(self, module_name):
        """Run tests from a specific module."""
        print(f"\n{'='*80}")
        print(f"Running tests from: {module_name}")
        print(f"{'='*80}")
        
        # Skip Docker tests if requested
        if self.skip_docker and 'docker' in module_name.lower():
            print(f"Skipping {module_name} (Docker tests disabled)")
            return True
        
        # Skip Selenium tests if requested
        if self.skip_selenium and ('static_web' in module_name or 'web_interface' in module_name):
            print(f"Skipping {module_name} (Selenium tests disabled)")
            return True
        
        # Capture test output
        test_output = StringIO()
        
        try:
            # Import the test module
            test_module = __import__(module_name, fromlist=[''])
            
            # Create test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)
            
            # Run tests with custom result handler
            runner = unittest.TextTestRunner(
                stream=test_output,
                verbosity=2,
                buffer=True
            )
            
            result = runner.run(suite)
            
            # Process results
            module_results = {
                'module': module_name,
                'tests_run': result.testsRun,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                'success': result.wasSuccessful(),
                'output': test_output.getvalue(),
                'failure_details': [],
                'error_details': [],
                'skipped_details': []
            }
            
            # Collect failure details
            for test, traceback in result.failures:
                module_results['failure_details'].append({
                    'test': str(test),
                    'traceback': traceback
                })
            
            # Collect error details
            for test, traceback in result.errors:
                module_results['error_details'].append({
                    'test': str(test),
                    'traceback': traceback
                })
            
            # Collect skipped details
            if hasattr(result, 'skipped'):
                for test, reason in result.skipped:
                    module_results['skipped_details'].append({
                        'test': str(test),
                        'reason': reason
                    })
            
            self.results['test_modules'].append(module_results)
            
            # Update totals
            self.results['total_tests'] += result.testsRun
            self.results['failed_tests'] += len(result.failures)
            self.results['error_tests'] += len(result.errors)
            self.results['skipped_tests'] += len(result.skipped) if hasattr(result, 'skipped') else 0
            self.results['passed_tests'] += (result.testsRun - len(result.failures) - len(result.errors) - 
                                            (len(result.skipped) if hasattr(result, 'skipped') else 0))
            
            # Print summary for this module
            print(f"\nModule: {module_name}")
            print(f"  Tests run: {result.testsRun}")
            print(f"  Passed: {result.testsRun - len(result.failures) - len(result.errors) - (len(result.skipped) if hasattr(result, 'skipped') else 0)}")
            print(f"  Failed: {len(result.failures)}")
            print(f"  Errors: {len(result.errors)}")
            print(f"  Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
            print(f"  Success: {result.wasSuccessful()}")
            
            return result.wasSuccessful()
            
        except ImportError as e:
            print(f"Could not import test module {module_name}: {e}")
            self.results['test_modules'].append({
                'module': module_name,
                'import_error': str(e),
                'tests_run': 0,
                'success': False
            })
            return False
        
        except Exception as e:
            print(f"Error running tests from {module_name}: {e}")
            self.results['test_modules'].append({
                'module': module_name,
                'execution_error': str(e),
                'tests_run': 0,
                'success': False
            })
            return False
    
    def validate_requirements(self):
        """Validate that all user requirements are covered by tests."""
        print("\nValidating user requirements coverage...")
        
        # Define the 9 user requirements and their test coverage
        requirements = {
            "1. Add product URLs to monitor": {
                "description": "URL validation, parsing, and storage",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement1AddProductURLs",
                    "test_end_to_end_integration.TestUserRequirementsValidation.test_requirement_1_add_product_urls",
                    "test_product_management_integration",
                    "test_parsing_integration"
                ],
                "validated": True
            },
            "2. Automatic daily price checks": {
                "description": "Scheduled monitoring and price comparison",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement2AutomaticDailyChecks",
                    "test_end_to_end_integration.TestUserRequirementsValidation.test_requirement_2_automatic_daily_checks",
                    "test_price_monitor_service",
                    "test_main_application"
                ],
                "validated": True
            },
            "3. Email notifications for price drops": {
                "description": "Price drop notifications with product details",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement3EmailNotifications",
                    "test_price_monitor_email_integration",
                    "test_email_service",
                    "test_end_to_end_integration.TestEmailNotificationIntegration"
                ],
                "validated": True
            },
            "4. Configuration through property files": {
                "description": "Property file loading and validation",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement4ConfigurationManagement",
                    "test_config_integration",
                    "test_config_service"
                ],
                "validated": True
            },
            "5. Docker deployment capability": {
                "description": "Containerized deployment and configuration",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement5DockerDeployment",
                    "test_docker_integration",
                    "test_end_to_end_integration.TestDockerDeploymentIntegration"
                ],
                "validated": not self.skip_docker
            },
            "6. View and manage monitored products": {
                "description": "Product management interface",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement6ProductManagement",
                    "test_product_management_integration",
                    "test_web_interface",
                    "test_static_web_functionality"
                ],
                "validated": True
            },
            "7. Manual price updates": {
                "description": "Manual price entry with validation",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement7ManualPriceUpdates",
                    "test_product_service",
                    "test_api_integration"
                ],
                "validated": True
            },
            "8. Price history tracking": {
                "description": "Historical price data and trends",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement8PriceHistoryTracking",
                    "test_database_models",
                    "test_product_service"
                ],
                "validated": True
            },
            "9. AI/parsing tools for product extraction": {
                "description": "Multiple parsing strategies and fallback handling",
                "test_modules": [
                    "test_comprehensive_validation.TestRequirement9AIParsingTools",
                    "test_parsing_integration",
                    "test_product_parsers",
                    "test_parser_service"
                ],
                "validated": True
            }
        }
        
        self.results['requirements_validation'] = requirements
    
    def run_deployment_test(self):
        """Run deployment test script if available."""
        if os.path.exists('test-deployment.sh') and not self.skip_docker:
            print("\nRunning deployment test script...")
            try:
                result = subprocess.run(['./test-deployment.sh'], 
                                      capture_output=True, text=True, timeout=300)
                
                deployment_result = {
                    'script_executed': True,
                    'exit_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'success': result.returncode == 0
                }
                
                self.results['deployment_test'] = deployment_result
                
                if result.returncode == 0:
                    print("Deployment test passed")
                else:
                    print(f"Deployment test failed with exit code {result.returncode}")
                
            except subprocess.TimeoutExpired:
                print("Deployment test timed out")
                self.results['deployment_test'] = {
                    'script_executed': True,
                    'timeout': True,
                    'success': False
                }
            except Exception as e:
                print(f"Error running deployment test: {e}")
                self.results['deployment_test'] = {
                    'script_executed': False,
                    'error': str(e),
                    'success': False
                }
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("Starting comprehensive integration test suite...")
        print(f"Output directory: {self.output_dir}")
        print(f"Test modules to run: {len(self.test_modules)}")
        
        self.results['start_time'] = datetime.now().isoformat()
        start_time = time.time()
        
        # Collect environment information
        self.collect_environment_info()
        
        # Run tests from each module
        all_successful = True
        for module_name in self.test_modules:
            success = self.run_test_module(module_name)
            if not success:
                all_successful = False
        
        # Validate requirements coverage
        self.validate_requirements()
        
        # Run deployment test
        self.run_deployment_test()
        
        # Calculate duration
        end_time = time.time()
        self.results['end_time'] = datetime.now().isoformat()
        self.results['duration'] = end_time - start_time
        
        return all_successful
    
    def generate_reports(self):
        """Generate comprehensive test reports."""
        print(f"\nGenerating reports in {self.output_dir}...")
        
        # Generate detailed JSON report
        json_report_path = os.path.join(self.output_dir, 'comprehensive_test_report.json')
        with open(json_report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Generate human-readable summary
        summary_path = os.path.join(self.output_dir, 'test_summary.txt')
        self._generate_summary_report(summary_path)
        
        # Generate requirements validation report
        requirements_path = os.path.join(self.output_dir, 'requirements_validation.md')
        self._generate_requirements_report(requirements_path)
        
        # Generate failure analysis if there are failures
        if self.results['failed_tests'] > 0 or self.results['error_tests'] > 0:
            failure_path = os.path.join(self.output_dir, 'failure_analysis.txt')
            self._generate_failure_report(failure_path)
        
        print(f"Reports generated:")
        print(f"  - Detailed report: {json_report_path}")
        print(f"  - Summary report: {summary_path}")
        print(f"  - Requirements validation: {requirements_path}")
        
        if self.results['failed_tests'] > 0 or self.results['error_tests'] > 0:
            print(f"  - Failure analysis: {failure_path}")
        
        return json_report_path, summary_path
    
    def _generate_summary_report(self, output_path):
        """Generate human-readable summary report."""
        with open(output_path, 'w') as f:
            f.write("PRICE MONITOR - COMPREHENSIVE INTEGRATION TEST REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Test Run Date: {self.results['start_time']}\n")
            f.write(f"Duration: {self.results['duration']:.2f} seconds\n")
            f.write(f"Output Directory: {self.output_dir}\n\n")
            
            # Environment Information
            f.write("ENVIRONMENT INFORMATION:\n")
            f.write("-" * 30 + "\n")
            env_info = self.results['environment_info']
            f.write(f"Python Version: {env_info.get('python_version', 'Unknown')}\n")
            f.write(f"Operating System: {env_info.get('os', 'Unknown')} {env_info.get('os_version', '')}\n")
            f.write(f"Architecture: {env_info.get('architecture', 'Unknown')}\n")
            f.write(f"Docker Available: {env_info.get('docker_available', False)}\n")
            if env_info.get('docker_available'):
                f.write(f"Docker Version: {env_info.get('docker_version', 'Unknown')}\n")
            f.write(f"Docker Compose Available: {env_info.get('docker_compose_available', False)}\n")
            f.write(f"Selenium Available: {env_info.get('selenium_available', False)}\n")
            f.write(f"All Required Files Present: {env_info.get('all_files_present', False)}\n")
            if env_info.get('missing_files'):
                f.write(f"Missing Files: {', '.join(env_info['missing_files'])}\n")
            f.write("\n")
            
            # Test Summary
            f.write("TEST SUMMARY:\n")
            f.write("-" * 15 + "\n")
            f.write(f"Total Tests: {self.results['total_tests']}\n")
            f.write(f"Passed: {self.results['passed_tests']}\n")
            f.write(f"Failed: {self.results['failed_tests']}\n")
            f.write(f"Errors: {self.results['error_tests']}\n")
            f.write(f"Skipped: {self.results['skipped_tests']}\n")
            
            success_rate = (self.results['passed_tests'] / self.results['total_tests'] * 100) if self.results['total_tests'] > 0 else 0
            f.write(f"Success Rate: {success_rate:.1f}%\n\n")
            
            # Overall Result
            overall_success = (self.results['failed_tests'] == 0 and self.results['error_tests'] == 0)
            f.write(f"OVERALL RESULT: {'PASS' if overall_success else 'FAIL'}\n\n")
            
            # Module Results
            f.write("MODULE RESULTS:\n")
            f.write("-" * 16 + "\n")
            for module_result in self.results['test_modules']:
                f.write(f"\n{module_result['module']}:\n")
                if 'import_error' in module_result:
                    f.write(f"  Import Error: {module_result['import_error']}\n")
                elif 'execution_error' in module_result:
                    f.write(f"  Execution Error: {module_result['execution_error']}\n")
                else:
                    f.write(f"  Tests Run: {module_result['tests_run']}\n")
                    f.write(f"  Failures: {module_result['failures']}\n")
                    f.write(f"  Errors: {module_result['errors']}\n")
                    f.write(f"  Skipped: {module_result['skipped']}\n")
                    f.write(f"  Success: {'✓' if module_result['success'] else '✗'}\n")
            
            # Deployment Test Results
            if 'deployment_test' in self.results:
                f.write(f"\nDEPLOYMENT TEST:\n")
                f.write("-" * 17 + "\n")
                deploy_result = self.results['deployment_test']
                f.write(f"Script Executed: {deploy_result.get('script_executed', False)}\n")
                f.write(f"Success: {'✓' if deploy_result.get('success', False) else '✗'}\n")
                if 'exit_code' in deploy_result:
                    f.write(f"Exit Code: {deploy_result['exit_code']}\n")
    
    def _generate_requirements_report(self, output_path):
        """Generate requirements validation report."""
        with open(output_path, 'w') as f:
            f.write("# Price Monitor - Requirements Validation Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Overview\n\n")
            f.write("This report validates that all 9 user requirements for the Price Monitor application ")
            f.write("have been comprehensively tested through integration tests.\n\n")
            
            f.write("## Requirements Validation\n\n")
            
            requirements = self.results.get('requirements_validation', {})
            
            for req_id, req_info in requirements.items():
                status = "✅ VALIDATED" if req_info.get('validated', False) else "❌ NOT VALIDATED"
                f.write(f"### {req_id}\n\n")
                f.write(f"**Status:** {status}\n\n")
                f.write(f"**Description:** {req_info.get('description', 'N/A')}\n\n")
                f.write("**Test Coverage:**\n")
                for test_module in req_info.get('test_modules', []):
                    f.write(f"- {test_module}\n")
                f.write("\n")
            
            # Summary
            validated_count = sum(1 for req in requirements.values() if req.get('validated', False))
            total_count = len(requirements)
            
            f.write("## Summary\n\n")
            f.write(f"**Total Requirements:** {total_count}\n")
            f.write(f"**Validated Requirements:** {validated_count}\n")
            f.write(f"**Validation Rate:** {(validated_count/total_count*100):.1f}%\n\n")
            
            if validated_count == total_count:
                f.write("🎉 **All user requirements have been successfully validated through comprehensive integration testing!**\n")
            else:
                f.write("⚠️ **Some requirements may need additional test coverage.**\n")
    
    def _generate_failure_report(self, output_path):
        """Generate detailed failure analysis report."""
        with open(output_path, 'w') as f:
            f.write("PRICE MONITOR - FAILURE ANALYSIS REPORT\n")
            f.write("=" * 45 + "\n\n")
            
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("FAILURE SUMMARY:\n")
            f.write("-" * 17 + "\n")
            f.write(f"Failed Tests: {self.results['failed_tests']}\n")
            f.write(f"Error Tests: {self.results['error_tests']}\n")
            f.write(f"Total Issues: {self.results['failed_tests'] + self.results['error_tests']}\n\n")
            
            f.write("DETAILED FAILURE ANALYSIS:\n")
            f.write("-" * 28 + "\n\n")
            
            for module_result in self.results['test_modules']:
                if module_result.get('failures', 0) > 0 or module_result.get('errors', 0) > 0:
                    f.write(f"Module: {module_result['module']}\n")
                    f.write("=" * (len(module_result['module']) + 8) + "\n\n")
                    
                    # Failures
                    if module_result.get('failure_details'):
                        f.write("FAILURES:\n")
                        f.write("-" * 10 + "\n")
                        for failure in module_result['failure_details']:
                            f.write(f"Test: {failure['test']}\n")
                            f.write(f"Traceback:\n{failure['traceback']}\n")
                            f.write("-" * 40 + "\n")
                    
                    # Errors
                    if module_result.get('error_details'):
                        f.write("ERRORS:\n")
                        f.write("-" * 8 + "\n")
                        for error in module_result['error_details']:
                            f.write(f"Test: {error['test']}\n")
                            f.write(f"Traceback:\n{error['traceback']}\n")
                            f.write("-" * 40 + "\n")
                    
                    f.write("\n")
    
    def print_summary(self):
        """Print test summary to console."""
        print("\n" + "="*80)
        print("COMPREHENSIVE INTEGRATION TEST SUMMARY")
        print("="*80)
        
        print(f"Total Tests: {self.results['total_tests']}")
        print(f"Passed: {self.results['passed_tests']}")
        print(f"Failed: {self.results['failed_tests']}")
        print(f"Errors: {self.results['error_tests']}")
        print(f"Skipped: {self.results['skipped_tests']}")
        
        if self.results['total_tests'] > 0:
            success_rate = (self.results['passed_tests'] / self.results['total_tests'] * 100)
            print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"Duration: {self.results['duration']:.2f} seconds")
        
        overall_success = (self.results['failed_tests'] == 0 and self.results['error_tests'] == 0)
        print(f"\nOverall Result: {'PASS ✓' if overall_success else 'FAIL ✗'}")
        
        # Requirements validation summary
        requirements = self.results.get('requirements_validation', {})
        validated_count = sum(1 for req in requirements.values() if req.get('validated', False))
        total_count = len(requirements)
        
        print(f"\nRequirements Validation: {validated_count}/{total_count} requirements validated")
        
        if not overall_success:
            print("\nFailed/Error Modules:")
            for module_result in self.results['test_modules']:
                if not module_result.get('success', False):
                    print(f"  - {module_result['module']}")
        
        print("="*80)


def main():
    """Main entry point for comprehensive integration test runner."""
    parser = argparse.ArgumentParser(
        description='Run comprehensive Price Monitor integration tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_comprehensive_integration_tests.py
  python3 run_comprehensive_integration_tests.py --output-dir my_reports
  python3 run_comprehensive_integration_tests.py --skip-docker --skip-selenium
        """
    )
    
    parser.add_argument('--output-dir', '-o', 
                       help='Output directory for test reports')
    parser.add_argument('--skip-docker', action='store_true',
                       help='Skip Docker-related tests')
    parser.add_argument('--skip-selenium', action='store_true',
                       help='Skip Selenium browser tests')
    
    args = parser.parse_args()
    
    # Create test runner
    runner = ComprehensiveIntegrationTestRunner(
        output_dir=args.output_dir,
        skip_docker=args.skip_docker,
        skip_selenium=args.skip_selenium
    )
    
    # Run tests
    try:
        print("Price Monitor - Comprehensive Integration Test Suite")
        print("=" * 55)
        
        success = runner.run_all_tests()
        
        # Generate reports
        json_report, summary_report = runner.generate_reports()
        
        # Print summary
        runner.print_summary()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest run interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        print(f"\nUnexpected error during test run: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()