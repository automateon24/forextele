"""
Replay ULTIMATE_DAY_HIGH_LOW against real 2026 spot data
using your EXACT manual trading rules:
  CE: spot touches running day low + next candle is green → Buy
  PE: spot touches running day high + next candle is red  → Sell
  SL:     low - 20pts (for CE) | high + 20pts (for PE)
  Target: day high (for CE)    | day low (for PE)
  Re-entry: allowed after SL hit if setup re-forms
  Filter:   only entries 10:00 - 14:30
"""
import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd
import numpy as np

LOT = 75          # NIFTY lot size
SL_BUFFER = 20    # 20 pts from day low/high
PROXIMITY_PCT = 0.0015   # within 0.15% of day extreme to consider "touching"
START_HHMM = 1000
END_HHMM   = 1430

spot_df = pd.read_parquet(r'c:\cursor\options\niftyopt\data\nifty_spot_2026_manual_dates.parquet')

# Normalize columns
spot_df.columns = [c.lower() for c in spot_df.columns]
spot_df['ts'] = pd.to_datetime(spot_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
spot_df['date_str'] = spot_df['ts'].dt.strftime('%Y-%m-%d')
spot_df['hhmm'] = spot_df['ts'].dt.hour * 100 + spot_df['ts'].dt.minute
spot_df = spot_df.sort_values('ts').reset_index(drop=True)

# Manual trades for comparison
MANUAL = {
    '2026-04-30': [{'dir':'CE','entry':23820,'sl':23779,'exit':24019,'pnl':12935}],
    '2026-05-04': [{'dir':'PE','entry':24232,'sl':24262,'exit':24061,'pnl':11115}],
    '2026-05-05': [{'dir':'CE','entry':23952,'sl':23893,'exit':23893,'pnl':-3835},
                   {'dir':'CE','entry':23919,'sl':23862,'exit':24072,'pnl':9945}],
    '2026-05-06': [{'dir':'CE','entry':24098,'sl':24053,'exit':24053,'pnl':-2925},
                   {'dir':'CE','entry':24038,'sl':23977,'exit':24250,'pnl':13780}],
    '2026-05-07': [{'dir':'CE','entry':24305,'sl':24264,'exit':24423,'pnl':7670}],
    '2026-05-08': [{'dir':'CE','entry':24148,'sl':24106,'exit':24215,'pnl':4355}],
    '2026-05-11': [{'dir':'CE','entry':23871,'sl':23825,'exit':23986,'pnl':7475},
                   {'dir':'PE','entry':23966,'sl':24017,'exit':23845,'pnl':7865}],
    '2026-05-12': [{'dir':'CE','entry':23628,'sl':23576,'exit':23576,'pnl':-3380}],
    '2026-05-13': [{'dir':'PE','entry':23481,'sl':23529,'exit':23529,'pnl':-3120}],
    '2026-05-14': [{'dir':'CE','entry':23473,'sl':23406,'exit':23589,'pnl':7540}],
}

def simulate_day(day_df, date_str, verbose=True):
    """Simulate the day-high/low touch strategy."""
    trades = []
    day_df = day_df[day_df['hhmm'] >= 915].copy().reset_index(drop=True)
    if len(day_df) < 10:
        return trades

    open_price = float(day_df.iloc[0]['open'])
    in_trade = False
    trade_dir = None
    entry_price = sl_price = target_price = None

    for i in range(1, len(day_df)):
        bar = day_df.iloc[i]
        prev = day_df.iloc[i-1]
        hhmm = int(bar['hhmm'])

        # Running day high/low (up to but NOT including current bar — no look-ahead)
        day_high = float(day_df.iloc[:i]['high'].max())
        day_low  = float(day_df.iloc[:i]['low'].min())

        # If in trade, check exit conditions
        if in_trade:
            lo, hi = float(bar['low']), float(bar['high'])
            if trade_dir == 'CE':
                if lo <= sl_price:
                    pnl = (sl_price - entry_price) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'CE',
                                   'entry': entry_price, 'exit': sl_price,
                                   'reason': 'SL', 'pnl_spot': pnl})
                    in_trade = False
                elif hi >= target_price:
                    pnl = (target_price - entry_price) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'CE',
                                   'entry': entry_price, 'exit': target_price,
                                   'reason': 'TARGET', 'pnl_spot': pnl})
                    in_trade = False
                elif hhmm >= 1520:
                    cl = float(bar['close'])
                    pnl = (cl - entry_price) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'CE',
                                   'entry': entry_price, 'exit': cl,
                                   'reason': 'EOD', 'pnl_spot': pnl})
                    in_trade = False
            else:  # PE
                if hi >= sl_price:
                    pnl = (entry_price - sl_price) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'PE',
                                   'entry': entry_price, 'exit': sl_price,
                                   'reason': 'SL', 'pnl_spot': pnl})
                    in_trade = False
                elif lo <= target_price:
                    pnl = (entry_price - target_price) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'PE',
                                   'entry': entry_price, 'exit': target_price,
                                   'reason': 'TARGET', 'pnl_spot': pnl})
                    in_trade = False
                elif hhmm >= 1520:
                    cl = float(bar['close'])
                    pnl = (entry_price - cl) * LOT
                    trades.append({'time': bar['ts'].strftime('%H:%M'), 'dir': 'PE',
                                   'entry': entry_price, 'exit': cl,
                                   'reason': 'EOD', 'pnl_spot': pnl})
                    in_trade = False
            continue  # Don't enter new trade while in one

        if not START_HHMM <= hhmm <= END_HHMM:
            continue

        cl_prev  = float(prev['close'])
        op_prev  = float(prev['open'])
        cl_curr  = float(bar['close'])
        lo_prev  = float(prev['low'])
        hi_prev  = float(prev['high'])
        lo_curr  = float(bar['low'])
        hi_curr  = float(bar['high'])

        prev_green = cl_prev > op_prev
        prev_red   = cl_prev < op_prev
        curr_green = cl_curr > float(bar['open'])
        curr_red   = cl_curr < float(bar['open'])

        # CE signal: previous bar touched/breached day low + current bar green (confirmation)
        touched_low  = lo_prev <= day_low * (1 + PROXIMITY_PCT)
        # PE signal: previous bar touched/reached day high + current bar red
        touched_high = hi_prev >= day_high * (1 - PROXIMITY_PCT)

        if touched_low and curr_green:
            # CE entry at close of confirmation candle
            entry_price  = cl_curr
            sl_price     = day_low - SL_BUFFER
            target_price = day_high
            in_trade = True
            trade_dir = 'CE'

        elif touched_high and curr_red:
            # PE entry at close of red candle confirming day high rejection
            entry_price  = cl_curr
            sl_price     = day_high + SL_BUFFER
            target_price = day_low
            in_trade = True
            trade_dir = 'PE'

    # Force close any open trade at end of day
    if in_trade:
        last = day_df.iloc[-1]
        cl = float(last['close'])
        if trade_dir == 'CE':
            pnl = (cl - entry_price) * LOT
        else:
            pnl = (entry_price - cl) * LOT
        trades.append({'time': last['ts'].strftime('%H:%M'), 'dir': trade_dir,
                       'entry': entry_price, 'exit': cl,
                       'reason': 'EOD', 'pnl_spot': pnl})

    return trades

