"""
Deep analysis: For every strategy, on every candle in its entry window,
count EXACTLY what blocks the signal from firing.
This tells us precisely what to loosen and by how much.
"""
import sys, warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
from datetime import date
from collections import defaultdict

sys.path.insert(0, '.')
from BACKTEST_V3_TUNED import load_option_data, load_eod_data, build_15min_spot, \
    calc_pcr, calc_vwap, calc_rsi, make_strategies

opt_data = load_option_data()
eod_data = load_eod_data()
strats   = {s.name: s for s in make_strategies()}
all_days = sorted(opt_data['date'].unique())

# ── collect per-day candle snapshots ────────────────────────────────────────
print("Scanning all candles across 58 days...\n")

rows = []
for day in all_days:
    day_data = opt_data[opt_data['date'] == day].copy()
    c15      = build_15min_spot(day_data)
    if len(c15) < 5:
        continue
    eod_row = eod_data[eod_data['dt'] == day]
    if eod_row.empty:
        continue
    r = eod_row.iloc[0]
    day_ohlc = {'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low'])}
    pcr  = calc_pcr(day_data)
    is_expiry = pd.Timestamp(day).weekday() == 3

    for i in range(4, len(c15)):
        row_c = c15.iloc[i]
        ts    = row_c['ts_ist']
        hhmm  = ts.hour * 100 + ts.minute
        candles_so_far = c15.iloc[:i+1]
        closes = candles_so_far['close'].values.astype(float)
        highs  = candles_so_far['high'].values.astype(float)
        lows   = candles_so_far['low'].values.astype(float)
        vols   = candles_so_far['volume'].values.astype(float)

        c   = candles_so_far.iloc[-1]
        p   = candles_so_far.iloc[-2]
        spot = float(c['close'])
        rsi  = calc_rsi(closes)
        vwap = calc_vwap(candles_so_far)
        ema5  = float(pd.Series(closes).ewm(span=5,  adjust=False).mean().iloc[-1])
        ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
        cur_vol   = float(vols[-1]) if len(vols) > 0 else 0
        avg5_vol  = float(np.mean(vols[-6:-1])) if len(vols) >= 6 else cur_vol
        vol_spike = cur_vol > avg5_vol * 1.5 if avg5_vol > 0 else True
        candle_rng = float(c['high']) - float(c['low'])
        avg5_rng   = float(np.mean(highs[-5:] - lows[-5:])) if len(candles_so_far) >= 5 else candle_rng

        rows.append(dict(
            day=day, hhmm=hhmm, is_expiry=is_expiry,
            spot=spot, rsi=rsi, ema5=ema5, ema20=ema20,
            vwap=vwap, above_vwap=spot > vwap, below_vwap=spot < vwap,
            vol_spike=vol_spike, pcr=pcr,
            c_close=float(c['close']), c_open=float(c['open']),
            c_high=float(c['high']),  c_low=float(c['low']),
            p_close=float(p['close']),p_high=float(p['high']),p_low=float(p['low']),
            candle_rng=candle_rng, avg5_rng=avg5_rng,
            day_high=day_ohlc['high'], day_low=day_ohlc['low'],
            n_candles=i+1,
            orb_high=float(candles_so_far.iloc[:4]['high'].max()),
            orb_low=float(candles_so_far.iloc[:4]['low'].min()),
        ))

df = pd.DataFrame(rows)
total_candles = len(df)
print(f"Total candles scanned: {total_candles}")
print("=" * 100)

# ── Per-strategy analysis ────────────────────────────────────────────────────
print(f"\n{'Strategy':<28} {'Window':<12} {'Candles':<10} {'RSI_pass':<10} "
      f"{'EMA_pass':<10} {'Vol_pass':<10} {'All_pass%':<10} {'Trades_possible':<15}")
print("-" * 100)

