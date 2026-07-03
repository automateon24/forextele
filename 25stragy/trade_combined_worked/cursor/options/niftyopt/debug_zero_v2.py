"""
Debug DAY_HIGH_LOW_TRADITIONAL and ZERO_HERO - why 0 trades?
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from BACKTEST_V3_TUNED import (load_option_data, load_eod_data, build_15min_spot,
    calc_pcr, calc_vwap, calc_rsi, signal_check, make_strategies)

opt_data = load_option_data()
eod_data = load_eod_data()
strats = {s.name: s for s in make_strategies()}

zero_strats = ['DAY_HIGH_LOW_TRADITIONAL', 'ZERO_HERO']

print("=" * 80)
print("DEEP DEBUG: Why 0 trades?")
print("=" * 80)

for strat_name in zero_strats:
    s = strats[strat_name]
    print(f"\n{'='*60}")
    print(f"Strategy: {strat_name}")
    print(f"Config: dir={s.direction}, strike={s.strike}, window={s.entry_start}-{s.entry_end}")
    print(f"        prem={s.min_premium}-{s.max_premium}")
    
    fire_count = {'CE': 0, 'PE': 0}
    attempts = []
    
    # Check first 5 trading days only for speed
    for day in sorted(opt_data['date'].unique())[:5]:
        day_data = opt_data[opt_data['date'] == day].copy()
        c15 = build_15min_spot(day_data)
        if len(c15) < 5:
            continue
            
        eod_row = eod_data[eod_data['dt'] == day]
        if eod_row.empty:
            continue
        r = eod_row.iloc[0]
        day_ohlc = {'open': r['open'], 'high': r['high'], 'low': r['low']}
        pcr = calc_pcr(day_data)
        expiry = day.weekday() == 3
        
        for i in range(4, min(10, len(c15))):  # Check first few candles only
            row = c15.iloc[i]
            ts = row['ts_ist']
            hhmm = ts.hour * 100 + ts.minute
            
            if hhmm < s.entry_start or hhmm > s.entry_end:
                continue
                
            candles_so_far = c15.iloc[:i+1]
            
            # Get option premium
            opt_type = 'CE'
            cur_opt_bars = day_data[
                (day_data['option_type_flag'] == opt_type) &
                (day_data['strike'] == s.strike) &
                (day_data['hhmm'] == hhmm)
            ]
            opt_premium = float(cur_opt_bars['close'].iloc[-1]) if len(cur_opt_bars) > 0 else 150.0
            
            for d in (['CE','PE'] if s.direction == 'BOTH' else [s.direction]):
                result = signal_check(s, d, candles_so_far, day_ohlc, pcr, hhmm, expiry, opt_premium)
                
                # Capture diagnostics
                c = candles_so_far.iloc[-1]
                closes = candles_so_far['close'].values.astype(float)
                highs = candles_so_far['high'].values.astype(float)
                lows = candles_so_far['low'].values.astype(float)
                rsi = calc_rsi(closes)
                vwap = calc_vwap(candles_so_far)
                ema5 = float(pd.Series(closes).ewm(span=5, adjust=False).mean().iloc[-1])
                ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
                
                attempts.append({
                    'day': day, 'hhmm': hhmm, 'dir': d, 'fired': result,
                    'rsi': rsi, 'spot': float(c['close']),
                    'ema5': ema5, 'ema20': ema20,
                    'close': float(c['close']), 'open': float(c['open']),
                    'premium': opt_premium,
                    'first_hour_high': max(highs[:4]) if len(highs) >= 4 else max(highs),
                    'first_hour_low': min(lows[:4]) if len(lows) >= 4 else min(lows),
                })
                
                if result:
                    fire_count[d] += 1
    
    print(f"Fire counts: CE={fire_count['CE']}, PE={fire_count['PE']}")
    
    if fire_count['CE'] == 0 and fire_count['PE'] == 0 and attempts:
        print("\nDiagnostics (first 5 attempts):")
        for i, a in enumerate(attempts[:5]):
            print(f"  {i+1}. {a['day']} {a['hhmm']} {a['dir']} rsi={a['rsi']:.1f} fired={a['fired']}")
            print(f"      spot={a['spot']:.0f} ema5={a['ema5']:.0f} ema20={a['ema20']:.0f}")
            print(f"      close={a['close']:.0f} vs open={a['open']:.0f}")
            if strat_name == 'DAY_HIGH_LOW_TRADITIONAL':
                print(f"      1st_hour_high={a['first_hour_high']:.0f} low={a['first_hour_low']:.0f}")
                print(f"      breakout_CE? {a['spot'] > a['first_hour_high'] * 1.0015}")
                print(f"      breakdown_PE? {a['spot'] < a['first_hour_low'] * 0.9985}")
            if strat_name == 'ZERO_HERO':
                strong_bull = a['close'] > a['open'] * 1.01
                strong_bear = a['close'] < a['open'] * 0.99
                print(f"      rsi<40? {a['rsi'] < 40} strong_bull? {strong_bull} ema5>ema20? {a['ema5'] > a['ema20'] * 0.998}")

print("\n" + "=" * 80)
print("FINDINGS:")
print("=" * 80)
print("If close > first_hour_high * 1.0015 is FALSE → breakout threshold too high")
print("If rsi<40 is FALSE → RSI threshold too extreme for ZERO_HERO")
