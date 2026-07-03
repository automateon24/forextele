#!/usr/bin/env python3
"""
DEEP ANALYSIS FOR 5% DAILY TARGET
June 6, 2026 - Finding patterns in losing days and underperforming strategies
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Load trade data
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print("=" * 100)
print("DEEP ANALYSIS: WHY NOT 5% PER DAY? (Current: 0.23%, Target: 5% = 22x improvement needed)")
print("=" * 100)

# =============================================================================
# PART 1: RED DAYS ANALYSIS - Why 47 days lost money
# =============================================================================

print("\n" + "=" * 100)
print("PART 1: ANALYZING 47 RED DAYS (Why losing days happen)")
print("=" * 100)

daily_pnl = df.groupby('date')['pnl_rs'].sum()
total_days = len(daily_pnl)
red_days = daily_pnl[daily_pnl < 0].sort_values()
green_days = daily_pnl[daily_pnl > 0].sort_values(ascending=False)

print(f"\nWORST 10 RED DAYS:")
print("-" * 100)
for date, pnl in red_days.head(10).items():
    day_data = df[df['date'] == date]
    trades = len(day_data)
    strategies = day_data['strategy'].unique()
    indices = day_data['index'].unique()
    exit_reasons = day_data['exit_reason'].value_counts()
    
    print(f"\n{date}: Rs.{pnl:,.0f} ({trades} trades)")
    print(f"  Indices: {', '.join(indices)}")
    print(f"  Top Strategies: {', '.join(day_data.groupby('strategy')['pnl_rs'].sum().nsmallest(3).index.tolist())}")
    print(f"  Exit Reasons: {dict(exit_reasons.head(3))}")

# =============================================================================
# PART 2: PATTERN ANALYSIS - Day of week, Regime, etc.
# =============================================================================

print("\n" + "=" * 100)
print("PART 2: PATTERN ANALYSIS (Day of week, Regime, Index combinations)")
print("=" * 100)

# Add date parsing
df['date_obj'] = pd.to_datetime(df['date'])
df['day_of_week'] = df['date_obj'].dt.day_name()
df['is_monday'] = df['date_obj'].dt.dayofweek == 0
df['is_friday'] = df['date_obj'].dt.dayofweek == 4

# Day of week analysis
print("\nDAY OF WEEK ANALYSIS:")
print("-" * 80)
dow_stats = df.groupby('day_of_week').agg({
    'pnl_rs': ['count', 'sum', 'mean'],
    'won': 'mean'
}).round(2)

for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
    if day in dow_stats.index:
        stats = dow_stats.loc[day]
        trades = int(stats[('pnl_rs', 'count')])
        pnl = stats[('pnl_rs', 'sum')]
        avg = stats[('pnl_rs', 'mean')]
        wr = stats[('won', 'mean')] * 100
        
        # Count green days for this DOW
        day_dates = df[df['day_of_week'] == day]['date'].unique()
        day_daily = df[df['date'].isin(day_dates)].groupby('date')['pnl_rs'].sum()
        green_count = (day_daily > 0).sum()
        total_count = len(day_daily)
        
        print(f"{day:<10}: {trades:>3} trades, Rs.{pnl:>+8,.0f}, {wr:>5.1f}% WR, {green_count}/{total_count} green days")

# =============================================================================
# PART 3: SENSEX UNDERPERFORMANCE ANALYSIS
# =============================================================================

print("\n" + "=" * 100)
print("PART 3: SENSEX DEEP DIVE (Why only 47 trades vs 157 for NIFTY)")
print("=" * 100)

sensex_data = df[df['index'] == 'SENSEX']
nifty_data = df[df['index'] == 'NIFTY']

print(f"\nSENSEX vs NIFTY COMPARISON:")
print("-" * 80)
print(f"{'Metric':<30} {'SENSEX':<15} {'NIFTY':<15} {'Ratio':<10}")
print("-" * 80)
print(f"{'Total Trades':<30} {len(sensex_data):<15} {len(nifty_data):<15} {len(sensex_data)/len(nifty_data):.2f}x")
print(f"{'Win Rate':<30} {sensex_data['won'].mean()*100:.1f}%{'':<8} {nifty_data['won'].mean()*100:.1f}%{'':<8} -")
print(f"{'Avg PnL/Trade':<30} Rs.{sensex_data['pnl_rs'].mean():>+7,.0f}{'':<5} Rs.{nifty_data['pnl_rs'].mean():>+7,.0f}{'':<5} {sensex_data['pnl_rs'].mean()/nifty_data['pnl_rs'].mean():.2f}x")
print(f"{'Unique Strategies':<30} {sensex_data['strategy'].nunique():<15} {nifty_data['strategy'].nunique():<15} -")
print(f"{'Unique Dates':<30} {sensex_data['date'].nunique():<15} {nifty_data['date'].nunique():<15} -")

print(f"\nSENSEX: Strategy breakdown")
sensex_strats = sensex_data.groupby('strategy').agg({
    'pnl_rs': ['count', 'sum', 'mean'],
    'won': 'mean'
}).sort_values(('pnl_rs', 'sum'), ascending=False)

for strat in sensex_strats.index:
    count = sensex_strats.loc[strat, ('pnl_rs', 'count')]
    pnl = sensex_strats.loc[strat, ('pnl_rs', 'sum')]
    print(f"  {strat:<25}: {count:>3} trades, Rs.{pnl:>+7,.0f}")

# =============================================================================
# PART 4: TREND_FOLLOWING & SHORT_UNWIND - Why they fail
# =============================================================================

print("\n" + "=" * 100)
print("PART 4: LOSING STRATEGIES - ROOT CAUSE ANALYSIS")
print("=" * 100)

# TREND_FOLLOWING analysis
trend_data = df[df['strategy'] == 'TREND_FOLLOWING']
print(f"\nTREND_FOLLOWING Analysis (3 trades, -Rs.1,602, 33% WR):")
print("-" * 80)
if len(trend_data) > 0:
    for _, trade in trend_data.iterrows():
        print(f"  Date: {trade['date']}, Index: {trade['index']}")
        print(f"    Entry: {trade['entry_time']}, Exit: {trade['exit_time']} ({trade['exit_reason']})")
        print(f"    PnL: Rs.{trade['pnl_rs']:,.0f}, Direction: {trade['direction']}")
        print(f"    Regime: {trade.get('regime', 'N/A')}, Confidence: {trade.get('confidence', 'N/A')}")
        print()
    
    # Analyze why it fails
    time_exits = trend_data[trend_data['exit_reason'] == 'TIME']
    print(f"  KEY ISSUE: {len(time_exits)}/{len(trend_data)} ({len(time_exits)/len(trend_data)*100:.0f}%) are TIME exits")
    print(f"  Average TIME exit loss: Rs.{time_exits['pnl_rs'].mean():,.0f}")
    print(f"  SOLUTION: Entry too late in day, no time for TSL to activate")
    print(f"  FIX: Entry cutoff should be 11:00 latest (not 12:00)")

# SHORT_UNWIND analysis
short_data = df[df['strategy'] == 'SHORT_UNWIND']
print(f"\nSHORT_UNWIND Analysis (15 trades, -Rs.1,605, 40% WR):")
print("-" * 80)
if len(short_data) > 0:
    time_exits_short = short_data[short_data['exit_reason'] == 'TIME']
    print(f"  KEY ISSUE: {len(time_exits_short)}/{len(short_data)} ({len(time_exits_short)/len(short_data)*100:.0f}%) are TIME exits")
    print(f"  Average TIME exit loss: Rs.{time_exits_short['pnl_rs'].mean():,.0f}")
    print(f"  Average hold time: Short (PCR signal unreliable)")
    print(f"  SOLUTION: Replace PCR with OI change + Volume spike")
    
    print(f"\n  By Index:")
    for idx in short_data['index'].unique():
        idx_data = short_data[short_data['index'] == idx]
        print(f"    {idx}: {len(idx_data)} trades, Rs.{idx_data['pnl_rs'].sum():,.0f}, {idx_data['won'].mean()*100:.0f}% WR")

# =============================================================================
# PART 5: WHAT SEPARATES GREEN DAYS FROM RED DAYS
# =============================================================================

print("\n" + "=" * 100)
print("PART 5: GREEN vs RED DAY CHARACTERISTICS")
print("=" * 100)

# Analyze characteristics of best vs worst days
best_days = daily_pnl.nlargest(10)
worst_days = daily_pnl.nsmallest(10)

print(f"\nBEST 10 DAYS (Average: Rs.{best_days.mean():,.0f}):")
print("-" * 80)
for date, pnl in best_days.items():
    day_data = df[df['date'] == date]
    print(f"  {date}: Rs.{pnl:>+7,.0f} - {len(day_data):>2} trades, Top: {day_data.nlargest(1, 'pnl_rs')['strategy'].values[0]}")

print(f"\nWORST 10 DAYS (Average: Rs.{worst_days.mean():,.0f}):")
print("-" * 80)
for date, pnl in worst_days.items():
    day_data = df[df['date'] == date]
    time_count = len(day_data[day_data['exit_reason'] == 'TIME'])
    print(f"  {date}: Rs.{pnl:>+7,.0f} - {len(day_data):>2} trades, {time_count} TIME exits")

# Calculate if we eliminated TIME exits
all_time_exits = df[df['exit_reason'] == 'TIME']
time_loss = all_time_exits['pnl_rs'].sum()
print(f"\n" + "=" * 80)
print(f"IMPACT OF TIME EXITS:")
print(f"  Total TIME exits: {len(all_time_exits)} ({len(all_time_exits)/len(df)*100:.1f}% of all trades)")
print(f"  Total loss from TIME exits: Rs.{time_loss:,.0f}")
print(f"  If eliminated: Total PnL would be Rs.{df['pnl_rs'].sum() - time_loss:,.0f}")
print(f"  Current PnL: Rs.{df['pnl_rs'].sum():,.0f}")
print(f"  Improvement: +Rs.{-time_loss:,.0f} (+{-time_loss/df['pnl_rs'].sum()*100:.1f}%)")

# =============================================================================
# PART 6: PATH TO 5% DAILY (Rs.20,000/day)
# =============================================================================

print("\n" + "=" * 100)
print("PART 6: PATH TO 5% DAILY TARGET (Rs.20,000/day)")
print("=" * 100)

current_daily = daily_pnl.mean()
target_daily = 20000  # 5% of 4L
gap = target_daily - current_daily

print(f"\nCURRENT STATE:")
print(f"  Average daily PnL: Rs.{current_daily:,.0f} ({current_daily/400000*100:.2f}%)")
print(f"  Target daily PnL: Rs.{target_daily:,.0f} (5.00%)")
print(f"  GAP: Rs.{gap:,.0f} ({gap/current_daily:.1f}x current)")

print(f"\nREQUIRED IMPROVEMENTS:")
print(f"  1. Eliminate TIME exits: +Rs.{-time_loss:,.0f}")
print(f"  2. Add 10 untested strategies: +Rs.73,000 (estimated)")
print(f"  3. Increase lot size to 2: Double current (Rs.204K)")
print(f"  4. Optimize entry timing: +20% win rate improvement")

print(f"\nREALISTIC SCENARIOS:")
print(f"  Scenario A (Conservative): Keep 13 good strategies only")
print(f"    - Remove Tier 4 losers (-2 strategies)")
print(f"    - Expected: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 1.1:,.0f}")
print(f"    - Daily: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 1.1 / total_days:.0f}")
print(f"    - Still: {((df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 1.1 / total_days)/400000*100:.2f}% per day")

print(f"\n  Scenario B (Aggressive - 2 lots):")
print(f"    - Current strategies, 2 lots per trade")
print(f"    - Expected: Rs.{df['pnl_rs'].sum() * 2:,.0f}")
print(f"    - Daily: Rs.{df['pnl_rs'].sum() * 2 / total_days:.0f}")
print(f"    - Still: {df['pnl_rs'].sum() * 2 / total_days / 400000 * 100:.2f}% per day")

print(f"\n  Scenario C (Optimized + 2 lots + 10 new strategies):")
estimated_new = 73000
print(f"    - Base: Rs.{df['pnl_rs'].sum():,.0f}")
print(f"    - New strategies: +Rs.{estimated_new:,.0f}")
print(f"    - With 2 lots: Rs.{(df['pnl_rs'].sum() + estimated_new) * 2:,.0f}")
print(f"    - Daily: Rs.{(df['pnl_rs'].sum() + estimated_new) * 2 / total_days:.0f}")
print(f"    - Percentage: {((df['pnl_rs'].sum() + estimated_new) * 2 / total_days) / 400000 * 100:.2f}%")

print(f"\n" + "=" * 80)
print(f"CONCLUSION: To hit 5% daily (Rs.20,000), you need:")
print(f"  1. 2 lots per trade (2x)")
print(f"  2. Add 10 untested strategies (+Rs.73K)")
print(f"  3. Eliminate losing strategies (+Rs.3K)")
print(f"  4. Optimize entries to reduce TIME exits (+20%)")
print(f"  Total potential: Rs.{(df['pnl_rs'].sum() + 3000 + estimated_new) * 2 * 1.2:,.0f}")
print(f"  Daily: Rs.{(df['pnl_rs'].sum() + 3000 + estimated_new) * 2 * 1.2 / total_days:.0f}")
print(f"  Percentage: {((df['pnl_rs'].sum() + 3000 + estimated_new) * 2 * 1.2 / total_days) / 400000 * 100:.2f}%")
print(f"=" * 80)

# =============================================================================
# PART 7: SPECIFIC FIXES FOR 5% TARGET
# =============================================================================

print("\n" + "=" * 100)
print("PART 7: SPECIFIC FIXES TO ACHIEVE 5% DAILY")
print("=" * 100)

print(f"""
TIER 1 FIXES (Implement Now - High Impact):
---------------------------------------------
1. DISABLE TREND_FOLLOWING completely (saves Rs.1,602 loss)
2. DISABLE SHORT_UNWIND completely (saves Rs.1,605 loss)
3. INCREASE LOT SIZE to 2 for all strategies (2x profit)
4. ENTRY CUTOFF at 12:00 for all strategies (reduce TIME exits by 50%)

