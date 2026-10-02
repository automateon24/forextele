"""
True Institutional SMC (ICT) Engine Backtest on GOLD (Sep 2026):
1. Liquidity Sweeps: Asian High/Low, Previous Day High/Low, 20-bar Swing High/Low
2. Displacement & Market Structure Shift (MSS)
3. Order Block (OB) Detection (last opposing candle before displacement)
4. Fair Value Gap (FVG) creation & 50% mitigation retest
5. Entry at OB/FVG mitigation with tight SL behind OB
6. Management: Partial TP1 (+2R) -> Move SL to BE -> Runner to TP2 (+4R to +5R)
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(r"C:\anlyzeforex\forextele\scratch")
df_m5 = pd.read_parquet(BASE / "gold_m5_sep2026.parquet")
df_h1 = pd.read_parquet(BASE / "gold_h1_sep2026.parquet")

for df in [df_m5, df_h1]:
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

def get_macro_h1_trend(ts):
    past = df_h1[df_h1.index < ts].tail(100)
    if len(past) < 50: return "NEUTRAL"
    c = past['close']
    ema50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = c.ewm(span=200, adjust=False).mean().iloc[-1]
    curr = c.iloc[-1]
    if curr > ema50 > ema200: return "BULLISH"
    elif curr < ema50 < ema200: return "BEARISH"
    return "NEUTRAL"

# True Institutional SMC Engine
def run_true_smc_backtest():
    trades = []
    all_days = sorted(set(df_m5.index.date))

    # Active Order Blocks & FVGs waiting for mitigation
    active_bull_obs = [] # {'entry': ob_high, 'sl': ob_low, 'tp1': ..., 'tp2': ..., 'created_ts': ...}
    active_bear_obs = []

    for day in all_days:
        day_m5 = df_m5[df_m5.index.date == day]
        if len(day_m5) < 30: continue

        # Identify Asian Session Range (00:00 to 06:00 UTC)
        asian_bars = day_m5[(day_m5.index.hour >= 0) & (day_m5.index.hour < 6)]
        ash = asian_bars['high'].max() if len(asian_bars) else None
        asl = asian_bars['low'].min() if len(asian_bars) else None

        # London & NY sessions: 07:00 to 18:00 UTC
        trading_bars = day_m5[(day_m5.index.hour >= 7) & (day_m5.index.hour < 18)]

        for i in range(25, len(trading_bars) - 5):
            curr_bar = trading_bars.iloc[i]
            ts = trading_bars.index[i]
            macro_trend = get_macro_h1_trend(ts)

            # ATR for buffer
            window = trading_bars.iloc[i-20:i]
            tr = np.maximum(window['high'] - window['low'],
                            np.maximum(abs(window['high'] - window['close'].shift(1)),
                                       abs(window['low'] - window['close'].shift(1))))
            atr = float(tr.tail(14).mean())

            # ── 1. CHECK MITIGATION OF EXISTING ORDER BLOCKS ──
            # Bullish OB Mitigation: price dips into OB zone [ob_low, ob_high]
            for ob in list(active_bull_obs):
                if (ts - ob['created_ts']).total_seconds() > 4 * 3600: # Expire after 4 hours
                    active_bull_obs.remove(ob)
                    continue
                # If current bar touches the OB entry level
                if curr_bar['low'] <= ob['entry'] and curr_bar['high'] >= ob['entry']:
                    # Trigger trade entry!
                    entry_p = ob['entry']
                    sl_p = ob['sl']
                    risk = entry_p - sl_p
                    if risk > 0.80 and risk < 4.0: # Valid institutional risk
                        tp1 = entry_p + (risk * 2.0)
                        tp2 = entry_p + (risk * 4.0)

                        # Simulate future
                        future = trading_bars.iloc[i+1:i+35]
                        outcome = "OPEN"
                        be_active = False
                        curr_sl = sl_p
                        pnl_pts = 0.0

                        for fb in future.itertuples():
                            if not be_active and fb.high >= tp1:
                                be_active = True
                                curr_sl = entry_p + 0.20 # Breakeven+ locked

                            if fb.low <= curr_sl:
                                if be_active:
                                    outcome = "BE_WIN"
                                    pnl_pts = (risk * 2.0 * 0.5) + (0.20 * 0.5) # 50% TP1 taken + 50% BE
                                else:
                                    outcome = "LOSS"
                                    pnl_pts = -risk
                                break

                            if fb.high >= tp2:
                                outcome = "FULL_WIN"
                                pnl_pts = (risk * 2.0 * 0.5) + (risk * 4.0 * 0.5) # 50% TP1 + 50% TP2
                                break

                        if outcome == "OPEN" and len(future):
                            last_c = future.iloc[-1]['close']
                            pnl_pts = (last_c - entry_p)
                            outcome = "TIMEOUT"

                        trades.append({
                            "day": str(day), "ts": str(ts), "type": "BULLISH_OB_MITIGATION",
                            "direction": "BUY", "risk": risk, "outcome": outcome, "pnl_pts": pnl_pts
                        })
                        active_bull_obs.remove(ob)
                        break

            # Bearish OB Mitigation: price rises into OB zone [ob_low, ob_high]
            for ob in list(active_bear_obs):
                if (ts - ob['created_ts']).total_seconds() > 4 * 3600:
                    active_bear_obs.remove(ob)
                    continue
                if curr_bar['high'] >= ob['entry'] and curr_bar['low'] <= ob['entry']:
                    entry_p = ob['entry']
                    sl_p = ob['sl']
                    risk = sl_p - entry_p
                    if risk > 0.80 and risk < 4.0:
                        tp1 = entry_p - (risk * 2.0)
                        tp2 = entry_p - (risk * 4.0)

                        future = trading_bars.iloc[i+1:i+35]
                        outcome = "OPEN"
                        be_active = False
                        curr_sl = sl_p
                        pnl_pts = 0.0

                        for fb in future.itertuples():
                            if not be_active and fb.low <= tp1:
                                be_active = True
                                curr_sl = entry_p - 0.20

                            if fb.high >= curr_sl:
                                if be_active:
                                    outcome = "BE_WIN"
                                    pnl_pts = (risk * 2.0 * 0.5) + (0.20 * 0.5)
                                else:
                                    outcome = "LOSS"
                                    pnl_pts = -risk
                                break

                            if fb.low <= tp2:
                                outcome = "FULL_WIN"
                                pnl_pts = (risk * 2.0 * 0.5) + (risk * 4.0 * 0.5)
                                break

                        if outcome == "OPEN" and len(future):
                            last_c = future.iloc[-1]['close']
                            pnl_pts = (entry_p - last_c)
                            outcome = "TIMEOUT"

                        trades.append({
                            "day": str(day), "ts": str(ts), "type": "BEARISH_OB_MITIGATION",
                            "direction": "SELL", "risk": risk, "outcome": outcome, "pnl_pts": pnl_pts
                        })
                        active_bear_obs.remove(ob)
                        break

            # ── 2. DETECT NEW LIQUIDITY SWEEP + DISPLACEMENT + ORDER BLOCK CREATION ──
            # Swing High/Low over past 20 bars
            prev_swing_high = window['high'].iloc[:-3].max()
            prev_swing_low  = window['low'].iloc[:-3].min()

            # Check 1: Bullish Liquidity Sweep & Displacement
            # Did price sweep Asian Low (ASL) or Swing Low, followed by strong bullish displacement?
            sweep_bear_liquidity = (window['low'].iloc[-4:-1].min() < prev_swing_low) or (asl and window['low'].iloc[-4:-1].min() < asl)
            # Bullish displacement: large green candle closing above previous swing with FVG
            c_curr = curr_bar['close']; o_curr = curr_bar['open']
            is_bull_displacement = (c_curr - o_curr) > (atr * 1.0) and curr_bar['low'] > trading_bars['high'].iloc[i-2]
            
            if sweep_bear_liquidity and is_bull_displacement and macro_trend in ("BULLISH", "NEUTRAL"):
                # Find the Order Block: the last bearish candle before this displacement
                for b_idx in range(i-1, max(i-6, 0), -1):
                    cand = trading_bars.iloc[b_idx]
                    if cand['close'] < cand['open']: # Bearish candle
                        ob_high = cand['high']
                        ob_low = min(cand['low'], curr_bar['low'] - 0.20)
                        active_bull_obs.append({
                            'entry': ob_high, # Entry at the top of the Order Block
                            'sl': ob_low - 0.30, # SL below OB low
                            'created_ts': ts
                        })
                        break

            # Check 2: Bearish Liquidity Sweep & Displacement
            sweep_bull_liquidity = (window['high'].iloc[-4:-1].max() > prev_swing_high) or (ash and window['high'].iloc[-4:-1].max() > ash)
            is_bear_displacement = (o_curr - c_curr) > (atr * 1.0) and curr_bar['high'] < trading_bars['low'].iloc[i-2]

            if sweep_bull_liquidity and is_bear_displacement and macro_trend in ("BEARISH", "NEUTRAL"):
                for b_idx in range(i-1, max(i-6, 0), -1):
                    cand = trading_bars.iloc[b_idx]
                    if cand['close'] > cand['open']: # Bullish candle
                        ob_high = max(cand['high'], curr_bar['high'] + 0.20)
                        ob_low = cand['low']
                        active_bear_obs.append({
                            'entry': ob_low,
                            'sl': ob_high + 0.30,
                            'created_ts': ts
                        })
                        break

    return pd.DataFrame(trades)

df_smc = run_true_smc_backtest()
print(f"Total True SMC Trades: {len(df_smc)}")
if not df_smc.empty:
    wins = df_smc[df_smc['outcome'].isin(['FULL_WIN', 'BE_WIN'])]
    losses = df_smc[df_smc['outcome'] == 'LOSS']
    wr = len(wins) / len(df_smc) * 100
    pnl_pts = df_smc['pnl_pts'].sum()
    print(f"Wins: {len(wins)} | Losses: {len(losses)} | Win Rate: {wr:.1f}%")
    print(f"Total PnL Points: {pnl_pts:.2f}")
    # Scaled to $1,000 SMC Capital at 0.03 lot ($3/pt)
    usd = pnl_pts * 0.03 * 100
    print(f"Net PnL (at 0.03 lot): ${usd:,.2f} USD (+{(usd/1000.0)*100:.1f}% ROI)")
    print("\nTrades breakdown by type:")
    print(df_smc['type'].value_counts())
    print("\nTrades breakdown by outcome:")
    print(df_smc['outcome'].value_counts())
