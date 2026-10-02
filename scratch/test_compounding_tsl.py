"""
Test Script:
1. BreakoutBoss Compounding Models (M0 - M4) + TSL / BE Evaluation over 1 month
2. True Institutional SMC (Liquidity Sweep -> Displacement -> FVG/OB Mitigation -> Entry with BE & Trailing TP)
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(r"C:\anlyzeforex\forextele\scratch")
df_m1 = pd.read_parquet(BASE / "gold_m1_sep2026.parquet")
df_h1 = pd.read_parquet(BASE / "gold_h1_sep2026.parquet")
df_m5 = pd.read_parquet(BASE / "gold_m5_sep2026.parquet")

for df in [df_m1, df_h1, df_m5]:
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

def get_h1_trend(ts, df_h1):
    past_h1 = df_h1[df_h1.index < ts].tail(210)
    if len(past_h1) < 50:
        return "NEUTRAL"
    closes = past_h1['close']
    ema50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = closes.ewm(span=200, adjust=False).mean().iloc[-1]
    c = closes.iloc[-1]
    if c > ema50 > ema200:
        return "BULLISH"
    elif c < ema50 < ema200:
        return "BEARISH"
    return "NEUTRAL"

VOLATILITY_CAPS = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
BLOCKED_UTC_HOURS = {5, 9, 18}

SESSIONS_CONFIG = [
    {"code": "ASIA", "start": (1, 0), "dur": 5, "tfs": [1,3,5,15], "rr": {1:1.5,3:2.0,5:2.0,15:2.0}},
    {"code": "FRA", "start": (6, 0), "dur": 4, "tfs": [1,3,5,15], "rr": {1:5.0,3:5.0,5:3.0,15:3.0}},
    {"code": "LON", "start": (8, 0), "dur": 4, "tfs": [1,3,5,15], "rr": {1:3.0,3:5.0,5:3.0,15:3.0}},
    {"code": "NYP", "start": (12,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:3.0,3:3.0,5:3.0,15:5.0}},
    {"code": "NYC", "start": (13,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:5.0,3:3.0,5:3.0,15:3.0}},
    {"code": "LNC", "start": (15,30), "dur": 3, "tfs": [1,3,5,15], "rr": {1:3.0,3:3.0,5:3.0,15:5.0}},
]

# ─────────────────────────────────────────────────────────────────
# 1. BREAKOUTBOSS WITH TSL & COMPOUNDING
# ─────────────────────────────────────────────────────────────────
def run_bb_with_tsl():
    trades = []
    processed = set()
    all_days = sorted(set(df_m1.index.date))

    for day in all_days:
        day_start = pd.Timestamp(day, tz="UTC")
        day_end = day_start + pd.Timedelta(hours=23, minutes=59)
        day_m1 = df_m1[(df_m1.index >= day_start) & (df_m1.index <= day_end)]

        for sc in SESSIONS_CONFIG:
            sh, sm = sc["start"]
            sess_open = day_start.replace(hour=sh, minute=sm)
            sess_close = sess_open + pd.Timedelta(hours=sc["dur"])

            for tf in sc["tfs"]:
                setup_id = f"{day}_{sc['code']}_M{tf}"
                if setup_id in processed:
                    continue

                ref_end = sess_open + pd.Timedelta(minutes=tf)
                if sh in BLOCKED_UTC_HOURS:
                    processed.add(setup_id)
                    continue

                ref_bars = day_m1[(day_m1.index >= sess_open) & (day_m1.index < ref_end)]
                if len(ref_bars) < tf:
                    continue

                ref_high = ref_bars['high'].max()
                ref_low = ref_bars['low'].min()
                ref_range = ref_high - ref_low
                ref_mid = (ref_high + ref_low) / 2.0

                max_range = VOLATILITY_CAPS.get(tf, 8.0)
                if ref_range < 0.35 or ref_range > max_range:
                    processed.add(setup_id)
                    continue

                post_bars = day_m1[day_m1.index >= ref_end]
                post_bars = post_bars[post_bars.index < sess_close]
                if len(post_bars) < 2:
                    continue

                broken_bull = post_bars['high'].max() > ref_high + 0.25
                broken_bear = post_bars['low'].min() < ref_low - 0.25
                trend = get_h1_trend(sess_open, df_h1)

                rr = sc["rr"].get(tf, 3.0)
                tol = 0.25

                for i in range(1, len(post_bars)):
                    bar = post_bars.iloc[i]
                    bl = bar['low']; bh = bar['high']; bc = bar['close']; bo = bar['open']

                    if broken_bull and not broken_bear:
                        if trend == "BEARISH":
                            break
                        if bl <= ref_high + tol and bh >= ref_high - tol and ((bc >= bo) or (bc > ref_high)):
                            entry = ref_high + 0.25
                            sl_d = ref_low if tf == 1 else (max(ref_low, entry - 2.5) if tf == 3 else max(ref_mid, entry - 3.0))
                            risk = max(entry - sl_d, 1.20)
                            tp = entry + risk * rr
                            sl = entry - risk

                            # SIMULATE WITH TSL & BREAKEVEN
                            future = post_bars.iloc[i+1:]
                            curr_sl = sl
                            be_triggered = False
                            pnl_pts = 0.0
                            outcome = "OPEN"

                            for fb in future.itertuples():
                                # Check BE trigger: once price reaches +1.5R profit, move SL to entry + 0.20
                                if not be_triggered and fb.high >= entry + (risk * 1.5):
                                    curr_sl = entry + 0.20
                                    be_triggered = True

                                # Trailing Stop: if price reaches +2.5R, trail SL at 1.5R distance
                                if be_triggered and fb.high >= entry + (risk * 2.5):
                                    trail_sl = fb.high - (risk * 1.5)
                                    if trail_sl > curr_sl:
                                        curr_sl = trail_sl

                                # Check SL hit
                                if fb.low <= curr_sl:
                                    if curr_sl > entry:
                                        outcome = "TRAIL_WIN"
                                        pnl_pts = curr_sl - entry
                                    elif curr_sl == entry + 0.20:
                                        outcome = "BE"
                                        pnl_pts = 0.20
                                    else:
                                        outcome = "LOSS"
                                        pnl_pts = -risk
                                    break

                                # Check TP hit
                                if fb.high >= tp:
                                    outcome = "WIN"
                                    pnl_pts = risk * rr
                                    break

                            if outcome == "OPEN":
                                outcome = "TIMEOUT"
                                pnl_pts = future.iloc[-1]['close'] - entry if len(future) else 0.0

                            trades.append({
                                "day": str(day), "session": sc["code"], "tf": tf, "direction": "BUY",
                                "entry": entry, "risk": risk, "rr": rr, "pnl_pts": pnl_pts, "outcome": outcome
                            })
                            processed.add(setup_id)
                            break
                        if bl <= ref_low:
                            processed.add(setup_id); break

                    elif broken_bear and not broken_bull:
                        if trend == "BULLISH":
                            break
                        if bh >= ref_low - tol and bl <= ref_low + tol and ((bc <= bo) or (bc < ref_low)):
                            entry = ref_low - 0.25
                            sl_d = ref_high if tf == 1 else (min(ref_high, entry + 2.5) if tf == 3 else min(ref_mid, entry + 3.0))
                            risk = max(sl_d - entry, 1.20)
                            tp = entry - risk * rr
                            sl = entry + risk

                            future = post_bars.iloc[i+1:]
                            curr_sl = sl
                            be_triggered = False
                            pnl_pts = 0.0
                            outcome = "OPEN"

                            for fb in future.itertuples():
                                if not be_triggered and fb.low <= entry - (risk * 1.5):
                                    curr_sl = entry - 0.20
                                    be_triggered = True

                                if be_triggered and fb.low <= entry - (risk * 2.5):
                                    trail_sl = fb.low + (risk * 1.5)
                                    if trail_sl < curr_sl:
                                        curr_sl = trail_sl

                                if fb.high >= curr_sl:
                                    if curr_sl < entry:
                                        outcome = "TRAIL_WIN"
                                        pnl_pts = entry - curr_sl
                                    elif curr_sl == entry - 0.20:
                                        outcome = "BE"
                                        pnl_pts = 0.20
                                    else:
                                        outcome = "LOSS"
                                        pnl_pts = -risk
                                    break

                                if fb.low <= tp:
                                    outcome = "WIN"
                                    pnl_pts = risk * rr
                                    break

                            if outcome == "OPEN":
                                outcome = "TIMEOUT"
                                pnl_pts = entry - future.iloc[-1]['close'] if len(future) else 0.0

                            trades.append({
                                "day": str(day), "session": sc["code"], "tf": tf, "direction": "SELL",
                                "entry": entry, "risk": risk, "rr": rr, "pnl_pts": pnl_pts, "outcome": outcome
                            })
                            processed.add(setup_id)
                            break
                        if bh >= ref_high:
                            processed.add(setup_id); break

    return pd.DataFrame(trades)

df_bb_tsl = run_bb_with_tsl()
print(f"Total BB Trades with TSL: {len(df_bb_tsl)}")
wins = df_bb_tsl[df_bb_tsl['outcome'].isin(['WIN', 'TRAIL_WIN'])]
losses = df_bb_tsl[df_bb_tsl['outcome'] == 'LOSS']
bes = df_bb_tsl[df_bb_tsl['outcome'] == 'BE']
print(f"Wins: {len(wins)}, Losses: {len(losses)}, BE: {len(bes)}")
print(f"Effective Win+BE Rate: {(len(wins)+len(bes))/len(df_bb_tsl)*100:.1f}%")
print(f"Total PnL Points: {df_bb_tsl['pnl_pts'].sum():.2f}")

# ── NOW SIMULATE COMPOUNDING ACROSS THE 5 MODELS ──
# Starting capital: $1,000 per model = $5,000 total
models_equity = {
    "M0_Fixed": 1000.0,
    "M1_StepLadder": 1000.0,
    "M2_Linear": 1000.0,
    "M3_AIConviction": 1000.0,
    "M4_HalfKelly": 1000.0
}

conviction_weights = {
    "FRA": 1.35, "LNC": 1.35, "NYC": 1.15, "NYP": 1.15, "LON": 1.00, "ASIA": 0.70
}

for _, t in df_bb_tsl.iterrows():
    pts = t['pnl_pts']
    sess = t['session']
    
    # M0: Fixed 0.02
    lot_m0 = 0.02
    models_equity["M0_Fixed"] += pts * lot_m0 * 100

    # M1: Step Ladder
    eq1 = models_equity["M1_StepLadder"]
    if eq1 < 1400: lot_m1 = 0.02
    elif eq1 < 2000: lot_m1 = 0.04
    elif eq1 < 3000: lot_m1 = 0.06
    elif eq1 < 4500: lot_m1 = 0.08
    else: lot_m1 = 0.12
    models_equity["M1_StepLadder"] += pts * lot_m1 * 100

    # M2: Linear Equity
    eq2 = models_equity["M2_Linear"]
    lot_m2 = min(max(round((eq2 / 1000.0) * 0.02, 2), 0.01), 0.40)
    models_equity["M2_Linear"] += pts * lot_m2 * 100

    # M3: AI Conviction
    eq3 = models_equity["M3_AIConviction"]
    w = conviction_weights.get(sess, 1.0)
    lot_m3 = min(max(round((eq3 / 1000.0) * 0.02 * w, 2), 0.01), 0.40)
    models_equity["M3_AIConviction"] += pts * lot_m3 * 100

    # M4: Half Kelly (Aggressive)
    eq4 = models_equity["M4_HalfKelly"]
    lot_m4 = min(max(round((eq4 / 1000.0) * 0.04, 2), 0.01), 0.50)
    models_equity["M4_HalfKelly"] += pts * lot_m4 * 100

total_start = 5000.0
total_end = sum(models_equity.values())
net_profit = total_end - total_start
roi = (net_profit / total_start) * 100

print("\n" + "="*60)
print("  BREAKOUTBOSS 5-MODEL COMPOUNDING + TSL RESULTS (1 MONTH)")
print("="*60)
for m, eq in models_equity.items():
    p = eq - 1000.0
    r = (p / 1000.0) * 100
    print(f"  {m:<16}: Final ${eq:,.2f} | Net: {'+'if p>=0 else ''}${p:,.2f} ({r:+.1f}%)")
print("-" * 60)
print(f"  TOTAL PORTFOLIO : ${total_start:,.2f} → ${total_end:,.2f}")
print(f"  NET PROFIT      : +${net_profit:,.2f} USD")
print(f"  COMPOUNDED ROI  : +{roi:.2f}%")
print("="*60)
