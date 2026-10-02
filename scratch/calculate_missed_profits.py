import os
import re
from datetime import datetime, timezone, timedelta
import pandas as pd
import MetaTrader5 as mt5

SYMBOL = "GOLD"
LOT_SIZE = 0.02
LOT_MULTIPLIER = 2.0  # 1.0 pt on 0.02 lot = $2.00 USD

def main():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return
        
    log_content = open('logs/breakout_boss.log', 'r', encoding='utf-8', errors='ignore').read()
    
    # Extract blocks of triggered setups
    # Each block: timestamp, setup_id, dir, entry, sl, tp, followed by either tickets or error
    lines = log_content.splitlines()
    
    setups = []
    curr_setup = None
    
    trigger_re = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - \[BREAKOUT_BOSS\] - INFO - 🎯 \[MULTI-MODEL SETUP TRIGGERED\] (\S+) (BUY|SELL) SIGNAL! Entry: ([\d\.]+) \| SL: ([\d\.]+) \| TP: ([\d\.]+)')
    executed_re = re.compile(r'🔥 \[Baseline Fixed\] Ticket #(\d+)')
    error_re = re.compile(r'❌ \[Baseline Fixed\] Order execution failed: Retcode 10030')
    
    IST_TZ = timezone(timedelta(hours=5, minutes=30))
    for i, line in enumerate(lines):
        m = trigger_re.search(line)
        if m:
            ts_str, setup_id, action, entry, sl, tp = m.groups()
            dt_ist = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=IST_TZ)
            dt = dt_ist.astimezone(timezone.utc)
            
            # Check subsequent lines for execution status
            status = "UNKNOWN"
            ticket = None
            for j in range(i+1, min(i+15, len(lines))):
                if executed_re.search(lines[j]):
                    status = "EXECUTED"
                    ticket = executed_re.search(lines[j]).group(1)
                    break
                elif error_re.search(lines[j]):
                    status = "MISSED_ERROR"
                    break
                    
            setups.append({
                "time": dt,
                "setup_id": setup_id,
                "action": action,
                "entry": float(entry),
                "sl": float(sl),
                "tp": float(tp),
                "status": status,
                "ticket": ticket
            })
            
    print(f"Total Parsed Setups: {len(setups)}")
    executed = [s for s in setups if s["status"] == "EXECUTED"]
    missed = [s for s in setups if s["status"] == "MISSED_ERROR"]
    print(f"Executed Setups: {len(executed)}")
    print(f"Missed Setups (due to bug): {len(missed)}")
    
    # Fetch M1 data covering 2026-09-30 to now
    start_fetch = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
    end_fetch = datetime.now(timezone.utc)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_fetch, end_fetch)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    
    print("\n" + "="*105)
    print(f"{'SETUP ID':<22} | {'TIME (UTC)':<16} | {'DIR':<4} | {'ENTRY':<7} | {'SL':<7} | {'TP':<7} | {'OUTCOME':<7} | {'EXIT':<7} | {'PTS':<6} | {'0.02 PNL':<9} | {'5-MODELS PNL'}")
    print("="*105)
    
    missed_wins = 0
    missed_losses = 0
    total_missed_pts = 0.0
    total_missed_usd_002 = 0.0
    total_missed_usd_5models = 0.0
    
    # Average lot multiplier across the 5 models (M0=0.02, M1=0.02, M2=0.02, M3=0.015, M4=0.03) -> total ~0.105 lots = ~5.25x of 0.02 lot
    MODEL_5X_FACTOR = 5.25
    
    for s in missed:
        t_entry = s["time"]
        direction = s["action"]
        entry = s["entry"]
        sl = s["sl"]
        tp = s["tp"]
        
        # End of day cutoff for that day at 20:50 UTC
        eod_cutoff = datetime(t_entry.year, t_entry.month, t_entry.day, 20, 50, tzinfo=timezone.utc)
        
        # Post-entry candles
        future_bars = df[(df.index >= t_entry) & (df.index <= eod_cutoff)]
        
        outcome = "OPEN"
        exit_p = entry
        pts = 0.0
        
        for t, bar in future_bars.iterrows():
            c_high = bar['high']
            c_low = bar['low']
            c_close = bar['close']
            
            if direction == "BUY":
                if c_low <= sl:
                    outcome = "LOSS"
                    exit_p = sl
                    pts = sl - entry
                    break
                elif c_high >= tp:
                    outcome = "WIN"
                    exit_p = tp
                    pts = tp - entry
                    break
            elif direction == "SELL":
                if c_high >= sl:
                    outcome = "LOSS"
                    exit_p = sl
                    pts = entry - sl
                    break
                elif c_low <= tp:
                    outcome = "WIN"
                    exit_p = tp
                    pts = entry - tp
                    break
                    
        if outcome == "OPEN" and len(future_bars) > 0:
            last_close = future_bars.iloc[-1]['close']
            exit_p = last_close
            pts = (last_close - entry) if direction == "BUY" else (entry - last_close)
            outcome = "EOD_WIN" if pts > 0 else "EOD_LOSS"
            
        usd_002 = pts * LOT_MULTIPLIER
        usd_5models = usd_002 * MODEL_5X_FACTOR
        
        if outcome in ["WIN", "EOD_WIN"]:
            missed_wins += 1
        else:
            missed_losses += 1
            
        total_missed_pts += pts
        total_missed_usd_002 += usd_002
        total_missed_usd_5models += usd_5models
        
        ts_display = t_entry.strftime("%m-%d %H:%M:%S")
        pnl_str = f"+${usd_002:.2f}" if usd_002 >= 0 else f"-${abs(usd_002):.2f}"
        pnl_5m_str = f"+${usd_5models:.2f}" if usd_5models >= 0 else f"-${abs(usd_5models):.2f}"
        
        print(f"{s['setup_id']:<22} | {ts_display:<16} | {direction:<4} | {entry:<7.2f} | {sl:<7.2f} | {tp:<7.2f} | {outcome:<7} | {exit_p:<7.2f} | {pts:+6.2f} | {pnl_str:<9} | {pnl_5m_str}")
        
    print("="*105)
    print(f"\n📊 SUMMARY OF MISSED TRADES AUDIT:")
    print(f"  Total Missed Setups   : {len(missed)}")
    print(f"  Hypothetical Wins     : {missed_wins} ({missed_wins/len(missed)*100:.1f}%)")
    print(f"  Hypothetical Losses   : {missed_losses} ({missed_losses/len(missed)*100:.1f}%)")
    print(f"  Total Net Points      : {total_missed_pts:+.2f} pts")
    print(f"  Net PnL (0.02 Lot)    : {'+$' if total_missed_usd_002>=0 else '-$'}{abs(total_missed_usd_002):.2f} USD")
    print(f"  Net PnL (All 5 Models): {'+$' if total_missed_usd_5models>=0 else '-$'}{abs(total_missed_usd_5models):.2f} USD")
    print("="*105)

if __name__ == "__main__":
    main()
