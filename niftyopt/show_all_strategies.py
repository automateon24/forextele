"""
Display ALL 21 strategies with complete performance metrics
"""
import pandas as pd
import numpy as np

df = pd.read_csv('results/BACKTEST_V3_TUNED_TRADES.csv')
summary = pd.read_csv('results/BACKTEST_V3_TUNED_SUMMARY.csv')

print("=" * 120)
print("COMPLETE 21 STRATEGY PERFORMANCE REPORT")
print("=" * 120)
print(f"Period: {df['date'].min()} to {df['date'].max()}")
print(f"Total Days: {df['date'].nunique()}")
print(f"Each Strategy Capital: ₹50,000")
print(f"Lot Size: 75 (1 lot per trade)")
print("=" * 120)

# Strategy list
all_strategies = [
    'AI_ENHANCED', 'BREAKOUT', 'DAY_HIGH_BEARISH', 'DAY_HIGH_LOW_TRADITIONAL',
    'DAY_LOW_BULLISH', 'ENHANCED_BEARISH', 'ENHANCED_BULLISH', 'GAMMA_BLAST',
    'LONG_UNWIND', 'MAGIC_SQUARE', 'MEAN_REVERSION', 'OPTIONS_GREEKS',
    'ORDER_BLOCK_REVERSAL', 'PUT_WRITER_SUPPORT', 'RESIST_BREAK', 'SCALPING',
    'SHORT_UNWIND', 'TREND_FOLLOWING', 'ULTIMATE_DAY_HIGH_LOW', 'VOLATILITY_BREAKOUT',
    'ZERO_HERO'
]

print("\n{:<30} {:>8} {:>8} {:>12} {:>12} {:>12} {:>12}".format(
    "Strategy", "Trades", "Win%", "Total P&L", "Avg Trade", "Max Profit", "Max Loss"))
print("-" * 120)

total_trades = 0
total_pnl = 0

for strat in all_strategies:
    sub = df[df['strategy'] == strat]
    if len(sub) == 0:
        print(f"{strat:<30} {0:>8} {0:>8}% {0:>12} {0:>12} {0:>12} {0:>12}")
        continue
    
    trades = len(sub)
    wins = len(sub[sub['pnl_rs'] > 0])
    win_pct = round(100 * wins / trades, 1) if trades > 0 else 0
    pnl = sub['pnl_rs'].sum()
    avg_trade = sub['pnl_rs'].mean()
    max_profit = sub['pnl_rs'].max()
    max_loss = sub['pnl_rs'].min()
    
    total_trades += trades
    total_pnl += pnl
    
    status = "✅" if pnl > 0 else "❌" if pnl < -1000 else "⚠️"
    
    print(f"{strat:<28} {status} {trades:>6} {win_pct:>6}% ₹{pnl:>10,.0f} ₹{avg_trade:>10,.0f} ₹{max_profit:>10,.0f} ₹{max_loss:>10,.0f}")

print("-" * 120)
print(f"{'TOTAL (All 21 Strategies)':<30} {total_trades:>8} {'':>8} ₹{total_pnl:>10,.0f}")
print("=" * 120)

# Profitable vs Losing
profitable = df[df['pnl_rs'] > 0]['strategy'].nunique()
losing = df[df['pnl_rs'] <= 0]['strategy'].nunique()
zero_trade = len([s for s in all_strategies if s not in df['strategy'].values])

print(f"\nSUMMARY:")
print(f"  Profitable Strategies: {profitable}")
print(f"  Losing Strategies: {losing}")
print(f"  Zero Trade Strategies: {zero_trade}")
print(f"  Total ROI: {100*total_pnl/(21*50000):.1f}% (on ₹10.5L capital across 21 strategies)")
print(f"  Daily Avg P&L: ₹{total_pnl/df['date'].nunique():,.0f}")
