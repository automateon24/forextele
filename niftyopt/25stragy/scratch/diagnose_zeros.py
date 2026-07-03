import sys, os
sys.path.insert(0, 'C:\\25stragy')
sys.path.insert(0, 'c:/cursor/options/niftyopt')

import pandas as pd
import numpy as np
from collections import defaultdict
from BACKTEST_V8_AI import (
    INDEX_CONFIGS, load_option_data_for_index, build_eod_from_option_data,
    compute_day_context, compute_intraday_state, match_profile,
    get_index_strategy_dna, make_strategies_v8, label_days,
    TRADEABLE_REGIMES, INDEX_PROFILES, signal_check, signal_check_idx,
    calc_rsi
)

def diagnose():
    print("Starting diagnostics...")
    idx_name = 'NIFTY'
    cfg = INDEX_CONFIGS[idx_name]
    opt_data = load_option_data_for_index(idx_name)
    if opt_data.empty:
        print("Error: No data loaded.")
        return
    
    # Limit to first 5 days
    trading_days = sorted(opt_data['date'].unique())[:5]
    opt_data = opt_data[opt_data['date'].isin(trading_days)]
    eod_data = build_eod_from_option_data(opt_data)
    day_regimes = label_days(opt_data)
    
    active_strats = make_strategies_v8()
    idx_profiles = INDEX_PROFILES[idx_name]
    
    grouped_opt = {date: grp for date, grp in opt_data.groupby('date')}
    grouped_eod = {row['dt']: pd.DataFrame([row]) for _, row in eod_data.iterrows()}
    
    # Statistics tracker
    stats = defaultdict(lambda: defaultdict(int))
    
    prev_close = 0.0
    for day in trading_days:
        regime = day_regimes.get(day, 'NORMAL')
        eod_row = grouped_eod.get(day, pd.DataFrame())
        if regime not in TRADEABLE_REGIMES:
            if not eod_row.empty:
                prev_close = float(eod_row.iloc[0]['close'])
            continue
            
        day_data = grouped_opt.get(day, pd.DataFrame()).copy()
        if day_data.empty:
            continue
        
        # 15min spot candles
        from BACKTEST_V3_TUNED import build_15min_spot, calc_pcr
        c15 = build_15min_spot(day_data)
        if len(c15) < 4:
            continue
            
        pcr = calc_pcr(day_data)
        expiry = (day.weekday() == cfg.expiry_dow)
        
        if not eod_row.empty:
            r = eod_row.iloc[0]
            day_ohlc = {k: float(r[k]) for k in ('open','high','low','close')}
        else:
            day_ohlc = {'open': float(c15.iloc[0]['close']),
                        'high': float(c15['high'].max()),
                        'low': float(c15['low'].min()),
                        'close': float(c15.iloc[-1]['close'])}
                        
        ctx = compute_day_context(c15, prev_close, pcr)
        
        for i in range(3, len(c15)):
            row = c15.iloc[i]
            ts = row['ts_ist'] if hasattr(row['ts_ist'], 'hour') else pd.Timestamp(row['ts_ist'])
            hhmm = ts.hour * 100 + ts.minute
            if hhmm < 945 or hhmm > cfg.entry_cutoff:
                continue
                
            state = compute_intraday_state(c15.iloc[:i+1], pcr)
            
            # Load strategy_dna database for regime matrix
            import json
            with open("C:\\25stragy\\strategy_dna.json", 'r') as f:
                strategy_db = json.load(f)
                
            for strat in active_strats:
                stats[strat.name]['checked'] += 1
                
                if strat.name not in idx_profiles:
                    stats[strat.name]['no_profile'] += 1
                    continue
                    
                if hhmm < strat.entry_start or hhmm > strat.entry_end:
                    stats[strat.name]['time_filter'] += 1
                    continue
                    
                regime_matrix = strategy_db.get("strategy_regime_matrix", {})
                compat = regime_matrix.get(strat.name, {}).get(regime, True)
                if not compat:
                    stats[strat.name]['regime_compat'] += 1
                    continue
                    
                dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]
                for direction in dirs:
                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = match_profile(profile, ctx, state, direction)
                    if not armed:
                        stats[strat.name][f'match_profile_failed_{direction}'] += 1
                        stats[strat.name][f'reason_{direction}_{arm_reason}'] += 1
                        continue
                        
                    dna = get_index_strategy_dna(idx_name, strat.name)
                    min_conf = dna.entry_threshold
                    if conf < min_conf:
                        stats[strat.name][f'low_confidence_{direction}'] += 1
                        continue
                        
                    # Option Chain
                    candidates = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if candidates.empty:
                        stats[strat.name][f'no_chain_candidates_{direction}'] += 1
                        continue
                        
                    # Pick strike
                    min_p = min(75.0, strat.min_premium * cfg.premium_scale)
                    max_p = max(220.0, strat.max_premium * cfg.premium_scale)
                    sweet_spot = candidates[
                        (candidates['close'] >= min_p) & 
                        (candidates['close'] <= max_p)
                    ]
                    best_strike = strat.strike
                    if not sweet_spot.empty:
                        max_oi = sweet_spot['oi'].fillna(0).max()
                        if max_oi > 0:
                            liquid = sweet_spot[sweet_spot['oi'].fillna(0) >= max_oi * 0.40]
                            best_row = liquid.loc[liquid['close'].idxmin()]
                            best_strike = best_row['strike']
                        else:
                            candidates_sorted = sweet_spot.iloc[(sweet_spot['close'] - 120.0).abs().argsort()]
                            best_strike = candidates_sorted.iloc[0]['strike']
                    else:
                        candidates_sorted = candidates.iloc[(candidates['close'] - 120.0).abs().argsort()]
                        best_strike = candidates_sorted.iloc[0]['strike']
                        
                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == best_strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        stats[strat.name][f'no_opt_bar_{direction}'] += 1
                        continue
                        
                    prem = float(opt_b['close'].iloc[-1])
                    if prem <= 0:
                        stats[strat.name][f'zero_premium_{direction}'] += 1
                        continue
                        
                    # signal_check_idx
                    try:
                        # Let's check internal conditions of signal_check
                        # signal_check checks min_premium / max_premium, require_vwap, require_volume, and name conditions
                        ok = signal_check_idx(strat, direction, c15.iloc[:i+1],
                                              day_ohlc, pcr, hhmm, expiry, prem, cfg, 
                                              regime, str(day), idx_profiles)
                    except Exception as e:
                        ok = False
                        stats[strat.name][f'signal_check_exception_{direction}'] += 1
                        
                    if not ok:
                        # Find which specific filter inside signal_check failed
                        ok_prem = prem >= (strat.min_premium * cfg.premium_scale) and prem <= (strat.max_premium * cfg.premium_scale)
                        if not ok_prem:
                            stats[strat.name][f'prem_bounds_failed_{direction}_prem_{prem:.1f}_bounds_{strat.min_premium}-{strat.max_premium}'] += 1
                        
                        # Check local conditions
                        c = c15.iloc[:i+1].iloc[-1]
                        closes = c15.iloc[:i+1]['close'].values.astype(float)
                        rsi_val = calc_rsi(pd.Series(closes))
                        # let's log signal_check_failed
                        stats[strat.name][f'signal_check_failed_{direction}'] += 1
                        continue
                        
                    # If we made it here, it triggered!
                    stats[strat.name][f'triggered_{direction}'] += 1

        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    # Print summary
    print("\n=== DIAGNOSTIC SUMMARY ===")
    for sname, sstats in sorted(stats.items()):
        print(f"\nStrategy: {sname}")
        for k, v in sorted(sstats.items()):
            if v > 0:
                print(f"  {k}: {v}")

if __name__ == "__main__":
    diagnose()
