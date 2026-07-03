import sys
import os
import pandas as pd
import numpy as np
import json
import time
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add workspace to path
sys.path.append(r'C:\25stragy')

# Import modules and classes from main script
import BACKTEST_V8_AI as bt

# Define custom run_index that enforces EXPIRY-ONLY trading for all active strategies
def run_index_expiry_only(idx_name: str, opt_data: pd.DataFrame, eod_data: pd.DataFrame, cfg: bt.IndexConfig):
    active_strats = [s for s in bt.make_strategies_v8() if s.name in bt.ACTIVE_STRATEGIES_BY_INDEX.get(idx_name, set())]
    idx_profiles  = bt.INDEX_PROFILES[idx_name]

    trading_days = sorted(opt_data['date'].unique())
    day_regimes  = bt.label_days(opt_data)

    ONE_TRADE_STRATS = {'MAGIC_SQUARE', 'VOLUME_CLIMAX'}

    all_trades: List[bt.Trade] = []
    prev_close = 0.0

    for day in trading_days:
        regime = day_regimes.get(day, 'NORMAL')
        eod_row = eod_data[eod_data['dt'] == day] if not eod_data.empty else pd.DataFrame()

        if regime not in bt.TRADEABLE_REGIMES:
            if not eod_row.empty:
                prev_close = float(eod_row.iloc[0]['close'])
            continue

        day_data = opt_data[opt_data['date'] == day].copy()
        c15      = bt.build_15min_spot(day_data)
        if len(c15) < 4:
            continue

        pcr    = bt.calc_pcr(day_data)
        expiry = (day.weekday() == cfg.expiry_dow) if hasattr(day, 'weekday') else False

        # ── EXCLUSIVELY TRADE ON EXPIRY DAYS ──
        if not expiry:
            if not eod_row.empty:
                prev_close = float(eod_row.iloc[0]['close'])
            continue

        if not eod_row.empty:
            r = eod_row.iloc[0]
            day_ohlc = {k: float(r[k]) for k in ('open','high','low','close')}
        else:
            day_ohlc = {'open':  float(c15.iloc[0]['close']),
                        'high':  float(c15['high'].max()),
                        'low':   float(c15['low'].min()),
                        'close': float(c15.iloc[-1]['close'])}

        ctx = bt.compute_day_context(c15, prev_close, pcr)

        trades_today: Dict[str, int]      = bt.defaultdict(int)
        strat_trades: Dict[str, int]      = bt.defaultdict(int)

        for i in range(3, len(c15)):
            row  = c15.iloc[i]
            ts   = bt._get_ts(row)
            hhmm = ts.hour * 100 + ts.minute
            if hhmm < 945 or hhmm > cfg.entry_cutoff:
                continue

            # Daily Circuit Breaker check
            today_pnl = sum(t.pnl_rs for t in all_trades if t.date == day)
            if today_pnl <= bt.DAILY_CIRCUIT_BREAKER_RS:
                break

            state = bt.compute_intraday_state(c15.iloc[:i+1], pcr)

            for strat in active_strats:
                if strat.name not in idx_profiles:
                    continue

                if hhmm < strat.entry_start or hhmm > strat.entry_end:
                    continue

                from regime_detector import STRATEGY_REGIME_MATRIX
                compat = STRATEGY_REGIME_MATRIX.get(strat.name, {}).get(regime, True)
                if not compat:
                    continue
                if strat.name in ONE_TRADE_STRATS and strat_trades[strat.name] >= 1:
                    continue

                dirs = ['CE','PE'] if strat.direction == 'BOTH' else [strat.direction]

                for direction in dirs:
                    if direction == 'CE' and trades_today['CE'] >= cfg.max_ce_day:
                        continue
                    if direction == 'PE' and trades_today['PE'] >= 15:
                        continue

                    profile = idx_profiles[strat.name]
                    armed, conf, arm_reason = bt.match_profile(profile, ctx, state, direction)
                    if not armed:
                        continue

                    # Threshold check using ENABLE_THRESH_RELAX flag
                    if bt.ENABLE_THRESH_RELAX:
                        dna = bt.get_index_strategy_dna(idx_name, strat.name)
                        min_conf = min(dna.entry_threshold, 0.78)
                    else:
                        min_conf = 0.52

                    if regime == 'EXPLOSIVE_GAP':
                        min_conf_gap = 0.55 if not bt.ENABLE_THRESH_RELAX else max(0.50, min_conf - 0.05)
                        if conf < min_conf_gap:
                            continue
                        conf = min(0.95, conf + 0.08)
                    else:
                        if conf < min_conf:
                            continue

                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        continue

                    prem = float(opt_b['close'].iloc[-1])

                    deploy_cap = bt.CAPITAL_PER_INDEX * bt.get_tier_deploy_pct(strat.name)
                    actual_lots = max(1, min(bt.MAX_LOTS_CAP, int(deploy_cap / (prem * cfg.lot_size))))
                    
                    try:
                        ok = bt.signal_check_idx(strat, direction, c15.iloc[:i+1],
                                               day_ohlc, pcr, hhmm, expiry, prem, cfg, 
                                               regime, str(day))
                    except Exception as e:
                        ok = False
                    if not ok:
                        continue

                    exec_bars = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] > hhmm)
                    ].reset_index(drop=True)
                    if len(exec_bars) < 2:
                        continue

                    entry_bar   = exec_bars.iloc[0]
                    entry_price = float(entry_bar['open'])
                    remaining   = exec_bars.iloc[1:].copy()

                    dynamic_exit = bt.get_dynamic_hard_exit(idx_name, strat.name, regime, expiry)
                    fixed_tgt = bt.FIXED_TARGET_STRATEGIES.get(strat.name)
                    if fixed_tgt:
                        xp, xr, xt = bt.execute_fixed_target_idx(entry_bar, remaining, fixed_tgt, dynamic_exit, idx_name, strat.name, regime)
                    else:
                        xp, xr, xt = bt.execute_tsl_idx(entry_bar, remaining, dynamic_exit, cfg.premium_scale, regime, strat.name, idx_name, expiry)

                    slippage = cfg.slippage_pts
                    pnl_pts = xp - entry_price - slippage
                    pnl_rs  = round(pnl_pts * cfg.lot_size * actual_lots - cfg.brokerage, 2)

                    all_trades.append(bt.Trade(
                        date=day, strategy=strat.name, direction=direction,
                        regime=regime, confidence=conf, lots=actual_lots,
                        entry_time=bt._get_ts(entry_bar),
                        entry_price=entry_price,
                        exit_price=xp, exit_time=xt, exit_reason=xr,
                        pnl_pts=round(pnl_pts, 2), pnl_rs=pnl_rs,
                        won=pnl_rs > 0, armed_reason=arm_reason,
                    ))
                    trades_today[direction] += 1
                    strat_trades[strat.name] += 1
                    break

        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    return all_trades, idx_name