for name, s in strats.items():
    w = df[(df['hhmm'] >= s.entry_start) & (df['hhmm'] <= s.entry_end)]
    if len(w) == 0:
        continue

    n_candles = len(w)

    if name == 'SHORT_UNWIND':
        rsi_pass = (w['rsi'] > 52).sum()
        ema_pass = (w['ema5'] > w['ema20']).sum()
        vol_pass = (w['above_vwap']).sum()
        pcr_pass = (w['pcr'] < 1.0).sum()
        all_pass = ((w['pcr'] < 1.0) & (w['ema5'] > w['ema20']) & (w['rsi'] > 52) & w['above_vwap']).sum()

    elif name == 'LONG_UNWIND':
        rsi_pass = (w['rsi'] < 48).sum()
        ema_pass = (w['ema5'] < w['ema20']).sum()
        vol_pass = n_candles
        pcr_pass = (w['pcr'] > 1.3).sum()
        all_pass = ((w['pcr'] > 1.3) & (w['ema5'] < w['ema20']) & (w['rsi'] < 48)).sum()

    elif name == 'MEAN_REVERSION':
        rsi_pass_ce = (w['rsi'] < 40).sum()
        rsi_pass_pe = (w['rsi'] > 60).sum()
        all_pass = rsi_pass_ce + rsi_pass_pe
        rsi_pass = all_pass
        ema_pass = n_candles
        vol_pass = n_candles
        pcr_pass = n_candles

    elif name == 'SCALPING':
        rsi_pass = (w['rsi'] > 50).sum()
        ema_pass = (w['ema5'] > w['ema20']).sum()
        vol_pass = w['vol_spike'].sum()
        above_prev = (w['c_close'] > w['p_high']).sum()
        all_pass = ((w['c_close'] > w['p_high']) & (w['rsi'] > 50) & (w['ema5'] > w['ema20']) & w['vol_spike']).sum()
        pcr_pass = above_prev

    elif name == 'DAY_HIGH_BEARISH':
        near_high = (abs(w['spot'] - w['day_high']) / w['day_high'] < 0.004)
        rejection  = w['c_close'] < w['p_low']
        price_cond = near_high | rejection
        rsi_pass   = (w['rsi'] > 58).sum()
        ema_pass   = n_candles
        vol_pass   = n_candles
        all_pass   = (price_cond & (w['rsi'] > 58)).sum()
        pcr_pass   = price_cond.sum()

    elif name == 'DAY_LOW_BULLISH':
        near_low  = (abs(w['spot'] - w['day_low']) / w['day_low'] < 0.004)
        bounce     = w['c_close'] > w['p_high']
        price_cond = near_low | bounce
        rsi_pass   = ((w['rsi'] < 47) | (w['pcr'] > 1.2)).sum()
        ema_pass   = n_candles
        vol_pass   = n_candles
        all_pass   = (price_cond & ((w['rsi'] < 47) | (w['pcr'] > 1.2))).sum()
        pcr_pass   = price_cond.sum()

    elif name == 'DAY_HIGH_LOW_TRADITIONAL':
        orb_break_ce = w['spot'] > w['orb_high'] * 1.002
        orb_break_pe = w['spot'] < w['orb_low']  * 0.998
        ce_all = (orb_break_ce & (w['rsi'] < 52) & (w['ema5'] > w['ema20'])).sum()
        pe_all = (orb_break_pe & (w['rsi'] > 48) & (w['ema5'] < w['ema20'])).sum()
        all_pass = ce_all + pe_all
        rsi_pass = orb_break_ce.sum() + orb_break_pe.sum()
        ema_pass = n_candles
        vol_pass = n_candles
        pcr_pass = n_candles

    elif name == 'ULTIMATE_DAY_HIGH_LOW':
        orb_high_c15 = w.groupby('day').apply(lambda x: x['c_high'].iloc[0]).reset_index(name='orb_h')
        ce_cond = ((w['spot'] > w['orb_high'] * 1.002) & (w['rsi'] > 52) & (w['ema5'] > w['ema20'])).sum()
        pe_cond = ((w['spot'] < w['orb_low']  * 0.998) & (w['rsi'] < 48) & (w['ema5'] < w['ema20'])).sum()
        all_pass = ce_cond + pe_cond
        rsi_pass = ((w['rsi'] > 52) | (w['rsi'] < 48)).sum()
        ema_pass = ((w['ema5'] > w['ema20']) | (w['ema5'] < w['ema20'])).sum()
        vol_pass = n_candles
        pcr_pass = n_candles

    elif name == 'ENHANCED_BEARISH':
        rsi_pass  = (w['rsi'] > 52).sum()
        ema_pass  = (w['ema5'] < w['ema20'] * 1.001).sum()
        vol_pass  = (w['c_close'] < w['c_open']).sum()
        all_pass  = ((w['rsi'] > 52) & (w['ema5'] < w['ema20'] * 1.001) & (w['c_close'] < w['c_open'])).sum()
        pcr_pass  = n_candles

    elif name == 'ENHANCED_BULLISH':
        rsi_pass  = (w['rsi'] < 46).sum()
        ema_pass  = (w['ema5'] > w['ema20'] * 0.999).sum()
        vol_pass  = (w['c_close'] > w['c_open']).sum()
        all_pass  = ((w['rsi'] < 46) & (w['ema5'] > w['ema20'] * 0.999) & (w['c_close'] > w['c_open'])).sum()
        pcr_pass  = n_candles

    elif name == 'TREND_FOLLOWING':
        rsi_pass  = (w['rsi'] < 48).sum()
        ema_pass  = (w['ema5'] < w['ema20']).sum()
        vol_pass  = (w['below_vwap']).sum()
        all_pass  = ((w['ema5'] < w['ema20']) & (w['rsi'] < 48) & w['below_vwap']).sum()
        pcr_pass  = n_candles

    elif name == 'AI_ENHANCED':
        bear = ((w['ema5'] < w['ema20']) & (w['pcr'] < 1.0) & (w['rsi'] > 52) & (w['c_close'] < w['c_open'])).sum()
        bull = ((w['ema5'] > w['ema20']) & (w['pcr'] > 1.3) & (w['rsi'] < 55) & (w['c_close'] > w['c_open'])).sum()
        all_pass = bear + bull
        rsi_pass = ((w['rsi'] > 52) | (w['rsi'] < 55)).sum()
        ema_pass = n_candles
        vol_pass = n_candles
        pcr_pass = ((w['pcr'] < 1.0) | (w['pcr'] > 1.3)).sum()

    elif name == 'OPTIONS_GREEKS':
        pe_cond = ((w['rsi'] > 58) & (w['c_close'] < w['c_open']) & (w['candle_rng'] > w['avg5_rng'])).sum()
        ce_cond = ((w['rsi'] < 42) & (w['c_close'] > w['c_open']) & (w['candle_rng'] > w['avg5_rng'])).sum()
        all_pass = pe_cond + ce_cond
        rsi_pass = ((w['rsi'] > 58) | (w['rsi'] < 42)).sum()
        ema_pass = n_candles
        vol_pass = n_candles
        pcr_pass = n_candles

    elif name == 'ORDER_BLOCK_REVERSAL':
        rsi_pass = ((w['rsi'] > 55) | (w['rsi'] < 45)).sum()
        ema_pass = n_candles
        vol_pass = n_candles
        all_pass = rsi_pass  # simplified
        pcr_pass = n_candles

    elif name == 'RESIST_BREAK':
        rsi_pass  = (w['rsi'] > 52).sum()
        ema_pass  = n_candles
        vol_pass  = n_candles
        all_pass  = rsi_pass  # simplified
        pcr_pass  = n_candles

    elif name == 'MAGIC_SQUARE':
        day_range = w['day_high'] - w['day_low']
        fib618    = w['day_low'] + day_range * 0.618
        fib382    = w['day_low'] + day_range * 0.382
        near618   = abs(w['spot'] - fib618) / (w['spot'] + 0.01) < 0.005
        near382   = abs(w['spot'] - fib382) / (w['spot'] + 0.01) < 0.005
        rsi_pass  = ((w['rsi'] > 55) | (w['rsi'] < 45)).sum()
        price_pass= (near618 | near382).sum()
        all_pass  = ((near618 & (w['rsi'] > 55)) | (near382 & (w['rsi'] < 45))).sum()
        ema_pass  = n_candles
        vol_pass  = n_candles
        pcr_pass  = price_pass

    elif name == 'VOLATILITY_BREAKOUT':
        rsi_pass  = n_candles
        ema_pass  = n_candles
        vol_pass  = w['vol_spike'].sum()
        big_candle= (w['candle_rng'] >= w['avg5_rng'] * 1.8).sum()
        all_pass  = ((w['candle_rng'] >= w['avg5_rng'] * 1.8) & (w['c_close'] < w['c_open']) &
                     (w['c_close'] < w['p_low']) & w['vol_spike']).sum()
        pcr_pass  = big_candle

    elif name == 'ZERO_HERO':
        rsi_pass = ((w['rsi'] < 40) | (w['rsi'] > 60)).sum()
        ema_pass = n_candles
        vol_pass = n_candles
        all_pass_ce = ((w['rsi'] < 40) & (w['c_close'] > w['c_open'])).sum()
        all_pass_pe = ((w['rsi'] > 60) & (w['c_close'] < w['c_open'])).sum()
        all_pass = all_pass_ce + all_pass_pe
        pcr_pass = n_candles

    elif name == 'GAMMA_BLAST':
        w_exp = w[w['is_expiry']]
        rsi_pass = len(w_exp)
        big_candle = (w_exp['candle_rng'] >= w_exp['avg5_rng'] * 1.5).sum() if len(w_exp) else 0
        all_pass = big_candle
        ema_pass = n_candles
        vol_pass = n_candles
        pcr_pass = n_candles

    elif name == 'PUT_WRITER_SUPPORT':
        rsi_pass = (w['rsi'] < 45).sum()
        ema_pass = n_candles
        vol_pass = (w['c_close'] > w['c_open']).sum()
        pcr_pass = (w['pcr'] > 1.5).sum()
        near_low = (abs(w['spot'] - w['day_low']) / w['day_low'] < 0.008)
        all_pass = ((w['pcr'] > 1.5) & (w['rsi'] < 45) & (w['c_close'] > w['c_open']) & near_low).sum()

    else:
        all_pass = 0
        rsi_pass = 0
        ema_pass = 0
        vol_pass = 0
        pcr_pass = 0

    pct = 100.0 * all_pass / n_candles if n_candles else 0
    print(f"{name:<28} {s.entry_start}-{s.entry_end:<6} {n_candles:<10} "
          f"{100*rsi_pass/n_candles:>6.1f}%   {100*ema_pass/n_candles:>6.1f}%   "
          f"{100*vol_pass/n_candles:>6.1f}%   {pct:>6.2f}%    {all_pass}")

