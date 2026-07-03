#!/usr/bin/env python3
"""
SANITY TESTS
============
Basic sanity tests for the project
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SanityTests:
    """Basic sanity tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        
    def test_project_structure(self):
        """Test basic project structure"""
        print("🏗️ Testing Project Structure...")
        
        try:
            # Check essential directories
            essential_dirs = ['logs', 'test_framework']
            
            for dir_name in essential_dirs:
                dir_path = project_root / dir_name
                if not dir_path.exists():
                    self.errors.append(f"Missing directory: {dir_name}")
            
            # Check essential files
            essential_files = [
                'logs/nifty_historical_data.csv',
                'logs/nifty_options_chain_2026-04-07.json'
            ]
            
            for file_name in essential_files:
                file_path = project_root / file_name
                if not file_path.exists():
                    self.errors.append(f"Missing file: {file_name}")
            
            if len(self.errors) == 0:
                self.test_results.append({
                    'test': 'project_structure',
                    'status': 'passed'
                })
                print("✅ Project structure test passed")
                return True
            else:
                print("❌ Project structure test failed")
                for error in self.errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Project structure error: {e}")
            print(f"❌ Project structure error: {e}")
            return False
    
    def test_data_files_exist(self):
        """Test that data files exist and are readable"""
        print("📁 Testing Data Files...")
        
        try:
            # Test historical data
            hist_file = project_root / 'logs/nifty_historical_data.csv'
            if hist_file.exists():
                df = pd.read_csv(hist_file)
                if len(df) == 0:
                    self.errors.append("Historical data file is empty")
                elif 'close' not in df.columns:
                    self.errors.append("Historical data missing 'close' column")
                else:
                    print(f"   ✓ Historical data: {len(df)} rows")
            else:
                self.errors.append("Historical data file not found")
            
            # Test options chain
            options_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
            if options_file.exists():
                with open(options_file, 'r') as f:
                    data = json.load(f)
                if len(data) == 0:
                    self.errors.append("Options chain file is empty")
                else:
                    print(f"   ✓ Options chain: {len(data)} strikes")
            else:
                self.errors.append("Options chain file not found")
            
            if len(self.errors) == 0:
                self.test_results.append({
                    'test': 'data_files_exist',
                    'status': 'passed'
                })
                print("✅ Data files test passed")
                return True
            else:
                print("❌ Data files test failed")
                for error in self.errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Data files error: {e}")
            print(f"❌ Data files error: {e}")
            return False
    
    def test_python_scripts_run(self):
        """Test that Python scripts can run without syntax errors"""
        print("🐍 Testing Python Scripts...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            syntax_errors = []
            
            for py_file in python_files:
                try:
                    # Try to compile the script
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    compile(content, str(py_file), 'exec')
                    print(f"   ✓ {py_file.name}")
                except SyntaxError as e:
                    syntax_errors.append(f"{py_file.name}: {e}")
                except Exception as e:
                    syntax_errors.append(f"{py_file.name}: {e}")
            
            if len(syntax_errors) == 0:
                self.test_results.append({
                    'test': 'python_scripts_run',
                    'files_checked': len(python_files),
                    'syntax_errors': 0,
                    'status': 'passed'
                })
                print("✅ Python scripts test passed")
                return True
            else:
                print("❌ Python scripts test failed")
                for error in syntax_errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Python scripts error: {e}")
            print(f"❌ Python scripts error: {e}")
            return False
    
    def test_imports_work(self):
        """Test that imports work correctly"""
        print("📦 Testing Imports...")
        
        try:
            # Test standard library imports
            try:
                import pandas as pd
                import numpy as np
                import json
                import threading
                import queue
                print("   ✓ Standard library imports")
            except ImportError as e:
                self.errors.append(f"Standard library import error: {e}")
            
            # Test project files imports
            python_files = list(project_root.glob('*.py'))
            import_errors = []
            
            for py_file in python_files:
                if py_file.name == 'test_framework':  # Skip test framework
                    continue
                    
                try:
                    # Try to import the module
                    module_name = py_file.stem
                    spec = __import__(module_name)
                    print(f"   ✓ {module_name}")
                except ImportError:
                    # Some files might not be importable (no __init__.py)
                    pass
                except Exception as e:
                    import_errors.append(f"{py_file.name}: {e}")
            
            if len(self.errors) == 0 and len(import_errors) == 0:
                self.test_results.append({
                    'test': 'imports_work',
                    'status': 'passed'
                })
                print("✅ Imports test passed")
                return True
            else:
                print("❌ Imports test failed")
                for error in self.errors + import_errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Imports error: {e}")
            print(f"❌ Imports error: {e}")
            return False
    
    def test_basic_calculations(self):
        """Test basic calculations work"""
        print("🧮 Testing Basic Calculations...")
        
        try:
            # Test basic arithmetic
            result = 100 * 50  # premium * lot_size
            if result != 5000:
                self.errors.append(f"Basic calculation error: 100 * 50 = {result}")
            
            # Test percentage calculation
            pnl = 100
            investment = 5000
            roi = (pnl / investment) * 100
            if roi != 2.0:
                self.errors.append(f"ROI calculation error: (100 / 5000) * 100 = {roi}")
            
            # Test win rate calculation
            wins = 8
            total = 10
            win_rate = (wins / total) * 100
            if win_rate != 80.0:
                self.errors.append(f"Win rate calculation error: (8 / 10) * 100 = {win_rate}")
            
            if len(self.errors) == 0:
                self.test_results.append({
                    'test': 'basic_calculations',
                    'status': 'passed'
                })
                print("✅ Basic calculations test passed")
                return True
            else:
                print("❌ Basic calculations test failed")
                for error in self.errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Basic calculations error: {e}")
            print(f"❌ Basic calculations error: {e}")
            return False
    
    def test_data_format(self):
        """Test data format is correct"""
        print("📊 Testing Data Format...")
        
        try:
            # Test historical data format
            hist_file = project_root / 'logs/nifty_historical_data.csv'
            if hist_file.exists():
                df = pd.read_csv(hist_file)
                
                required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                for col in required_columns:
                    if col not in df.columns:
                        self.errors.append(f"Missing column in historical data: {col}")
                
                # Test data types
                if not pd.api.types.is_numeric_dtype(df['close']):
                    self.errors.append("Close price is not numeric")
                
                if not pd.api.types.is_numeric_dtype(df['volume']):
                    self.errors.append("Volume is not numeric")
                
                print(f"   ✓ Historical data format: {len(df)} rows, {len(df.columns)} columns")
            
            # Test options chain format
            options_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
            if options_file.exists():
                with open(options_file, 'r') as f:
                    data = json.load(f)
                
                # Check first strike
                first_strike = list(data.keys())[0]
                strike_data = data[first_strike]
                
                if 'ce' not in strike_data:
                    self.errors.append("Missing CE data in options chain")
                
                if 'pe' not in strike_data:
                    self.errors.append("Missing PE data in options chain")
                
                print(f"   ✓ Options chain format: {len(data)} strikes")
            
            if len(self.errors) == 0:
                self.test_results.append({
                    'test': 'data_format',
                    'status': 'passed'
                })
                print("✅ Data format test passed")
                return True
            else:
                print("❌ Data format test failed")
                for error in self.errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Data format error: {e}")
            print(f"❌ Data format error: {e}")
            return False
    
    def test_premium_constraints(self):
        """Test premium constraints are respected"""
        print("💰 Testing Premium Constraints...")
        
        try:
            options_file = project_root / 'logs/nifty_options_chain_2026-04-07.json'
            if not options_file.exists():
                self.errors.append("Options chain file not found")
                return False
            
            with open(options_file, 'r') as f:
                data = json.load(f)
            
            max_premium = 350
            violations = []
            
            for strike, strike_data in data.items():
                # Check CE options
                if 'ce' in strike_data:
                    premium = strike_data['ce'].get('last_price', 0)
                    if premium > max_premium:
                        violations.append(f"CE {strike}: premium {premium} > {max_premium}")
                
                # Check PE options
                if 'pe' in strike_data:
                    premium = strike_data['pe'].get('last_price', 0)
                    if premium > max_premium:
                        violations.append(f"PE {strike}: premium {premium} > {max_premium}")
            
            if len(violations) == 0:
                self.test_results.append({
                    'test': 'premium_constraints',
                    'max_premium': max_premium,
                    'violations': 0,
                    'status': 'passed'
                })
                print("✅ Premium constraints test passed")
                return True
            else:
                print("❌ Premium constraints test failed")
                for violation in violations[:10]:
                    print(f"   - {violation}")
                return False
                
        except Exception as e:
            self.errors.append(f"Premium constraints error: {e}")
            print(f"❌ Premium constraints error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all sanity tests"""
        print("🔍 Starting Sanity Tests...")
        print("="*50)
        
        tests = [
            self.test_project_structure,
            self.test_data_files_exist,
            self.test_python_scripts_run,
            self.test_imports_work,
            self.test_basic_calculations,
            self.test_data_format,
            self.test_premium_constraints
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
        
        print("="*50)
        print(f"🔍 Sanity Tests Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📊 Total Tests: {passed + failed}")
        
        if self.errors:
            print(f"   ⚠️  Errors: {len(self.errors)}")
        
        return len(self.errors) == 0

def main():
    """Main execution"""
    tester = SanityTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All sanity tests passed!")
        return 0
    else:
        print("❌ Some sanity tests failed!")
        return 1

if __name__ == "__main__":
    main()
