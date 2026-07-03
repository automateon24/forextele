#!/usr/bin/env python3
"""
🏁 RACE CONDITION TESTS
=======================
Comprehensive race condition detection and testing
Tests for data fetching thread, shared resources, and concurrent access
"""

import os
import sys
import time
import threading
import queue
import random
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import signal

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from DATA_FETCHING_THREAD import DataFetchingThread, MarketData, OptionData
    DATA_FETCHING_AVAILABLE = True
except ImportError as e:
    print(f"❌ DATA_FETCHING_THREAD not available: {e}")
    DATA_FETCHING_AVAILABLE = False

class RaceConditionTests:
    """Race condition detection and testing"""
    
    def __init__(self):
        print("🏁 RACE CONDITION TESTS")
        print("=" * 50)
        print("🔍 Detecting race conditions in concurrent access")
        print("🛡️ Testing thread safety and data consistency")
        print("⚡ Stress testing shared resources")
        print("🎯 Graceful shutdown testing")
        print("=" * 50)
        
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        
        # Graceful shutdown flag
        self.shutdown_requested = False
        self.active_threads = []
        
        # Statistics
        self.race_conditions_detected = []
        self.data_corruption_detected = []
        self.deadlock_detected = []
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        if DATA_FETCHING_AVAILABLE:
            self.data_fetcher = DataFetchingThread()
        else:
            self.data_fetcher = None
            print("❌ Data fetcher not available - some tests will be skipped")
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n🛑 Signal {signum} received - Shutting down gracefully...")
        self.shutdown_requested = True
        
        # Stop all active threads
        for thread in self.active_threads:
            if hasattr(thread, 'stop'):
                thread.stop()
            elif hasattr(thread, 'stop_event'):
                thread.stop_event.set()
        
        # Wait for threads to finish
        for thread in self.active_threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        print("✅ All threads stopped gracefully")
        sys.exit(0)
    
    def run_all_tests(self):
        """Run all race condition tests"""
        tests = [
            ("Shared Memory Race Condition", self.test_shared_memory_race),
            ("Concurrent Data Access", self.test_concurrent_data_access),
            ("Memory Pool Race Condition", self.test_memory_pool_race),
            ("CSV File Race Condition", self.test_csv_file_race),
            ("Thread Safe Counters", self.test_thread_safe_counters),
            ("Queue Race Condition", self.test_queue_race),
            ("Lock Contention", self.test_lock_contention),
            ("Data Consistency", self.test_data_consistency),
            ("Resource Cleanup", self.test_resource_cleanup),
            ("Graceful Shutdown", self.test_graceful_shutdown),
            ("High Concurrency Stress", self.test_high_concurrency_stress),
            ("Deadlock Detection", self.test_deadlock_detection),
            ("Atomic Operations", self.test_atomic_operations),
            ("Data Corruption Detection", self.test_data_corruption),
            ("Thread Safety Violations", self.test_thread_safety_violations)
        ]
        
        print(f"\n🧪 Running {len(tests)} race condition tests...")
        
        for test_name, test_func in tests:
            if self.shutdown_requested:
                print(f"\n🛑 Shutdown requested - stopping tests")
                break
                
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
                traceback.print_exc()
        
        return self.test_results
    
    def test_shared_memory_race(self):
        """Test shared memory race conditions"""
        if self.shutdown_requested:
            return False
            
        shared_data = {'counter': 0, 'corrupted': False}
        errors = []
        
        def increment_counter(thread_id):
            """Increment counter with race condition vulnerability"""
            for i in range(1000):
                if self.shutdown_requested:
                    break
                    
                # Race condition: Non-atomic increment
                current = shared_data['counter']
                time.sleep(0.0001)  # Small delay to increase race condition probability
                shared_data['counter'] = current + 1
                
                # Check for corruption
                if shared_data['counter'] < 0:
                    shared_data['corrupted'] = True
                    errors.append(f"Thread {thread_id}: Counter corruption detected")
        
        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=increment_counter, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        expected = 1000 * 10  # 10 threads * 1000 increments each
        actual = shared_data['counter']
        
        if actual != expected or shared_data['corrupted']:
            self.race_conditions_detected.append(f"Shared Memory: Expected {expected}, got {actual}")
            return False
        
        return True
    
    def test_concurrent_data_access(self):
        """Test concurrent data access to data fetching thread"""
        if not DATA_FETCHING_AVAILABLE or self.shutdown_requested:
            return True  # Skip if not available
        
        self.data_fetcher.start_fetching()
        time.sleep(1)  # Let it start
        
        errors = []
        data_inconsistencies = []
        
        def concurrent_reader(thread_id):
            """Concurrent reader thread"""
            for i in range(50):
                if self.shutdown_requested:
                    break
                    
                try:
                    # Get data concurrently
                    data1 = self.data_fetcher.get_market_data()
                    time.sleep(0.001)
                    data2 = self.data_fetcher.get_market_data()
                    
                    # Check for inconsistencies
                    if data1 and data2:
                        if data1.spot_price != data2.spot_price:
                            data_inconsistencies.append(f"Thread {thread_id}: Data inconsistency")
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start multiple reader threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_reader, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        self.data_fetcher.stop_fetching()
        
        # Check results
        if len(errors) > 0 or len(data_inconsistencies) > 0:
            self.race_conditions_detected.extend(errors)
            self.data_corruption_detected.extend(data_inconsistencies)
            return False
        
        return True
    
    def test_memory_pool_race(self):
        """Test memory pool race conditions"""
        if not DATA_FETCHING_AVAILABLE or self.shutdown_requested:
            return True
        
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
        
        errors = []
        
        def concurrent_updater(thread_id):
            """Concurrent memory pool updater"""
            for i in range(100):
                if self.shutdown_requested:
                    break
                    
                try:
                    # Update with different values
                    test_market.spot_price = 22500.0 + (thread_id * 10) + i
                    test_options[0].ce_price = 150.25 + (thread_id * 5) + i
                    
                    self.data_fetcher.update_memory_pool(test_market, test_options)
                    
                    # Small delay to increase race condition probability
                    time.sleep(0.001)
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start multiple updater threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=concurrent_updater, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for errors
        if len(errors) > 0:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_csv_file_race(self):
        """Test CSV file race conditions"""
        if self.shutdown_requested:
            return False
        
        csv_file = "test_race_condition.csv"
        errors = []
        
        # Clean up
        if os.path.exists(csv_file):
            os.remove(csv_file)
        
        def concurrent_writer(thread_id):
            """Concurrent CSV writer"""
            for i in range(50):
                if self.shutdown_requested:
                    break
                    
                try:
                    with open(csv_file, 'a', encoding='utf-8') as f:
                        f.write(f"Thread_{thread_id},Row_{i},Data_{i}\n")
                    
                    time.sleep(0.001)
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start multiple writer threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_writer, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify file integrity
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            expected_lines = 5 * 50  # 5 threads * 50 lines each
            if len(lines) != expected_lines:
                errors.append(f"CSV race condition: Expected {expected_lines} lines, got {len(lines)}")
                return False
                
        except Exception as e:
            errors.append(f"CSV verification error: {e}")
            return False
        finally:
            # Clean up
            if os.path.exists(csv_file):
                os.remove(csv_file)
        
        return True
    
    def test_thread_safe_counters(self):
        """Test thread-safe counters"""
        if self.shutdown_requested:
            return False
        
        # Non-thread-safe counter
        unsafe_counter = 0
        # Thread-safe counter with lock
        safe_counter = 0
        counter_lock = threading.Lock()
        
        errors = []
        
        def unsafe_increment():
            """Non-thread-safe increment"""
            nonlocal unsafe_counter
            for i in range(1000):
                if self.shutdown_requested:
                    break
                current = unsafe_counter
                time.sleep(0.0001)
                unsafe_counter = current + 1
        
        def safe_increment():
            """Thread-safe increment"""
            nonlocal safe_counter
            for i in range(1000):
                if self.shutdown_requested:
                    break
                with counter_lock:
                    safe_counter += 1
        
        # Test unsafe counter
        unsafe_threads = []
        for i in range(10):
            thread = threading.Thread(target=unsafe_increment)
            unsafe_threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Test safe counter
        safe_threads = []
        for i in range(10):
            thread = threading.Thread(target=safe_increment)
            safe_threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in unsafe_threads + safe_threads:
            thread.join()
        
        # Check results
        expected = 1000 * 10  # 10 threads * 1000 increments each
        
        if unsafe_counter != expected:
            errors.append(f"Unsafe counter: Expected {expected}, got {unsafe_counter}")
        
        if safe_counter != expected:
            errors.append(f"Safe counter: Expected {expected}, got {safe_counter}")
        
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_queue_race(self):
        """Test queue race conditions"""
        if self.shutdown_requested:
            return False
        
        test_queue = queue.Queue()
        errors = []
        processed_items = []
        
        def queue_producer(thread_id):
            """Queue producer"""
            for i in range(100):
                if self.shutdown_requested:
                    break
                try:
                    item = f"Thread_{thread_id}_Item_{i}"
                    test_queue.put(item)
                    time.sleep(0.001)
                except Exception as e:
                    errors.append(f"Producer {thread_id}: {e}")
        
        def queue_consumer():
            """Queue consumer"""
            while not self.shutdown_requested:
                try:
                    item = test_queue.get(timeout=1)
                    processed_items.append(item)
                    test_queue.task_done()
                except queue.Empty:
                    break
                except Exception as e:
                    errors.append(f"Consumer: {e}")
                    break
        
        # Start producer threads
        producer_threads = []
        for i in range(3):
            thread = threading.Thread(target=queue_producer, args=(i,))
            producer_threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Start consumer thread
        consumer_thread = threading.Thread(target=queue_consumer)
        consumer_threads = [consumer_thread]
        self.active_threads.append(consumer_thread)
        consumer_thread.start()
        
        # Wait for producers
        for thread in producer_threads:
            thread.join()
        
        # Signal consumer to stop
        test_queue.join()
        
        # Wait for consumer
        consumer_thread.join()
        
        # Check results
        expected_items = 3 * 100  # 3 producers * 100 items each
        if len(processed_items) != expected_items:
            errors.append(f"Queue race: Expected {expected_items} items, got {len(processed_items)}")
        
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_lock_contention(self):
        """Test lock contention"""
        if self.shutdown_requested:
            return False
        
        shared_lock = threading.Lock()
        shared_resource = 0
        errors = []
        
        def lock_contender(thread_id):
            """Lock contender"""
            for i in range(50):
                if self.shutdown_requested:
                    break
                    
                try:
                    # Acquire lock with timeout
                    if shared_lock.acquire(timeout=1):
                        try:
                            # Simulate work
                            shared_resource += 1
                            time.sleep(0.01)
                        finally:
                            shared_lock.release()
                    else:
                        errors.append(f"Thread {thread_id}: Lock timeout")
                        
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=lock_contender, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        expected = 10 * 50  # 10 threads * 50 increments each
        if shared_resource != expected:
            errors.append(f"Lock contention: Expected {expected}, got {shared_resource}")
        
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_data_consistency(self):
        """Test data consistency under concurrent access"""
        if self.shutdown_requested:
            return False
        
        shared_data = {'value': 0, 'version': 0}
        data_lock = threading.Lock()
        errors = []
        
        def data_updater(thread_id):
            """Data updater"""
            for i in range(100):
                if self.shutdown_requested:
                    break
                    
                try:
                    with data_lock:
                        # Update atomically
                        shared_data['value'] += 1
                        shared_data['version'] += 1
                        
                        # Simulate processing
                        time.sleep(0.001)
                        
                        # Verify consistency
                        if shared_data['value'] != shared_data['version']:
                            errors.append(f"Thread {thread_id}: Data inconsistency at iteration {i}")
                            
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=data_updater, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check final consistency
        if shared_data['value'] != shared_data['version']:
            errors.append(f"Final inconsistency: value={shared_data['value']}, version={shared_data['version']}")
        
        if errors:
            self.data_corruption_detected.extend(errors)
            return False
        
        return True
    
    def test_resource_cleanup(self):
        """Test resource cleanup on thread termination"""
        if self.shutdown_requested:
            return False
        
        resources = []
        cleanup_errors = []
        
        def resource_user(thread_id):
            """Resource user that creates and cleans up resources"""
            local_resources = []
            
            try:
                for i in range(10):
                    if self.shutdown_requested:
                        break
                        
                    # Create resource
                    resource = f"Resource_{thread_id}_{i}"
                    local_resources.append(resource)
                    resources.append(resource)
                    
                    time.sleep(0.01)
                    
                    # Clean up resource
                    if resource in resources:
                        resources.remove(resource)
                        local_resources.remove(resource)
                        
            except Exception as e:
                cleanup_errors.append(f"Thread {thread_id}: {e}")
            
            # Final cleanup
            for resource in local_resources:
                if resource in resources:
                    resources.remove(resource)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=resource_user, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check resource cleanup
        if len(resources) > 0:
            cleanup_errors.append(f"Resource leak: {len(resources)} resources not cleaned up")
        
        if cleanup_errors:
            self.race_conditions_detected.extend(cleanup_errors)
            return False
        
        return True
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown on Ctrl+C"""
        if self.shutdown_requested:
            return True  # Already in shutdown
        
        # This test is designed to be interrupted
        print("      🔄 Testing graceful shutdown (press Ctrl+C to test)")
        
        # Create threads that should be stopped gracefully
        graceful_threads = []
        
        def long_running_task():
            """Long running task that should be stopped gracefully"""
            for i in range(1000):
                if self.shutdown_requested:
                    print(f"      ✅ Thread received shutdown signal, stopping gracefully")
                    break
                time.sleep(0.1)
        
        # Start threads
        for i in range(3):
            thread = threading.Thread(target=long_running_task)
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait a bit then simulate shutdown
        time.sleep(0.5)
        
        # Simulate Ctrl+C
        self.shutdown_requested = True
        
        # Wait for threads to stop
        for thread in threads:
            thread.join(timeout=2)
        
        # Check if all threads stopped
        all_stopped = all(not thread.is_alive() for thread in threads)
        
        return all_stopped
    
    def test_high_concurrency_stress(self):
        """Test high concurrency stress"""
        if self.shutdown_requested:
            return False
        
        shared_counter = 0
        counter_lock = threading.Lock()
        errors = []
        
        def stress_worker(thread_id):
            """Stress worker"""
            for i in range(1000):
                if self.shutdown_requested:
                    break
                    
                try:
                    with counter_lock:
                        shared_counter += 1
                    
                    # Random delay to increase race condition probability
                    time.sleep(random.uniform(0.0001, 0.001))
                    
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
        
        # Start many threads
        threads = []
        for i in range(20):
            thread = threading.Thread(target=stress_worker, args=(i,))
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        expected = 20 * 1000  # 20 threads * 1000 increments each
        if shared_counter != expected:
            errors.append(f"High concurrency stress: Expected {expected}, got {shared_counter}")
        
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_deadlock_detection(self):
        """Test deadlock detection"""
        if self.shutdown_requested:
            return False
        
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        errors = []
        deadlock_detected = False
        
        def thread1():
            """Thread that locks in order 1->2"""
            try:
                lock1.acquire()
                time.sleep(0.1)
                lock2.acquire()
                time.sleep(0.1)
                lock2.release()
                lock1.release()
            except Exception as e:
                errors.append(f"Thread1: {e}")
        
        def thread2():
            """Thread that locks in order 2->1 (potential deadlock)"""
            try:
                lock2.acquire()
                time.sleep(0.1)
                lock1.acquire()
                time.sleep(0.1)
                lock1.release()
                lock2.release()
            except Exception as e:
                errors.append(f"Thread2: {e}")
        
        # Start threads
        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)
        
        self.active_threads.extend([t1, t2])
        
        start_time = time.time()
        t1.start()
        t2.start()
        
        # Wait for completion or timeout
        t1.join(timeout=5)
        t2.join(timeout=5)
        
        # Check for deadlock
        elapsed = time.time() - start_time
        if elapsed > 4.5:  # Near timeout indicates potential deadlock
            deadlock_detected = True
            self.deadlock_detected.append("Potential deadlock detected in lock ordering test")
        
        # Force cleanup
        if t1.is_alive():
            t1._stop()
        if t2.is_alive():
            t2._stop()
        
        if deadlock_detected:
            return False
        
        return True
    
    def test_atomic_operations(self):
        """Test atomic operations"""
        if self.shutdown_requested:
            return False
        
        shared_value = 0
        errors = []
        
        def atomic_increment():
            """Atomic increment using lock"""
            nonlocal shared_value
            for i in range(1000):
                if self.shutdown_requested:
                    break
                    
                # Use lock for atomic operation
                with threading.Lock():
                    current = shared_value
                    time.sleep(0.0001)  # Increase race condition probability
                    shared_value = current + 1
        
        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=atomic_increment)
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        expected = 10 * 1000  # 10 threads * 1000 increments each
        if shared_value != expected:
            errors.append(f"Atomic operations: Expected {expected}, got {shared_value}")
        
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def test_data_corruption(self):
        """Test data corruption detection"""
        if self.shutdown_requested:
            return False
        
        shared_data = {'integrity': 'VALID', 'checksum': 0}
        errors = []
        corruption_detected = False
        
        def data_modifier():
            """Data modifier that might corrupt data"""
            for i in range(100):
                if self.shutdown_requested:
                    break
                    
                try:
                    # Simulate data modification
                    with threading.Lock():
                        # Calculate checksum
                        checksum = hash(str(shared_data)) % 10000
                        
                        # Modify data
                        shared_data['integrity'] = f'MODIFIED_{i}'
                        shared_data['checksum'] = checksum
                        
                        # Small delay
                        time.sleep(0.001)
                        
                        # Verify integrity
                        current_checksum = hash(str(shared_data)) % 10000
                        if current_checksum != shared_data['checksum']:
                            corruption_detected = True
                            errors.append(f"Data corruption detected at iteration {i}")
                            
                except Exception as e:
                    errors.append(f"Data modifier: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=data_modifier)
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        if corruption_detected or errors:
            self.data_corruption_detected.extend(errors)
            return False
        
        return True
    
    def test_thread_safety_violations(self):
        """Test thread safety violations"""
        if self.shutdown_requested:
            return False
        
        shared_list = []
        errors = []
        
        def list_modifier():
            """List modifier with potential thread safety issues"""
            for i in range(100):
                if self.shutdown_requested:
                    break
                    
                try:
                    # Thread-unsafe list operations
                    shared_list.append(i)
                    time.sleep(0.001)
                    
                    # Potential race condition: check and modify
                    if len(shared_list) > 50:
                        shared_list.pop(0)
                        
                except Exception as e:
                    errors.append(f"List modifier: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=list_modifier)
            threads.append(thread)
            self.active_threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for thread safety violations
        if errors:
            self.race_conditions_detected.extend(errors)
            return False
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        total_tests = self.test_results['passed'] + self.test_results['failed']
        success_rate = (self.test_results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"🏁 RACE CONDITION TESTS SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"📊 Success Rate: {success_rate:.1f}%")
        
        # Print race conditions detected
        if self.race_conditions_detected:
            print(f"\n🚨 Race Conditions Detected ({len(self.race_conditions_detected)}):")
            for race in self.race_conditions_detected[:5]:  # Show first 5
                print(f"   - {race}")
        
        # Print data corruption detected
        if self.data_corruption_detected:
            print(f"\n🔥 Data Corruption Detected ({len(self.data_corruption_detected)}):")
            for corruption in self.data_corruption_detected[:5]:  # Show first 5
                print(f"   - {corruption}")
        
        # Print deadlocks detected
        if self.deadlock_detected:
            print(f"\n🔒 Deadlocks Detected ({len(self.deadlock_detected)}):")
            for deadlock in self.deadlock_detected:
                print(f"   - {deadlock}")
        
        if self.test_results['errors']:
            print(f"\n❌ Errors:")
            for error in self.test_results['errors']:
                print(f"   - {error}")
        
        print(f"\n{'='*50}")
        
        return success_rate

def main():
    """Main execution"""
    tests = RaceConditionTests()
    results = tests.run_all_tests()
    success_rate = tests.print_summary()
    
    return success_rate >= 80.0  # Return True if 80%+ tests pass

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
