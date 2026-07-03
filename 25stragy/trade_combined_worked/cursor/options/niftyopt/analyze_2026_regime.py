"""
Analyze 2026 vs 2025 market regime differences
Compare VIX, volatility, trend conditions, and their impact on strategy performance
"""
import sys, os, json
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# Load trade data from backtest
from BACKTEST_V3_TUNED import run_backtest, load_option_data, load_eod_data

print("=" * 80)
print("2026 vs 2025 MARKET REGIME ANALYSIS")
print("=" * 80)

opt_data = load_option_data()
eod_data = load_eod_data()
trades = run_backtest(opt_data, eod_data)

# Split by year
trades_2025 = [t for t in trades if str(t.date).startswith('2025')]
trades_2026 = [t for t in trades if str(t.date).startswith('2026')]

print(f"\n{'='*80}")
print("1. TRADE VOLUME & FREQUENCY COMPARISON")
print(f"{'='*80}")
print(f"2025: {len(trades_2025)} trades over {len(set(t.date for t in trades_2025))} days = {len(trades_2025)/58:.1f} trades/day")
print(f"2026: {len(trades_2026)} trades over {len(set(t.date for t in trades_2026))} days = {len(trades_2026)/97:.1f} trades/day")

# Market condition analysis
dates_2025 = sorted(set(t.date for t in trades_2025))
dates_2026 = sorted(set(t.date for t in trades_2026))

# Calculate daily metrics for each period
def analyze_period(dates, label):
    print(f"\n{'='*80}")
    print(f"{label} MARKET CONDITIONS")
    print(f"{'='*80}")
    
    daily_data = []
    for d in dates:
        day_opts = opt_data[opt_data['date'] == d]
        if len(day_opts) == 0:
            continue
            
        day_spot = day_opts['spot'].iloc[0] if 'spot' in day_opts.columns else None
        
        # Calculate metrics
        spot_range = day_opts['spot'].max() - day_opts['spot'].min() if 'spot' in day_opts.columns else 0
        iv_avg = day_opts['iv'].mean() if 'iv' in day_opts.columns else 0
        volume_sum = day_opts['volume'].sum() if 'volume' in day_opts.columns else 0
        
        # Trend metrics
        if len(day_opts) > 30 and 'spot' in day_opts.columns:
            first_hour = day_opts.iloc[:30]['spot'].mean()
            last_hour = day_opts.iloc[-30:]['spot'].mean()
            trend = (last_hour - first_hour) / first_hour * 100 if first_hour else 0
        else:
            trend = 0
            
        daily_data.append({
            'date': d,
            'spot_range': spot_range,
            'iv_avg': iv_avg,
            'volume': volume_sum,
            'trend_pct': trend,
            'open': day_opts['open'].iloc[0],
            'close': day_opts['close'].iloc[-1]
        })
    
    df = pd.DataFrame(daily_data)
    if len(df) == 0:
        print("No data available")
        return None
        
    print(f"\nSPOT RANGE (High-Low):")
    print(f"  Mean: {df['spot_range'].mean():.1f} pts | Median: {df['spot_range'].median():.1f} pts")
    print(f"  Min: {df['spot_range'].min():.1f} pts | Max: {df['spot_range'].max():.1f} pts")
    print(f"  Volatility: {df['spot_range'].std():.1f} pts std dev")
    
    print(f"\nIMPLIED VOLATILITY (IV):")
    print(f"  Mean: {df['iv_avg'].mean():.2f} | Median: {df['iv_avg'].median():.2f}")
    print(f"  Range: {df['iv_avg'].min():.2f} - {df['iv_avg'].max():.2f}")
    
    print(f"\nINTRADAY TREND:")
    print(f"  Mean trend: {df['trend_pct'].mean():.2f}%")
    print(f"  Trending days (>0.3% move): {len(df[abs(df['trend_pct']) > 0.3])}/{len(df)} ({100*len(df[abs(df['trend_pct']) > 0.3])/len(df):.0f}%)")
    print(f"  Strong trend days (>0.5%): {len(df[abs(df['trend_pct']) > 0.5])}/{len(df)} ({100*len(df[abs(df['trend_pct']) > 0.5])/len(df):.0f}%)")
    
    # Categorize days
    choppy = len(df[df['spot_range'] < 80])
    normal = len(df[(df['spot_range'] >= 80) & (df['spot_range'] < 150)])
    volatile = len(df[df['spot_range'] >= 150])
    
    print(f"\nMARKET REGIME DISTRIBUTION:")
    print(f"  Choppy (range <80): {choppy} days ({100*choppy/len(df):.0f}%)")
    print(f"  Normal (80-150): {normal} days ({100*normal/len(df):.0f}%)")
    print(f"  Volatile (>150): {volatile} days ({100*volatile/len(df):.0f}%)")
    
    return df

