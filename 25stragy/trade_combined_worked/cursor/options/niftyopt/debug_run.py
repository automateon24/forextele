import sys
sys.path.insert(0, r'c:\cursor\options\niftyopt')

print("Step 1: Testing imports...")
try:
    import pandas as pd
    print("  pandas OK")
    
    from dataclasses import dataclass
    print("  dataclasses OK")
    
    from BACKTEST_V6_PROFILED import (
        ACTIVE_STRATEGIES, ENTRY_START, ENTRY_CUTOFF, FIXED_TARGET_STRATEGIES,
        TRADEABLE_REGIMES, STRATEGY_PROFILES,
        StrategyProfile, compute_day_context, compute_intraday_state,
        match_profile, Trade, execute_fixed_target,
    )
    print("  BACKTEST_V6_PROFILED imports OK")
    print("Step 2: All imports successful!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Step 3: Script structure OK - ready to run backtest")
