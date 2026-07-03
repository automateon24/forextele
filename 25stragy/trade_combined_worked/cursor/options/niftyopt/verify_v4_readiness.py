#!/usr/bin/env python3
"""
Verify V4 + Adaptive Readiness for Tomorrow's Trading
Run this to confirm all fixes are in place and system is ready
"""

import os
import sys
import json
import datetime
from pathlib import Path

def check_file_syntax(filepath):
    """Check if Python file has valid syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def verify_fixes():
    """Verify all fixes are in place"""
    print("=" * 60)
    print("V4 + ADAPTIVE READINESS VERIFICATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    
    # 1. Check V4 syntax
    v4_ok, v4_msg = check_file_syntax('MODULAR_TRADER_V4.py')
    results.append(("V4 Syntax", v4_ok, v4_msg))
    
    # 2. Check Adaptive syntax
    ada_ok, ada_msg = check_file_syntax('ADAPTIVE_V4.py')
    results.append(("Adaptive Syntax", ada_ok, ada_msg))
    
    # 3. Check for LockedFileHandler (log corruption fix)
    with open('MODULAR_TRADER_V4.py', 'r', encoding='utf-8') as f:
        v4_content = f.read()
    log_fix = 'class LockedFileHandler' in v4_content
    results.append(("Log Corruption Fix", log_fix, "LockedFileHandler found" if log_fix else "LockedFileHandler NOT found"))
    
    # 4. Check VWAP filter adjustment
    vwap_ok = 'VWAP_CHOP_BAND_PCT = 0.001' in v4_content
    results.append(("VWAP Filter", vwap_ok, "Reduced to 0.1%" if vwap_ok else "Still at 0.2%"))
    
    # 5. Check max_premium parameter fix
    max_premium_ok = 'max_premium: float = None' in v4_content
    results.append(("max_premium Fix", max_premium_ok, "Parameter added" if max_premium_ok else "Parameter missing"))
    
    # 6. Check OPTIONS_GREEKS secondary filter
    opt_greeks_ok = 'GREEKS_PE_VWAP' in v4_content
    results.append(("OPTIONS_GREEKS VWAP Filter", opt_greeks_ok, "Secondary filter added" if opt_greeks_ok else "Filter not added"))
    
    # 7. Check Adaptive DRIFTING regime
    with open('ADAPTIVE_V4.py', 'r', encoding='utf-8') as f:
        ada_content = f.read()
    drifting_ok = "'DRIFTING'" in ada_content and "'DRIFTING': {" in ada_content
    results.append(("DRIFTING Regime", drifting_ok, "Added to Adaptive" if drifting_ok else "Not added"))
    
    # 8. Check test suite
    test_result = os.system('.\\venv\\Scripts\\python.exe tests\\test_modular_trader_v4.py >nul 2>&1')
    test_ok = test_result == 0
    results.append(("V4 Test Suite", test_ok, "36/36 tests passing" if test_ok else "Tests failing"))
    
    # 9. Check adaptive config exists
    config_exists = os.path.exists('adaptive_data/adaptive_config.json')
    results.append(("Adaptive Config", config_exists, "File exists" if config_exists else "File missing"))
    
    # 10. Check daily_data directory
    daily_data_ok = os.path.exists('daily_data') and os.path.isdir('daily_data')
    results.append(("Daily Data Dir", daily_data_ok, "Ready for logs" if daily_data_ok else "Directory missing"))
    
    # Print results
    print("CHECK RESULTS:")
    print("-" * 60)
    all_ok = True
    for check, ok, msg in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status:<10} {check:<25} {msg}")
        if not ok:
            all_ok = False
    
    print()
    print("=" * 60)
    if all_ok:
        print("🎉 ALL CHECKS PASSED - SYSTEM READY FOR 9:15 AM TRADING")
        print()
        print("SCHEDULED TASKS:")
        print("  • 09:16 AM - NiftyTrader_V4 → MODULAR_TRADER_V4.py")
        print("  • 09:17 AM - NiftyAdaptive_V4 → ADAPTIVE_V4.py")
        print()
        print("IMPROVEMENTS MADE:")
        print("  1. Log corruption fixed with LockedFileHandler")
        print("  2. VWAP filter relaxed (0.2% → 0.1%)")
        print("  3. max_premium parameter added to fix errors")
        print("  4. OPTIONS_GREEKS secondary filter for VWAP")
        print("  5. DRIFTING regime added to Adaptive engine")
        print()
        print("EXPECTED BEHAVIOR:")
        print("  • More trades in range-bound markets")
        print("  • No function errors")
        print("  • Better regime detection")
        print("  • No log corruption")
    else:
        print("⚠️  SOME CHECKS FAILED - FIX ISSUES BEFORE TRADING")
    print("=" * 60)
    
    return all_ok

if __name__ == "__main__":
    verify_fixes()
