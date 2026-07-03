#!/usr/bin/env python3
"""
CRITICAL ISSUE TESTS
==================
Critical issue detection and prevention tests
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class CriticalIssueTests:
    """Critical issue detection tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        self.critical_issues = []
        
    def test_infinite_loop_detection(self):
        """Test for potential infinite loops"""
        print("🔄 Testing Infinite Loop Detection...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            infinite_loop_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for while True without break
                        if 'while True:' in line:
                            # Check if there's a break statement in the next 20 lines
                            has_break = False
                            for i in range(1, 21):
                                if line_number + i < len(lines):
                                    if 'break' in lines[line_number + i]:
                                        has_break = True
                                        break
                            
                            if not has_break:
                                infinite_loop_risks.append(f"{py_file.name}:{line_number} - while True without break")
                        
                        # Check for for loops with very large ranges
                        if 'for' in line and 'range(' in line:
                            if 'range(' in line and ('999999' in line or '99999' in line or '9999' in line):
                                infinite_loop_risks.append(f"{py_file.name}:{line_number} - Very large range in for loop")
                        
                        line_number += 1
                
                except Exception as e:
                    infinite_loop_risks.append(f"{py_file.name}: {e}")
            
            if len(infinite_loop_risks) == 0:
                self.test_results.append({
                    'test': 'infinite_loop_detection',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ Infinite loop detection passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(infinite_loop_risks)
                print(f"❌ Infinite loop detection failed: {len(infinite_loop_risks)} risks found")
                for risk in infinite_loop_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Infinite loop detection error: {e}")
            print(f"❌ Infinite loop detection error: {e}")
            return False
    
    def test_division_by_zero(self):
        """Test for potential division by zero"""
        print("🔢 Testing Division by Zero...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            division_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for division operations
                        if '/' in line or '//' in line:
                            # Check if denominator could be zero
                            if '/ 0' in line or '// 0' in line:
                                division_risks.append(f"{py_file.name}:{line_number} - Division by zero")
                            
                            # Check for variable division
                            if '/' in line:
                                parts = line.split('/')
                                if len(parts) > 1:
                                    denominator = parts[1].strip()
                                    # Check if denominator could be zero
                                    if '0' in denominator and not any(char in denominator for char in '123456789'):
                                        division_risks.append(f"{py_file.name}:{line_number} - Potential division by zero")
                        
                        line_number += 1
                
                except Exception as e:
                    division_risks.append(f"{py_file.name}: {e}")
            
            if len(division_risks) == 0:
                self.test_results.append({
                    'test': 'division_by_zero',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ Division by zero test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(division_risks)
                print(f"❌ Division by zero test failed: {len(division_risks)} risks found")
                for risk in division_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Division by zero error: {e}")
            print(f"❌ Division by zero error: {e}")
            return False
    
    def test_null_pointer_dereference(self):
        """Test for null pointer dereference"""
        print("🚫 Testing Null Pointer Dereference...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            null_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for None access
                        if 'None' in line and ('.' in line or '[' in line):
                            null_risks.append(f"{py_file.name}:{line_number} - Potential None access")
                        
                        # Check for variable access without None check
                        if '.' in line or '[' in line:
                            # Look for variable access that might be None
                            if 'if' not in line and 'None' not in line:
                                # This is a simplified check
                                if any(var in line for var in ['data', 'result', 'response', 'object']):
                                    null_risks.append(f"{py_file.name}:{line_number} - Variable access without None check")
                        
                        line_number += 1
                
                except Exception as e:
                    null_risks.append(f"{py_file.name}: {e}")
            
            if len(null_risks) < 10:  # Allow some potential risks
                self.test_results.append({
                    'test': 'null_pointer_dereference',
                    'files_checked': len(python_files),
                    'risks_found': len(null_risks),
                    'status': 'passed'
                })
                print(f"✅ Null pointer dereference test passed: {len(null_risks)} risks found")
                return True
            else:
                self.critical_issues.extend(null_risks)
                print(f"❌ Null pointer dereference test failed: {len(null_risks)} risks found")
                for risk in null_risks[:10]:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Null pointer dereference error: {e}")
            print(f"❌ Null pointer dereference error: {e}")
            return False
    
    def test_buffer_overflow(self):
        """Test for potential buffer overflow"""
        print("💾 Testing Buffer Overflow...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            buffer_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for array/list operations without bounds checking
                        if '[' in line and ']' in line:
                            # Check for hardcoded large indices
                            if any(num in line for num in ['9999', '99999', '999999']):
                                buffer_risks.append(f"{py_file.name}:{line_number} - Large array index")
                        
                        # Check for string operations that might overflow
                        if 'join(' in line or 'format(' in line:
                            if 'len(' in line and '*' in line:
                                buffer_risks.append(f"{py_file.name}:{line_number} - Potential string overflow")
                        
                        line_number += 1
                
                except Exception as e:
                    buffer_risks.append(f"{py_file.name}: {e}")
            
            if len(buffer_risks) == 0:
                self.test_results.append({
                    'test': 'buffer_overflow',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ Buffer overflow test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(buffer_risks)
                print(f"❌ Buffer overflow test failed: {len(buffer_risks)} risks found")
                for risk in buffer_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Buffer overflow error: {e}")
            print(f"❌ Buffer overflow error: {e}")
            return False
    
    def test_sql_injection(self):
        """Test for SQL injection vulnerabilities"""
        print("🗄️ Testing SQL Injection...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            sql_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for SQL operations
                        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP']
                        if any(keyword in line.upper() for keyword in sql_keywords):
                            # Check for string formatting in SQL
                            if '%' in line or 'format(' in line or 'f"' in line:
                                sql_risks.append(f"{py_file.name}:{line_number} - SQL with string formatting")
                            
                            # Check for direct concatenation
                            if '+' in line and 'sql' in line.lower():
                                sql_risks.append(f"{py_file.name}:{line_number} - SQL concatenation")
                        
                        line_number += 1
                
                except Exception as e:
                    sql_risks.append(f"{py_file.name}: {e}")
            
            if len(sql_risks) == 0:
                self.test_results.append({
                    'test': 'sql_injection',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ SQL injection test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(sql_risks)
                print(f"❌ SQL injection test failed: {len(sql_risks)} risks found")
                for risk in sql_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"SQL injection error: {e}")
            print(f"❌ SQL injection error: {e}")
            return False
    
    def test_hardcoded_secrets(self):
        """Test for hardcoded secrets and credentials"""
        print("🔐 Testing Hardcoded Secrets...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            secret_risks = []
            
            # Common secret patterns
            secret_patterns = [
                'password', 'passwd', 'pwd', 'secret', 'key', 'token',
                'api_key', 'access_key', 'private_key', 'auth',
                'client_id', 'client_secret', 'database_url'
            ]
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for hardcoded secrets
                        for pattern in secret_patterns:
                            if pattern in line.lower():
                                # Check for assignment with string value
                                if '=' in line and ('"' in line or "'" in line):
                                    secret_risks.append(f"{py_file.name}:{line_number} - Potential hardcoded {pattern}")
                        
                        line_number += 1
                
                except Exception as e:
                    secret_risks.append(f"{py_file.name}: {e}")
            
            if len(secret_risks) == 0:
                self.test_results.append({
                    'test': 'hardcoded_secrets',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ Hardcoded secrets test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(secret_risks)
                print(f"❌ Hardcoded secrets test failed: {len(secret_risks)} risks found")
                for risk in secret_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Hardcoded secrets error: {e}")
            print(f"❌ Hardcoded secrets error: {e}")
            return False
    
    def test_unsafe_deserialization(self):
        """Test for unsafe deserialization"""
        print("📦 Testing Unsafe Deserialization...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            deserialization_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for pickle usage
                        if 'pickle' in line.lower():
                            if 'load(' in line or 'loads(' in line:
                                deserialization_risks.append(f"{py_file.name}:{line_number} - Unsafe pickle deserialization")
                        
                        # Check for eval/exec usage
                        if 'eval(' in line or 'exec(' in line:
                            deserialization_risks.append(f"{py_file.name}:{line_number} - Unsafe eval/exec usage")
                        
                        line_number += 1
                
                except Exception as e:
                    deserialization_risks.append(f"{py_file.name}: {e}")
            
            if len(deserialization_risks) == 0:
                self.test_results.append({
                    'test': 'unsafe_deserialization',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ Unsafe deserialization test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(deserialization_risks)
                print(f"❌ Unsafe deserialization test failed: {len(deserialization_risks)} risks found")
                for risk in deserialization_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Unsafe deserialization error: {e}")
            print(f"❌ Unsafe deserialization error: {e}")
            return False
    
    def test_file_path_traversal(self):
        """Test for file path traversal vulnerabilities"""
        print("📁 Testing File Path Traversal...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            path_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for file operations with user input
                        if 'open(' in line or 'file(' in line:
                            # Check for path traversal patterns
                            if '../' in line or '..\\' in line:
                                path_risks.append(f"{py_file.name}:{line_number} - Path traversal pattern")
                            
                            # Check for direct use of user input in file paths
                            if 'input(' in line or 'argv[' in line:
                                path_risks.append(f"{py_file.name}:{line_number} - User input in file path")
                        
                        line_number += 1
                
                except Exception as e:
                    path_risks.append(f"{py_file.name}: {e}")
            
            if len(path_risks) == 0:
                self.test_results.append({
                    'test': 'file_path_traversal',
                    'files_checked': len(python_files),
                    'risks_found': 0,
                    'status': 'passed'
                })
                print(f"✅ File path traversal test passed: {len(python_files)} files checked")
                return True
            else:
                self.critical_issues.extend(path_risks)
                print(f"❌ File path traversal test failed: {len(path_risks)} risks found")
                for risk in path_risks:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"File path traversal error: {e}")
            print(f"❌ File path traversal error: {e}")
            return False
    
    def test_race_conditions(self):
        """Test for race conditions"""
        print("🏁 Testing Race Conditions...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            race_risks = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    line_number = 1
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check for shared resource access without locks
                        if 'threading' in content:
                            if 'append(' in line or 'extend(' in line:
                                if 'lock' not in line and 'Lock' not in line:
                                    race_risks.append(f"{py_file.name}:{line_number} - Shared list access without lock")
                            
                            if '=' in line and not any(keyword in line for keyword in ['lock', 'Lock', 'with']):
                                if any(var in line for var in ['counter', 'total', 'sum']):
                                    race_risks.append(f"{py_file.name}:{line_number} - Shared variable access without lock")
                        
                        line_number += 1
                
                except Exception as e:
                    race_risks.append(f"{py_file.name}: {e}")
            
            if len(race_risks) < 5:  # Allow some potential race conditions
                self.test_results.append({
                    'test': 'race_conditions',
                    'files_checked': len(python_files),
                    'risks_found': len(race_risks),
                    'status': 'passed'
                })
                print(f"✅ Race conditions test passed: {len(race_risks)} risks found")
                return True
            else:
                self.critical_issues.extend(race_risks)
                print(f"❌ Race conditions test failed: {len(race_risks)} risks found")
                for risk in race_risks[:10]:
                    print(f"   - {risk}")
                return False
                
        except Exception as e:
            self.errors.append(f"Race conditions error: {e}")
            print(f"❌ Race conditions error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all critical issue tests"""
        print("⚠️ Starting Critical Issue Tests...")
        print("="*60)
        
        tests = [
            self.test_infinite_loop_detection,
            self.test_division_by_zero,
            self.test_null_pointer_dereference,
            self.test_buffer_overflow,
            self.test_sql_injection,
            self.test_hardcoded_secrets,
            self.test_unsafe_deserialization,
            self.test_file_path_traversal,
            self.test_race_conditions
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test failed: {e}")
                failed += 1
        
        print("="*60)
        print(f"⚠️ Critical Issue Tests Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📊 Total Tests: {passed + failed}")
        print(f"   📝 Test Results: {len(self.test_results)}")
        
        if self.critical_issues:
            print(f"   🚨 Critical Issues: {len(self.critical_issues)}")
            for issue in self.critical_issues:
                print(f"      - {issue}")
        
        if self.errors:
            print(f"   ⚠️  Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"      - {error}")
        
        return len(self.critical_issues) == 0 and len(self.errors) == 0

def main():
    """Main execution"""
    tester = CriticalIssueTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All critical issue tests passed!")
        return 0
    else:
        print("❌ Some critical issue tests failed!")
        return 1

if __name__ == "__main__":
    main()