print("="*80)
print("REPLAYING YOUR MANUAL STRATEGY ON REAL 2026 DATA")
print("="*80)
print(f"Rules: Touch day low/high + 1-candle confirmation + SL=extreme±20pts + Target=opposite extreme")
print()

total_sim = 0
total_manual = sum(t['pnl'] for ts in MANUAL.values() for t in ts)

for date_str in sorted(spot_df['date_str'].unique()):
    day_df = spot_df[spot_df['date_str'] == date_str]
    sim_trades = simulate_day(day_df, date_str)
    day_sim_pnl = sum(t['pnl_spot'] for t in sim_trades)
    total_sim += day_sim_pnl

    manual_trades = MANUAL.get(date_str, [])
    day_manual_pnl = sum(t['pnl'] for t in manual_trades)

    print(f"\n{'='*60}")
    print(f"DATE: {date_str}")
    day_data = spot_df[spot_df['date_str'] == date_str]
    day_high_actual = float(day_data['high'].max())
    day_low_actual  = float(day_data['low'].min())
    print(f"Day High: {day_high_actual:.0f} | Day Low: {day_low_actual:.0f} | Range: {day_high_actual-day_low_actual:.0f}pts")

    print(f"\n  SIMULATED ({len(sim_trades)} trades, PnL={day_sim_pnl:+,.0f}):")
    for t in sim_trades:
        print(f"    {t['time']} {t['dir']} entry={t['entry']:.0f} exit={t['exit']:.0f} [{t['reason']}] PnL={t['pnl_spot']:+,.0f}")
    if not sim_trades:
        print("    -- no signals fired --")

    print(f"\n  MANUAL    ({len(manual_trades)} trades, PnL={day_manual_pnl:+,.0f}):")
    for t in manual_trades:
        print(f"    {t['dir']} entry={t['entry']:.0f} exit={t['exit']:.0f} PnL={t['pnl']:+,.0f}")

print(f"\n{'='*80}")
print(f"TOTAL SIMULATED PnL: Rs {total_sim:+,.0f}")
print(f"TOTAL MANUAL PnL:    Rs {total_manual:+,.0f}")
print(f"Gap: Rs {total_sim - total_manual:+,.0f}")
print()
print("KEY DIFFERENCES between simulation and your manual trades:")
print("  1. SL in simulation uses spot points (day_low - 20pts)")
print("  2. In your real trades, option premium SL would be different")
print("  3. Options premium appreciation ≈ delta * spot_move")
print("  4. Your PnL includes option premium leverage, not spot P&L")
