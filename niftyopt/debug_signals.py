import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from BACKTEST_V3_TUNED import (load_option_data, load_eod_data, build_15min_spot,
    calc_pcr, calc_vwap, calc_rsi, signal_check, make_strategies)
from datetime import date

opt_data = load_option_data()
eod_data = load_eod_data()
strats = {s.name: s for s in make_strategies()}

zero = ['ULTIMATE_DAY_HIGH_LOW','DAY_HIGH_BEARISH','DAY_HIGH_LOW_TRADITIONAL',
        'ENHANCED_BEARISH','ENHANCED_BULLISH','AI_ENHANCED','MEAN_REVERSION',
        'OPTIONS_GREEKS','MAGIC_SQUARE','ZERO_HERO']

print("=== Strategy config ===")
for n in zero:
    s = strats[n]
    print(f"{n}: dir={s.direction} window={s.entry_start}-{s.entry_end} vwap={s.require_vwap} vol={s.require_volume} strike={s.strike} prem={s.min_premium}-{s.max_premium}")

# Test across all 58 trading days - count how many days each zero-strategy fires with gates removed
print()
print("=== Signal fire counts (gates removed) across all 58 days ===")
fire_counts = {n: {'CE': 0, 'PE': 0} for n in zero}

for day in sorted(opt_data['date'].unique()):
    day_data = opt_data[opt_data['date'] == day].copy()
    c15 = build_15min_spot(day_data)
    if len(c15) < 3:
        continue
    eod_row = eod_data[eod_data['dt'] == day]
    if eod_row.empty:
        continue
    r = eod_row.iloc[0]
    day_ohlc = {'open': r['open'], 'high': r['high'], 'low': r['low']}
    pcr = calc_pcr(day_data)
    expiry = day.weekday() == 3

    for i in range(len(c15)):
        row = c15.iloc[i]
        ts = row['ts_ist']
        hhmm = ts.hour * 100 + ts.minute
        if hhmm < 1100 or hhmm > 1430:
            continue
        candles_so_far = c15.iloc[:i+1]
        for n in zero:
            s = strats[n]
            from dataclasses import replace
            # Remove gates for diagnosis
            s2 = type(s)(name=s.name, direction=s.direction, strike=s.strike,
                entry_start=900, entry_end=1500, sl_pct=s.sl_pct, target_pct=s.target_pct,
                tsl_pts=s.tsl_pts, min_premium=10.0, max_premium=9999.0,
                require_vwap=False, require_volume=False, direction_bias='')
            for d in (['CE','PE'] if s.direction == 'BOTH' else [s.direction]):
                if signal_check(s2, d, candles_so_far, day_ohlc, pcr, hhmm, expiry, 200.0):
                    fire_counts[n][d] += 1

for n in zero:
    print(f"  {n}: CE={fire_counts[n]['CE']} PE={fire_counts[n]['PE']}")

# Now show what condition is blocking each
print()
print("=== Blocking analysis on Apr 7 (best day) ===")
test_day = date(2025, 4, 7)
day_data = opt_data[opt_data['date'] == test_day].copy()
c15 = build_15min_spot(day_data)
r = eod_data[eod_data['dt'] == test_day].iloc[0]
day_ohlc = {'open': r['open'], 'high': r['high'], 'low': r['low']}
pcr = calc_pcr(day_data)
cbar = c15[c15['ts_ist'].dt.hour * 100 + c15['ts_ist'].dt.minute <= 1400]
c = cbar.iloc[-1]
closes = cbar['close'].values.astype(float)
highs = cbar['high'].values.astype(float)
lows  = cbar['low'].values.astype(float)
vols  = cbar['volume'].values.astype(float)
rsi   = calc_rsi(closes)
vwap  = calc_vwap(cbar)
spot  = float(c['close'])
ema5  = float(pd.Series(closes).ewm(span=5, adjust=False).mean().iloc[-1])
ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
cur_vol  = float(vols[-1])
avg5_vol = float(np.mean(vols[-6:-1])) if len(vols) >= 6 else cur_vol
candle_rng = float(c['high']) - float(c['low'])
avg5_rng   = float(np.mean(highs[-5:] - lows[-5:]))
p = cbar.iloc[-2]
pp = cbar.iloc[-3]

print(f"spot={spot:.0f} vwap={vwap:.0f} above={spot>vwap} below={spot<vwap}")
print(f"rsi={rsi:.1f} ema5={ema5:.0f} ema20={ema20:.0f} pcr={pcr:.2f}")
print(f"candle_rng={candle_rng:.1f} avg5_rng={avg5_rng:.1f}")
print(f"candle: open={c['open']:.0f} close={c['close']:.0f} bullish={c['close']>c['open']}")
print(f"p close={p['close']:.0f} pp close={pp['close']:.0f}")
print(f"vol_spike={cur_vol>avg5_vol*1.5} cur_vol={cur_vol:.0f} avg5_vol={avg5_vol:.0f}")
print()
# Diagnose each
print("AI_ENHANCED CE needs: ema5>ema20 AND pcr>1.3 AND rsi<45 AND close>open AND rng>avg5*0.8")
print(f"  ema5>ema20:{ema5>ema20} pcr>1.3:{pcr>1.3} rsi<45:{rsi<45} bullish:{c['close']>c['open']} rng:{candle_rng:.1f}>{avg5_rng*0.8:.1f}:{candle_rng>avg5_rng*0.8}")
print("MEAN_REVERSION PE needs: spot>bb_up AND rsi>65 AND close<open")
if len(closes)>=15:
    bb_mid = float(pd.Series(closes).rolling(15).mean().iloc[-1])
    bb_std = float(pd.Series(closes).rolling(15).std().iloc[-1])
    bb_up = bb_mid + 2.0*bb_std
    bb_dn = bb_mid - 2.0*bb_std
    print(f"  spot={spot:.0f} bb_up={bb_up:.0f} bb_dn={bb_dn:.0f} spot>bb_up:{spot>bb_up} spot<bb_dn:{spot<bb_dn} rsi>65:{rsi>65} rsi<35:{rsi<35}")
print("ENHANCED_BEARISH PE: rsi>65 AND spot<ema5 AND c<p AND ema5<ema20")
print(f"  rsi>65:{rsi>65} spot<ema5:{spot<ema5} c<p:{c['close']<p['close']} ema5<ema20:{ema5<ema20}")
print("OPTIONS_GREEKS PE: rsi>60 AND close<open AND rng>avg5*1.2")
print(f"  rsi>60:{rsi>60} bearish:{c['close']<c['open']} rng:{candle_rng:.1f}>{avg5_rng*1.2:.1f}:{candle_rng>avg5_rng*1.2}")
print("MAGIC_SQUARE PE: near fib618 AND rsi>60 AND ema5<ema20 AND close<open")
fib618 = float(day_ohlc['open']) + (float(day_ohlc['high'])-float(day_ohlc['open']))*0.618
print(f"  fib618={fib618:.0f} spot={spot:.0f} near:{abs(spot-fib618)/spot<0.004} rsi>60:{rsi>60}")
print("ZERO_HERO PE: rng>=avg5*1.5 AND close<open AND rsi>67 AND vol_spike")
print(f"  rng:{candle_rng:.1f}>={avg5_rng*1.5:.1f}:{candle_rng>=avg5_rng*1.5} bearish:{c['close']<c['open']} rsi>67:{rsi>67} vol:{cur_vol>avg5_vol*1.5}")
