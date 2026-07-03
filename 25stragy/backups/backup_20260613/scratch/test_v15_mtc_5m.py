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

# Define custom run_index with 5-minute micro-confirmation (MTC)
def run_index_v15_mtc(idx_name: str, opt_data: pd.DataFrame, eod_data: pd.DataFrame, cfg: bt.IndexConfig):
    print(f"  [{idx_name}] Starting backtest with 5-Min MTC...", flush=True)
    active_strats = [s for s in bt.make_strategies_v8() if s.name in bt.ACTIVE_STRATEGIES_BY_INDEX.get(idx_name, set())]
    idx_profiles  = bt.INDEX_PROFILES[idx_name]

    trading_days = sorted(opt_data['date'].unique())
    day_regimes  = bt.label_days(opt_data)

    # Pre-build a map of day -> 1-minute spot series for fast lookups
    spot_by_day_1m = {}
    for day, group in opt_data.groupby('date'):
        ce_group = group[group['option_type_flag'] == 'CE']
        if not ce_group.empty:
            spot_by_day_1m[day] = ce_group[['hhmm', 'spot']].drop_duplicates('hhmm').set_index('hhmm')['spot'].to_dict()

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

        # Get 1-minute spot mapping for today
        day_spot_1m = spot_by_day_1m.get(day, {})

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

                    # ── V15.0 5-Minute Micro-Timeframe Confirmation (MTC) ──
                    # Enforce that the micro-trend (last 5 minutes) aligns with direction.
                    # e.g., if CE: spot(hhmm) > spot(hhmm - 5m)
                    # For 15m candle close at hhmm, the 5m close is at hhmm. The previous 5m close was hhmm - 5m.
                    # In hhmm math, subtracting 5 minutes:
                    minute = hhmm % 100
                    hour = hhmm // 100
                    if minute >= 5:
                        prev_hhmm = hour * 100 + (minute - 5)
                    else:
                        # Wrap hour back
                        prev_hhmm = (hour - 1) * 100 + (60 + minute - 5)
                    
                    spot_now = day_spot_1m.get(hhmm)
                    spot_prev = day_spot_1m.get(prev_hhmm)
                    
                    # If we don't have exact minute data, check nearest values
                    if spot_now is None:
                        spot_now = float(row['close']) # Use 15m candle close as fallback
                    if spot_prev is None:
                        # Search back up to 6 minutes
                        for offset in range(1, 7):
                            test_min = prev_hhmm - offset
                            if test_min % 100 > 59: # handle clock bounds
                                continue
                            if test_min in day_spot_1m:
                                spot_prev = day_spot_1m[test_min]
                                break
                    
                    if spot_now is not None and spot_prev is not None:
                        if direction == 'CE' and spot_now <= spot_prev:
                            continue # Block CE: spot went down or remained flat over last 5m
                        if direction == 'PE' and spot_now >= spot_prev:
                            continue # Block PE: spot went up or remained flat over last 5m

                    opt_b = day_data[
                        (day_data['option_type_flag'] == direction) &
                        (day_data['strike'] == strat.strike) &
                        (day_data['hhmm'] == hhmm)
                    ]
                    if len(opt_b) == 0:
                        continue

                    prem = float(opt_b['close'].iloc[-1])

                    # V14 Premium-Adaptive Sizing (Risk Management)
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

    print(f"  [{idx_name}] Done — {len(all_trades)} trades", flush=True)
    return all_trades, idx_name

# Patch the engine function in memory
bt.run_index = run_index_v15_mtc

# Optimized 23 active list
final_active_23 = [
    "ZERO_HERO", "BEAR_TREND_FOLLOWER", "MACD_DIVERGENCE", "MOMENTUM_BURST",
    "VWAP_BOUNCE", "GAMMA_BLAST", "OPTIONS_GREEKS", "SCALPING", "MAGIC_SQUARE",
    "BOLLINGER_SQUEEZE", "ATR_BREAK", "ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH",
    "EMA_CROSSOVER", "VOLUME_CLIMAX", "RSI_REVERSAL", "DAY_HIGH_BEARISH",
    "LONG_UNWIND", "TREND_FOLLOWING", "PUT_WRITER_SUPPORT", "AI_ENHANCED",
    "BREAKOUT", "RESIST_BREAK"
]

config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

for idx in config['index_profiles']:
    config['index_profiles'][idx]['active_strategies'] = final_active_23

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

def main():
    print("=" * 70)
    print("RUNNING V15 MTC (5-MINUTE SPOT CONFIRMATION) BACKTEST")
    print("=" * 70)

    # ── Step 1: Load real parquets for each index ─────────────────────────────
    print("\nLoading option data for all indices...")
    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, bt.IndexConfig]] = {}
    total_days = 0

    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            print(f"  [{idx_name}] SKIPPED — no parquets found")
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

    print(f"\nLoaded {len(datasets)} indices: {list(datasets.keys())}")

    # ── Step 2: Run all indices in parallel threads ───────────────────────────
    print(f"\nRunning backtests in parallel...")
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
                print(f"  [{name}] Completed: {len(trades)} trades", flush=True)
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                import traceback; traceback.print_exc()

    # ── Step 3: Report ────────────────────────────────────────────────────────
    print()
    bt.report_multi(results, total_days)

if __name__ == '__main__':
    main()
