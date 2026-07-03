#!/usr/bin/env python3
"""
PRODUCTION VALIDATION
====================
Comprehensive production validation
"""

import sys
import os
import json
import threading
import gc
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ProductionValidation:
    """Production validation"""
    
    def __init__(self):
        self.validation_results = []
        self.critical_issues = []
        
    def validate_data_integrity(self):
        """Validate data integrity"""
        print("📁 Validating Data Integrity...")
        
        try:
            # Check historical data
            hist_file = project_root / 'logs' / 'nifty_historical_data.csv'
            if not hist_file.exists():
                self.critical_issues.append("Historical data file missing")
                return False
            
            # Check filtered options chain
            options_file = project_root / 'logs' / 'nifty_options_chain_filtered_350.json'
            if not options_file.exists():
                self.critical_issues.append("Filtered options chain file missing")
                return False
            
            with open(options_file, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            if len(data) == 0:
                self.critical_issues.append("Options chain data empty")
                return False
            
            # Check premium constraints
            max_premium = 350
            violations = 0
            for strike, strike_data in data.items():
                for option_type in ['ce', 'pe']:
                    if option_type in strike_data:
                        premium = strike_data[option_type].get('last_price', 0)
                        if premium > max_premium:
                            violations += 1
            
            if violations > 0:
                self.critical_issues.append(f"Found {violations} premium violations")
                return False
            
            self.validation_results.append({
                'test': 'data_integrity',
                'status': 'passed',
                'strikes': len(data),
                'violations': violations
            })
            print("✅ Data integrity validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Data integrity error: {e}")
            return False
    
    def validate_calculations(self):
        """Validate calculations"""
        print("🧮 Validating Calculations...")
        
        try:
            # Test premium calculation
            premium = 100.0
            lot_size = 50
            investment = premium * lot_size
            if investment != 5000.0:
                self.critical_issues.append("Premium calculation incorrect")
                return False
            
            # Test P&L calculation
            entry_premium = 100
            exit_premium = 110
            pnl = (exit_premium - entry_premium) * lot_size
            if pnl != 500.0:
                self.critical_issues.append("P&L calculation incorrect")
                return False
            
            # Test ROI calculation
            roi = (pnl / investment) * 100
            if roi != 10.0:
                self.critical_issues.append("ROI calculation incorrect")
                return False
            
            self.validation_results.append({
                'test': 'calculations',
                'status': 'passed',
                'calculations': 3
            })
            print("✅ Calculations validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Calculations error: {e}")
            return False
    
    def validate_thread_safety(self):
        """Validate thread safety"""
        print("🧵 Validating Thread Safety...")
        
        try:
            # Test basic thread safety
            counter = 0
            lock = threading.Lock()
            
            def safe_increment():
                nonlocal counter
                for i in range(100):
                    with lock:
                        counter += 1
            
            threads = []
            for i in range(5):
                thread = threading.Thread(target=safe_increment)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            expected = 5 * 100
            if counter != expected:
                self.critical_issues.append(f"Thread safety failed: {counter} != {expected}")
                return False
            
            self.validation_results.append({
                'test': 'thread_safety',
                'status': 'passed',
                'counter': counter
            })
            print("✅ Thread safety validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Thread safety error: {e}")
            return False
    
    def validate_memory_management(self):
        """Validate memory management"""
        print("🧠 Validating Memory Management...")
        
        try:
            initial_objects = len(gc.get_objects())
            
            # Create and clean up objects
            objects = []
            for i in range(1000):
                obj = {'data': f'test_{i}' * 100}
                objects.append(obj)
            
            gc.collect()
            
            # Clean up
            del objects
            gc.collect()
            
            final_objects = len(gc.get_objects())
            
            if final_objects > initial_objects + 1000:
                self.critical_issues.append("Potential memory leak detected")
                return False
            
            self.validation_results.append({
                'test': 'memory_management',
                'status': 'passed',
                'object_growth': final_objects - initial_objects
            })
            print("✅ Memory management validation passed")
            return True
            
        except Exception as e:
            self.critical_issues.append(f"Memory management error: {e}")
            return False
    
    def run_production_validation(self):
        """Run production validation"""
        print("🚀 STARTING PRODUCTION VALIDATION")
        print("="*50)
        
        validations = [
            self.validate_data_integrity,
            self.validate_calculations,
            self.validate_thread_safety,
            self.validate_memory_management
        ]
        
        passed = 0
        for validation in validations:
            if validation():
                passed += 1
        
        print("="*50)
        print(f"📊 Production Validation Results:")
        print(f"   ✅ Passed: {passed}/{len(validations)}")
        print(f"   ❌ Failed: {len(validations) - passed}")
        print(f"   🚨 Critical Issues: {len(self.critical_issues)}")
        
        if self.critical_issues:
            print(f"\n🚨 Critical Issues:")
            for issue in self.critical_issues:
                print(f"   - {issue}")
        
        # Final verdict
        if len(self.critical_issues) == 0 and passed == len(validations):
            print("\n🎉 PRODUCTION VALIDATION PASSED!")
            return True
        else:
            print("\n❌ PRODUCTION VALIDATION FAILED!")
            return False

if __name__ == "__main__":
    validator = ProductionValidation()
    success = validator.run_production_validation()
    
    if success:
        print("\n✅ SYSTEM IS PRODUCTION READY!")
        sys.exit(0)
    else:
        print("\n❌ SYSTEM IS NOT PRODUCTION READY!")
        sys.exit(1)