print("\n" + "=" * 100)
print("BOTTLENECK DETAIL PER STRATEGY")
print("=" * 100)

# Detailed RSI distribution for key strategies
key_strats = ['SHORT_UNWIND','DAY_HIGH_LOW_TRADITIONAL','ZERO_HERO','BREAKOUT',
              'LONG_UNWIND','PUT_WRITER_SUPPORT','VOLATILITY_BREAKOUT','MAGIC_SQUARE']
for name in key_strats:
    s    = strats[name]
    w    = df[(df['hhmm'] >= s.entry_start) & (df['hhmm'] <= s.entry_end)]
    if len(w) == 0:
        continue
    rsi_pcts = [5,10,25,40,50,60,75,90,95]
    rsi_vals = np.percentile(w['rsi'], rsi_pcts)
    pcr_vals = np.percentile(w['pcr'], [25,50,75])
    print(f"\n{name}  (window {s.entry_start}-{s.entry_end}, {len(w)} candles)")
    print(f"  RSI distribution: " + "  ".join([f"p{p}={v:.0f}" for p,v in zip(rsi_pcts, rsi_vals)]))
    print(f"  PCR distribution: p25={pcr_vals[0]:.2f}  median={pcr_vals[1]:.2f}  p75={pcr_vals[2]:.2f}")
    print(f"  Vol spike %:      {100*w['vol_spike'].mean():.0f}%")
    print(f"  EMA5>EMA20 %:     {100*(w['ema5']>w['ema20']).mean():.0f}%")
    if name == 'DAY_HIGH_LOW_TRADITIONAL':
        orb_break_ce = (w['spot'] > w['orb_high'] * 1.002).mean()
        orb_break_pe = (w['spot'] < w['orb_low']  * 0.998).mean()
        print(f"  ORB break CE %:   {100*orb_break_ce:.1f}%  (spot>ORB_high by 0.2%)")
        print(f"  ORB break PE %:   {100*orb_break_pe:.1f}%  (spot<ORB_low by 0.2%)")
        print(f"  ORB break 0.1% CE:{100*(w['spot']>w['orb_high']*1.001).mean():.1f}%")
        print(f"  ORB break 0.1% PE:{100*(w['spot']<w['orb_low']*0.999).mean():.1f}%")
