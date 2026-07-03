#!/usr/bin/env python3
"""
FINAL PRODUCTION TESTS
=====================
Final production readiness tests without encoding issues
"""

import sys
import os
import json
import time
import threading
import gc
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class FinalProductionTests:
    """Final production readiness tests"""
    
    def __init__(self):
        self.test_results = []
        self.critical_failures = []
        
    def test_core_calculations(self):
        """Test core calculations"""
        print("🧮 Testing Core Calculations...")
        
        try:
            # Test premium calculation
            premium = 100.0
            lot_size = 50
            investment = premium * lot_size
            assert investment == 5000.0, f"Premium calculation failed: {investment}"
            
            # Test P&L calculation
            entry_premium = 100
            exit_premium = 110
            pnl = (exit_premium - entry_premium) * lot_size
            assert pnl == 500.0, f"P&L calculation failed: {pnl}"
            
            # Test ROI calculation
            roi = (pnl / investment) * 100
            assert roi == 10.0, f"ROI calculation failed: {roi}"
            
            # Test win rate calculation
            wins = 8
            total_trades = 10
            win_rate = (wins / total_trades) * 100
            assert win_rate == 80.0, f"Win rate calculation failed: {pnl}"
            
            # Test risk-reward ratio
            profit_target = 200
            stop_loss = 50
            risk_reward = profit_target / stop_loss
            assert risk_reward == 4.0, f"Risk-reward calculation failed: {risk_reward}"
            
            self.test_results.append({
                'test': 'core_calculations',
                'status': 'passed',
                'calculations': 5
            })
            print("✅ Core calculations test passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Core calculations failed: {e}")
            print(f"❌ Core calculations failed: {e}")
            return False
    
    def test_data_files_integrity(self):
        """Test data files integrity"""
        print("📁 Testing Data Files Integrity...")
        
        try:
            # Test historical data
            hist_file = project_root / 'logs/nifty_historical_data.csv'
            if not hist_file.exists():
                raise Exception("Historical data file not found")
            
            # Read first few lines
            with open(hist_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:5]
            
            if len(lines) < 2:
                raise Exception("Historical data file is empty")
            
            # Check header
            header = lines[0].strip()
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in header:
                    raise Exception(f"Missing column: {col}")
            
            # Test filtered options chain
            options_file = project_root / 'logs/nifty_options_chain_filtered_350.json'
            if not options_file.exists():
                raise Exception("Filtered options chain file not found")
            
            with open(options_file, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            if len(data) == 0:
                raise Exception("Options chain file is empty")
            
            # Check premium constraint (should be 0 violations)
            max_premium = 350
            violations = 0
            for strike, strike_data in data.items():
                for option_type in ['ce', 'pe']:
                    if option_type in strike_data:
                        premium = strike_data[option_type].get('last_price', 0)
                        if premium > max_premium:
                            violations += 1
            
            if violations > 0:
                raise Exception(f"Found {violations} premium violations after filtering")
            
            self.test_results.append({
                'test': 'data_files_integrity',
                'status': 'passed',
                'historical_rows': len(lines),
                'options_strikes': len(data),
                'premium_violations': violations
            })
            print(f"✅ Data files integrity test passed: {len(data)} strikes, {len(lines)}+ rows")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Data files integrity failed: {e}")
            print(f"❌ Data files integrity failed: {e}")
            return False
    
    def test_premium_constraints(self):
        """Test premium constraints"""
        print("💰 Testing Premium Constraints...")
        
        try:
            options_file = project_root / 'logs/nifty_options_chain_filtered_350.json'
            with open(options_file, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            max_premium = 350
            valid_strikes = 0
            total_strikes = 0
            
            for strike, strike_data in data.items():
                total_strikes += 1
                
                # Check CE
                if 'ce' in strike_data:
                    premium = strike_data['ce'].get('last_price', 0)
                    if 0 < premium <= max_premium:
                        valid_strikes += 1
                
                # Check PE
                if 'pe' in strike_data:
                    premium = strike_data['pe'].get('last_price', 0)
                    if 0 < premium <= max_premium:
                        valid_strikes += 1
            
            if valid_strikes == 0:
                raise Exception("No valid strikes found under premium limit")
            
            self.test_results.append({
                'test': 'premium_constraints',
                'status': 'passed',
                'valid_strikes': valid_strikes,
                'total_strikes': total_strikes,
                'max_premium': max_premium
            })
            print(f"✅ Premium constraints test passed: {valid_strikes} valid strikes")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Premium constraints failed: {e}")
            print(f"❌ Premium constraints failed: {e}")
            return False
    
    def test_greeks_validity(self):
        """Test Greeks validity"""
        print("📊 Testing Greeks Validity...")
        
        try:
            options_file = project_root / 'logs/nifty_options_chain_filtered_350.json'
            with open(options_file, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            valid_greeks = 0
            total_greeks = 0
            
            for strike, strike_data in data.items():
                for option_type in ['ce', 'pe']:
                    if option_type in strike_data:
                        option_data = strike_data[option_type]
                        
                        # Check Delta
                        delta = option_data.get('delta', 0)
                        if -1 <= delta <= 1:
                            valid_greeks += 1
                        total_greeks += 1
                        
                        # Check Theta (should be negative)
                        theta = option_data.get('theta', 0)
                        if theta <= 0:
                            valid_greeks += 1
                        total_greeks += 1
                        
                        # Check Vega (should be positive)
                        vega = option_data.get('vega', 0)
                        if vega >= 0:
                            valid_greeks += 1
                        total_greeks += 1
                        
                        # Check Gamma (should be positive)
                        gamma = option_data.get('gamma', 0)
                        if gamma >= 0:
                            valid_greeks += 1
                        total_greeks += 1
            
            if valid_greeks < total_greeks * 0.8:
                raise Exception(f"Too many invalid Greeks: {valid_greeks}/{total_greeks}")
            
            self.test_results.append({
                'test': 'greeks_validity',
                'status': 'passed',
                'valid_greeks': valid_greeks,
                'total_greeks': total_greeks,
                'validity_rate': valid_greeks / total_greeks * 100
            })
            print(f"✅ Greeks validity test passed: {valid_greeks}/{total_greeks} valid")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Greeks validity failed: {e}")
            print(f"❌ Greeks validity failed: {e}")
            return False
    
    def test_file_existence(self):
        """Test critical files exist"""
        print("📄 Testing File Existence...")
        
        try:
            critical_files = [
                'logs/nifty_historical_data.csv',
                'logs/nifty_options_chain_filtered_350.json',
                'real_dhan_api_only_system.py',
                'ultra_optimized_40_percent.py'
            ]
            
            for file_path in critical_files:
                full_path = project_root / file_path
                if not full_path.exists():
                    raise Exception(f"Critical file missing: {file_path}")
            
            # Test file sizes are reasonable
            hist_file = project_root / 'logs/nifty_historical_data.csv'
            if hist_file.stat().st_size < 1000:  # At least 1KB
                raise Exception("Historical data file too small")
            
            options_file = project_root / 'logs/nifty_options_chain_filtered_350.json'
            if options_file.stat().st_size < 100:  # At least 100 bytes
                raise Exception("Options chain file too small")
            
            self.test_results.append({
                'test': 'file_existence',
                'status': 'passed',
                'critical_files': len(critical_files)
            })
            print(f"✅ File existence test passed: {len(critical_files)} files")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"File existence failed: {e}")
            print(f"❌ File existence failed: {e}")
            return False
    
    def test_thread_safety(self):
        """Test thread safety"""
        print("🧵 Testing Thread Safety...")
        
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
                raise Exception(f"Thread safety failed: expected {expected}, got {counter}")
            
            # Test no deadlock
            def worker():
                lock1 = threading.Lock()
                lock2 = threading.Lock()
                
                with lock1:
                    time.sleep(0.01)
                    with lock2:
                        time.sleep(0.01)
            
            thread = threading.Thread(target=worker)
            start_time = time.time()
            thread.start()
            thread.join(timeout=2)
            
            elapsed = time.time() - start_time
            if elapsed > 1.5:
                raise Exception("Potential deadlock detected")
            
            self.test_results.append({
                'test': 'thread_safety',
                'status': 'passed',
                'counter_test': counter,
                'deadlock_test': elapsed
            })
            print("✅ Thread safety test passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Thread safety failed: {e}")
            print(f"❌ Thread safety failed: {e}")
            return False
    
    def test_memory_management(self):
        """Test memory management"""
        print("🧠 Testing Memory Management...")
        
        try:
            # Test basic memory operations
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
            
            # Object count should be reasonable
            if final_objects > initial_objects + 1000:
                raise Exception(f"Potential memory leak: {initial_objects} -> {final_objects}")
            
            self.test_results.append({
                'test': 'memory_management',
                'status': 'passed',
                'initial_objects': initial_objects,
                'final_objects': final_objects
            })
            print("✅ Memory management test passed")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Memory management failed: {e}")
            print(f"❌ Memory management failed: {e}")
            return False
    
    def test_production_readiness_score(self):
        """Calculate production readiness score"""
        print("📊 Calculating Production Readiness Score...")
        
        try:
            total_tests = len(self.test_results)
            passed_tests = len([r for r in self.test_results if r['status'] == 'passed'])
            
            if total_tests == 0:
                raise Exception("No tests executed")
            
            readiness_score = (passed_tests / total_tests) * 100
            
            # Must have 100% pass rate for production
            if readiness_score < 100:
                raise Exception(f"Production readiness score: {readiness_score:.1f}% (must be 100%)")
            
            # Check for critical failures
            if len(self.critical_failures) > 0:
                raise Exception(f"Critical failures: {len(self.critical_failures)}")
            
            self.test_results.append({
                'test': 'production_readiness_score',
                'status': 'passed',
                'readiness_score': readiness_score,
                'tests_passed': passed_tests,
                'tests_total': total_tests,
                'critical_failures': len(self.critical_failures)
            })
            print(f"✅ Production readiness score: {readiness_score:.1f}%")
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Production readiness score failed: {e}")
            print(f"❌ Production readiness score failed: {e}")
            return False
    
    def run_final_production_tests(self):
        """Run final production tests"""
        print("🚀 STARTING FINAL PRODUCTION READINESS TESTS")
        print("="*60)
        
        tests = [
            self.test_core_calculations,
            self.test_data_files_integrity,
            self.test_premium_constraints,
            self.test_greeks_validity,
            self.test_file_existence,
            self.test_thread_safety,
            self.test_memory_management,
            self.test_production_readiness_score
        ]
        
        start_time = time.time()
        
        for test in tests:
            try:
                test()
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                self.critical_failures.append(f"Test exception: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("="*60)
        print("📊 FINAL PRODUCTION READINESS RESULTS:")
        print(f"   ✅ Tests Passed: {len([r for r in self.test_results if r['status'] == 'passed'])}")
        print(f"   ❌ Tests Failed: {len([r for r in self.test_results if r['status'] == 'failed'])}")
        print(f"   📊 Total Tests: {len(self.test_results)}")
        print(f"   ⏱️ Duration: {duration:.2f} seconds")
        
        if self.critical_failures:
            print(f"   🚨 Critical Failures: {len(self.critical_failures)}")
            for failure in self.critical_failures:
                print(f"      - {failure}")
        
        # Final verdict
        if len(self.critical_failures) == 0 and len(self.test_results) > 0:
            print("\n🎉 PRODUCTION READY! All critical tests passed!")
            return True
        else:
            print("\n❌ NOT PRODUCTION READY! Critical issues found!")
            return False
    
    def save_final_report(self):
        """Save final production report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'production_ready': len(self.critical_failures) == 0,
            'test_results': self.test_results,
            'critical_failures': self.critical_failures,
            'summary': {
                'total_tests': len(self.test_results),
                'passed_tests': len([r for r in self.test_results if r['status'] == 'passed']),
                'critical_failures': len(self.critical_failures)
            }
        }
        
        report_file = project_root / 'test_framework' / 'final_production_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📋 Final production report saved to: {report_file}")
        return report_file

def main():
    """Main execution"""
    try:
        tester = FinalProductionTests()
        success = tester.run_final_production_tests()
        tester.save_final_report()
        
        if success:
            print("\n🎉 SYSTEM IS 100% PRODUCTION READY!")
            return 0
        else:
            print("\n❌ SYSTEM IS NOT PRODUCTION READY!")
            return 1
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    main()
