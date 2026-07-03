#!/usr/bin/env python3
import pandas as pd

df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print("="*60)
print("OPTION A ANALYSIS - Exit Breakdown by Index")
print("="*60)

for idx in df['index'].unique():
    sub = df[df['index'] == idx]
    print(f"\n{idx}:")
    print("-" * 40)
    exit_counts = sub['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        sub_exit = sub[sub['exit_reason'] == reason]
        avg_pnl = sub_exit['pnl_rs'].mean()
        total_pnl = sub_exit['pnl_rs'].sum()
        print(f"  {reason:12s}: {count:3d} trades | Avg: ₹{avg_pnl:+7.0f} | Total: ₹{total_pnl:+8.0f}")
    
    print(f"\n  Overall {idx}: {len(sub)} trades | Avg: ₹{sub['pnl_rs'].mean():+.0f} | Total: ₹{sub['pnl_rs'].sum():+,.0f}")
    print(f"  Win Rate: {100*sub['won'].mean():.0f}%")

print("\n" + "="*60)
print("COMPARISON: TSL vs TIME Exits")
print("="*60)

for idx in df['index'].unique():
    sub = df[df['index'] == idx]
    tsl = sub[sub['exit_reason'] == 'TSL']
    time = sub[sub['exit_reason'] == 'TIME']
    
    print(f"\n{idx}:")
    if len(tsl) > 0:
        print(f"  TSL exits:  {len(tsl):3d} | Avg: ₹{tsl['pnl_rs'].mean():+7.0f} | Total: ₹{tsl['pnl_rs'].sum():+8.0f}")
    if len(time) > 0:
        print(f"  TIME exits: {len(time):3d} | Avg: ₹{time['pnl_rs'].mean():+7.0f} | Total: ₹{time['pnl_rs'].sum():+8.0f}")
