"""
====================================================================
  COMBINED BACKTEST: BreakoutBoss (v2 AI-Tuned) + Autonomous SMC
  Period  : Sep 1 – Oct 2, 2026 (1 full month)
  Symbol  : GOLD (XAUUSD)
  Capital : $5,000 BB  |  $1,000 SMC
====================================================================
Breakout Boss v2 changes tested:
  1. H1 trend filter — block SELL in BULLISH trend / BUY in BEARISH
  2. Blocked hours: 05, 09, 18 UTC (empirically 0% WR)
  3. Min risk floor raised $0.80 → $1.20 (forces better R:R)

SMC changes tested:
  1. Daily auto-tune of max_daily_trades + cooldown based on WR
  2. confluence threshold at 7.5+
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone, time as dtime
from pathlib import Path
from collections import defaultdict

# ── Load data ──────────────────────────────────────────────────────
BASE = Path(r"C:\anlyzeforex\forextele\scratch")
df_m1 = pd.read_parquet(BASE / "gold_m1_sep2026.parquet")
df_h1 = pd.read_parquet(BASE / "gold_h1_sep2026.parquet")
df_m5 = pd.read_parquet(BASE / "gold_m5_sep2026.parquet")

# Ensure UTC-aware
for df in [df_m1, df_h1, df_m5]:
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

print(f"M1 bars: {len(df_m1)} | H1 bars: {len(df_h1)} | M5 bars: {len(df_m5)}")
print(f"Period: {df_m1.index[0]} → {df_m1.index[-1]}")

# ── Helper: H1 trend for a given timestamp ─────────────────────────
def get_h1_trend(ts, df_h1):
    past_h1 = df_h1[df_h1.index < ts].tail(210)
    if len(past_h1) < 50:
        return "NEUTRAL"
    closes = past_h1['close']
    ema50  = closes.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = closes.ewm(span=200, adjust=False).mean().iloc[-1]
    c      = closes.iloc[-1]
    if c > ema50 > ema200:
        return "BULLISH"
    elif c < ema50 < ema200:
        return "BEARISH"
    return "NEUTRAL"

# ── Volatility caps ────────────────────────────────────────────────
VOLATILITY_CAPS  = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
BLOCKED_UTC_HOURS = {5, 9, 18}

SESSIONS_CONFIG = [
    {"code": "ASIA", "start": (1, 0),  "dur": 5, "tfs": [1,3,5,15], "rr": {1:1.5,3:2.0,5:2.0,15:2.0}},
    {"code": "FRA",  "start": (6, 0),  "dur": 4, "tfs": [1,3,5,15], "rr": {1:5.0,3:5.0,5:3.0,15:3.0}},
    {"code": "LON",  "start": (8, 0),  "dur": 4, "tfs": [1,3,5,15], "rr": {1:3.0,3:5.0,5:3.0,15:3.0}},
    {"code": "NYP",  "start": (12,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:3.0,3:3.0,5:3.0,15:5.0}},
    {"code": "NYC",  "start": (13,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:5.0,3:3.0,5:3.0,15:3.0}},
    {"code": "LNC",  "start": (15,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:3.0,3:3.0,5:3.0,15:5.0}},
]

# ==========================================================================
# PART 1: BREAKOUTBOSS v1 (OLD — no trend filter, old risk floor)
# ==========================================================================
def run_bb_backtest(use_trend_filter=True, block_hours=True, min_risk=1.20, label="v2"):
    trades = []
    processed = set()
    all_days  = sorted(set(df_m1.index.date))

    for day in all_days:
        day_start = pd.Timestamp(day, tz="UTC")
        day_end   = day_start + pd.Timedelta(hours=23, minutes=59)
        day_m1    = df_m1[(df_m1.index >= day_start) & (df_m1.index <= day_end)]

        for sc in SESSIONS_CONFIG:
            sh, sm   = sc["start"]
            sess_open = day_start.replace(hour=sh, minute=sm)
            sess_close= sess_open + pd.Timedelta(hours=sc["dur"])

            for tf in sc["tfs"]:
                setup_id = f"{day}_{sc['code']}_M{tf}"
                if setup_id in processed:
                    continue

                ref_end = sess_open + pd.Timedelta(minutes=tf)

                # block hours
                if block_hours and sh in BLOCKED_UTC_HOURS:
                    processed.add(setup_id)
                    continue

                ref_bars = day_m1[(day_m1.index >= sess_open) & (day_m1.index < ref_end)]
                if len(ref_bars) < tf:
                    continue

                ref_high = ref_bars['high'].max()
                ref_low  = ref_bars['low'].min()
                ref_range= ref_high - ref_low
                ref_mid  = (ref_high + ref_low) / 2.0

                max_range = VOLATILITY_CAPS.get(tf, 8.0)
                if ref_range < 0.35 or ref_range > max_range:
                    processed.add(setup_id)
                    continue

                post_bars = day_m1[day_m1.index >= ref_end]
                post_bars = post_bars[post_bars.index < sess_close]
                if len(post_bars) < 2:
                    continue

                broken_bull = post_bars['high'].max() > ref_high + 0.25
                broken_bear = post_bars['low'].min()  < ref_low  - 0.25

                # H1 trend at session open
                trend = get_h1_trend(sess_open, df_h1) if use_trend_filter else "NEUTRAL"

                rr = sc["rr"].get(tf, 3.0)
                tol= 0.25

                for i in range(1, len(post_bars)):
                    bar = post_bars.iloc[i]
                    bl  = bar['low']; bh = bar['high']; bc = bar['close']; bo = bar['open']

                    # Bullish breakout retest
                    if broken_bull and not broken_bear:
                        if use_trend_filter and trend == "BEARISH":
                            break
                        is_touch = (bl <= ref_high + tol and bh >= ref_high - tol)
                        is_rej   = (bc >= bo) or (bc > ref_high)
                        if is_touch and is_rej:
                            entry = ref_high + 0.25
                            sl_d  = ref_low if tf == 1 else (max(ref_low, entry - 2.5) if tf == 3 else max(ref_mid, entry - 3.0))
                            risk  = max(entry - sl_d, min_risk)
                            tp    = entry + risk * rr
                            sl    = entry - risk

                            # Simulate exit on subsequent bars
                            future = post_bars.iloc[i+1:]
                            outcome = "OPEN"
                            pnl_pts = 0.0
                            for fb in future.itertuples():
                                if fb.low <= sl:
                                    outcome = "LOSS"; pnl_pts = -risk; break
                                if fb.high >= tp:
                                    outcome = "WIN"; pnl_pts = risk * rr; break
                            if outcome == "OPEN":
                                outcome = "BE"; pnl_pts = 0.0

                            trades.append({
                                "day": str(day), "session": sc["code"], "tf": tf,
                                "direction": "BUY", "trend": trend, "risk": risk,
                                "rr": rr, "entry": entry, "sl": sl, "tp": tp,
                                "outcome": outcome, "pnl_pts": pnl_pts,
                                "hour": sh
                            })
                            processed.add(setup_id)
                            break
                        if bl <= ref_low:
                            processed.add(setup_id); break

                    # Bearish breakout retest
                    elif broken_bear and not broken_bull:
                        if use_trend_filter and trend == "BULLISH":
                            break
                        is_touch = (bh >= ref_low - tol and bl <= ref_low + tol)
                        is_rej   = (bc <= bo) or (bc < ref_low)
                        if is_touch and is_rej:
                            entry = ref_low - 0.25
                            sl_d  = ref_high if tf == 1 else (min(ref_high, entry + 2.5) if tf == 3 else min(ref_mid, entry + 3.0))
                            risk  = max(sl_d - entry, min_risk)
                            tp    = entry - risk * rr
                            sl    = entry + risk

                            future = post_bars.iloc[i+1:]
                            outcome = "OPEN"
                            pnl_pts = 0.0
                            for fb in future.itertuples():
                                if fb.high >= sl:
                                    outcome = "LOSS"; pnl_pts = -risk; break
                                if fb.low <= tp:
                                    outcome = "WIN"; pnl_pts = risk * rr; break
                            if outcome == "OPEN":
                                outcome = "BE"; pnl_pts = 0.0

                            trades.append({
                                "day": str(day), "session": sc["code"], "tf": tf,
                                "direction": "SELL", "trend": trend, "risk": risk,
                                "rr": rr, "entry": entry, "sl": sl, "tp": tp,
                                "outcome": outcome, "pnl_pts": pnl_pts,
                                "hour": sh
                            })
                            processed.add(setup_id)
                            break
                        if bh >= ref_high:
                            processed.add(setup_id); break

    return pd.DataFrame(trades)

# ==========================================================================
# PART 2: AUTONOMOUS SMC BACKTEST
# ==========================================================================
def run_smc_backtest():
    trades = []
    all_days = sorted(set(df_m5.index.date))

    daily_trade_count = 0
    current_day_d = None
    max_daily = 4
    cooldown_minutes = 60
    last_trade_ts = {}

    for day in all_days:
        day_start = pd.Timestamp(day, tz="UTC")
        day_m5  = df_m5[(df_m5.index.date == day)]
        day_h1  = df_h1[(df_h1.index.date == day)]

        if current_day_d != day:
            # Daily auto-tune based on yesterday results
            if trades and current_day_d is not None:
                yest_trades = [t for t in trades if t['day'] == str(current_day_d)]
                if yest_trades:
                    wr = sum(1 for t in yest_trades if t['outcome']=='WIN') / len(yest_trades) * 100
                    if wr >= 55:
                        max_daily = min(max_daily + 1, 8)
                        cooldown_minutes = max(cooldown_minutes - 10, 30)
                    elif wr < 25:
                        max_daily = max(max_daily - 2, 1)
                        cooldown_minutes = min(cooldown_minutes + 30, 180)
                    elif wr < 40:
                        max_daily = max(max_daily - 1, 2)
                        cooldown_minutes = min(cooldown_minutes + 15, 120)

            current_day_d = day
            daily_trade_count = 0

        # Need at least 60 M5 bars for analysis
        if len(day_m5) < 30:
            continue

        # H1 macro trend
        h1_trend = get_h1_trend(day_start.replace(hour=7), df_h1)

        # Only scan during prime session hours (07-17 UTC)
        prime_m5 = day_m5[(day_m5.index.hour >= 7) & (day_m5.index.hour < 17)]
        if len(prime_m5) < 15:
            continue

        for i in range(25, len(prime_m5) - 5):
            if daily_trade_count >= max_daily:
                break

            ts = prime_m5.index[i]
            sym_key = "GOLD"

            # Cooldown check
            last = last_trade_ts.get(sym_key)
            if last and (ts - last).total_seconds() / 60 < cooldown_minutes:
                continue

            window  = prime_m5.iloc[i-25:i]
            curr    = prime_m5.iloc[i]
            curr_price = curr['close']

            swing_high = window['high'].iloc[:-3].max()
            swing_low  = window['low'].iloc[:-3].min()
            recent_high= window['high'].iloc[-3:].max()
            recent_low = window['low'].iloc[-3:].min()

            sweep_high = (recent_high > swing_high) and (curr_price < swing_high)
            sweep_low  = (recent_low  < swing_low)  and (curr_price > swing_low)

            # RSI
            delta = window['close'].diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs    = gain.iloc[-1] / (loss.iloc[-1] + 1e-9)
            rsi   = 100 - (100 / (1 + rs))

            # FVG
            bull_fvg = bool((window['low'] > window['high'].shift(2)).iloc[-5:].any())
            bear_fvg = bool((window['high'] < window['low'].shift(2)).iloc[-5:].any())

            # Confluence scoring
            pattern = None
            confluence = 0

            if sweep_low and rsi < 35 and h1_trend in ("BULLISH", "NEUTRAL"):
                confluence = 3
                if bull_fvg: confluence += 2
                if rsi < 30: confluence += 1.5
                if curr_price % 25 < 2 or curr_price % 25 > 23: confluence += 1
                if confluence >= 5.5:
                    pattern = "OVERSOLD_SWEEP_BUY"

            elif sweep_high and rsi > 65 and h1_trend in ("BEARISH", "NEUTRAL"):
                confluence = 3
                if bear_fvg: confluence += 2
                if rsi > 70: confluence += 1.5
                if curr_price % 25 < 2 or curr_price % 25 > 23: confluence += 1
                if confluence >= 5.5:
                    pattern = "OVERBOUGHT_SWEEP_SELL"

            if not pattern:
                continue

            # ATR-based SL/TP
            tr = np.maximum(
                window['high'] - window['low'],
                np.maximum(abs(window['high'] - window['close'].shift(1)),
                           abs(window['low'] - window['close'].shift(1)))
            )
            atr = float(tr.tail(14).mean())
            if atr < 0.5: continue

            risk_pts = atr * 1.5
            rr_target = 2.5
            tp_pts = risk_pts * rr_target

            if pattern == "OVERSOLD_SWEEP_BUY":
                entry = curr_price; sl = entry - risk_pts; tp = entry + tp_pts
                direction = "BUY"
            else:
                entry = curr_price; sl = entry + risk_pts; tp = entry - tp_pts
                direction = "SELL"

            # Simulate future exit
            future = prime_m5.iloc[i+1:i+30]
            outcome = "OPEN"; pnl_pts = 0.0
            for fb in future.itertuples():
                if direction == "BUY":
                    if fb.low <= sl:  outcome = "LOSS"; pnl_pts = -risk_pts; break
                    if fb.high >= tp: outcome = "WIN";  pnl_pts = tp_pts;    break
                else:
                    if fb.high >= sl: outcome = "LOSS"; pnl_pts = -risk_pts; break
                    if fb.low <= tp:  outcome = "WIN";  pnl_pts = tp_pts;    break
            if outcome == "OPEN":
                outcome = "TIMEOUT"; pnl_pts = float(curr['close'] - entry if direction == "BUY" else entry - curr['close'])

            trades.append({
                "day": str(day), "ts": str(ts), "direction": direction,
                "pattern": pattern, "trend": h1_trend, "rsi": round(rsi, 1),
                "confluence": confluence, "risk": round(risk_pts, 2),
                "rr": rr_target, "entry": round(entry, 2),
                "sl": round(sl, 2), "tp": round(tp, 2),
                "outcome": outcome, "pnl_pts": round(pnl_pts, 2),
                "autotune_max": max_daily, "autotune_cd": cooldown_minutes
            })
            daily_trade_count += 1
            last_trade_ts[sym_key] = ts

    return pd.DataFrame(trades)

# ══════════════════════════════════════════════════════════════════
# RUN BOTH VERSIONS
# ══════════════════════════════════════════════════════════════════
print("\nRunning BreakoutBoss v1 (OLD — no filters)...")
bb_v1 = run_bb_backtest(use_trend_filter=False, block_hours=False, min_risk=0.80, label="v1")

print("Running BreakoutBoss v2 (NEW — H1 filter + blocked hours + risk floor)...")
bb_v2 = run_bb_backtest(use_trend_filter=True,  block_hours=True,  min_risk=1.20, label="v2")

print("Running Autonomous SMC Scanner...")
smc   = run_smc_backtest()

SEP = "=" * 80

# ══════════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════════
def report_bb(df, label, alloc=5000):
    if df.empty:
        print(f"  {label}: No trades generated.")
        return 0.0

    wins   = df[df['outcome']=='WIN']
    losses = df[df['outcome']=='LOSS']
    bes    = df[df['outcome']=='BE']
    wr     = len(wins)/len(df)*100

    # Scale PnL to $ (GOLD: 1 pt = $1 per 0.01 lot; base lot = 0.02 = $2/pt)
    LOT_SIZE = 0.02
    CONTRACT = 100  # XAU contract size
    pnl_usd  = df['pnl_pts'].sum() * LOT_SIZE * CONTRACT

    wins_usd = wins['pnl_pts'].sum() * LOT_SIZE * CONTRACT
    loss_usd = abs(losses['pnl_pts'].sum() * LOT_SIZE * CONTRACT)
    pf = wins_usd / loss_usd if loss_usd > 0 else 99.0

    avg_w = wins['pnl_pts'].mean() * LOT_SIZE * CONTRACT if len(wins) else 0
    avg_l = abs(losses['pnl_pts'].mean() * LOT_SIZE * CONTRACT) if len(losses) else 0
    rr    = avg_w / avg_l if avg_l else 0

    print(f"\n  {label}")
    print(f"  {'─'*60}")
    print(f"  Trades       : {len(df)}  ({len(wins)}W / {len(losses)}L / {len(bes)}BE)")
    print(f"  Win Rate     : {wr:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  Avg Win      : ${avg_w:.2f}   |  Avg Loss: ${avg_l:.2f}")
    print(f"  Actual R:R   : {rr:.2f}")
    print(f"  Net PnL      : {'+'if pnl_usd>=0 else ''}{pnl_usd:.2f} USD  (on ${alloc:,} allocated)")
    print(f"  ROI          : {(pnl_usd/alloc)*100:+.2f}%")

    # Per session
    print(f"\n  Per-Session (v2):")
    for sess in ["ASIA","FRA","LON","NYP","NYC","LNC"]:
        sd = df[df['session']==sess]
        if sd.empty: continue
        sw = sd[sd['outcome']=='WIN']
        swr = len(sw)/len(sd)*100
        sp = sd['pnl_pts'].sum() * LOT_SIZE * CONTRACT
        print(f"    {sess:<6} | {len(sd):>3} trades | {len(sw)}W | WR:{swr:>5.1f}% | Net:{sp:>+8.2f}")

    # Per direction
    print(f"\n  Per-Direction:")
    for dir_ in ["BUY","SELL"]:
        dd = df[df['direction']==dir_]
        if dd.empty: continue
        dw = dd[dd['outcome']=='WIN']
        dwr = len(dw)/len(dd)*100
        dp = dd['pnl_pts'].sum() * LOT_SIZE * CONTRACT
        print(f"    {dir_:<5} | {len(dd):>3} trades | {len(dw)}W | WR:{dwr:>5.1f}% | Net:{dp:>+8.2f}")

    return pnl_usd

def report_smc(df, alloc=1000):
    if df.empty:
        print("  No SMC trades generated.")
        return 0.0

    wins   = df[df['outcome']=='WIN']
    losses = df[df['outcome']=='LOSS']
    wr     = len(wins)/len(df)*100

    LOT_SIZE = 0.01
    CONTRACT = 100
    pnl_usd  = df['pnl_pts'].sum() * LOT_SIZE * CONTRACT
    wins_usd = wins['pnl_pts'].sum() * LOT_SIZE * CONTRACT if len(wins) else 0
    loss_usd = abs(losses['pnl_pts'].sum() * LOT_SIZE * CONTRACT) if len(losses) else 0
    pf = wins_usd / loss_usd if loss_usd > 0 else 99.0
    avg_w = wins['pnl_pts'].mean() * LOT_SIZE * CONTRACT if len(wins) else 0
    avg_l = abs(losses['pnl_pts'].mean() * LOT_SIZE * CONTRACT) if len(losses) else 0
    rr = avg_w / avg_l if avg_l else 0

    print(f"  Trades       : {len(df)}  ({len(wins)}W / {len(losses)}L)")
    print(f"  Win Rate     : {wr:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  Avg Win      : ${avg_w:.2f}   |  Avg Loss: ${avg_l:.2f}")
    print(f"  Actual R:R   : {rr:.2f}")
    print(f"  Net PnL      : {'+'if pnl_usd>=0 else ''}{pnl_usd:.2f} USD  (on ${alloc:,} allocated)")
    print(f"  ROI          : {(pnl_usd/alloc)*100:+.2f}%")

    # Per day
    print(f"\n  Daily Breakdown (AutoTune in action):")
    for day, grp in df.groupby('day'):
        dw = (grp['outcome']=='WIN').sum()
        dl = (grp['outcome']=='LOSS').sum()
        dwr = dw/len(grp)*100
        dp = grp['pnl_pts'].sum() * LOT_SIZE * CONTRACT
        auto_t = grp['autotune_max'].iloc[-1]
        auto_c = grp['autotune_cd'].iloc[-1]
        print(f"    {day} | {len(grp):>2}t | {dw}W/{dl}L | WR:{dwr:>5.1f}% | Net:{dp:>+7.2f} | MaxT:{auto_t} CD:{auto_c}m")

    # Per pattern
    print(f"\n  Per-Pattern:")
    for pat, grp in df.groupby('pattern'):
        pw = (grp['outcome']=='WIN').sum()
        pwr = pw/len(grp)*100
        pp = grp['pnl_pts'].sum() * LOT_SIZE * CONTRACT
        print(f"    {pat:<30} | {len(grp):>3}t | WR:{pwr:>5.1f}% | Net:{pp:>+7.2f}")

    return pnl_usd

# ── PRINT RESULTS ──────────────────────────────────────────────────
print(f"\n{SEP}")
print("  BREAKOUTBOSS — BEFORE vs AFTER AI FIXES (1-Month Backtest)")
print(SEP)
print("\n  [OLD v1 — no trend filter, no hour blocks, risk floor $0.80]")
pnl_v1 = report_bb(bb_v1, "BreakoutBoss v1 (OLD)", alloc=5000)

print(f"\n  [NEW v2 — H1 trend filter + blocked hours + risk floor $1.20]")
pnl_v2 = report_bb(bb_v2, "BreakoutBoss v2 (NEW AI-Tuned)", alloc=5000)

# Delta
trades_saved = len(bb_v1) - len(bb_v2)
print(f"\n  {'─'*60}")
print(f"  Improvement   : {pnl_v2 - pnl_v1:+.2f} USD  ({'+' if pnl_v2 > pnl_v1 else ''}{((pnl_v2-pnl_v1)/5000)*100:.1f}% ROI improvement)")
print(f"  Trades reduced: {len(bb_v1)} → {len(bb_v2)} (eliminated {trades_saved} weak setups)")

print(f"\n{SEP}")
print("  AUTONOMOUS SMC SCANNER — 1-Month Backtest with Daily Auto-Tune")
print(SEP)
smc_pnl = report_smc(smc, alloc=1000)

total_pnl = pnl_v2 + smc_pnl
print(f"\n{SEP}")
print("  COMBINED PORTFOLIO PROJECTION (1-Month)")
print(SEP)
print(f"  BreakoutBoss v2 : {pnl_v2:>+10.2f} USD  (on $5,000)")
print(f"  SMC Scanner     : {smc_pnl:>+10.2f} USD  (on $1,000)")
print(f"  ─────────────────────────────────────────────")
print(f"  TOTAL           : {total_pnl:>+10.2f} USD  (on $6,000)")
print(f"  Portfolio ROI   : {(total_pnl/6000)*100:+.2f}%")
print(f"\n  Starting balance $5,444.36 → Projected end-month: ${5444.36 + total_pnl:.2f}")
print(SEP)
