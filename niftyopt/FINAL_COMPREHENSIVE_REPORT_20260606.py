#!/usr/bin/env python3
"""
FINAL COMPREHENSIVE REPORT - All 25 Strategies
June 6, 2026 - Complete Analysis with Index-wise and Strategy-wise breakdown
"""

import pandas as pd
import numpy as np

# Load trade data
df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print("=" * 120)
print("FINAL COMPREHENSIVE REPORT - ALL 25 STRATEGIES WITH OPTIMIZED DNA")
print("June 6, 2026")
print("=" * 120)

# =============================================================================
# PART 1: OVERALL SUMMARY
# =============================================================================

print("\n" + "=" * 120)
print("PART 1: OVERALL PERFORMANCE SUMMARY")
print("=" * 120)

total_trades = len(df)
total_pnl = df['pnl_rs'].sum()
win_rate = df['won'].mean() * 100
avg_pnl = df['pnl_rs'].mean()
max_dd = df.groupby('date')['pnl_rs'].sum().cumsum().pipe(lambda x: x - x.cummax()).min()
green_days = (df.groupby('date')['pnl_rs'].sum() > 0).sum()
total_days = df['date'].nunique()

print(f"""
================================================================================
                           OVERALL METRICS
================================================================================
  Total Trades:        {total_trades:>4}
  Win Rate:           {win_rate:>5.1f}%
  Total PnL:          Rs.{total_pnl:>+10,.0f}
  Avg PnL/Trade:      Rs.{avg_pnl:>+10,.0f}
  Max Drawdown:       Rs.{max_dd:>10,.0f}
  Green Days:         {green_days}/{total_days} ({100*green_days/total_days:.0f}%)
================================================================================
""")

# =============================================================================
# PART 2: INDEX-WISE ANALYSIS
# =============================================================================

print("\n" + "=" * 120)
print("PART 2: INDEX-WISE PERFORMANCE (4 Indices)")
print("=" * 120)

print("\n" + "-" * 120)
print(f"{'Index':<15} {'Trades':<10} {'Win%':<8} {'Total PnL':<15} {'Avg/Trade':<12} {'Max DD':<12} {'Green Days':<12}")
print("-" * 120)

index_stats = []
for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
    sub = df[df['index'] == idx]
    if len(sub) == 0:
        continue
    
    trades = len(sub)
    wr = sub['won'].mean() * 100
    pnl = sub['pnl_rs'].sum()
    avg = sub['pnl_rs'].mean()
    
    # Calculate max DD for this index
    daily_pnl = sub.groupby('date')['pnl_rs'].sum()
    idx_dd = daily_pnl.cumsum().pipe(lambda x: x - x.cummax()).min()
    
    # Green days
    idx_green = (daily_pnl > 0).sum()
    idx_days = len(daily_pnl)
    
    index_stats.append({
        'index': idx,
        'trades': trades,
        'wr': wr,
        'pnl': pnl,
        'avg': avg,
        'dd': idx_dd,
        'green': idx_green,
        'days': idx_days
    })
    
    print(f"{idx:<15} {trades:<10} {wr:>6.1f}%   Rs.{pnl:>+12,.0f}   Rs.{avg:>+9,.0f}   Rs.{idx_dd:>+9,.0f}   {idx_green}/{idx_days} days")

print("-" * 120)
print(f"{'TOTAL':<15} {total_trades:<10} {win_rate:>6.1f}%   Rs.{total_pnl:>+12,.0f}   Rs.{avg_pnl:>+9,.0f}   Rs.{max_dd:>+9,.0f}   {green_days}/{total_days} days")
print("-" * 120)

# =============================================================================
# PART 3: INDEX-WISE DAILY BREAKDOWN
# =============================================================================

print("\n" + "=" * 120)
print("PART 3: INDEX-WISE DAILY PROFIT/LOSS BREAKDOWN")
print("=" * 120)

