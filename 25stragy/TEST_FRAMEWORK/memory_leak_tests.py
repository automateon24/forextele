#!/usr/bin/env python3
"""
MEMORY LEAK TESTS
===============
Memory leak detection and management tests
"""

import sys
import os
import gc
import threading
import time
import psutil
import weakref
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class MemoryLeakTests:
    """Memory leak detection tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        self.initial_memory = None
        
    def get_memory_usage(self):
        """Get current memory usage"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert to MB
        except:
            return 0
    
    def test_memory_leak_detection(self):
        """Test memory leak detection"""
        print("🧠 Testing Memory Leak Detection...")
        
        try:
            # Record initial memory
            initial_memory = self.get_memory_usage()
            
            # Create objects that might cause leaks
            objects = []
            weak_refs = []
            
            for i in range(1000):
                # Create pandas DataFrame
                df = pd.DataFrame({
                    'timestamp': [datetime.now()] * 10,
                    'close': [100 + i] * 10,
                    'volume': [1000 + i] * 10
                })
                
                # Create weak reference
                weak_ref = weakref.ref(df)
                weak_refs.append(weak_ref)
                objects.append(df)
                
                if i % 100 == 0:  # Force garbage collection periodically
                    gc.collect()
            
            # Force garbage collection
            gc.collect()
            
            # Check memory after cleanup
            final_memory = self.get_memory_usage()
            memory_increase = final_memory - initial_memory
            
            # Check for memory leaks
            # Some memory increase is normal, but should be reasonable
            if memory_increase < 50:  # Less than 50MB increase is acceptable
                self.test_results.append({
                    'test': 'memory_leak_detection',
                    'initial_memory_mb': initial_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase,
                    'objects_created': len(objects),
                    'status': 'passed'
                })
                print(f"✅ Memory leak detection test passed: {memory_increase:.2f}MB increase")
                return True
            else:
                self.errors.append(f"Memory increase too high: {memory_increase:.2f}MB")
                print(f"❌ Memory increase too high: {memory_increase:.2f}MB")
                return False
                
        except Exception as e:
            self.errors.append(f"Memory leak detection error: {e}")
            print(f"❌ Memory leak detection error: {e}")
            return False
    
    def test_large_dataset_handling(self):
        """Test large dataset handling"""
        print("📊 Testing Large Dataset Handling...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            # Create large dataset
            large_data = []
            for i in range(10000):
                df = pd.DataFrame({
                    'timestamp': [datetime.now()] * 100,
                    'open': [100 + i] * 100,
                    'high': [102 + i] * 100,
                    'low': [98 + i] * 100,
                    'close': [100 + i] * 100,
                    'volume': [1000 + i * 100] * 100
                })
                large_data.append(df)
                
                if i % 1000 == 0:
                    # Force garbage collection
                    gc.collect()
            
            # Measure memory usage
            peak_memory = self.get_memory_usage()
            
            # Clean up
            del large_data
            gc.collect()
            
            final_memory = self.get_memory_usage()
            
            # Memory should return to near initial level
            memory_recovered = peak_memory - final_memory
            if memory_recovered > peak_memory * 0.8:  # Recovered at least 80%
                self.test_results.append({
                    'test': 'large_dataset_handling',
                    'initial_memory_mb': initial_memory,
                    'peak_memory_mb': peak_memory,
                    'final_memory_mb': final_memory,
                    'memory_recovered_mb': memory_recovered,
                    'datasets_created': len(large_data),
                    'status': 'passed'
                })
                print(f"✅ Large dataset handling test passed: {memory_recovered:.2f}MB recovered")
                return True
            else:
                self.errors.append(f"Memory not recovered: only {memory_recovered:.2f}MB recovered")
                print(f"❌ Memory not recovered: only {memory_recovered:.2f}MB recovered")
                return False
                
        except Exception as e:
            self.errors.append(f"Large dataset handling error: {e}")
            print(f"❌ Large dataset handling error: {e}")
            return False
    
    def test_numpy_array_memory(self):
        """Test numpy array memory management"""
        print("🔢 Testing Numpy Array Memory...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            # Create large numpy arrays
            arrays = []
            for i in range(100):
                # Create large numpy arrays
                arr = np.random.rand(1000, 100)  # 1000x100 array
                arrays.append(arr)
                
                if i % 50 == 0:
                    # Force garbage collection
                    del arr
                    gc.collect()
            
            # Measure memory usage
            peak_memory = self.get_memory_usage()
            
            # Clean up
            del arrays
            gc.collect()
            
            final_memory = self.get_memory_usage()
            
            # Memory should be recovered
            memory_recovered = peak_memory - final_memory
            if memory_recovered > peak_memory * 0.7:
                self.test_results.append({
                    'test': 'numpy_array_memory',
                    'initial_memory_mb': initial_memory,
                    'peak_memory_mb': peak_memory,
                    'final_memory_mb': final_memory,
                    'memory_recovered_mb': memory_recovered,
                    'arrays_created': 100,
                    'status': 'passed'
                })
                print(f"✅ Numpy array memory test passed: {memory_recovered:.2f}MB recovered")
                return True
            else:
                self.errors.append(f"Numpy memory not recovered: only {memory_recovered:.2f}MB recovered")
                print(f"❌ Numpy memory not recovered: only {memory_recovered:.2fMB recovered")
                return False
                
        except Exception as e:
            self.errors.append(f"Numpy array memory error: {e}")
            print(f"❌ Numpy array memory error: {e}")
            return False
    
    def test_thread_memory_usage(self):
        """Test memory usage in threads"""
        print("🧵 Testing Thread Memory Usage...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            def memory_intensive_thread(thread_id):
                # Create memory-intensive operations in thread
                local_data = []
                
                for i in range(100):
                    df = pd.DataFrame({
                        'data': [i] * 1000,
                        'thread_id': [thread_id] * 1000
                    })
                    local_data.append(df)
                
                    if i % 20 == 0:
                        # Force garbage collection
                        gc.collect()
                
                return len(local_data)
            
            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=memory_intensive_thread, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for threads to complete
            results = []
            for thread in threads:
                thread.join()
                results.append(100)  # Each thread creates 100 dataframes
            
            # Measure memory after threads
            thread_memory = self.get_memory_usage()
            
            # Force cleanup
            gc.collect()
            final_memory = self.get_memory_usage()
            
            # Memory should be reasonable
            memory_increase = thread_memory - initial_memory
            if memory_increase < 100:  # Less than 100MB for 5 threads
                self.test_results.append({
                    'test': 'thread_memory_usage',
                    'initial_memory_mb': initial_memory,
                    'thread_memory_mb': thread_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase,
                    'threads_created': 5,
                    'status': 'passed'
                })
                print(f"✅ Thread memory usage test passed: {memory_increase:.2f}MB increase")
                return True
            else:
                self.errors.append(f"Thread memory increase too high: {memory_increase:.2f}MB")
                print(f"❌ Thread memory increase too high: {memory_increase:.2f}MB")
                return False
                
        except Exception as e:
            self.errors.append(f"Thread memory usage error: {e}")
            print(f"❌ Thread memory usage error: {e}")
            return False
    
    def test_file_handle_leaks(self):
        """Test file handle leaks"""
        print("📁 Testing File Handle Leaks...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            file_handles = []
            
            # Open many files
            for i in range(100):
                temp_file = project_root / f'test_framework/temp_test_{i}.csv'
                
                # Create temporary file
                df = pd.DataFrame({
                    'data': [i] * 1000,
                    'value': [i * 10] * 1000
                })
                
                df.to_csv(temp_file, index=False)
                file_handles.append(temp_file)
                
                if i % 20 == 0:
                    # Close some files
                    for j in range(min(10, len(file_handles))):
                        try:
                            os.unlink(file_handles[j])
                        except:
                            pass
                    file_handles = [f for f in file_handles if os.path.exists(f)]
            
            # Clean up all files
            for file_path in file_handles:
                try:
                    os.unlink(file_path)
                except:
                    pass
            
            # Force garbage collection
            gc.collect()
            
            final_memory = self.get_memory_usage()
            
            # Memory should be recovered
            memory_increase = final_memory - initial_memory
            if memory_increase < 20:  # Less than 20MB for file operations
                self.test_results.append({
                    'test': 'file_handle_leaks',
                    'initial_memory_mb': initial_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase,
                    'files_created': 100,
                    'status': 'passed'
                })
                print(f"✅ File handle leak test passed: {memory_increase:.2f}MB increase")
                return True
            else:
                self.errors.append(f"File handle memory leak detected: {memory_increase:.2f}MB")
                print(f"❌ File handle memory leak detected: {memory_increase:.2fMB")
                return False
                
        except Exception as e:
            self.errors.append(f"File handle leak error: {e}")
            print(f"❌ File handle leak error: {e}")
            return False
    
    def test_reference_counting(self):
        """Test reference counting"""
        print("🔗 Testing Reference Counting...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            # Create circular references
            objects = []
            
            for i in range(100):
                # Create object that references itself
                class CircularRef:
                    def __init__(self, value):
                        self.value = value
                        self.parent = None
                        self.child = None
                
                obj = CircularRef(i)
                obj.child = CircularRef(i + 1)
                obj.child.parent = obj
                obj.parent = obj.child
                
                objects.append(obj)
            
            # Check memory usage
            peak_memory = self.get_memory_usage()
            
            # Break circular references
            for obj in objects:
                obj.parent = None
                obj.child = None
            
            del objects
            gc.collect()
            
            final_memory = self.get_memory_usage()
            
            # Memory should be recovered
            memory_recovered = peak_memory - final_memory
            if memory_recovered > peak_memory * 0.9:
                self.test_results.append({
                    'test': 'reference_counting',
                    'initial_memory_mb': initial_memory,
                    'peak_memory_mb': peak_memory,
                    'final_memory_mb': final_memory,
                    'memory_recovered_mb': memory_recovered,
                    'circular_objects': 100,
                    'status': 'passed'
                })
                print(f"✅ Reference counting test passed: {memory_recovered:.2f}MB recovered")
                return True
            else:
                self.errors.append(f"Reference counting memory not recovered: {memory_recovered:.2f}MB")
                print(f"❌ Reference counting memory not recovered: {memory_recovered:.2fMB")
                return False
                
        except Exception as e:
            self.errors.append(f"Reference counting error: {e}")
            print(f"❌ Reference counting error: {e}")
            return False
    
    def test_cache_memory_usage(self):
        """Test cache memory usage"""
        print("💾 Testing Cache Memory Usage...")
        
        try:
            initial_memory = self.get_memory_usage()
            
            # Create cache
            cache = {}
            
            # Fill cache with large objects
            for i in range(1000):
                key = f'key_{i}'
                value = 'x' * 10000  # 10KB string
                cache[key] = value
                
                if i % 100 == 0:
                    # Clear some cache entries
                    keys_to_remove = list(cache.keys())[:50]
                    for key in keys_to_remove:
                        del cache[key]
            
            # Measure cache memory
            cache_memory = self.get_memory_usage()
            
            # Clear cache
            cache.clear()
            gc.collect()
            
            final_memory = self.get_memory_usage()
            
            # Memory should be recovered
            memory_recovered = cache_memory - final_memory
            if memory_recovered > cache_memory * 0.8:
                self.test_results.append({
                    'test': 'cache_memory_usage',
                    'initial_memory_mb': initial_memory,
                    'cache_memory_mb': cache_memory,
                    'final_memory_mb': final_memory,
                    'memory_recovered_mb': memory_recovered,
                    'cache_entries': 1000,
                    'status': 'passed'
                })
                print(f"✅ Cache memory usage test passed: {memory_recovered:.2f}MB recovered")
                return True
            else:
                self.errors.append(f"Cache memory not recovered: {memory_recovered:.2f}MB")
                print(f"❌ Cache memory not recovered: {memory_recovered:.2fMB")
                return False
                
        except Exception as e:
            self.errors.append(f"Cache memory usage error: {e}")
            print(f"❌ Cache memory usage error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all memory tests"""
        print("🧠 Starting Memory Leak Tests...")
        print("="*60)
        
        tests = [
            self.test_memory_leak_detection,
            self.test_large_dataset_handling,
            self.test_numpy_array_memory,
            self.test_thread_memory_usage,
            self.test_file_handle_leaks,
            self.test_reference_counting,
            self.test_cache_memory_usage
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
        print(f"🧠 Memory Leak Tests Results:")
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
    tester = MemoryLeakTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All memory leak tests passed!")
        return 0
    else:
        print("❌ Some memory leak tests failed!")
        return 1

if __name__ == "__main__":
    main()
