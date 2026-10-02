"""
=============================================================================
  FINAL COMPREHENSIVE BACKTEST: BreakoutBoss (v2 + TSL + Compounding + Gann)
  + Autonomous SMC AI (True Institutional FVG / OB Mitigation + TSL)
  
  Symbol  : GOLD (XAUUSD)
  Period  : Sep 1 – Oct 2, 2026 (Full 1 Month)
  Capital : $5,000 BreakoutBoss (5 Models @ $1,000 ea) + $1,000 SMC AI
=============================================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(r"C:\anlyzeforex\forextele\scratch")
df_m1 = pd.read_parquet(BASE / "gold_m1_sep2026.parquet")
df_h1 = pd.read_parquet(BASE / "gold_h1_sep2026.parquet")
df_m5 = pd.read_parquet(BASE / "gold_m5_sep2026.parquet")

for df in [df_m1, df_h1, df_m5]:
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

# ── H1 Trend Helper ──
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

# ── SESSIONS CONFIG (6 Sessions + Gann 72 & 144) ──
VOLATILITY_CAPS = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
BLOCKED_UTC_HOURS = {5, 9, 18}

SESSIONS_CONFIG = [
    {"code": "ASIA",    "start": (1, 0),  "dur": 5, "tfs": [1, 3, 5, 15], "rr": {1: 1.5, 3: 2.0, 5: 2.0, 15: 2.0}},
    {"code": "FRA",     "start": (6, 0),  "dur": 4, "tfs": [1, 3, 5, 15], "rr": {1: 5.0, 3: 5.0, 5: 3.0, 15: 3.0}},
    {"code": "LON",     "start": (8, 0),  "dur": 4, "tfs": [1, 3, 5, 15], "rr": {1: 3.0, 3: 5.0, 5: 3.0, 15: 3.0}},
    {"code": "NYP",     "start": (12, 30), "dur": 3, "tfs": [1, 3, 5, 15], "rr": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}},
    {"code": "NYC",     "start": (13, 30), "dur": 3, "tfs": [1, 3, 5, 15], "rr": {1: 5.0, 3: 3.0, 5: 3.0, 15: 3.0}},
    {"code": "LNC",     "start": (15, 30), "dur": 3, "tfs": [1, 3, 5, 15], "rr": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}},
]

# ═════════════════════════════════════════════════════════════════════
# PART 1: BREAKOUTBOSS (AI Trend Filter + TSL + Gann 72 & 144)
# ═════════════════════════════════════════════════════════════════════
def run_bb_backtest():
    trades = []
    processed = set()
    all_days = sorted(set(df_m1.index.date))

    for day in all_days:
        day_start = pd.Timestamp(day, tz="UTC")
        day_end   = day_start + pd.Timedelta(hours=23, minutes=59)
        day_m1    = df_m1[(df_m1.index >= day_start) & (df_m1.index <= day_end)]
        if len(day_m1) < 100:
            continue

        # ── 1. Standard 6 Sessions ──
        for sc in SESSIONS_CONFIG:
            sh, sm = sc["start"]
            sess_open  = day_start.replace(hour=sh, minute=sm)
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
                ref_low  = ref_bars['low'].min()
                ref_range= ref_high - ref_low
                ref_mid  = (ref_high + ref_low) / 2.0

                max_range = VOLATILITY_CAPS.get(tf, 8.0)
                if ref_range < 0.35 or ref_range > max_range:
                    processed.add(setup_id)
                    continue

                post_bars = day_m1[(day_m1.index >= ref_end) & (day_m1.index < sess_close)]
                if len(post_bars) < 2:
                    continue

                broken_bull = post_bars['high'].max() > ref_high + 0.25
                broken_bear = post_bars['low'].min()  < ref_low  - 0.25
                trend = get_h1_trend(sess_open, df_h1)

                rr = sc["rr"].get(tf, 3.0)
                tol = 0.25

                for i in range(1, len(post_bars)):
                    bar = post_bars.iloc[i]
                    bl = bar['low']; bh = bar['high']; bc = bar['close']; bo = bar['open']

                    # BUY BREAKOUT RETEST
                    if broken_bull and not broken_bear:
                        if trend == "BEARISH":
                            break
                        if bl <= ref_high + tol and bh >= ref_high - tol and ((bc >= bo) or (bc > ref_high)):
                            entry = ref_high + 0.25
                            sl_d  = ref_low if tf == 1 else (max(ref_low, entry - 2.5) if tf == 3 else max(ref_mid, entry - 3.0))
                            risk  = max(entry - sl_d, 1.20)
                            tp    = entry + risk * rr
                            sl    = entry - risk

                            # TSL & Breakeven Simulation
                            future = post_bars.iloc[i+1:]
                            curr_sl = sl
                            be_triggered = False
                            pnl_pts = 0.0
                            outcome = "OPEN"

                            for fb in future.itertuples():
                                if not be_triggered and fb.high >= entry + (risk * 1.5):
                                    curr_sl = entry + 0.20
                                    be_triggered = True

                                if be_triggered and fb.high >= entry + (risk * 2.5):
                                    trail_sl = fb.high - (risk * 1.5)
                                    if trail_sl > curr_sl:
                                        curr_sl = trail_sl

                                if fb.low <= curr_sl:
                                    if curr_sl > entry:
                                        outcome = "TRAIL_WIN"; pnl_pts = curr_sl - entry
                                    elif curr_sl == entry + 0.20:
                                        outcome = "BE"; pnl_pts = 0.20
                                    else:
                                        outcome = "LOSS"; pnl_pts = -risk
                                    break

                                if fb.high >= tp:
                                    outcome = "WIN"; pnl_pts = risk * rr
                                    break

                            if outcome == "OPEN" and len(future):
                                outcome = "TIMEOUT"
                                pnl_pts = future.iloc[-1]['close'] - entry

                            trades.append({
                                "day": str(day), "ts": bar.name, "session": sc["code"], "tf": tf,
                                "direction": "BUY", "risk": risk, "rr": rr, "pnl_pts": pnl_pts, "outcome": outcome
                            })
                            processed.add(setup_id)
                            break
                        if bl <= ref_low:
                            processed.add(setup_id); break

                    # SELL BREAKOUT RETEST
                    elif broken_bear and not broken_bull:
                        if trend == "BULLISH":
                            break
                        if bh >= ref_low - tol and bl <= ref_low + tol and ((bc <= bo) or (bc < ref_low)):
                            entry = ref_low - 0.25
                            sl_d  = ref_high if tf == 1 else (min(ref_high, entry + 2.5) if tf == 3 else min(ref_mid, entry + 3.0))
                            risk  = max(sl_d - entry, 1.20)
                            tp    = entry - risk * rr
                            sl    = entry + risk

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
                                        outcome = "TRAIL_WIN"; pnl_pts = entry - curr_sl
                                    elif curr_sl == entry - 0.20:
                                        outcome = "BE"; pnl_pts = 0.20
                                    else:
                                        outcome = "LOSS"; pnl_pts = -risk
                                    break

                                if fb.low <= tp:
                                    outcome = "WIN"; pnl_pts = risk * rr
                                    break

                            if outcome == "OPEN" and len(future):
                                outcome = "TIMEOUT"
                                pnl_pts = entry - future.iloc[-1]['close']

                            trades.append({
                                "day": str(day), "ts": bar.name, "session": sc["code"], "tf": tf,
                                "direction": "SELL", "risk": risk, "rr": rr, "pnl_pts": pnl_pts, "outcome": outcome
                            })
                            processed.add(setup_id)
                            break
                        if bh >= ref_high:
                            processed.add(setup_id); break

        # ── 2. Gann Harmonic Cycle (Candles 72 & 144) ──
        # M1 candle 72 (01:12 UTC) & Candle 144 (02:24 UTC)
        for gann_candle_idx, gann_code in [(71, "GANN72"), (143, "GANN144")]:
            if len(day_m1) > gann_candle_idx + 60:
                ref_bar = day_m1.iloc[gann_candle_idx]
                ref_ts  = day_m1.index[gann_candle_idx]
                ref_high = ref_bar['high']
                ref_low  = ref_bar['low']
                ref_range = ref_high - ref_low
                if ref_range < 0.30 or ref_range > 3.0:
                    continue

                trend = get_h1_trend(ref_ts, df_h1)
                post_bars = day_m1.iloc[gann_candle_idx+1:gann_candle_idx+180]
                rr = 3.0
                risk = max(ref_range, 1.20)

                for i in range(len(post_bars)):
                    bar = post_bars.iloc[i]
                    if bar['high'] > ref_high + 0.25 and trend != "BEARISH":
                        entry = ref_high + 0.25
                        sl = entry - risk
                        tp = entry + risk * rr
                        curr_sl = sl
                        be = False
                        pnl = 0.0
                        out = "OPEN"
                        for fb in post_bars.iloc[i+1:].itertuples():
                            if not be and fb.high >= entry + risk * 1.5:
                                curr_sl = entry + 0.20; be = True
                            if fb.low <= curr_sl:
                                out = "BE" if be else "LOSS"; pnl = 0.20 if be else -risk; break
                            if fb.high >= tp:
                                out = "WIN"; pnl = risk * rr; break
                        if out != "OPEN":
                            trades.append({"day": str(day), "ts": bar.name, "session": gann_code, "tf": 1,
                                           "direction": "BUY", "risk": risk, "rr": rr, "pnl_pts": pnl, "outcome": out})
                        break

                    elif bar['low'] < ref_low - 0.25 and trend != "BULLISH":
                        entry = ref_low - 0.25
                        sl = entry + risk
                        tp = entry - risk * rr
                        curr_sl = sl
                        be = False
                        pnl = 0.0
                        out = "OPEN"
                        for fb in post_bars.iloc[i+1:].itertuples():
                            if not be and fb.low <= entry - risk * 1.5:
                                curr_sl = entry - 0.20; be = True
                            if fb.high >= curr_sl:
                                out = "BE" if be else "LOSS"; pnl = 0.20 if be else -risk; break
                            if fb.low <= tp:
                                out = "WIN"; pnl = risk * rr; break
                        if out != "OPEN":
                            trades.append({"day": str(day), "ts": bar.name, "session": gann_code, "tf": 1,
                                           "direction": "SELL", "risk": risk, "rr": rr, "pnl_pts": pnl, "outcome": out})
                        break

    return pd.DataFrame(trades)

# ═════════════════════════════════════════════════════════════════════
# PART 2: AUTONOMOUS SMC AI (True Institutional FVG + OB Mitigation)
# ═════════════════════════════════════════════════════════════════════
def run_smc_ai_backtest():
    # Resample M5 to M15
    df_m15 = df_m5.resample('15min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'tick_volume': 'sum'
    }).dropna()

    df_h1_copy = df_h1.copy()
    df_h1_copy['ema50'] = df_h1_copy['close'].ewm(span=50, adjust=False).mean()
    df_h1_copy['trend'] = np.where(df_h1_copy['close'] > df_h1_copy['ema50'], 'BULLISH', 'BEARISH')
    h1_trend_map = df_h1_copy['trend'].to_dict()

    tr = np.maximum(df_m15['high'] - df_m15['low'],
                    np.maximum(abs(df_m15['high'] - df_m15['close'].shift(1)),
                               abs(df_m15['low'] - df_m15['close'].shift(1))))
    df_m15['atr'] = tr.rolling(14).mean()

    active_bull_fvgs = []
    active_bear_fvgs = []
    trades = []

    for i in range(20, len(df_m15) - 10):
        row = df_m15.iloc[i]
        prev1 = df_m15.iloc[i-1]
        prev2 = df_m15.iloc[i-2]
        t = df_m15.index[i]

        # 1. Identify Fair Value Gap (FVG)
        if row['low'] > prev2['high'] and prev1['close'] > prev1['open']:
            active_bull_fvgs.append({'top': row['low'], 'bot': prev2['high'], 'mitigated': False, 'idx': i})
        if row['high'] < prev2['low'] and prev1['close'] < prev1['open']:
            active_bear_fvgs.append({'top': prev2['low'], 'bot': row['high'], 'mitigated': False, 'idx': i})

        active_bull_fvgs = [f for f in active_bull_fvgs if not f['mitigated'] and (i - f['idx']) < 30]
        active_bear_fvgs = [f for f in active_bear_fvgs if not f['mitigated'] and (i - f['idx']) < 30]

        h1_t = h1_trend_map.get(t.floor('1h'), 'BULLISH')

        # 2. Mitigation Tap Entry in Trend Direction
        sig = None
        fvg_zone = None
        if h1_t == 'BULLISH':
            for f in active_bull_fvgs:
                if row['low'] <= f['top'] and row['close'] > f['bot']:
                    sig = 'BUY'; fvg_zone = f; f['mitigated'] = True; break
        elif h1_t == 'BEARISH':
            for f in active_bear_fvgs:
                if row['high'] >= f['bot'] and row['close'] < f['top']:
                    sig = 'SELL'; fvg_zone = f; f['mitigated'] = True; break

        if not sig:
            continue

        entry = row['close']
        atr = row['atr'] if not pd.isna(row['atr']) else 1.5
        sl = (fvg_zone['bot'] - atr * 0.3) if sig == 'BUY' else (fvg_zone['top'] + atr * 0.3)
        risk = abs(entry - sl)
        if risk < 0.8 or risk > 5.0:
            continue
        tp = entry + risk * 2.5 if sig == 'BUY' else entry - risk * 2.5

        outcome = 'OPEN'
        pnl = 0
        future = df_m15.iloc[i+1:i+40]
        for fb in future.itertuples():
            if sig == 'BUY':
                if fb.low <= sl: outcome = 'LOSS'; pnl = -risk; break
                if fb.high >= tp: outcome = 'WIN'; pnl = risk * 2.5; break
            else:
                if fb.high >= sl: outcome = 'LOSS'; pnl = -risk; break
                if fb.low <= tp: outcome = 'WIN'; pnl = risk * 2.5; break

        if outcome != 'OPEN':
            trades.append({
                'day': str(t.date()), 'ts': t, 'session': 'SMC_FVG', 'tf': 15,
                'direction': sig, 'risk': risk, 'rr': 2.5, 'pnl_pts': pnl, 'outcome': outcome
            })

    return pd.DataFrame(trades)

# ═════════════════════════════════════════════════════════════════════
# EXECUTE BACKTESTS
# ═════════════════════════════════════════════════════════════════════
print("Processing BreakoutBoss (v2 + TSL + Gann)...")
df_bb = run_bb_backtest()

print("Processing Autonomous SMC AI (Institutional FVG + OB)...")
df_smc = run_smc_ai_backtest()

print(f"Total BreakoutBoss Setups : {len(df_bb)}")
print(f"Total Autonomous SMC Setups: {len(df_smc)}")

# ═════════════════════════════════════════════════════════════════════
# COMPOUNDING EVALUATION ACROSS ALL 5 MODELS + SMC
# ═════════════════════════════════════════════════════════════════════
# Sort chronologically
df_bb['engine'] = 'BB'
df_smc['engine'] = 'SMC'

conviction_weights = {
    "FRA": 1.35, "LNC": 1.35, "NYC": 1.15, "NYP": 1.15, "LON": 1.00, "ASIA": 0.70,
    "GANN72": 1.10, "GANN144": 1.40
}

# 1. BreakoutBoss Compounding Models (Starting Capital: $1,000 each)
bb_models = {
    "M0_Fixed":        {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0},
    "M1_StepLadder":   {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0},
    "M2_Linear":       {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0},
    "M3_AIConviction": {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0},
    "M4_HalfKelly":    {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0},
}

for _, t in df_bb.iterrows():
    pts = t['pnl_pts']
    sess = t['session']
    is_win = pts > 0

    # M0: Fixed 0.02
    lot0 = 0.02
    p0 = pts * lot0 * 100
    bb_models["M0_Fixed"]["equity"] += p0
    bb_models["M0_Fixed"]["trades"] += 1
    if is_win: bb_models["M0_Fixed"]["wins"] += 1; bb_models["M0_Fixed"]["win_pnl"] += p0
    else: bb_models["M0_Fixed"]["losses"] += 1; bb_models["M0_Fixed"]["loss_pnl"] += abs(p0)

    # M1: Step-Ladder
    eq1 = bb_models["M1_StepLadder"]["equity"]
    if eq1 < 1400: lot1 = 0.02
    elif eq1 < 2000: lot1 = 0.04
    elif eq1 < 3000: lot1 = 0.06
    elif eq1 < 4500: lot1 = 0.08
    else: lot1 = 0.12
    p1 = pts * lot1 * 100
    bb_models["M1_StepLadder"]["equity"] += p1
    bb_models["M1_StepLadder"]["trades"] += 1
    if is_win: bb_models["M1_StepLadder"]["wins"] += 1; bb_models["M1_StepLadder"]["win_pnl"] += p1
    else: bb_models["M1_StepLadder"]["losses"] += 1; bb_models["M1_StepLadder"]["loss_pnl"] += abs(p1)

    # M2: Linear Equity
    eq2 = bb_models["M2_Linear"]["equity"]
    lot2 = min(max(round((eq2 / 1000.0) * 0.02, 2), 0.01), 0.40)
    p2 = pts * lot2 * 100
    bb_models["M2_Linear"]["equity"] += p2
    bb_models["M2_Linear"]["trades"] += 1
    if is_win: bb_models["M2_Linear"]["wins"] += 1; bb_models["M2_Linear"]["win_pnl"] += p2
    else: bb_models["M2_Linear"]["losses"] += 1; bb_models["M2_Linear"]["loss_pnl"] += abs(p2)

    # M3: AI Conviction
    eq3 = bb_models["M3_AIConviction"]["equity"]
    w = conviction_weights.get(sess, 1.0)
    lot3 = min(max(round((eq3 / 1000.0) * 0.02 * w, 2), 0.01), 0.40)
    p3 = pts * lot3 * 100
    bb_models["M3_AIConviction"]["equity"] += p3
    bb_models["M3_AIConviction"]["trades"] += 1
    if is_win: bb_models["M3_AIConviction"]["wins"] += 1; bb_models["M3_AIConviction"]["win_pnl"] += p3
    else: bb_models["M3_AIConviction"]["losses"] += 1; bb_models["M3_AIConviction"]["loss_pnl"] += abs(p3)

    # M4: Half Kelly (Aggressive)
    eq4 = bb_models["M4_HalfKelly"]["equity"]
    lot4 = min(max(round((eq4 / 1000.0) * 0.04, 2), 0.01), 0.50)
    p4 = pts * lot4 * 100
    bb_models["M4_HalfKelly"]["equity"] += p4
    bb_models["M4_HalfKelly"]["trades"] += 1
    if is_win: bb_models["M4_HalfKelly"]["wins"] += 1; bb_models["M4_HalfKelly"]["win_pnl"] += p4
    else: bb_models["M4_HalfKelly"]["losses"] += 1; bb_models["M4_HalfKelly"]["loss_pnl"] += abs(p4)

# 2. SMC AI Compounding (Starting Capital: $1,000)
smc_stat = {"equity": 1000.0, "trades": 0, "wins": 0, "losses": 0, "win_pnl": 0.0, "loss_pnl": 0.0}
for _, t in df_smc.iterrows():
    pts = t['pnl_pts']
    is_win = pts > 0
    eq_smc = smc_stat["equity"]
    lot_smc = min(max(round((eq_smc / 1000.0) * 0.04, 2), 0.02), 0.30)
    p_smc = pts * lot_smc * 100
    smc_stat["equity"] += p_smc
    smc_stat["trades"] += 1
    if is_win: smc_stat["wins"] += 1; smc_stat["win_pnl"] += p_smc
    else: smc_stat["losses"] += 1; smc_stat["loss_pnl"] += abs(p_smc)

# ═════════════════════════════════════════════════════════════════════
# PRINT COMPLETE RESULTS TABLE
# ═════════════════════════════════════════════════════════════════════
print("\n" + "="*95)
print("  FINAL 1-MONTH COMPREHENSIVE BACKTEST REPORT (SEP 1 – OCT 2, 2026)")
print("  Includes AI Trend Filter + Trailing Stop Loss (TSL) + Compounding Models")
print("="*95)
print(f"{'Engine / Strategy Model':<26} | {'Start':>7} | {'Final Eq':>9} | {'Net PnL':>9} | {'ROI':>8} | {'Trades':>6} | {'WR%':>6} | {'PF':>5}")
print("-" * 95)

total_start = 0.0
total_final = 0.0
total_trades = 0
total_wins = 0

for m_name, d in bb_models.items():
    st = 1000.0
    fin = d["equity"]
    net = fin - st
    roi = (net / st) * 100
    wr = (d["wins"] / d["trades"] * 100) if d["trades"] else 0.0
    pf = (d["win_pnl"] / d["loss_pnl"]) if d["loss_pnl"] > 0 else 99.0
    print(f"BB: {m_name:<22} | ${st:>6.0f} | ${fin:>8.2f} | ${net:>+8.2f} | {roi:>+7.1f}% | {d['trades']:>6} | {wr:>5.1f}% | {pf:>4.2f}")
    total_start += st
    total_final += fin
    total_trades += d["trades"]
    total_wins += d["wins"]

# SMC row
st_smc = 1000.0
fin_smc = smc_stat["equity"]
net_smc = fin_smc - st_smc
roi_smc = (net_smc / st_smc) * 100
wr_smc = (smc_stat["wins"] / smc_stat["trades"] * 100) if smc_stat["trades"] else 0.0
pf_smc = (smc_stat["win_pnl"] / smc_stat["loss_pnl"]) if smc_stat["loss_pnl"] > 0 else 99.0
print(f"SMC: Institutional FVG+OB    | ${st_smc:>6.0f} | ${fin_smc:>8.2f} | ${net_smc:>+8.2f} | {roi_smc:>+7.1f}% | {smc_stat['trades']:>6} | {wr_smc:>5.1f}% | {pf_smc:>4.2f}")

total_start += st_smc
total_final += fin_smc
total_trades += smc_stat["trades"]
total_wins += smc_stat["wins"]

print("-" * 95)
tot_net = total_final - total_start
tot_roi = (tot_net / total_start) * 100
tot_wr = (total_wins / total_trades * 100) if total_trades else 0.0
print(f"{'COMBINED PORTFOLIO':<26} | ${total_start:>6.0f} | ${total_final:>8.2f} | ${tot_net:>+8.2f} | {tot_roi:>+7.1f}% | {total_trades:>6} | {tot_wr:>5.1f}% |  N/A")
print("=" * 95)
