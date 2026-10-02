import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from backtest_magical_candle_numbers import fetch_m1_data, run_magical_candles_backtest

df_m1 = fetch_m1_data(35)
res = run_magical_candles_backtest(df_m1, counting_mode='session_bars', rr_ratio=1.5)

print(f"{'DATE':<10} | {'CANDLE':<10} | {'TIME (UTC)':<10} | {'DIR':<4} | {'OUTCOME':<7} | {'PROFIT ($)'}")
print("-" * 65)
for idx, r in res.iterrows():
    pnl_str = f"+${r['pnl']:.2f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):.2f}"
    print(f"{r['date']:<10} | Candle #{r['candle_num']:<3} | {r['ref_time'][11:16]} UTC | {r['dir']:<4} | {r['outcome']:<7} | {pnl_str}")

print("-" * 65)
wins = len(res[res['outcome'] == 'WIN'])
print(f"Total: {len(res)} Trades | {wins}W / {len(res)-wins}L ({wins/len(res)*100:.1f}% WR) | Total PnL: +${res['pnl'].sum():.2f}")