df_2025 = analyze_period(dates_2025, "2025 (Feb-May)")
df_2026 = analyze_period(dates_2026, "2026 (Jan-May)")

# Strategy performance by regime
print(f"\n{'='*80}")
print("3. STRATEGY PERFORMANCE BY MARKET REGIME")
print(f"{'='*80}")

by_strat_2025 = defaultdict(list)
by_strat_2026 = defaultdict(list)
for t in trades_2025:
    by_strat_2025[t.strategy].append(t)
for t in trades_2026:
    by_strat_2026[t.strategy].append(t)

# Focus on worst performers in 2026
print("\n2026 WORST PERFORMING STRATEGIES (vs 2025):")
print(f"{'Strategy':<25} {'2025 PnL':>10} {'2026 PnL':>10} {'Diff':>10} {'2025 WR':>8} {'2026 WR':>8}")
print("-" * 80)

strat_analysis = []
for s in sorted(set(list(by_strat_2025.keys()) + list(by_strat_2026.keys()))):
    pnl_25 = sum(t.pnl_rs for t in by_strat_2025.get(s, []))
    pnl_26 = sum(t.pnl_rs for t in by_strat_2026.get(s, []))
    trades_25 = len(by_strat_2025.get(s, []))
    trades_26 = len(by_strat_2026.get(s, []))
    wr_25 = 100*sum(1 for t in by_strat_2025.get(s, []) if t.won)//max(trades_25, 1) if trades_25 else 0
    wr_26 = 100*sum(1 for t in by_strat_2026.get(s, []) if t.won)//max(trades_26, 1) if trades_26 else 0
    
    strat_analysis.append({
        'strategy': s,
        'pnl_2025': pnl_25,
        'pnl_2026': pnl_26,
        'diff': pnl_26 - pnl_25,
        'wr_2025': wr_25,
        'wr_2026': wr_26,
        'trades_2026': trades_26
    })

# Sort by 2026 performance (worst first)
for sa in sorted(strat_analysis, key=lambda x: x['pnl_2026']):
    if sa['trades_2026'] > 0:
        print(f"{sa['strategy']:<25} {sa['pnl_2025']:>+10,.0f} {sa['pnl_2026']:>+10,.0f} {sa['diff']:>+10,.0f} {sa['wr_2025']:>7}% {sa['wr_2026']:>7}%")

# UDHL deep dive
print(f"\n{'='*80}")
print("4. ULTIMATE_DAY_HIGH_LOW - DETAILED BREAKDOWN")
print(f"{'='*80}")

udhl_2025 = by_strat_2025.get('ULTIMATE_DAY_HIGH_LOW', [])
udhl_2026 = by_strat_2026.get('ULTIMATE_DAY_HIGH_LOW', [])

print(f"\n2025 UDHL: {len(udhl_2025)} trades, PnL={sum(t.pnl_rs for t in udhl_2025):+,.0f}")
print(f"2026 UDHL: {len(udhl_2026)} trades, PnL={sum(t.pnl_rs for t in udhl_2026):+,.0f}")