# Patch the engine function in memory
bt.run_index = run_index_expiry_only

# Top 4 profitable expiry strategies
top_4_expiry_strategies = ["ZERO_HERO", "GAMMA_BLAST", "ATR_BREAK", "MOMENTUM_BURST"]

def run_test_profile(capital_per_index: float, max_lots_cap: int, label: str):
    print("\n" + "="*70)
    print(f"RUNNING 4-STRAT EXPIRY PORTFOLIO: {label}")
    print(f"  Capital per index: Rs. {capital_per_index:,} | Max Lots Cap: {max_lots_cap}")
    print("="*70)
    
    # Configure in memory
    bt.CAPITAL_PER_INDEX = capital_per_index
    bt.MAX_LOTS_CAP = max_lots_cap
    bt.ENABLE_REGIME_SCALING = True
    bt.EXPIRY_UNCAP_TIGHT = True
    
    for idx in bt.INDEX_CONFIGS:
        bt.ACTIVE_STRATEGIES_BY_INDEX[idx] = set(top_4_expiry_strategies)

    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, bt.IndexConfig]] = {}
    total_days = 0
    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

    results: Dict[str, List[bt.Trade]] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(bt.run_index, idx_name, opt, eod, cfg): idx_name
            for idx_name, (opt, eod, cfg) in datasets.items()
        }
        for future in as_completed(futures):
            idx_name = futures[future]
            try:
                trades, name = future.result()
                results[name] = trades
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                
    bt.report_multi(results, total_days)

if __name__ == '__main__':
    run_test_profile(250000, 150, "BALANCED AGGRESSIVE (Rs. 250k / 150 lots)")
    run_test_profile(500000, 300, "HYPER AGGRESSIVE (Rs. 500k / 300 lots)")