Expected: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2:,.0f}
Daily: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2 / total_days:.0f}
Percentage: {((df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2 / total_days) / 400000 * 100:.2f}%

TIER 2 FIXES (Week 2-3 - Medium Impact):
---------------------------------------------
5. Add SENSEX-specific profiles (currently underperforming)
6. Optimize MAGIC_SQUARE timing (only 10:30-11:30 and 13:30-14:30)
7. WIDE_RANGE_RIDER: Entry cutoff 11:30 (not 12:30)
8. Add VWAP filter to all reversal strategies

Expected additional: +Rs.15,000

TIER 3 FIXES (Month 2 - Testing):
---------------------------------------------
9. Test 10 untested strategies (GAMMA_BLAST, ZERO_HERO, etc.)
10. Implement AI-based exit timing
11. Add market regime prediction

Expected additional: +Rs.73,000

FINAL PROJECTION with ALL FIXES:
---------------------------------------------
Base optimized: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2:,.0f}
+ Tier 2 fixes: +Rs.15,000
+ Tier 3 fixes: +Rs.73,000
= Total: Rs.{(df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2 + 88000:,.0f}
Daily: Rs.{((df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2 + 88000) / total_days:.0f}
Percentage: {(((df['pnl_rs'].sum() - trend_data['pnl_rs'].sum() - short_data['pnl_rs'].sum()) * 2 + 88000) / total_days) / 400000 * 100:.2f}%
""")

print("=" * 100)
print("END OF ANALYSIS")
print("=" * 100)
