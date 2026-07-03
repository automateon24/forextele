import sys
import os
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(r'C:\25stragy')
import BACKTEST_V8_AI as bt

# Implement strict gating in memory
def run_index_sweep(idx_name: str, opt_data: pd.DataFrame, eod_data: pd.DataFrame, cfg: bt.IndexConfig, cap_limit: float):
    base_strats = bt.make_strategies_v8()
    
    with open(r'C:\25stragy\config_ultimate.json', 'r') as f:
        config_db = json.load(f)
    full_active_strats = set(config_db["index_profiles"][idx_name].get("active_strategies", []))
    
    idx_profiles  = bt.INDEX_PROFILES[idx_name]
    trading_days  = sorted(opt_data['date'].unique())
    day_regimes   = bt.label_days(opt_data)

    ONE_TRADE_STRATS = {'MAGIC_SQUARE', 'VOLUME_CLIMAX'}
    all_trades: List[bt.Trade] = []
    prev_close = 0.0

    # Scale daily circuit breaker with capital
    scaled_cb = -9000.0 * (cap_limit / 150000.0)

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

        if expiry:
            allowed_strategies = {"ZERO_HERO", "GAMMA_BLAST"}
        else:
            allowed_strategies = full_active_strats

        active_strats = [s for s in base_strats if s.name in allowed_strategies]

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

            today_pnl = sum(t.pnl_rs for t in all_trades if t.date == day)
            if today_pnl <= scaled_cb:
                break

            active_capital = 0.0
            for t in all_trades:
                if t.date == day:
                    if t.entry_time <= ts < t.exit_time:
                        active_capital += t.entry_price * cfg.lot_size * t.lots

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

                    min_conf = 0.52
                    if regime == 'EXPLOSIVE_GAP':
                        if conf < min_conf:
                            continue
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

                    deploy_cap = cap_limit * bt.get_tier_deploy_pct(strat.name)
                    actual_lots = max(1, min(60, int(deploy_cap / (prem * cfg.lot_size))))
                    
                    required_margin = prem * cfg.lot_size * actual_lots
                    if active_capital + required_margin > cap_limit:
                        continue

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
                    active_capital += required_margin
                    trades_today[direction] += 1
                    strat_trades[strat.name] += 1
                    break

        if not eod_row.empty:
            prev_close = float(eod_row.iloc[0]['close'])

    return all_trades

def sweep():
    # Pre-load datasets once
    print("Pre-loading option and EOD data for sweep...")
    datasets = {}
    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)

    capital_levels = [50000, 75000, 100000, 125000, 150000]
    
    print("\n" + "="*80)
    print("CAPITAL SWEEP RESULTS:")
    print(f"{'Cap/Index (Rs.)':<16} | {'Total Trades':<12} | {'Win Rate':<10} | {'Total PnL (Rs.)':<16} | {'Max Drawdown':<14} | {'ROI (%)':<10}")
    print("-"*80)

    for cap in capital_levels:
        results = {}
        for idx_name, (opt, eod, cfg) in datasets.items():
            trades = run_index_sweep(idx_name, opt, eod, cfg, cap)
            results[idx_name] = trades

        # Combine all trades
        all_trades = []
        for idx_name, trades in results.items():
            for t in trades:
                all_trades.append(t)
        
        if not all_trades:
            print(f"  {cap:<14} | No trades")
            continue

        df = pd.DataFrame([t.__dict__ for t in all_trades])
        total_pnl = df['pnl_rs'].sum()
        wr = 100 * df['won'].mean()
        
        # Combined portfolio drawdown
        df['date'] = pd.to_datetime(df['date'])
        daily_pnl = df.groupby('date')['pnl_rs'].sum()
        cum_pnl = daily_pnl.cumsum()
        portfolio_drawdown = (cum_pnl - cum_pnl.cummax()).min()
        
        total_capital = cap * 4
        roi = 100.0 * total_pnl / total_capital

        print(f"  Rs. {cap:<12,} | {len(df):<12} | {wr:>8.1f}% | Rs. {total_pnl:>+12,.2f} | Rs. {portfolio_drawdown:>+10,.2f} | {roi:>8.1f}%")

if __name__ == '__main__':
    sweep()
