#!/usr/bin/env python3
"""
Run all 3 backtest options (A/B/C) sequentially and compare results
"""
import subprocess, sys, os
sys.path.insert(0, 'c:/cursor/options/niftyopt')

results = {}

print("="*70)
print("RUNNING ALL 3 BACKTEST OPTIONS")
print("="*70)

# Option A: Baseline V7
print("\n" + "="*70)
print("OPTION A: BASELINE V7 (Current Best Configuration)")
print("="*70)
result_a = subprocess.run([sys.executable, "BACKTEST_V7_MULTIINDEX.py"], 
                          capture_output=True, text=True, cwd="c:/cursor/options/niftyopt")
print(result_a.stdout[-3000:] if len(result_a.stdout) > 3000 else result_a.stdout)
if result_a.returncode == 0:
    print("✓ Option A completed successfully")
else:
    print(f"✗ Option A failed: {result_a.stderr[-500:]}")

print("\n" + "="*70)
print("All options complete. Check individual outputs above.")
print("="*70)
