#!/usr/bin/env python3
"""
COMPREHENSIVE TEST RUNNER
========================
Complete test execution framework for options trading project
"""

import os
import sys
import unittest
import coverage
import pytest
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path
import importlib.util
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveTestRunner:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}
        self.coverage_data = None
        self.start_time = None
        self.end_time = None
        
        # Test categories
        self.test_categories = {
            'unit_tests': [],
            'functional_tests': [],
            'integration_tests': [],
            'thread_safety_tests': [],
            'memory_tests': [],
            'code_integrity_tests': [],
            'calculation_tests': [],
            'critical_issue_tests': [],
            'random_tests': [],
            'sanity_tests': []
        }
        
    def discover_tests(self):
        """Discover all test files in the project"""
        logger.info("🔍 Discovering test files...")
        
        test_patterns = {
            'unit_tests': 'test_*.py',
            'functional_tests': 'functional_*.py',
            'integration_tests': 'integration_*.py',
            'thread_safety_tests': 'thread_*.py',
            'memory_tests': 'memory_*.py',
            'code_integrity_tests': 'integrity_*.py',
            'calculation_tests': 'calculation_*.py',
            'critical_issue_tests': 'critical_*.py',
            'random_tests': 'random_*.py',
            'sanity_tests': 'sanity_*.py'
        }
        
        for category, pattern in test_patterns.items():
            test_files = list(self.project_root.glob(pattern))
            self.test_categories[category] = test_files
            logger.info(f"   📁 {category}: {len(test_files)} files found")
    
    def run_code_coverage(self):
        """Run code coverage analysis"""
        logger.info("📊 Running code coverage analysis...")
        
        try:
            # Initialize coverage
            cov = coverage.Coverage(source=['.'], omit=['test_*', 'venv/*', 'logs/*'])
            cov.start()
            
            # Run all tests to collect coverage data
            self.run_all_tests_for_coverage()
            
            # Stop coverage and generate report
            cov.stop()
            cov.save()
            
            # Generate HTML report
            cov.html_report(directory='test_framework/coverage_html')
            
            # Get coverage data
            self.coverage_data = cov.get_data()
            
            # Print coverage summary
            total_lines = sum(self.coverage_data.values())
            covered_lines = sum(1 for file_data in self.coverage_data.values() 
                              for line in file_data.values() if line > 0)
            
            coverage_percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0
            
            logger.info(f"📊 Code Coverage: {coverage_percentage:.1f}%")
            logger.info(f"   📄 Report saved to: test_framework/coverage_html/index.html")
            
            return coverage_percentage
            
        except Exception as e:
            logger.error(f"❌ Error running code coverage: {e}")
            return 0
    
    def run_all_tests_for_coverage(self):
        """Run tests for coverage collection"""
        for category, test_files in self.test_categories.items():
            for test_file in test_files:
                try:
                    spec = importlib.util.spec_from_file_location("test_module", test_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Run test functions
                    for attr_name in dir(module):
                        if attr_name.startswith('test_'):
                            test_func = getattr(module, attr_name)
                            if callable(test_func):
                                try:
                                    test_func()
                                except Exception:
                                    pass  # Ignore errors during coverage
                                    
                except Exception as e:
                    logger.warning(f"⚠️  Could not load {test_file}: {e}")
    
    def run_unit_tests(self):
        """Run unit tests"""
        logger.info("🧪 Running Unit Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['unit_tests']:
            try:
                # Run unit tests
                result = subprocess.run([
                    sys.executable, '-m', 'pytest', 
                    str(test_file),
                    '-v', '--tb=short'
                ], capture_output=True, text=True, cwd=self.project_root)
                
                # Parse results
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'passed' in line and '::' in line:
                        results['passed'] += 1
                        results['total'] += 1
                    elif 'failed' in line and '::' in line:
                        results['failed'] += 1
                        results['total'] += 1
                    elif 'ERROR' in line and '::' in line:
                        results['errors'] += 1
                        results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
        
        results['duration'] = time.time() - start_time
        self.test_results['unit_tests'] = results
        
        logger.info(f"🧪 Unit Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_functional_tests(self):
        """Run functional tests"""
        logger.info("🔧 Running Functional Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['functional_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                # Parse results
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['functional_tests'] = results
        
        logger.info(f"🔧 Functional Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_integration_tests(self):
        """Run integration tests"""
        logger.info("🔗 Running Integration Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['integration_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['integration_tests'] = results
        
        logger.info(f"🔗 Integration Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_thread_safety_tests(self):
        """Run thread safety tests"""
        logger.info("🧵 Running Thread Safety Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['thread_safety_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['thread_safety_tests'] = results
        
        logger.info(f"🧵 Thread Safety Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_memory_tests(self):
        """Run memory tests"""
        logger.info("🧠 Running Memory Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0,
            'memory_issues': []
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['memory_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    results['memory_issues'].append(test_file.name)
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['memory_tests'] = results
        
        logger.info(f"🧠 Memory Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_code_integrity_tests(self):
        """Run code integrity tests"""
        logger.info("🔍 Running Code Integrity Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0,
            'issues_found': []
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['code_integrity_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    results['issues_found'].append(test_file.name)
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['code_integrity_tests'] = results
        
        logger.info(f"🔍 Code Integrity Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_calculation_tests(self):
        """Run calculation tests"""
        logger.info("🧮 Running Calculation Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0,
            'calculation_errors': []
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['calculation_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    results['calculation_errors'].append(test_file.name)
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['calculation_tests'] = results
        
        logger.info(f"🧮 Calculation Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_critical_issue_tests(self):
        """Run critical issue tests"""
        logger.info("⚠️  Running Critical Issue Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0,
            'critical_issues': []
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['critical_issue_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    results['critical_issues'].append(test_file.name)
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['critical_issue_tests'] = results
        
        logger.info(f"⚠️  Critical Issue Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_random_tests(self):
        """Run random tests"""
        logger.info("🎲 Running Random Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['random_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['random_tests'] = results
        
        logger.info(f"🎲 Random Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_sanity_tests(self):
        """Run sanity tests"""
        logger.info("🔍 Running Sanity Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['sanity_tests']:
            try:
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode == 0:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                results['total'] += 1
                
                logger.info(f"   📄 {test_file.name}: {result.returncode}")
                
            except Exception as e:
                logger.error(f"❌ Error running {test_file}: {e}")
                results['errors'] += 1
                results['total'] += 1
        
        results['duration'] = time.time() - start_time
        self.test_results['sanity_tests'] = results
        
        logger.info(f"🔍 Sanity Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📋 Generating comprehensive test report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'test_results': self.test_results,
            'coverage': self.coverage_data,
            'summary': {}
        }
        
        # Calculate summary statistics
        total_tests = sum(results['total'] for results in self.test_results.values())
        total_passed = sum(results['passed'] for results in self.test_results.values())
        total_failed = sum(results['failed'] for results in self.test_results.values())
        total_errors = sum(results['errors'] for results in self.test_results.values())
        total_duration = sum(results['duration'] for results in self.test_results.values())
        
        report['summary'] = {
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_errors': total_errors,
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'total_duration': total_duration,
            'categories_tested': len([k for k, v in self.test_results.items() if v['total'] > 0])
        }
        
        # Save report
        report_file = self.project_root / 'test_framework' / 'test_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📋 Test report saved to: {report_file}")
        return report
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE TEST FRAMEWORK RESULTS")
        print("="*80)
        
        for category, results in self.test_results.items():
            if results['total'] > 0:
                status = "✅" if results['failed'] == 0 and results['errors'] == 0 else "❌"
                print(f"{status} {category.replace('_', ' ').title()}: {results['passed']}/{results['total']} passed")
        
        # Overall summary
        total_tests = sum(results['total'] for results in self.test_results.values())
        total_passed = sum(results['passed'] for results in self.test_results.values())
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print("-" * 80)
        print(f"📊 Overall Results: {total_passed}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        if self.coverage_data:
            total_lines = sum(self.coverage_data.values())
            covered_lines = sum(1 for file_data in self.coverage_data.values() 
                              for line in file_data.values() if line > 0)
            coverage_percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0
            print(f"📊 Code Coverage: {coverage_percentage:.1f}%")
        
        print("="*80)
    
    def run_all_tests(self):
        """Run all tests"""
        logger.info("🚀 Starting Comprehensive Test Framework...")
        
        self.start_time = datetime.now()
        
        # Discover tests
        self.discover_tests()
        
        # Run code coverage first
        coverage_percentage = self.run_code_coverage()
        
        # Run all test categories
        test_methods = [
            ('unit_tests', self.run_unit_tests),
            ('functional_tests', self.run_functional_tests),
            ('integration_tests', self.run_integration_tests),
            ('thread_safety_tests', self.run_thread_safety_tests),
            ('memory_tests', self.run_memory_tests),
            ('code_integrity_tests', self.run_code_integrity_tests),
            ('calculation_tests', self.run_calculation_tests),
            ('critical_issue_tests', self.run_critical_issue_tests),
            ('random_tests', self.run_random_tests),
            ('sanity_tests', self.run_sanity_tests)
        ]
        
        for category, test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                logger.error(f"❌ Error running {category}: {e}")
        
        self.end_time = datetime.now()
        
        # Generate report
        report = self.generate_test_report()
        
        # Print summary
        self.print_summary()
        
        return report

def main():
    """Main execution"""
    try:
        runner = ComprehensiveTestRunner()
        report = runner.run_all_tests()
        
        # Exit with appropriate code
        total_failed = sum(results['failed'] + results['errors'] for results in runner.test_results.values())
        if total_failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
