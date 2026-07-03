import sys
sys.path.insert(0, r'c:\cursor\options\niftyopt')

import pandas as pd

try:
    df = pd.read_csv('backtest_results/v7_multiindex_trades.csv')
    
    with open('analysis_result.txt', 'w') as f:
        f.write('=== CURRENT BACKTEST DATA ===\n\n')
        f.write(f'Total Trades: {len(df)}\n')
        f.write(f'Total PnL: Rs.{df.pnl_rs.sum():,.0f}\n')
        f.write(f'Win Rate: {df.won.sum()/len(df)*100:.1f}%\n')
        f.write(f'Avg per trade: Rs.{df.pnl_rs.mean():.0f}\n')
        f.write(f'Lots: {df.lots.mean():.1f}\n\n')
        
        # Per-index breakdown
        f.write('--- PER INDEX ---\n')
        for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
            idx_df = df[df['index'] == idx]
            if len(idx_df) > 0:
                f.write(f'{idx}: {len(idx_df)} trades, Rs.{idx_df.pnl_rs.sum():,.0f}\n')
        
        # Daily analysis
        daily = df.groupby('date')['pnl_rs'].sum()
        f.write(f'\n--- DAILY ---\n')
        f.write(f'Best Day: Rs.{daily.max():,.0f} ({daily.max()/500000*100:.1f}%)\n')
        f.write(f'Avg Day: Rs.{daily.mean():.0f}\n')
        f.write(f'Days >=Rs.40K: {(daily >= 40000).sum()}/{len(daily)}\n')
        f.write(f'Days >=Rs.75K: {(daily >= 75000).sum()}/{len(daily)}\n')
        
    print("Analysis complete - see analysis_result.txt")
    
except Exception as e:
    with open('analysis_error.txt', 'w') as f:
        f.write(f'ERROR: {e}\n')
        import traceback
        f.write(traceback.format_exc())
    print(f"Error: {e}")
