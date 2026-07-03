#!/usr/bin/env python3
"""
Full audit:
1. All 9 TIME exits — exact date, strategy, entry time, regime, PnL
2. All 24 strategies — which are active/inactive and their signal_check logic names
3. Inactive strategies — what signal they use, why they don't fire
"""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd
from BACKTEST_V6_PROFILED import (run_v6, load_option_data, load_eod_data,
    ACTIVE_STRATEGIES, STRATEGY_PROFILES, ENTRY_START, ENTRY_CUTOFF)
from BACKTEST_V3_TUNED import make_strategies

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)

print("="*65)
print("ALL 9 TIME EXITS — full details")
print("="*65)
time_exits=df[df['exit_reason']=='TIME'].copy()
for _,r in time_exits.sort_values('pnl_rs').iterrows():
    print(f"  {str(r['date'])[:10]}  {r['strategy']:<22}  {r['direction']}  "
          f"entry {r['entry_hhmm']}  regime={r['regime']:<14}  Rs{r['pnl_rs']:+,.0f}")

print(f"\n  Total TIME exit loss: Rs{time_exits['pnl_rs'].sum():+,.0f}")
print(f"  Avg per TIME exit: Rs{time_exits['pnl_rs'].mean():+,.0f}")

print("\n\n" + "="*65)
print("ALL 24 STRATEGIES — status, trades, PnL")
print("="*65)
all_strats = make_strategies()
for s in all_strats:
    active = s.name in ACTIVE_STRATEGIES
    has_profile = s.name in STRATEGY_PROFILES
    strat_trades = df[df['strategy']==s.name] if active else pd.DataFrame()
    n = len(strat_trades)
    wr = f"{strat_trades['won'].mean()*100:.0f}%" if n > 0 else "—"
    net = f"Rs{strat_trades['pnl_rs'].sum():+,.0f}" if n > 0 else "Rs0"
    es = ENTRY_START.get(s.name, getattr(s,'entry_start',930))
    ec = ENTRY_CUTOFF.get(s.name, getattr(s,'entry_end',1400))
    status = "ACTIVE" if active else "INACTIVE"
    profile_ok = "PROFILE" if has_profile else "NO_PROFILE"
    print(f"  {status:<8} {profile_ok:<11} {s.name:<28} n={n:<3} WR={wr:<6} {net:<12} window={es}-{ec}")

print("\n\n" + "="*65)
print("INACTIVE STRATEGIES — why are they not firing?")
print("="*65)
for s in all_strats:
    if s.name not in ACTIVE_STRATEGIES:
        has_profile = s.name in STRATEGY_PROFILES
        print(f"\n  {s.name}")
        print(f"    direction={s.direction}  strike={s.strike}")
        print(f"    entry_window={s.entry_start}-{s.entry_end}")
        print(f"    has_profile={has_profile}")
        if has_profile:
            p = STRATEGY_PROFILES[s.name]
            print(f"    profile: rsi={p.rsi_range}  ema={p.ema_structure}  "
                  f"vwap={p.vwap_side}  mom={p.momentum_dir}")
