import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
from BACKTEST_V3_TUNED import make_strategies
from BACKTEST_V6_PROFILED import ACTIVE_STRATEGIES

strats = make_strategies()
active = [s for s in strats if s.name in ACTIVE_STRATEGIES]
print('Strategy min/max premium (NIFTY DNA):')
for s in active:
    print(f'  {s.name:30s}  min={s.min_premium:6.0f}  max={s.max_premium:6.0f}  dir={s.direction}')

# What scale do we need for BN?
# BN ATM premium range (from data): p5=180, median=698, p95=1343
# NIFTY ATM premium range: p5=~50, median=~225, p95=~450
# So to normalize BN premium to NIFTY-equivalent:
# BN_prem / scale = NIFTY_equiv
# scale = BN_median / NIFTY_median = 698 / 225 = 3.10
# But strat.max_premium for MEAN_REVERSION might be 200-300, which after /3.35 still gives 274 > max
print()
print('BN premium scale = 3.35')
print('Sample BN prem 920 / 3.35 =', 920/3.35)
print()

# Let's also check signal_check source for min_premium check
import inspect
from BACKTEST_V3_TUNED import signal_check
src = inspect.getsource(signal_check)
# Find the premium filter lines
lines = src.split('\n')
for i, line in enumerate(lines):
    if 'min_premium' in line or 'max_premium' in line:
        print(f'Line {i}: {line}')
