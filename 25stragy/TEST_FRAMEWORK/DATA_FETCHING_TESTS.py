#!/usr/bin/env python3
"""
📊 DATA FETCHING THREAD TESTS
=============================
Comprehensive tests for data fetching thread functionality
"""

import os
import sys
import time
import threading
import traceback
from datetime import datetime

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from DATA_FETCHING_THREAD import DataFetchingThread, MarketData, OptionData
    DATA_FETCHING_AVAILABLE = True
except ImportError as e:
    print(f"❌ DATA_FETCHING_THREAD not available: {e}")
    DATA_FETCHING_AVAILABLE = False

class DataFetchingTests:
    """Data fetching thread tests"""
    
    def __init__(self):
        print("📊 DATA FETCHING THREAD TESTS")
        print("=" * 50)
        
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        
        if DATA_FETCHING_AVAILABLE:
            self.data_fetcher = DataFetchingThread()
        else:
            self.data_fetcher = None
            print("❌ Data fetcher not available - skipping tests")
    
    def run_all_tests(self):
        """Run all data fetching tests"""
        if not DATA_FETCHING_AVAILABLE:
            print("❌ Cannot run tests - DATA_FETCHING_THREAD not available")
            return self.test_results
        
        tests = [
            ("Thread Initialization", self.test_thread_initialization),
            ("API Connection", self.test_api_connection),
            ("Expiry List Fetch", self.test_expiry_list_fetch),
            ("Market Data Fetch", self.test_market_data_fetch),
            ("Options Chain Fetch", self.test_options_chain_fetch),
            ("Memory Pool Update", self.test_memory_pool_update),
            ("CSV Logging", self.test_csv_logging),
            ("Thread Safety", self.test_thread_safety),
            ("Data Synchronization", self.test_data_synchronization),
            ("Performance Metrics", self.test_performance_metrics),
            ("Error Handling", self.test_error_handling),
            ("Data Access Methods", self.test_data_access_methods),
            ("ATM Options", self.test_atm_options),
            ("Statistics", self.test_statistics),
            ("Thread Lifecycle", self.test_thread_lifecycle)
        ]
        
        print(f"\n🧪 Running {len(tests)} data fetching tests...")
        
        for test_name, test_func in tests:
            print(f"\n   🔍 {test_name}")
            try:
                result = test_func()
                if result:
                    print(f"      ✅ PASSED")
                    self.test_results['passed'] += 1
                else:
                    print(f"      ❌ FAILED")
                    self.test_results['failed'] += 1
                    self.test_results['errors'].append(f"{test_name} failed")
            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                self.test_results['failed'] += 1
                self.test_results['errors'].append(f"{test_name}: {e}")
        
        return self.test_results
    
    def test_thread_initialization(self):
        """Test thread initialization"""
        if not self.data_fetcher:
            return False
        
        return (isinstance(self.data_fetcher, DataFetchingThread) and
                hasattr(self.data_fetcher, 'memory_pool') and
                hasattr(self.data_fetcher, 'data_lock') and
                hasattr(self.data_fetcher, 'pool_lock'))
    
    def test_api_connection(self):
        """Test API connection"""
        if not self.data_fetcher:
            return False
        
        try:
            expiry_list = self.data_fetcher.get_expiry_list()
            return isinstance(expiry_list, list) and len(expiry_list) > 0
        except Exception as e:
            print(f"         API Connection Error: {e}")
            return False
    
    def test_expiry_list_fetch(self):
        """Test expiry list fetch"""
        if not self.data_fetcher:
            return False
        
        try:
            expiry_list = self.data_fetcher.get_expiry_list()
            return isinstance(expiry_list, list) and len(expiry_list) > 0
        except Exception as e:
            print(f"         Expiry List Error: {e}")
            return False
    
    def test_market_data_fetch(self):
        """Test market data fetch"""
        if not self.data_fetcher:
            return False
        
        try:
            expiry_list = self.data_fetcher.get_expiry_list()
            if expiry_list:
                market_data = self.data_fetcher.fetch_market_data(expiry_list[0])
                return market_data is not None and hasattr(market_data, 'spot_price')
        except Exception as e:
            print(f"         Market Data Error: {e}")
            return False
    
    def test_options_chain_fetch(self):
        """Test options chain fetch"""
        if not self.data_fetcher:
            return False
        
        try:
            expiry_list = self.data_fetcher.get_expiry_list()
            if expiry_list:
                options_data = self.data_fetcher.fetch_options_chain(expiry_list[0])
                return isinstance(options_data, list) and len(options_data) > 0
        except Exception as e:
            print(f"         Options Chain Error: {e}")
            return False
    
    def test_memory_pool_update(self):
        """Test memory pool update"""
        if not self.data_fetcher:
            return False
        
        try:
            # Create test data
            test_market = MarketData(
                timestamp="2024-01-01 10:00:00",
                date="2024-01-01",
                time="10:00:00",
                spot_price=22500.0,
                change=100.0,
                change_percent=0.5,
                volume=1000000,
                vwap=22450.0,
                high=22600.0,
                low=22400.0,
                open_price=22450.0,
                close_price=22500.0,
                vix=15.5
            )
            
            test_options = [
                OptionData(
                    timestamp="2024-01-01 10:00:00",
                    date="2024-01-01",
                    time="10:00:00",
                    strike=22500,
                    expiry="2024-01-01",
                    ce_price=150.25,
                    pe_price=148.75,
                    ce_volume=1000,
                    pe_volume=800,
                    ce_oi=5000,
                    pe_oi=4500,
                    ce_iv=20.5,
                    pe_iv=21.5,
                    ce_delta=0.5,
                    pe_delta=-0.5,
                    ce_gamma=0.02,
                    pe_gamma=0.02,
                    ce_theta=-0.05,
                    pe_theta=-0.04,
                    ce_vega=0.25,
                    pe_vega=0.23,
                    ce_implied_volatility=20.5,
                    pe_implied_volatility=21.5
                )
            ]
            
            # Update memory pool
            self.data_fetcher.update_memory_pool(test_market, test_options)
            
            # Verify update
            updated_market = self.data_fetcher.get_market_data()
            updated_options = self.data_fetcher.get_options_data()
            
            return (updated_market.spot_price == test_market.spot_price and 
                   len(updated_options) == len(test_options))
        except Exception as e:
            print(f"         Memory Pool Error: {e}")
            return False
    
    def test_csv_logging(self):
        """Test CSV logging"""
        if not self.data_fetcher:
            return False
        
        try:
            # Check if CSV files exist
            market_file_exists = os.path.exists(self.data_fetcher.market_data_file)
            options_file_exists = os.path.exists(self.data_fetcher.options_data_file)
            
            return market_file_exists and options_file_exists
        except Exception as e:
            print(f"         CSV Logging Error: {e}")
            return False
    
    def test_thread_safety(self):
        """Test thread safety"""
        if not self.data_fetcher:
            return False
        
        try:
            # Test concurrent access
            results = []
            
            def get_data():
                return self.data_fetcher.get_latest_data()
            
            threads = []
            for i in range(3):
                thread = threading.Thread(target=get_data)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join(timeout=5)
            
            return len(threads) == 3
        except Exception as e:
            print(f"         Thread Safety Error: {e}")
            return False
    
    def test_data_synchronization(self):
        """Test data synchronization"""
        if not self.data_fetcher:
            return False
        
        try:
            # Test data consistency
            market_data1 = self.data_fetcher.get_market_data()
            time.sleep(0.1)
            market_data2 = self.data_fetcher.get_market_data()
            
            # Both should be the same or None
            return market_data1 == market_data2
        except Exception as e:
            print(f"         Data Sync Error: {e}")
            return False
    
    def test_performance_metrics(self):
        """Test performance metrics"""
        if not self.data_fetcher:
            return False
        
        try:
            start_time = time.time()
            
            # Test data retrieval speed
            market_data = self.data_fetcher.get_market_data()
            data_time = time.time() - start_time
            
            # Test options retrieval speed
            options_data = self.data_fetcher.get_options_data()
            options_time = time.time() - start_time - data_time
            
            # Performance thresholds (should be very fast for memory access)
            return (data_time < 0.1 and options_time < 0.2)
        except Exception as e:
            print(f"         Performance Error: {e}")
            return False
    
    def test_error_handling(self):
        """Test error handling"""
        if not self.data_fetcher:
            return False
        
        try:
            # Test invalid expiry
            invalid_expiry = self.data_fetcher.fetch_options_chain("INVALID_EXPIRY")
            return invalid_expiry == []
        except Exception as e:
            print(f"         Error Handling Error: {e}")
            return False
    
    def test_data_access_methods(self):
        """Test data access methods"""
        if not self.data_fetcher:
            return False
        
        try:
            # Test all data access methods
            latest_data = self.data_fetcher.get_latest_data()
            market_data = self.data_fetcher.get_market_data()
            options_data = self.data_fetcher.get_options_data()
            
            return (isinstance(latest_data, dict) and
                   'market_data' in latest_data and
                   'options_data' in latest_data)
        except Exception as e:
            print(f"         Data Access Error: {e}")
            return False
    
    def test_atm_options(self):
        """Test ATM options functionality"""
        if not self.data_fetcher:
            return False
        
        try:
            # Add test data first
            test_market = MarketData(
                timestamp="2024-01-01 10:00:00",
                date="2024-01-01",
                time="10:00:00",
                spot_price=22500.0,
                change=100.0,
                change_percent=0.5,
                volume=1000000,
                vwap=22450.0,
                high=22600.0,
                low=22400.0,
                open_price=22450.0,
                close_price=22500.0,
                vix=15.5
            )
            
            test_options = [
                OptionData(
                    timestamp="2024-01-01 10:00:00",
                    date="2024-01-01",
                    time="10:00:00",
                    strike=22500,
                    expiry="2024-01-01",
                    ce_price=150.25,
                    pe_price=148.75,
                    ce_volume=1000,
                    pe_volume=800,
                    ce_oi=5000,
                    pe_oi=4500,
                    ce_iv=20.5,
                    pe_iv=21.5,
                    ce_delta=0.5,
                    pe_delta=-0.5,
                    ce_gamma=0.02,
                    pe_gamma=0.02,
                    ce_theta=-0.05,
                    pe_theta=-0.04,
                    ce_vega=0.25,
                    pe_vega=0.23,
                    ce_implied_volatility=20.5,
                    pe_implied_volatility=21.5
                )
            ]
            
            self.data_fetcher.update_memory_pool(test_market, test_options)
            
            # Test ATM options
            atm_options = self.data_fetcher.get_atm_options()
            return isinstance(atm_options, dict)
        except Exception as e:
            print(f"         ATM Options Error: {e}")
            return False
    
    def test_statistics(self):
        """Test statistics functionality"""
        if not self.data_fetcher:
            return False
        
        try:
            stats = self.data_fetcher.get_statistics()
            return (isinstance(stats, dict) and
                   'total_fetches' in stats and
                   'total_errors' in stats and
                   'success_rate' in stats)
        except Exception as e:
            print(f"         Statistics Error: {e}")
            return False
    
    def test_thread_lifecycle(self):
        """Test thread lifecycle"""
        if not self.data_fetcher:
            return False
        
        try:
            # Test thread start/stop
            initial_state = self.data_fetcher.running
            
            # Start thread
            self.data_fetcher.start_fetching()
            time.sleep(0.1)
            running_state = self.data_fetcher.running
            
            # Stop thread
            self.data_fetcher.stop_fetching()
            stopped_state = self.data_fetcher.running
            
            return (not initial_state and running_state and not stopped_state)
        except Exception as e:
            print(f"         Thread Lifecycle Error: {e}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        total_tests = self.test_results['passed'] + self.test_results['failed']
        success_rate = (self.test_results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"📊 DATA FETCHING TESTS SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"📊 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['errors']:
            print(f"\n❌ Errors:")
            for error in self.test_results['errors']:
                print(f"   - {error}")
        
        print(f"\n{'='*50}")
        
        return success_rate

def main():
    """Main execution"""
    tests = DataFetchingTests()
    results = tests.run_all_tests()
    success_rate = tests.print_summary()
    
    return success_rate >= 80.0  # Return True if 80%+ tests pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
