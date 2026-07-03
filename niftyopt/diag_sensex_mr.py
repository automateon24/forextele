"""Quick check: what strategies fire for SENSEX and what's the WR breakdown?
Also check MEAN_REVERSION TIME exits across all non-NIFTY indices."""
import sys, pandas as pd
sys.path.insert(0, 'c:/cursor/options/niftyopt')

trades = pd.read_csv('backtest_results/v7_multiindex_trades.csv')

print('=== SENSEX trade breakdown ===')
sx = trades[trades['index']=='SENSEX']
print(sx[['date','strategy','direction','entry_price','exit_price','exit_reason','pnl_rs']].to_string())

print('\n=== MEAN_REVERSION TIME exits by index ===')
mr_time = trades[(trades['strategy']=='MEAN_REVERSION') & (trades['exit_reason']=='TIME')]
print(mr_time.groupby('index')['pnl_rs'].agg(['count','sum','mean']))

print('\n=== All TIME exits with entry_time ===')
time_exits = trades[trades['exit_reason']=='TIME'][['index','strategy','date','entry_price','exit_price','pnl_rs']]
print(time_exits.to_string())

print('\n=== MEAN_REVERSION stats by exit type ===')
mr = trades[trades['strategy']=='MEAN_REVERSION']
print(mr.groupby(['index','exit_reason'])['pnl_rs'].agg(['count','sum','mean']).to_string())
