import sys
sys.path.insert(0, r'c:\cursor\options\niftyopt')

print("Test 1: Basic imports...")
try:
    import pandas as pd
    print("  pandas OK")
except Exception as e:
    print(f"  pandas ERROR: {e}")
    
print("Test 2: V6 imports...")
try:
    from BACKTEST_V6_PROFILED import (
        ACTIVE_STRATEGIES, STRATEGY_PROFILES,
        StrategyProfile, Trade
    )
    print(f"  V6 OK - {len(ACTIVE_STRATEGIES)} strategies")
except Exception as e:
    print(f"  V6 ERROR: {e}")
    import traceback
    traceback.print_exc()

print("Test 3: V7 AGGRESSIVE import...")
try:
    # Just import the module without running it
    import BACKTEST_V7_AGGRESSIVE
    print("  V7 AGGRESSIVE import OK")
except Exception as e:
    print(f"  V7 ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nAll tests complete!")
