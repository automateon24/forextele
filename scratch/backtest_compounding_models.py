"""
BREAKOUTBOSS COMPOUNDING & DYNAMIC LOT SIZING BACKTEST
======================================================
Tests 5 Compounding & Dynamic Lot Sizing Models on 1-Month Historical Gold M1 Data:
1. Baseline: Fixed 0.02 Lots (No Compounding)
2. Model 1 : Linear Equity Compounding (0.02 lots per $1,000 equity)
3. Model 2 : Milestone Step-Ladder Compounding ($1.5k -> 0.03, $2.2k -> 0.04, $3k -> 0.06...)
4. Model 3 : AI Conviction Dynamic Compounding (Equity Scaling x Session Win-Rate Weight)
5. Model 4 : Aggressive Half-Kelly Compounding (0.03 lots per $1,000 equity)
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta, time
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def fetch_gold_m1(days=35):
    if not mt5.initialize():
        print("❌ Could not initialize MT5")
        return pd.DataFrame()
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_M1, from_date, now)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time_utc', inplace=True)
    df.sort_index(inplace=True)
    return df

def run_simulation(df, model_name="BASELINE", initial_capital=1000.0, spread=0.25):
    sessions = [
        {"name": "Asian Open", "code": "ASIA", "time": (1, 0), "duration": 5, "conviction": 0.70},
        {"name": "Frankfurt Open", "code": "FRA", "time": (6, 0), "duration": 4, "conviction": 1.35},
        {"name": "London Core", "code": "LON", "time": (8, 0), "duration": 4, "conviction": 1.00},
        {"name": "NY Pre-Mkt", "code": "NYP", "time": (12, 30), "duration": 3, "conviction": 1.15},
        {"name": "NY Cash", "code": "NYC", "time": (13, 30), "duration": 3, "conviction": 1.15},
        {"name": "London Close", "code": "LNC", "time": (15, 30), "duration": 3, "conviction": 1.35}
    ]
    timeframes = [1, 3, 5, 15]
    rr_ratios = [1.0, 1.5, 2.0, 3.0, 5.0]
    dates = np.unique(df.index.date)
    eod_cutoff = time(20, 50)
    retest_tol = 0.25
    
    balance = initial_capital
    equity = initial_capital
    peak_equity = initial_capital
    max_floating_dd_usd = 0.0
    max_floating_dd_pct = 0.0
    peak_concurrent_trades = 0
    peak_margin_used = 0.0
    lowest_margin_level = 999999.0
    
    all_closed_trades = []
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < 60:
            continue
            
        active_trades = []
        day_setups = []
        
        # Build setups for this day
        for s in sessions:
            sh, sm = s["time"]
            s_start = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
            session_candles = day_df[day_df.index >= s_start]
            
            for tf in timeframes:
                if len(session_candles) < tf + 10:
                    continue
                ref_candles = session_candles[(session_candles.index >= s_start) & (session_candles.index < s_start + timedelta(minutes=tf))]
                if len(ref_candles) < tf:
                    continue
                ref_h = ref_candles['high'].max()
                ref_l = ref_candles['low'].min()
                ref_sz = ref_h - ref_l
                ref_m = (ref_h + ref_l) / 2.0
                caps = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
                if ref_sz < 0.35 or ref_sz > caps.get(tf, 8.00):
                    continue
                    
                w_start = s_start + timedelta(minutes=tf)
                w_end = min(s_start + timedelta(hours=s["duration"]), datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc))
                
                for rr in rr_ratios:
                    day_setups.append({
                        "session_name": s["name"],
                        "session_code": s["code"],
                        "conviction": s["conviction"],
                        "tf": tf,
                        "rr": rr,
                        "ref_h": ref_h,
                        "ref_l": ref_l,
                        "ref_m": ref_m,
                        "w_start": w_start,
                        "w_end": w_end,
                        "broken_bull": False,
                        "broken_bear": False,
                        "triggered": False
                    })
                    
        # Minute-by-minute simulation
        for t, row in day_df.iterrows():
            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            remaining_trades = []
            for tr in active_trades:
                lots = tr["lot_size"]
                lot_mult = lots * 100.0 # $100 per point for 1.0 lot, so $2/pt for 0.02
                
                # EOD Auto-Close
                if t.time() >= eod_cutoff:
                    exit_p = c_close
                    pnl_pts = (exit_p - tr["entry"]) if tr["dir"] == "BUY" else (tr["entry"] - exit_p)
                    pnl_usd = pnl_pts * lot_mult
                    balance += pnl_usd
                    all_closed_trades.append({
                        "pnl_usd": pnl_usd,
                        "lots": lots,
                        "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                    })
                    continue
                    
                closed = False
                if tr["dir"] == "BUY":
                    if not tr["is_be"] and (c_high >= tr["entry"] + tr["risk"]):
                        tr["sl"] = tr["entry"] + 0.10
                        tr["is_be"] = True
                        
                    if c_low <= tr["sl"]:
                        pnl_pts = tr["sl"] - tr["entry"]
                        pnl_usd = pnl_pts * lot_mult
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "lots": lots,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                        })
                        closed = True
                    elif c_high >= tr["tp"]:
                        pnl_pts = tr["tp"] - tr["entry"]
                        pnl_usd = pnl_pts * lot_mult
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "lots": lots,
                            "result": "WIN"
                        })
                        closed = True
                        
                elif tr["dir"] == "SELL":
                    if not tr["is_be"] and (c_low <= tr["entry"] - tr["risk"]):
                        tr["sl"] = tr["entry"] - 0.10
                        tr["is_be"] = True
                        
                    if c_high >= tr["sl"]:
                        pnl_pts = tr["entry"] - tr["sl"]
                        pnl_usd = pnl_pts * lot_mult
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "lots": lots,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                        })
                        closed = True
                    elif c_low <= tr["tp"]:
                        pnl_pts = tr["entry"] - tr["tp"]
                        pnl_usd = pnl_pts * lot_mult
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "lots": lots,
                            "result": "WIN"
                        })
                        closed = True
                        
                if not closed:
                    remaining_trades.append(tr)
                    
            active_trades = remaining_trades
            
            # Check for new entries
            if t.time() < eod_cutoff:
                for st in day_setups:
                    if st["triggered"] or t < st["w_start"] or t > st["w_end"]:
                        continue
                    ref_h = st["ref_h"]
                    ref_l = st["ref_l"]
                    ref_m = st["ref_m"]
                    tf = st["tf"]
                    
                    if not st["broken_bull"] and not st["broken_bear"]:
                        if c_high > ref_h + retest_tol:
                            st["broken_bull"] = True
                        elif c_low < ref_l - retest_tol:
                            st["broken_bear"] = True
                    elif st["broken_bull"]:
                        if c_low <= ref_h + retest_tol and c_high >= ref_h - retest_tol:
                            if (c_close >= c_open) or (c_close > ref_h):
                                entry_p = ref_h + spread
                                sl_p = ref_l if tf == 1 else (max(ref_l, entry_p - 2.50) if tf == 3 else max(ref_m, entry_p - 3.00))
                                risk = entry_p - sl_p
                                if risk < 0.60:
                                    risk = 0.80
                                tp_p = entry_p + (risk * st["rr"])
                                
                                # Dynamic Lot Sizing Logic based on Model
                                current_equity = balance + sum(
                                    ((c_close - tr["entry"]) if tr["dir"] == "BUY" else (tr["entry"] - c_close)) * (tr["lot_size"] * 100.0)
                                    for tr in active_trades
                                )
                                current_capital = max(current_equity, balance * 0.80)
                                
                                if model_name == "BASELINE":
                                    trade_lots = 0.02
                                elif model_name == "LINEAR_EQUITY":
                                    # 0.02 lots per $1,000 equity (0.01 lot per $500)
                                    trade_lots = round(max(0.01, (current_capital / 1000.0) * 0.02), 2)
                                    trade_lots = min(trade_lots, 0.40) # Safety ceiling
                                elif model_name == "STEP_LADDER":
                                    # Step-ladder milestones
                                    if current_capital < 1400:
                                        trade_lots = 0.02
                                    elif current_capital < 2000:
                                        trade_lots = 0.03
                                    elif current_capital < 2800:
                                        trade_lots = 0.04
                                    elif current_capital < 3800:
                                        trade_lots = 0.06
                                    elif current_capital < 5000:
                                        trade_lots = 0.08
                                    else:
                                        trade_lots = 0.10
                                elif model_name == "AI_CONVICTION":
                                    # Base linear scaling * session conviction factor
                                    base_lots = (current_capital / 1000.0) * 0.02
                                    weighted_lots = base_lots * st["conviction"]
                                    trade_lots = round(max(0.01, weighted_lots), 2)
                                    trade_lots = min(trade_lots, 0.40)
                                elif model_name == "AGGRESSIVE_HALF_KELLY":
                                    # 0.03 lots per $1,000 equity
                                    trade_lots = round(max(0.01, (current_capital / 1000.0) * 0.03), 2)
                                    trade_lots = min(trade_lots, 0.50)
                                else:
                                    trade_lots = 0.02
                                    
                                active_trades.append({
                                    "session": st["session_name"],
                                    "tf": tf,
                                    "rr": st["rr"],
                                    "dir": "BUY",
                                    "entry": entry_p,
                                    "sl": sl_p,
                                    "tp": tp_p,
                                    "risk": risk,
                                    "is_be": False,
                                    "lot_size": trade_lots
                                })
                                st["triggered"] = True
                                
                    elif st["broken_bear"]:
                        if c_high >= ref_l - retest_tol and c_low <= ref_l + retest_tol:
                            if (c_close <= c_open) or (c_close < ref_l):
                                entry_p = ref_l - spread
                                sl_p = ref_h if tf == 1 else (min(ref_h, entry_p + 2.50) if tf == 3 else min(ref_m, entry_p + 3.00))
                                risk = sl_p - entry_p
                                if risk < 0.60:
                                    risk = 0.80
                                tp_p = entry_p - (risk * st["rr"])
                                
                                current_equity = balance + sum(
                                    ((c_close - tr["entry"]) if tr["dir"] == "BUY" else (tr["entry"] - c_close)) * (tr["lot_size"] * 100.0)
                                    for tr in active_trades
                                )
                                current_capital = max(current_equity, balance * 0.80)
                                
                                if model_name == "BASELINE":
                                    trade_lots = 0.02
                                elif model_name == "LINEAR_EQUITY":
                                    trade_lots = round(max(0.01, (current_capital / 1000.0) * 0.02), 2)
                                    trade_lots = min(trade_lots, 0.40)
                                elif model_name == "STEP_LADDER":
                                    if current_capital < 1400:
                                        trade_lots = 0.02
                                    elif current_capital < 2000:
                                        trade_lots = 0.03
                                    elif current_capital < 2800:
                                        trade_lots = 0.04
                                    elif current_capital < 3800:
                                        trade_lots = 0.06
                                    elif current_capital < 5000:
                                        trade_lots = 0.08
                                    else:
                                        trade_lots = 0.10
                                elif model_name == "AI_CONVICTION":
                                    base_lots = (current_capital / 1000.0) * 0.02
                                    weighted_lots = base_lots * st["conviction"]
                                    trade_lots = round(max(0.01, weighted_lots), 2)
                                    trade_lots = min(trade_lots, 0.40)
                                elif model_name == "AGGRESSIVE_HALF_KELLY":
                                    trade_lots = round(max(0.01, (current_capital / 1000.0) * 0.03), 2)
                                    trade_lots = min(trade_lots, 0.50)
                                else:
                                    trade_lots = 0.02
                                    
                                active_trades.append({
                                    "session": st["session_name"],
                                    "tf": tf,
                                    "rr": st["rr"],
                                    "dir": "SELL",
                                    "entry": entry_p,
                                    "sl": sl_p,
                                    "tp": tp_p,
                                    "risk": risk,
                                    "is_be": False,
                                    "lot_size": trade_lots
                                })
                                st["triggered"] = True
                                
            # Real-time Floating Equity & Margin Tracking
            floating_pnl = 0.0
            margin_used = 0.0
            for tr in active_trades:
                lots = tr["lot_size"]
                lot_mult = lots * 100.0
                if tr["dir"] == "BUY":
                    floating_pnl += (c_close - tr["entry"]) * lot_mult
                else:
                    floating_pnl += (tr["entry"] - c_close) * lot_mult
                # 1:1000 leverage on Gold @ ~$4,300: Margin = lots * 100 * price / 1000 ~= lots * 430 USD
                margin_used += lots * 430.0
                
            curr_equity = balance + floating_pnl
            if curr_equity > peak_equity:
                peak_equity = curr_equity
                
            drawdown_usd = peak_equity - curr_equity
            drawdown_pct = (drawdown_usd / peak_equity * 100.0) if peak_equity > 0 else 0.0
            
            if drawdown_usd > max_floating_dd_usd:
                max_floating_dd_usd = drawdown_usd
                max_floating_dd_pct = drawdown_pct
                
            if len(active_trades) > peak_concurrent_trades:
                peak_concurrent_trades = len(active_trades)
                
            if margin_used > peak_margin_used:
                peak_margin_used = margin_used
                
            if margin_used > 0:
                ml = (curr_equity / margin_used) * 100.0
                if ml < lowest_margin_level:
                    lowest_margin_level = ml
                    
    # Metrics
    total_trades = len(all_closed_trades)
    wins = sum(1 for tr in all_closed_trades if tr["result"] == "WIN")
    losses = sum(1 for tr in all_closed_trades if tr["result"] == "LOSS")
    bes = sum(1 for tr in all_closed_trades if tr["result"] == "BE")
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    
    gross_profit = sum(tr["pnl_usd"] for tr in all_closed_trades if tr["pnl_usd"] > 0)
    gross_loss = abs(sum(tr["pnl_usd"] for tr in all_closed_trades if tr["pnl_usd"] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
    
    net_profit = balance - initial_capital
    roi_pct = (net_profit / initial_capital) * 100.0
    avg_lot = np.mean([tr["lots"] for tr in all_closed_trades]) if total_trades > 0 else 0.02
    max_lot = max([tr["lots"] for tr in all_closed_trades]) if total_trades > 0 else 0.02
    
    return {
        "model": model_name,
        "initial_capital": initial_capital,
        "final_balance": round(balance, 2),
        "net_profit": round(net_profit, 2),
        "roi_pct": round(roi_pct, 1),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "bes": bes,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "max_floating_dd_usd": round(max_floating_dd_usd, 2),
        "max_floating_dd_pct": round(max_floating_dd_pct, 1),
        "peak_margin_used": round(peak_margin_used, 2),
        "lowest_margin_level": round(lowest_margin_level, 1),
        "peak_concurrent_trades": peak_concurrent_trades,
        "avg_lot": round(avg_lot, 3),
        "max_lot": round(max_lot, 2)
    }

def main():
    print("=" * 85)
    print("  🚀 BREAKOUTBOSS 1-MONTH COMPOUNDING & DYNAMIC LOT SIZING BACKTEST")
    print("  Comparing 5 Dynamic Lot Sizing & Compounding Models on Gold M1 Data")
    print("=" * 85)
    
    print("\n⏳ Fetching 35 days of high-resolution Gold M1 data from MT5...")
    df = fetch_gold_m1(35)
    if df.empty:
        print("❌ Failed to fetch data.")
        return
        
    start_d = df.index.min().strftime('%Y-%m-%d')
    end_d = df.index.max().strftime('%Y-%m-%d')
    print(f"✅ Data Loaded: {len(df):,} M1 candles from {start_d} to {end_d} ({len(np.unique(df.index.date))} trading days)\n")
    
    models = [
        ("BASELINE", "1. Baseline (Fixed 0.02 Lots - No Compounding)"),
        ("STEP_LADDER", "2. Milestone Step-Ladder ($1k: 0.02, $1.5k: 0.03, $2.2k: 0.04...)"),
        ("LINEAR_EQUITY", "3. Linear Equity Compounding (0.02 lots per $1,000 equity)"),
        ("AI_CONVICTION", "4. AI Conviction Weighted Compounding (Equity x Win-Rate Kelly)"),
        ("AGGRESSIVE_HALF_KELLY", "5. Aggressive Half-Kelly (0.03 lots per $1,000 equity)")
    ]
    
    results = []
    for code, desc in models:
        print(f"🔄 Simulating {desc}...")
        res = run_simulation(df, model_name=code, initial_capital=1000.0)
        res["description"] = desc
        results.append(res)
        
    print("\n" + "=" * 105)
    print(f"{'MODEL NAME':<32} | {'FINAL BAL':<10} | {'NET PROFIT':<11} | {'ROI %':<8} | {'MAX DD %':<8} | {'MAX DD $':<9} | {'PF':<5} | {'AVG LOT':<7}")
    print("-" * 105)
    for r in results:
        sign = "+" if r['net_profit'] >= 0 else ""
        print(f"{r['model']:<32} | ${r['final_balance']:<9.2f} | {sign}${r['net_profit']:<10.2f} | {sign}{r['roi_pct']:<6.1f}% | {r['max_floating_dd_pct']:<6.1f}% | ${r['max_floating_dd_usd']:<8.2f} | {r['profit_factor']:<5.2f} | {r['avg_lot']:<7.3f}")
    print("=" * 105)
    
    # Save detailed JSON summary
    out_file = BASE_DIR / "scratch" / "compounding_backtest_results.json"
    import json
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Full detailed results exported to: {out_file}\n")

if __name__ == "__main__":
    main()
