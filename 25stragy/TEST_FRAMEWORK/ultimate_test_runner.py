#!/usr/bin/env python3
"""
ULTIMATE TEST RUNNER
==================
Ultimate test runner that bypasses subprocess issues
"""

import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'test_framework'))

def run_ultimate_tests():
    """Run ultimate tests"""
    print("🚀 ULTIMATE TEST RUNNER")
    print("="*50)
    
    test_results = {}
    total_passed = 0
    total_tests = 0
    
    # Test 1: Working Unit Tests
    print("\n🧪 Working Unit Tests...")
    try:
        from working_unit_tests import run_working_unit_tests
        result = run_working_unit_tests()
        test_results['working_unit_tests'] = result
        total_passed += result['passed']
        total_tests += result['total']
        print(f"✅ {result['passed']}/{result['total']} passed")
    except Exception as e:
        print(f"❌ Working Unit Tests failed: {e}")
        test_results['working_unit_tests'] = {'passed': 0, 'total': 5}
        total_tests += 5
    
    # Test 2: Fixed Thread Safety Tests
    print("\n🧵 Fixed Thread Safety Tests...")
    try:
        from fixed_thread_safety_tests import FixedThreadSafetyTests
        tester = FixedThreadSafetyTests()
        success = tester.run_all_tests()
        passed = len([r for r in tester.test_results if r['status'] == 'passed'])
        total_passed += passed
        total_tests += len(tester.test_results)
        test_results['fixed_thread_safety_tests'] = {'passed': passed, 'total': len(tester.test_results)}
        print(f"✅ {passed}/{len(tester.test_results)} passed")
    except Exception as e:
        print(f"❌ Thread Safety Tests failed: {e}")
        test_results['fixed_thread_safety_tests'] = {'passed': 0, 'total': 3}
        total_tests += 3
    
    # Test 3: Production Validation
    print("\n🚀 Production Validation...")
    try:
        from production_validation import ProductionValidation
        validator = ProductionValidation()
        success = validator.run_production_validation()
        passed = len([r for r in validator.validation_results if r['status'] == 'passed'])
        total_passed += passed
        total_tests += len(validator.validation_results)
        test_results['production_validation'] = {'passed': passed, 'total': len(validator.validation_results)}
        print(f"✅ {passed}/{len(validator.validation_results)} passed")
    except Exception as e:
        print(f"❌ Production Validation failed: {e}")
        test_results['production_validation'] = {'passed': 0, 'total': 4}
        total_tests += 4
    
    # Test 4: Definitive Production Test
    print("\n🎯 Definitive Production Test...")
    try:
        from definitive_production_test import DefinitiveProductionTest
        tester = DefinitiveProductionTest()
        success = tester.run_definitive_test()
        total_passed += tester.success_count
        total_tests += tester.total_tests
        test_results['definitive_production_test'] = {'passed': tester.success_count, 'total': tester.total_tests}
        print(f"✅ {tester.success_count}/{tester.total_tests} passed")
    except Exception as e:
        print(f"❌ Definitive Production Test failed: {e}")
        test_results['definitive_production_test'] = {'passed': 0, 'total': 22}
        total_tests += 22
    
    # Results
    print("\n" + "="*50)
    print("📊 ULTIMATE TEST RESULTS:")
    print(f"✅ Total Passed: {total_passed}")
    print(f"❌ Total Failed: {total_tests - total_passed}")
    print(f"📊 Total Tests: {total_tests}")
    print(f"📈 Success Rate: {(total_passed/total_tests)*100:.1f}%")
    
    if total_passed == total_tests:
        print("\n🎉 ULTIMATE RESULT: PRODUCTION READY!")
        return True
    else:
        print("\n❌ ULTIMATE RESULT: NOT PRODUCTION READY!")
        return False

if __name__ == "__main__":
    success = run_ultimate_tests()
    sys.exit(0 if success else 1)
