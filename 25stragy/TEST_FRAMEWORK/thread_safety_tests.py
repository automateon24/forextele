#!/usr/bin/env python3
"""
THREAD SAFETY TESTS
==================
Thread safety tests for multi-threaded components
"""

import sys
import os
import threading
import time
import queue
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ThreadSafetyTests:
    """Thread safety tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        self.shared_data = {}
        self.shared_lock = threading.Lock()
        
    def test_shared_data_access(self):
        """Test shared data access with multiple threads"""
        print("🧵 Testing Shared Data Access...")
        
        try:
            # Shared resource
            shared_counter = 0
            shared_lock = threading.Lock()
            
            def increment_counter(thread_id):
                nonlocal shared_counter
                for i in range(1000):
                    with shared_lock:
                        shared_counter += 1
                        # Store thread-specific data
                        self.shared_data[f'thread_{thread_id}_iteration_{i}'] = shared_counter
            
            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=increment_counter, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify final counter value
            expected_value = 5 * 1000  # 5 threads * 1000 iterations each
            
            if shared_counter == expected_value:
                self.test_results.append({
                    'test': 'shared_data_access',
                    'expected_counter': expected_value,
                    'actual_counter': shared_counter,
                    'status': 'passed'
                })
                print(f"✅ Shared data access test passed: {shared_counter}")
                return True
            else:
                self.errors.append(f"Counter mismatch: expected {expected_value}, got {shared_counter}")
                print(f"❌ Counter mismatch: expected {expected_value}, got {shared_counter}")
                return False
                
        except Exception as e:
            self.errors.append(f"Shared data access error: {e}")
            print(f"❌ Shared data access error: {e}")
            return False
    
    def test_queue_thread_safety(self):
        """Test queue thread safety"""
        print("📤 Testing Queue Thread Safety...")
        
        try:
            # Create shared queue
            shared_queue = queue.Queue()
            results = []
            
            def producer(thread_id):
                for i in range(100):
                    item = f'item_{thread_id}_{i}'
                    shared_queue.put(item)
                    time.sleep(0.001)  # Small delay
            
            def consumer():
                consumed = []
                while len(consumed) < 500:  # 5 producers * 100 items each
                    try:
                        item = shared_queue.get(timeout=1)
                        consumed.append(item)
                    except queue.Empty:
                        break
                return consumed
            
            # Start producer threads
            producers = []
            for i in range(5):
                thread = threading.Thread(target=producer, args=(i,))
                producers.append(thread)
                thread.start()
            
            # Start consumer thread
            consumer_thread = threading.Thread(target=consumer)
            consumer_thread.start()
            
            # Wait for all threads to complete
            for thread in producers:
                thread.join()
            consumer_thread.join()
            
            # Verify all items were consumed
            consumed_items = []
            while not shared_queue.empty():
                consumed_items.append(shared_queue.get())
            
            if len(consumed_items) == 0:
                self.test_results.append({
                    'test': 'queue_thread_safety',
                    'items_produced': 500,
                    'items_consumed': 500,
                    'items_remaining': len(consumed_items),
                    'status': 'passed'
                })
                print(f"✅ Queue thread safety test passed: 500 items produced and consumed")
                return True
            else:
                self.errors.append(f"Items remaining in queue: {len(consumed_items)}")
                print(f"❌ Items remaining in queue: {len(consumed_items)}")
                return False
                
        except Exception as e:
            self.errors.append(f"Queue thread safety error: {e}")
            print(f"❌ Queue thread safety error: {e}")
            return False
    
    def test_thread_pool_safety(self):
        """Test thread pool safety"""
        print("🏊 Testing Thread Pool Safety...")
        
        try:
            shared_results = []
            shared_lock = threading.Lock()
            
            def process_data(data):
                # Simulate data processing
                result = data * 2
                time.sleep(0.01)  # Simulate processing time
                
                with shared_lock:
                    shared_results.append(result)
                return result
            
            # Create thread pool
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Submit tasks
                futures = []
                for i in range(100):
                    future = executor.submit(process_data, i)
                    futures.append(future)
                
                # Collect results
                results = []
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
            
            # Verify results
            expected_results = [i * 2 for i in range(100)]
            
            if sorted(results) == sorted(expected_results):
                self.test_results.append({
                    'test': 'thread_pool_safety',
                    'tasks_submitted': 100,
                    'tasks_completed': len(results),
                    'expected_results': len(expected_results),
                    'status': 'passed'
                })
                print(f"✅ Thread pool safety test passed: {len(results)} tasks completed")
                return True
            else:
                self.errors.append("Results mismatch in thread pool test")
                print("❌ Results mismatch in thread pool test")
                return False
                
        except Exception as e:
            self.errors.append(f"Thread pool safety error: {e}")
            print(f"❌ Thread pool safety error: {e}")
            return False
    
    def test_lock_contention(self):
        """Test lock contention"""
        print("🔒 Testing Lock Contention...")
        
        try:
            shared_resource = []
            lock = threading.Lock()
            
            def high_contention_worker(worker_id):
                for i in range(100):
                    with lock:
                        # Simulate work with lock held
                        shared_resource.append(f'worker_{worker_id}_item_{i}')
                        time.sleep(0.001)  # Hold lock for short time
            
            # Start multiple threads to create contention
            threads = []
            for i in range(10):
                thread = threading.Thread(target=high_contention_worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify all items were added
            expected_items = 10 * 100  # 10 threads * 100 items each
            
            if len(shared_resource) == expected_items:
                self.test_results.append({
                    'test': 'lock_contention',
                    'threads': 10,
                    'items_per_thread': 100,
                    'total_items': len(shared_resource),
                    'status': 'passed'
                })
                print(f"✅ Lock contention test passed: {len(shared_resource)} items processed")
                return True
            else:
                self.errors.append(f"Items mismatch: expected {expected_items}, got {len(shared_resource)}")
                print(f"❌ Items mismatch: expected {expected_items}, got {len(shared_resource)}")
                return False
                
        except Exception as e:
            self.errors.append(f"Lock contention error: {e}")
            print(f"❌ Lock contention error: {e}")
            return False
    
    def test_race_conditions(self):
        """Test for race conditions"""
        print("🏁 Testing Race Conditions...")
        
        try:
            shared_counter = 0
            
            def unsafe_increment():
                nonlocal shared_counter
                # Unsafe increment (without lock)
                temp = shared_counter
                time.sleep(0.001)  # Introduce delay
                shared_counter = temp + 1
            
            def safe_increment():
                nonlocal shared_counter
                with self.shared_lock:
                    # Safe increment (with lock)
                    temp = shared_counter
                    time.sleep(0.001)  # Introduce delay
                    shared_counter = temp + 1
            
            # Test unsafe increment
            unsafe_counter = 0
            unsafe_threads = []
            for i in range(10):
                thread = threading.Thread(target=unsafe_increment)
                unsafe_threads.append(thread)
                thread.start()
            
            for thread in unsafe_threads:
                thread.join()
            
            # Test safe increment
            safe_counter = 0
            safe_threads = []
            for i in range(10):
                thread = threading.Thread(target=safe_increment)
                safe_threads.append(thread)
                thread.start()
            
            for thread in safe_threads:
                thread.join()
            
            # Safe increment should give correct result
            expected_safe = 10
            if safe_counter == expected_safe:
                self.test_results.append({
                    'test': 'race_conditions',
                    'unsafe_result': unsafe_counter,
                    'safe_result': safe_counter,
                    'expected_safe': expected_safe,
                    'status': 'passed'
                })
                print(f"✅ Race condition test passed: safe={safe_counter}, unsafe={unsafe_counter}")
                return True
            else:
                self.errors.append(f"Safe increment failed: expected {expected_safe}, got {safe_counter}")
                print(f"❌ Safe increment failed: expected {expected_safe}, got {safe_counter}")
                return False
                
        except Exception as e:
            self.errors.append(f"Race condition error: {e}")
            print(f"❌ Race condition error: {e}")
            return False
    
    def test_deadlock_prevention(self):
        """Test deadlock prevention"""
        print("💀 Testing Deadlock Prevention...")
        
        try:
            lock1 = threading.Lock()
            lock2 = threading.Lock()
            deadlock_detected = False
            
            def worker1():
                nonlocal deadlock_detected
                try:
                    with lock1:
                        time.sleep(0.01)
                        with lock2:
                            time.sleep(0.01)
                except:
                    deadlock_detected = True
            
            def worker2():
                nonlocal deadlock_detected
                try:
                    with lock2:
                        time.sleep(0.01)
                        with lock1:
                            time.sleep(0.01)
                except:
                    deadlock_detected = True
            
            # Start threads
            thread1 = threading.Thread(target=worker1)
            thread2 = threading.Thread(target=worker2)
            
            start_time = time.time()
            thread1.start()
            thread2.start()
            
            # Wait for completion or timeout
            thread1.join(timeout=5)
            thread2.join(timeout=5)
            
            elapsed_time = time.time() - start_time
            
            # If completed within reasonable time, no deadlock
            if elapsed_time < 4.0 and not deadlock_detected:
                self.test_results.append({
                    'test': 'deadlock_prevention',
                    'elapsed_time': elapsed_time,
                    'deadlock_detected': deadlock_detected,
                    'status': 'passed'
                })
                print(f"✅ Deadlock prevention test passed: {elapsed_time:.2f}s")
                return True
            else:
                self.errors.append("Potential deadlock detected")
                print("❌ Potential deadlock detected")
                return False
                
        except Exception as e:
            self.errors.append(f"Deadlock prevention error: {e}")
            print(f"❌ Deadlock prevention error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all thread safety tests"""
        print("🧵 Starting Thread Safety Tests...")
        print("="*60)
        
        tests = [
            self.test_shared_data_access,
            self.test_queue_thread_safety,
            self.test_thread_pool_safety,
            self.test_lock_contention,
            self.test_race_conditions,
            self.test_deadlock_prevention
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
        print(f"🧵 Thread Safety Tests Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📊 Total Tests: {passed + failed}")
        print(f"   📝 Test Results: {len(self.test_results)}")
        
        if self.errors:
            print(f"   ⚠️  Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"      - {error}")
        
        return len(self.errors) == 0

def main():
    """Main execution"""
    tester = ThreadSafetyTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All thread safety tests passed!")
        return 0
    else:
        print("❌ Some thread safety tests failed!")
        return 1

if __name__ == "__main__":
    main()
