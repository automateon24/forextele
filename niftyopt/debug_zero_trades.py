"""
Deep diagnostic: Why are these 4 strategies firing 0 trades?
- DAY_HIGH_LOW_TRADITIONAL
- ENHANCED_BEARISH
- ENHANCED_BULLISH  
- ZERO_HERO
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
import pandas as pd, numpy as np
from BACKTEST_V3_TUNED import (load_option_data, load_eod_data, build_15min_spot,
    calc_pcr, calc_vwap, calc_rsi, signal_check, make_strategies, STRIKES)
from datetime import date

opt_data = load_option_data()
eod_data = load_eod_data()
strats = {s.name: s for s in make_strategies()}

zero_strats = ['DAY_HIGH_LOW_TRADITIONAL', 'ENHANCED_BEARISH', 'ENHANCED_BULLISH', 'ZERO_HERO']

print("=" * 80)
print("ZERO TRADE STRATEGY DIAGNOSTIC")
print("=" * 80)

for strat_name in zero_strats:
    s = strats[strat_name]
    print(f"\n{'='*40}")
    print(f"Strategy: {strat_name}")
    print(f"Config: dir={s.direction}, strike={s.strike}, window={s.entry_start}-{s.entry_end}")
    print(f"        vwap={s.require_vwap}, vol={s.require_volume}, prem={s.min_premium}-{s.max_premium}")
    
    fire_count = {'CE': 0, 'PE': 0}
    fail_reasons = []
    
    for day in sorted(opt_data['date'].unique()):
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
        
        for i in range(4, len(c15)):
            row = c15.iloc[i]
            ts = row['ts_ist']
            hhmm = ts.hour * 100 + ts.minute
            
            if hhmm < s.entry_start or hhmm > s.entry_end:
                continue
                
            candles_so_far = c15.iloc[:i+1]
            
            # Get option premium for this strike
            opt_type = 'CE'
            cur_opt_bars = day_data[
                (day_data['option_type_flag'] == opt_type) &
                (day_data['strike'] == s.strike) &
                (day_data['hhmm'] == hhmm)
            ]
            opt_premium = float(cur_opt_bars['close'].iloc[-1]) if len(cur_opt_bars) > 0 else 150.0
            
            for d in (['CE','PE'] if s.direction == 'BOTH' else [s.direction]):
                result = signal_check(s, d, candles_so_far, day_ohlc, pcr, hhmm, expiry, opt_premium)
                
                if result:
                    fire_count[d] += 1
                else:
                    # Capture why it failed on first attempt
                    if len(fail_reasons) < 10 and fire_count[d] == 0:
                        c = candles_so_far.iloc[-1]
                        p = candles_so_far.iloc[-2]
                        closes = candles_so_far['close'].values.astype(float)
                        highs = candles_so_far['high'].values.astype(float)
                        lows = candles_so_far['low'].values.astype(float)
                        vols = candles_so_far['volume'].values.astype(float)
                        rsi = calc_rsi(closes)
                        vwap = calc_vwap(candles_so_far)
                        spot = float(c['close'])
                        ema5 = float(pd.Series(closes).ewm(span=5, adjust=False).mean().iloc[-1])
                        ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
                        candle_rng = float(c['high']) - float(c['low'])
                        avg5_rng = float(np.mean(highs[-5:] - lows[-5:]))
                        cur_vol = float(vols[-1])
                        avg5_vol = float(np.mean(vols[-5:]))
                        vol_spike = cur_vol > avg5_vol * 1.5
                        
                        day_open = float(day_ohlc['open'])
                        day_high = float(day_ohlc['high'])
                        day_low = float(day_ohlc['low'])
                        
                        fail_reasons.append({
                            'date': day, 'hhmm': hhmm, 'dir': d,
                            'spot': spot, 'vwap': vwap, 'rsi': rsi,
                            'ema5': ema5, 'ema20': ema20,
                            'candle': c['close'], 'open_candle': c['open'],
                            'candle_rng': candle_rng, 'avg5_rng': avg5_rng,
                            'vol_spike': vol_spike, 'pcr': pcr,
                            'premium': opt_premium,
                            'day_range_pct': (day_high - day_low) / day_open * 100
                        })
    
    print(f"Fire counts: CE={fire_count['CE']}, PE={fire_count['PE']}")
    
    if fire_count['CE'] == 0 and fire_count['PE'] == 0 and fail_reasons:
        print("\nSample conditions when signal CHECKED but FAILED:")
        for i, f in enumerate(fail_reasons[:3]):
            print(f"  Attempt {i+1}: {f['date']} {f['hhmm']} {f['dir']}")
            print(f"    spot={f['spot']:.0f} vwap={f['vwap']:.0f} rsi={f['rsi']:.1f}")
            print(f"    ema5={f['ema5']:.0f} ema20={f['ema20']:.0f} ema5>ema20:{f['ema5']>f['ema20']}")
            print(f"    candle={f['candle']:.0f} vs open={f['open_candle']:.0f} bullish:{f['candle']>f['open_candle']}")
            print(f"    day_range={f['day_range_pct']:.2f}% | premium={f['premium']:.0f} | pcr={f['pcr']:.2f}")
            
            # Strategy-specific diagnostics
            if strat_name == 'DAY_HIGH_LOW_TRADITIONAL':
                intra_high = max([f['spot']] + [x['spot'] for x in fail_reasons[:i+1]])
                intra_low = min([f['spot']] + [x['spot'] for x in fail_reasons[:i+1]])
                print(f"    DIAGNOSTIC: spot > intra_high*1.001? {f['spot'] > intra_high * 1.001}")
                print(f"    spot < intra_low*0.999? {f['spot'] < intra_low * 0.999}")
                
            elif strat_name in ['ENHANCED_BEARISH', 'ENHANCED_BULLISH']:
                if f['dir'] == 'PE':
                    print(f"    ENHANCED_BEARISH check: rsi>55? {f['rsi'] > 55} | ema5<ema20? {f['ema5'] < f['ema20']} | bearish? {f['candle'] < f['open_candle']}")
                else:
                    print(f"    ENHANCED_BULLISH check: rsi<45? {f['rsi'] < 45} | ema5>ema20? {f['ema5'] > f['ema20']} | bullish? {f['candle'] > f['open_candle']}")
                    
            elif strat_name == 'ZERO_HERO':
                rsi_bear = 60 if f['date'].weekday() == 3 else 65
                rsi_bull = 40 if f['date'].weekday() == 3 else 35
                if f['dir'] == 'PE':
                    print(f"    ZERO_HERO PE: rsi>{rsi_bear}? {f['rsi'] > rsi_bear} | ema5<ema20? {f['ema5'] < f['ema20']} | bearish? {f['candle'] < f['open_candle']}")
                else:
                    print(f"    ZERO_HERO CE: rsi<{rsi_bull}? {f['rsi'] < rsi_bull} | ema5>ema20? {f['ema5'] > f['ema20']} | bullish? {f['candle'] > f['open_candle']}")
                print(f"    Premium check: {s.min_premium} <= {f['premium']:.0f} <= {s.max_premium}? {s.min_premium <= f['premium'] <= s.max_premium}")

print("\n" + "=" * 80)
print("KEY FINDINGS:")
print("=" * 80)
print("1. If fire_count=0 and conditions ARE met → Logic bug in signal_check")
print("2. If fire_count=0 and conditions NOT met → Thresholds too strict")
print("3. Check if premium filter is blocking ZERO_HERO (ATM+2 may not exist in data)")