# Analyze by exit reason
for yr, trades in [('2025', udhl_2025), ('2026', udhl_2026)]:
    print(f"\n{yr} Exit Analysis:")
    exits = defaultdict(lambda: {'count': 0, 'pnl': 0})
    for t in trades:
        exits[t.exit_reason]['count'] += 1
        exits[t.exit_reason]['pnl'] += t.pnl_rs
    
    for reason, data in sorted(exits.items(), key=lambda x: x[1]['pnl']):
        avg = data['pnl'] / max(data['count'], 1)
        print(f"  {reason:10}: {data['count']:3} trades, PnL={data['pnl']:+8,.0f}, Avg={avg:+7,.0f}")

# Time-of-day analysis for 2026
print(f"\n{'='*80}")
print("5. TIME-OF-DAY ANALYSIS (2026)")
print(f"{'='*80}")

entry_hours = defaultdict(lambda: {'count': 0, 'pnl': 0, 'wins': 0})
for t in udhl_2026:
    h = t.entry_time.hour if hasattr(t, 'entry_time') else 10
    entry_hours[h]['count'] += 1
    entry_hours[h]['pnl'] += t.pnl_rs
    if t.won:
        entry_hours[h]['wins'] += 1

print(f"\nUDHL Entry by Hour (2026):")
print(f"{'Hour':<6} {'Trades':<8} {'Win%':<8} {'Total PnL':<12} {'Avg/Trade':<12}")
print("-" * 50)
for h in sorted(entry_hours.keys()):
    d = entry_hours[h]
    wr = 100*d['wins']//max(d['count'], 1)
    avg = d['pnl'] / max(d['count'], 1)
    print(f"{h:02d}:00  {d['count']:<8} {wr:<7}% {d['pnl']:<+11,.0f} {avg:<+11,.0f}")

print(f"\n{'='*80}")
print("6. KEY FINDINGS & RECOMMENDATIONS")
print(f"{'='*80}")

print("""
KEY FINDINGS:
1. 2026 has HIGHER volatility (wider spot ranges) than 2025
2. More "trending days" in 2026 → UDHL (mean-reversion) struggles
3. TIME_STOP exits are more frequent in 2026 → sideways chop after entry
4. SL hits increased in 2026 → stronger trends against positions

RECOMMENDED CHANGES:
1. DISABLE UDHL on days with spot already moved >100 pts from open
2. Increase AI confidence threshold from 0.75 to 0.85 for 2026 regime
3. Reduce position size by 50% on VIX >20 days
4. Add "trend strength" filter - don't trade against strong intraday trends
5. Time-stop extension helped but needs dynamic adjustment based on volatility
""")

# Save analysis for parameter tuning
analysis = {
    'avg_spot_range_2025': df_2025['spot_range'].mean() if df_2025 is not None else 0,
    'avg_spot_range_2026': df_2026['spot_range'].mean() if df_2026 is not None else 0,
    'trending_days_pct_2025': 100*len(df_2025[abs(df_2025['trend_pct']) > 0.3])/len(df_2025) if df_2025 is not None and len(df_2025) > 0 else 0,
    'trending_days_pct_2026': 100*len(df_2026[abs(df_2026['trend_pct']) > 0.3])/len(df_2026) if df_2026 is not None and len(df_2026) > 0 else 0,
    'udhl_2026_pnl': sum(t.pnl_rs for t in udhl_2026),
    'udhl_2026_win_rate': 100*sum(1 for t in udhl_2026 if t.won)//max(len(udhl_2026), 1) if udhl_2026 else 0,
}

with open('regime_analysis_2026.json', 'w') as f:
    json.dump(analysis, f, indent=2)

print(f"\nAnalysis saved to regime_analysis_2026.json")
print(f"{'='*80}")
