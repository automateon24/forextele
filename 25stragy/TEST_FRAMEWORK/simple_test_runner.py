#!/usr/bin/env python3
"""
SIMPLE TEST RUNNER
==================
Simple test runner without external dependencies
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SimpleTestRunner:
    """Simple test runner"""
    
    def __init__(self):
        self.project_root = project_root
        self.test_results = {}
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
            'sanity_tests': []
        }
        
    def discover_tests(self):
        """Discover all test files"""
        print("🔍 Discovering test files...")
        
        test_patterns = {
            'unit_tests': 'test_*.py',
            'functional_tests': 'functional_*.py',
            'integration_tests': 'integration_*.py',
            'thread_safety_tests': 'thread_*.py',
            'memory_tests': 'memory_*.py',
            'code_integrity_tests': 'integrity_*.py',
            'calculation_tests': 'calculation_*.py',
            'critical_issue_tests': 'critical_*.py',
            'sanity_tests': 'sanity_*.py'
        }
        
        for category, pattern in test_patterns.items():
            test_files = list(self.project_root.glob(pattern))
            self.test_categories[category] = test_files
            print(f"   📁 {category}: {len(test_files)} files found")
    
    def run_test_file(self, test_file):
        """Run a single test file"""
        try:
            result = subprocess.run([
                sys.executable, str(test_file)
            ], capture_output=True, text=True, cwd=self.project_root, timeout=60)
            
            return {
                'file': test_file.name,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                'file': test_file.name,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Test timed out',
                'success': False
            }
        except Exception as e:
            return {
                'file': test_file.name,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    def run_unit_tests(self):
        """Run unit tests"""
        print("🧪 Running Unit Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['unit_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['unit_tests'] = results
        
        print(f"🧪 Unit Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_functional_tests(self):
        """Run functional tests"""
        print("🔧 Running Functional Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['functional_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['functional_tests'] = results
        
        print(f"🔧 Functional Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_thread_safety_tests(self):
        """Run thread safety tests"""
        print("🧵 Running Thread Safety Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['thread_safety_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['thread_safety_tests'] = results
        
        print(f"🧵 Thread Safety Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_memory_tests(self):
        """Run memory tests"""
        print("🧠 Running Memory Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['memory_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['memory_tests'] = results
        
        print(f"🧠 Memory Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_code_integrity_tests(self):
        """Run code integrity tests"""
        print("🔍 Running Code Integrity Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['code_integrity_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['code_integrity_tests'] = results
        
        print(f"🔍 Code Integrity Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_calculation_tests(self):
        """Run calculation tests"""
        print("🧮 Running Calculation Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['calculation_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['calculation_tests'] = results
        
        print(f"🧮 Calculation Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_critical_issue_tests(self):
        """Run critical issue tests"""
        print("⚠️ Running Critical Issue Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['critical_issue_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['critical_issue_tests'] = results
        
        print(f"⚠️ Critical Issue Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def run_sanity_tests(self):
        """Run sanity tests"""
        print("🔍 Running Sanity Tests...")
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        for test_file in self.test_categories['sanity_tests']:
            result = self.run_test_file(test_file)
            results['total'] += 1
            
            if result['success']:
                results['passed'] += 1
                print(f"   ✅ {test_file.name}")
            else:
                results['failed'] += 1
                print(f"   ❌ {test_file.name}")
                if result['stderr']:
                    print(f"      Error: {result['stderr'][:100]}...")
        
        results['duration'] = time.time() - start_time
        self.test_results['sanity_tests'] = results
        
        print(f"🔍 Sanity Tests: {results['passed']}/{results['total']} passed")
        return results
    
    def generate_test_report(self):
        """Generate test report"""
        print("📋 Generating test report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'test_results': self.test_results,
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
        
        print(f"📋 Test report saved to: {report_file}")
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
        
        total_duration = sum(results['duration'] for results in self.test_results.values())
        print(f"⏱️ Total Duration: {total_duration:.2f} seconds")
        
        print("="*80)
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Comprehensive Test Framework...")
        print("="*80)
        
        self.start_time = datetime.now()
        
        # Discover tests
        self.discover_tests()
        
        # Run all test categories
        test_methods = [
            ('unit_tests', self.run_unit_tests),
            ('functional_tests', self.run_functional_tests),
            ('thread_safety_tests', self.run_thread_safety_tests),
            ('memory_tests', self.run_memory_tests),
            ('code_integrity_tests', self.run_code_integrity_tests),
            ('calculation_tests', self.run_calculation_tests),
            ('critical_issue_tests', self.run_critical_issue_tests),
            ('sanity_tests', self.run_sanity_tests)
        ]
        
        for category, test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                print(f"❌ Error running {category}: {e}")
        
        self.end_time = datetime.now()
        
        # Generate report
        report = self.generate_test_report()
        
        # Print summary
        self.print_summary()
        
        return report

def main():
    """Main execution"""
    try:
        runner = SimpleTestRunner()
        report = runner.run_all_tests()
        
        # Exit with appropriate code
        total_failed = sum(results['failed'] + results['errors'] for results in runner.test_results.values())
        if total_failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
