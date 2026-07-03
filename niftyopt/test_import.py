import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')

try:
    print("Testing imports...")
    from BACKTEST_V6_PROFILED import (
        ACTIVE_STRATEGIES, ENTRY_START, ENTRY_CUTOFF, FIXED_TARGET_STRATEGIES,
        TRADEABLE_REGIMES, STRATEGY_PROFILES,
        StrategyProfile, compute_day_context, compute_intraday_state,
        match_profile, Trade, execute_fixed_target,
    )
    print("V6 imports OK")
    
    # Test TSL values
    TSL_ACTIVATE = 0.04
    TSL_TRAIL = 0.06
    TARGET_PCT = 0.50
    HARD_EXIT = 1430
    print(f"TSL values: ACTIVATE={TSL_ACTIVATE}, TRAIL={TSL_TRAIL}, TARGET={TARGET_PCT}")
    print("All imports successful!")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