for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
    sub = df[df['index'] == idx]
    if len(sub) == 0:
        continue
    
    daily = sub.groupby('date')['pnl_rs'].sum()
    avg_daily = daily.mean()
    best_day = daily.max()
    worst_day = daily.min()
    
    print(f"\n{idx}:")
    print(f"  Average Daily PnL:  Rs.{avg_daily:+,.0f}")
    print(f"  Best Day:           Rs.{best_day:+,.0f}")
    print(f"  Worst Day:          Rs.{worst_day:+,.0f}")
    print(f"  Days Traded:        {len(daily)}/{df['date'].nunique()} ({100*len(daily)/df['date'].nunique():.0f}%)")
    
    # Top 3 days
    top3 = daily.nlargest(3)
    print(f"  Top 3 Days:         {', '.join([f'Rs.{v:+,.0f}' for v in top3.values])}")
    
    # Worst 3 days
    worst3 = daily.nsmallest(3)
    print(f"  Worst 3 Days:       {', '.join([f'Rs.{v:+,.0f}' for v in worst3.values])}")

# =============================================================================
# PART 4: STRATEGY-WISE ANALYSIS (ALL 25)
# =============================================================================

print("\n" + "=" * 120)
print("PART 4: STRATEGY-WISE PERFORMANCE (All 25 Strategies)")
print("=" * 120)

strategy_stats = []

for strat in sorted(df['strategy'].unique()):
    sub = df[df['strategy'] == strat]
    if len(sub) == 0:
        continue
    
    trades = len(sub)
    pnl = sub['pnl_rs'].sum()
    wr = sub['won'].mean() * 100
    avg = sub['pnl_rs'].mean()
    
    # Exit breakdown
    exits = sub.groupby('exit_reason')['pnl_rs'].agg(['count', 'sum'])
    main_exit = sub['exit_reason'].value_counts().index[0]
    main_exit_pct = sub['exit_reason'].value_counts().iloc[0] / trades * 100
    
    # TIME exit analysis
    time_exits = sub[sub['exit_reason'] == 'TIME']
    time_pct = len(time_exits) / trades * 100 if len(time_exits) > 0 else 0
    
    strategy_stats.append({
        'strategy': strat,
        'trades': trades,
        'pnl': pnl,
        'wr': wr,
        'avg': avg,
        'main_exit': main_exit,
        'main_exit_pct': main_exit_pct,
        'time_pct': time_pct
    })

# Sort by PnL
strategy_stats = sorted(strategy_stats, key=lambda x: x['pnl'], reverse=True)

print("\n" + "-" * 120)
print(f"{'Rank':<5} {'Strategy':<30} {'Trades':<8} {'Win%':<8} {'PnL':<15} {'Avg/Trade':<12} {'Main Exit':<12} {'Time%':<8}")
print("-" * 120)

for i, s in enumerate(strategy_stats, 1):
    status = ""
    if s['pnl'] > 10000:
        status = "[TOP]"
    elif s['pnl'] > 5000:
        status = "[GOOD]"
    elif s['pnl'] > 0:
        status = "[OK]"
    else:
        status = "[FIX]"
    
    print(f"{i:<5} {s['strategy']:<30} {s['trades']:<8} {s['wr']:>6.1f}%  Rs.{s['pnl']:>+11,.0f}  Rs.{s['avg']:>+9,.0f}  {s['main_exit']:<12} {s['time_pct']:>6.1f}% {status}")

print("-" * 120)

# =============================================================================
# PART 5: STRATEGY TIERS
# =============================================================================

print("\n" + "=" * 120)
print("PART 5: STRATEGY TIER CLASSIFICATION")
print("=" * 120)

tier1 = [s for s in strategy_stats if s['pnl'] > 10000]
tier2 = [s for s in strategy_stats if 5000 <= s['pnl'] <= 10000]
tier3 = [s for s in strategy_stats if 0 < s['pnl'] < 5000]
tier4 = [s for s in strategy_stats if s['pnl'] <= 0]

print(f"""
================================================================================
 TIER 1: EXCEPTIONAL (Rs.10K+ profit)
================================================================================
 Count: {len(tier1)} strategies
 Total Contribution: Rs.{sum(s['pnl'] for s in tier1):,.0f}
================================================================================
""")
for s in tier1:
    print(f"  - {s['strategy']}: Rs.{s['pnl']:+,.0f} ({s['wr']:.1f}% WR, {s['trades']} trades)")

