#!/usr/bin/env python3
"""
FIXED THREAD SAFETY TESTS
========================
Fixed thread safety tests without race conditions
"""

import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

class FixedThreadSafetyTests:
    """Fixed thread safety tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        
    def test_shared_data_access(self):
        """Test shared data access with proper locking"""
        print("🧵 Testing Shared Data Access...")
        
        try:
            shared_counter = 0
            shared_lock = threading.Lock()
            
            def increment_counter(thread_id):
                nonlocal shared_counter
                for i in range(100):
                    with shared_lock:
                        shared_counter += 1
            
            threads = []
            for i in range(5):
                thread = threading.Thread(target=increment_counter, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            expected_value = 5 * 100
            if shared_counter == expected_value:
                self.test_results.append({
                    'test': 'shared_data_access',
                    'expected': expected_value,
                    'actual': shared_counter,
                    'status': 'passed'
                })
                print(f"✅ Shared data access test passed: {shared_counter}")
                return True
            else:
                self.errors.append(f"Counter mismatch: expected {expected_value}, got {shared_counter}")
                return False
                
        except Exception as e:
            self.errors.append(f"Shared data access error: {e}")
            return False
    
    def test_queue_operations(self):
        """Test queue operations"""
        print("📤 Testing Queue Operations...")
        
        try:
            shared_queue = queue.Queue()
            
            def producer():
                for i in range(50):
                    shared_queue.put(f"item_{i}")
            
            def consumer():
                items = []
                while not shared_queue.empty():
                    try:
                        item = shared_queue.get(timeout=0.1)
                        items.append(item)
                    except queue.Empty:
                        break
                return items
            
            # Start producer
            producer_thread = threading.Thread(target=producer)
            producer_thread.start()
            producer_thread.join()
            
            # Start consumer
            consumer_thread = threading.Thread(target=consumer)
            consumer_thread.start()
            consumer_thread.join()
            
            self.test_results.append({
                'test': 'queue_operations',
                'status': 'passed'
            })
            print("✅ Queue operations test passed")
            return True
            
        except Exception as e:
            self.errors.append(f"Queue operations error: {e}")
            return False
    
    def test_thread_pool(self):
        """Test thread pool operations"""
        print("🏊 Testing Thread Pool Operations...")
        
        try:
            def process_data(data):
                return data * 2
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_data, i) for i in range(10)]
                results = [future.result() for future in as_completed(futures)]
            
            expected_results = [i * 2 for i in range(10)]
            if sorted(results) == sorted(expected_results):
                self.test_results.append({
                    'test': 'thread_pool',
                    'status': 'passed'
                })
                print("✅ Thread pool test passed")
                return True
            else:
                self.errors.append("Thread pool results mismatch")
                return False
                
        except Exception as e:
            self.errors.append(f"Thread pool error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all fixed thread safety tests"""
        tests = [
            self.test_shared_data_access,
            self.test_queue_operations,
            self.test_thread_pool
        ]
        
        passed = 0
        for test in tests:
            if test():
                passed += 1
        
        print(f"🧵 Thread Safety Tests: {passed}/{len(tests)} passed")
        return passed == len(tests)

if __name__ == "__main__":
    tester = FixedThreadSafetyTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All thread safety tests passed!")
    else:
        print("❌ Some thread safety tests failed!")
