#!/usr/bin/env python3
"""
Reality check:
1. What is 5% per day in rupees on 1 lot NIFTY?
2. What do our current trades actually return per trade in %?
3. How many trades per day on average?
4. What premium do we typically buy? (option price = capital at risk)
5. Monthly distribution — which days have 0 trades?
"""
import sys; sys.path.insert(0,'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from BACKTEST_V6_PROFILED import run_v6, load_option_data, load_eod_data

opt=load_option_data(); eod=load_eod_data()
trades=run_v6(opt,eod)
df=pd.DataFrame([t.__dict__ for t in trades])
df['entry_hhmm']=pd.to_datetime(df['entry_time']).apply(lambda x: x.hour*100+x.minute)
df['date']=pd.to_datetime(df['date'])
df['month']=df['date'].dt.to_period('M')

# NIFTY lot size = 25
LOT = 25

print("="*65)
print("WHAT IS 5% PER DAY?")
print("="*65)
print()
# Option premium typically 80-200 rupees ATM
# Capital at risk = premium * lot_size
for premium in [80, 120, 150, 200]:
    capital = premium * LOT
    target_5pct = capital * 0.05
    print(f"  If option premium = Rs{premium:3d}  → capital = Rs{capital:,}  → 5% = Rs{target_5pct:.0f}")

print()
print("="*65)
print("ACTUAL TRADE RETURNS (current backtest)")
print("="*65)
print()
# Avg PnL per trade
print(f"  Avg PnL per trade: Rs{df['pnl_rs'].mean():+,.0f}")
print(f"  Median PnL:        Rs{df['pnl_rs'].median():+,.0f}")
print(f"  Win avg:           Rs{df[df['won']]['pnl_rs'].mean():+,.0f}")
print(f"  Loss avg:          Rs{df[~df['won']]['pnl_rs'].mean():+,.0f}")
print()

# Return % per trade (if premium ~Rs100 * 25 = Rs2500 capital)
for premium in [80, 120, 150]:
    capital = premium * LOT
    df[f'ret_{premium}'] = df['pnl_rs'] / capital * 100
    avg_ret = df[f'ret_{premium}'].mean()
    print(f"  If premium=Rs{premium}: avg return per trade = {avg_ret:+.1f}%")

print()
print("="*65)
print("DAILY PnL DISTRIBUTION")
print("="*65)
daily = df.groupby('date').agg(
    n_trades=('pnl_rs','count'),
    total_pnl=('pnl_rs','sum'),
    won=('won','sum')
).reset_index()

# What capital base gives 5%?
# Per day PnL stats
print(f"\n  Total traded days: {len(daily)}")
print(f"  Avg trades/day:    {daily['n_trades'].mean():.1f}")
print(f"  Avg PnL/day:       Rs{daily['total_pnl'].mean():+,.0f}")
print(f"  Median PnL/day:    Rs{daily['total_pnl'].median():+,.0f}")
print(f"  Max PnL/day:       Rs{daily['total_pnl'].max():+,.0f}")
print(f"  Min PnL/day:       Rs{daily['total_pnl'].min():+,.0f}")
print(f"  Days >= Rs500:     {(daily['total_pnl']>=500).sum()}")
print(f"  Days >= Rs1000:    {(daily['total_pnl']>=1000).sum()}")
print(f"  Days >= Rs2000:    {(daily['total_pnl']>=2000).sum()}")

print()
print("="*65)
print("WHAT CAPITAL MAKES CURRENT RETURNS = 5%/day?")
print("="*65)
avg_daily = daily['total_pnl'].mean()
capital_for_5pct = avg_daily / 0.05
print(f"\n  Avg daily PnL = Rs{avg_daily:,.0f}")
print(f"  To make that 5%: capital = Rs{capital_for_5pct:,.0f} ({capital_for_5pct/100000:.1f}L)")
print(f"  Meaning: need {capital_for_5pct/100000:.1f}L capital for 5%/day on current strategy returns")

print()
print("="*65)
print("MONTHLY BREAKDOWN — traded days vs total days")
print("="*65)
eod_df = pd.DataFrame(eod)
if isinstance(eod_df.index, pd.DatetimeIndex):
    all_days_by_month = eod_df.groupby(pd.Grouper(freq='ME')).count()
else:
    eod_df.index = pd.to_datetime(eod_df.index)
    all_days_by_month = eod_df.groupby(pd.Grouper(freq='ME')).count()

monthly_trades = df.groupby('month').agg(
    traded_days=('date','nunique'),
    total_pnl=('pnl_rs','sum'),
    n_trades=('pnl_rs','count')
).reset_index()

for _,r in monthly_trades.iterrows():
    print(f"  {r['month']}  traded={r['traded_days']} days  "
          f"trades={r['n_trades']:2d}  PnL=Rs{r['total_pnl']:+,.0f}  "
          f"per_day=Rs{r['total_pnl']/r['traded_days']:+,.0f}")

print()
print("="*65)
print("ROUTES TO 5%/DAY — what would need to change?")
print("="*65)
print("""
  Option A: Increase lot size (capital scaling)
    - Current avg Rs684/traded day
    - 5% on Rs10,000 capital = Rs500/day → ALREADY THERE
    - 5% on Rs20,000 capital = Rs1,000/day → 57% of days achieve this
    - Real question: what is 'capital'?

  Option B: More trades per day (frequency)
    - Currently 1.18 trades/traded day
    - Need ~3-4 trades/day to consistently hit Rs2000+
    - Problem: most strategies fire max 1x/day by design

  Option C: Larger moves per trade (bigger % gain per trade)
    - Current avg TSL exit = Rs689
    - Need Rs2000+ per trade on 1 lot
    - That needs 80pt move in option premium (on Rs150 ATM)
    - Only happens on strong trending days

  Option D: Multi-timeframe / different strategies for uncovered days
    - 155 total days, only 55 traded = 100 days with 0 trades
    - Fill those 100 days with safe, selective strategies
""")

print("="*65)
print("UNCOVERED DAYS BY REGIME")
print("="*65)
traded_dates = set(df['date'].dt.date)
for day, row in eod.iterrows():
    day_d = pd.Timestamp(day).date()
    if day_d not in traded_dates:
        pass

eod_index = [pd.Timestamp(d).date() for d in eod.index]
untrade_regimes = {}
for i, day in enumerate(eod.index):
    day_d = pd.Timestamp(day).date()
    if day_d not in traded_dates:
        r = eod.iloc[i].get('regime', 'UNKNOWN') if hasattr(eod.iloc[i], 'get') else 'UNKNOWN'
        untrade_regimes[r] = untrade_regimes.get(r, 0) + 1

print(f"\n  Untraded days: {len(eod_index) - len(traded_dates)} / {len(eod_index)}")
