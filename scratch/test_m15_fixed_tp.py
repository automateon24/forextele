import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

mt5.initialize()
now = datetime.now(timezone.utc)
from_date = now - timedelta(days=35)
rates = mt5.copy_rates_range('GOLD', mt5.TIMEFRAME_M1, from_date, now)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time_utc', inplace=True)
df.sort_index(inplace=True)

dates = np.unique(df.index.date)

print("=== TESTING M15 WITH STRUCTURE SL AND FIXED TP TARGETS ===")
for tp_target in [3.0, 5.0, 7.0, 10.0, 15.0]:
    for sl_dist in [2.5, 3.5, 5.0]:
        trades = []
        for d in dates:
            day_df = df[df.index.date == d]
            if len(day_df) < 60:
                continue
            asian_start = day_df.index[0]
            if asian_start.hour > 3:
                continue
            ref = day_df[(day_df.index >= asian_start) & (day_df.index < asian_start + timedelta(minutes=15))]
            if len(ref) < 15:
                continue
            ref_high = ref['high'].max()
            ref_low = ref['low'].min()
            ref_size = ref_high - ref_low
            
            post = day_df[(day_df.index >= asian_start + timedelta(minutes=15)) & (day_df.index <= asian_start + timedelta(hours=6))]
            
            broken_bull = False
            broken_bear = False
            in_trade = False
            trade_dir = None
            entry_p = 0.0
            sl_p = 0.0
            tp_p = 0.0
            
            for t, row in post.iterrows():
                ch, cl, cc = row['high'], row['low'], row['close']
                if not in_trade:
                    if not broken_bull and not broken_bear:
                        if ch > ref_high + 0.25:
                            broken_bull = True
                        elif cl < ref_low - 0.25:
                            broken_bear = True
                    elif broken_bull:
                        if cl <= ref_high + 0.25 and ch >= ref_high - 0.25:
                            in_trade = True
                            trade_dir = 'BUY'
                            entry_p = ref_high + 0.25
                            sl_p = entry_p - sl_dist
                            tp_p = entry_p + tp_target
                            continue
                        elif cl <= ref_low:
                            break
                    elif broken_bear:
                        if ch >= ref_low - 0.25 and cl <= ref_low + 0.25:
                            in_trade = True
                            trade_dir = 'SELL'
                            entry_p = ref_low - 0.25
                            sl_p = entry_p + sl_dist
                            tp_p = entry_p - tp_target
                            continue
                        elif ch >= ref_high:
                            break
                else:
                    if trade_dir == 'BUY':
                        if cl <= sl_p:
                            trades.append({'res': 'LOSS', 'pnl': -(entry_p - sl_p)})
                            break
                        elif ch >= tp_p:
                            trades.append({'res': 'WIN', 'pnl': tp_target})
                            break
                    elif trade_dir == 'SELL':
                        if ch >= sl_p:
                            trades.append({'res': 'LOSS', 'pnl': -(sl_p - entry_p)})
                            break
                        elif cl <= tp_p:
                            trades.append({'res': 'WIN', 'pnl': tp_target})
                            break
                            
        wins = sum(1 for tr in trades if tr['res'] == 'WIN')
        losses = sum(1 for tr in trades if tr['res'] == 'LOSS')
        total = len(trades)
        if total > 0:
            pnl_dollars = sum(tr['pnl'] * 2.0 for tr in trades)
            wr = (wins / total) * 100
            gp = sum(tr['pnl'] * 2.0 for tr in trades if tr['pnl'] > 0)
            gl = abs(sum(tr['pnl'] * 2.0 for tr in trades if tr['pnl'] < 0))
            pf = round(gp / gl, 2) if gl > 0 else 0
            if pnl_dollars > 0:
                print(f"M15 -> SL: {sl_dist:.1f} pts | TP: {tp_target:.1f} pts | Trades: {total} | Wins: {wins} | Loss: {losses} | WR: {wr:.1f}% | Net PnL: +{pnl_dollars:.2f} USD | PF: {pf}")