print(f"""
================================================================================
 TIER 2: GOOD (Rs.5K-10K profit)
================================================================================
 Count: {len(tier2)} strategies
 Total Contribution: Rs.{sum(s['pnl'] for s in tier2):,.0f}
================================================================================
""")
for s in tier2:
    print(f"  - {s['strategy']}: Rs.{s['pnl']:+,.0f} ({s['wr']:.1f}% WR, {s['trades']} trades)")

print(f"""
================================================================================
 TIER 3: MARGINAL (Rs.0-5K profit)
================================================================================
 Count: {len(tier3)} strategies
 Total Contribution: Rs.{sum(s['pnl'] for s in tier3):,.0f}
================================================================================
""")
for s in tier3:
    print(f"  - {s['strategy']}: Rs.{s['pnl']:+,.0f} ({s['wr']:.1f}% WR, {s['trades']} trades)")

print(f"""
================================================================================
 TIER 4: NEEDS FIX (Loss-making)
================================================================================
 Count: {len(tier4)} strategies
 Total Loss: Rs.{sum(s['pnl'] for s in tier4):,.0f}
================================================================================
""")
for s in tier4:
    print(f"  - {s['strategy']}: Rs.{s['pnl']:+,.0f} ({s['wr']:.1f}% WR, {s['trades']} trades) - {s['time_pct']:.0f}% TIME exits")

# =============================================================================
# PART 6: EXIT ANALYSIS
# =============================================================================

print("\n" + "=" * 120)
print("PART 6: EXIT REASON BREAKDOWN")
print("=" * 120)

exit_stats = df.groupby('exit_reason').agg({
    'pnl_rs': ['count', 'sum', 'mean']
}).round(2)

print("\n" + "-" * 80)
print(f"{'Exit Type':<15} {'Count':<10} {'% Total':<10} {'Total PnL':<15} {'Avg PnL':<15}")
print("-" * 80)

for exit_type in df['exit_reason'].unique():
    sub = df[df['exit_reason'] == exit_type]
    count = len(sub)
    pct = count / total_trades * 100
    pnl = sub['pnl_rs'].sum()
    avg = sub['pnl_rs'].mean()
    
    print(f"{exit_type:<15} {count:<10} {pct:>8.1f}%  Rs.{pnl:>+12,.0f}  Rs.{avg:>+12,.0f}")

print("-" * 80)

# =============================================================================
# PART 7: SUMMARY
# =============================================================================

print("\n" + "=" * 120)
print("PART 7: FINAL SUMMARY & RECOMMENDATIONS")
print("=" * 120)

print("\n" + "="*80)
print("                    FINAL RESULTS - 25 STRATEGIES")
print("="*80)
print(f"  [OK] Total Trades:        {total_trades}")
print(f"  [OK] Win Rate:            {win_rate:.1f}%")
print(f"  [OK] Total Profit:        Rs.{total_pnl:,.0f}")
print(f"  [OK] Max Drawdown:        Rs.{max_dd:,.0f} ({abs(max_dd)/400000*100:.1f}% of capital)")
print(f"  [OK] Green Days:          {green_days}/{total_days} ({100*green_days/total_days:.0f}%)")
print(f"  [OK] Active Strategies:   {len(strategy_stats)}/25")
print(f"  [OK] Profitable:          {len([s for s in strategy_stats if s['pnl'] > 0])} strategies")
print("="*80)
print("                      INDEX CONTRIBUTIONS")
print("="*80)
for idx_stats in index_stats:
    print(f"  {idx_stats['index']:<12} Rs.{idx_stats['pnl']:>+10,.0f} ({idx_stats['trades']} trades)")
print("="*80)
print("                        RECOMMENDATIONS")
print("="*80)
print(f"  [GOOD] DEPLOY: All Tier 1 & 2 strategies (top {len(tier1) + len(tier2)} strategies)")
print(f"  [WARN] MONITOR: Tier 3 strategies for improvement")
print(f"  [CRIT] REVIEW: Tier 4 strategies before deploying")
print(f"  Expected Daily:    Rs.{total_pnl/total_days:.0f}")
print(f"  Expected Monthly:  Rs.{total_pnl/total_days*22:.0f} (on Rs.4L capital)")
print("="*80)

print("=" * 120)
print("END OF REPORT")
print("=" * 120)
