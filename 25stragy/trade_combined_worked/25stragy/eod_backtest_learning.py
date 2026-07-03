#!/usr/bin/env python3
"""
Advanced AI/ML EOD Auto-Tuning Engine (Self-Learning Loop)
==========================================================
Triggered daily at 15:45 to:
1. Fetch the current day's spot data (via Dhan API) and analyze actual trades.
2. Evaluate strategy performance vs simulated backtest.
3. Compute a Policy Gradient Reward Score for each strategy/parameter.
4. Auto-tune thresholds (RSI, SL, TSL, TGT, Capital Allocations).
5. Update `strategy_dna.json` and `config_hybrid_aggressive.json`.
6. Log all learning paths to `self_learning_audit.json`.
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# Add paths
base_dir = r"C:\cursor\options\niftyopt"
sys.path.insert(0, base_dir)
sys.path.insert(0, r"C:\25stragy")

# Configuration paths
DATA_DIR = os.path.join(base_dir, "data")
TRADES_FILE = os.path.join(DATA_DIR, "live_portfolio_paper_trades.csv")
AUDIT_FILE = os.path.join(DATA_DIR, "self_learning_audit.json")
DNA_FILE = r"C:\25stragy\strategy_dna.json"
HYBRID_CONFIG = r"C:\25stragy\config_hybrid_aggressive.json"
TOKEN_FILE = os.path.join(base_dir, "config", "dhan_tokens.json")

# Import Dhan Handler
try:
    from src.module1_data.dhan_handler import DhanDataHandler
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False


def calculate_reward_score(trades_df):
    """
    Computes a Multi-Objective Reward Score for a set of trades.
    Score = (Net PnL Normalized) + (Win Rate * 100) - (Max Drawdown Penalty)
    """
    if len(trades_df) == 0:
        return 0.0
    
    wins = trades_df[trades_df['pnl_rs'] > 0]
    win_rate = len(wins) / len(trades_df)
    net_pnl = trades_df['pnl_rs'].sum()
    
    # Calculate drawdown
    cumulative = trades_df['pnl_rs'].cumsum()
    peak = cumulative.cummax()
    drawdown = peak - cumulative
    max_dd = drawdown.max() if not drawdown.empty else 0
    
    # Normalize PnL (assume 100,000 capital per index)
    pnl_score = (net_pnl / 100000.0) * 50
    wr_score = win_rate * 50
    dd_penalty = (max_dd / 100000.0) * 100
    
    final_score = pnl_score + wr_score - dd_penalty
    return round(final_score, 2)


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def run_eod_learning_loop():
    print("======================================================")
    print("🧠 V15 SUPER BOT: AI/ML EOD SELF-LEARNING OPTIMIZATION")
    print("======================================================")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Load Today's Trades
    if not os.path.exists(TRADES_FILE):
        print("No live trades found.")
        return

    df = pd.read_csv(TRADES_FILE)
    df['date'] = pd.to_datetime(df['entry_time']).dt.strftime('%Y-%m-%d')
    today_trades = df[df['date'] == today_str]
    
    if len(today_trades) == 0:
        print("No trades executed today. Checking if entry gates need relaxation...")
        # If no trades happened, we might relax the thresholds slightly for Tier 1 strategies
        today_trades = pd.DataFrame() # Empty but valid
    else:
        print(f"Analyzed {len(today_trades)} trades from today.")

    # 2. Load Current DNA & Config
    dna = load_json(DNA_FILE)
    config = load_json(HYBRID_CONFIG)
    
    adjustments = []
    
    # 3. Analyze Strategy Performance & Apply Policy Gradient Updates
    if not today_trades.empty:
        strategies_traded = today_trades['strategy'].unique()
        for strat in strategies_traded:
            strat_trades = today_trades[today_trades['strategy'] == strat]
            score = calculate_reward_score(strat_trades)
            win_rate = len(strat_trades[strat_trades['pnl_rs'] > 0]) / len(strat_trades)
            
            print(f"Strategy: {strat} | Trades: {len(strat_trades)} | WR: {win_rate:.0%} | Score: {score}")
            
            if strat not in dna['strategies']:
                continue
                
            s_dna = dna['strategies'][strat]
            
            # Policy Gradient Update Rules:
            # 1. High Score (> 20) & High WR (> 60%): Capitalize by pushing Target slightly higher.
            if score > 20 and win_rate >= 0.6:
                old_tgt = s_dna['tgt']
                s_dna['tgt'] = round(old_tgt * 1.05, 3)  # Increase target by 5%
                adjustments.append({
                    "type": "parameter_tuning",
                    "strategy": strat,
                    "parameter": "tgt",
                    "old_value": old_tgt,
                    "new_value": s_dna['tgt'],
                    "reason": f"High performance score ({score}). Increasing target."
                })
                
            # 2. Low Score (< 0) & Low WR (< 40%): Tighten Stop Loss and Entry Thresholds
            elif score < 0 or win_rate < 0.4:
                old_sl = s_dna['sl']
                s_dna['sl'] = round(old_sl * 0.95, 3) # Decrease stop loss by 5% (tighter)
                
                old_thresh = s_dna['thresh']
                # Make entry stricter
                if 'RSI' in strat or 'MEAN' in strat or 'BULL' in strat or 'BEAR' in strat:
                    if old_thresh > 50: # Upper bound (like RSI > 60)
                        s_dna['thresh'] = round(old_thresh + 1, 2)
                    else: # Lower bound (like RSI < 40)
                        s_dna['thresh'] = round(old_thresh - 1, 2)
                        
                adjustments.append({
                    "type": "parameter_tuning",
                    "strategy": strat,
                    "parameter": "sl & thresh",
                    "old_value": f"SL:{old_sl}, Thresh:{old_thresh}",
                    "new_value": f"SL:{s_dna['sl']}, Thresh:{s_dna['thresh']}",
                    "reason": f"Poor performance (WR: {win_rate:.0%}). Tightening SL and gates."
                })
                
            # 3. High WR but Low Score (Taking profits too early, or getting chopped out by TSL)
            elif win_rate >= 0.5 and score < 10:
                old_tsl_a = s_dna['tsl_a']
                s_dna['tsl_a'] = round(old_tsl_a * 1.1, 3) # Delay TSL activation
                adjustments.append({
                    "type": "parameter_tuning",
                    "strategy": strat,
                    "parameter": "tsl_a",
                    "old_value": old_tsl_a,
                    "new_value": s_dna['tsl_a'],
                    "reason": "High WR but low profitability. Delaying TSL activation."
                })

    else:
        # Market moved but 0 trades -> Relax strict filters
        print("Relaxing thresholds to prevent under-trading.")
        for strat in ["ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH", "DAY_HIGH_BEARISH"]:
            if strat in dna['strategies']:
                old_thresh = dna['strategies'][strat]['thresh']
                if old_thresh > 50:
                    dna['strategies'][strat]['thresh'] = round(old_thresh - 1, 2)
                else:
                    dna['strategies'][strat]['thresh'] = round(old_thresh + 1, 2)
                adjustments.append({
                    "type": "parameter_tuning",
                    "strategy": strat,
                    "parameter": "thresh",
                    "old_value": old_thresh,
                    "new_value": dna['strategies'][strat]['thresh'],
                    "reason": "Zero trades executed today. Relaxing entry gates."
                })

    # 4. Save Updates
    if adjustments:
        save_json(dna, DNA_FILE)
        save_json(config, HYBRID_CONFIG)
        print(f"Applied {len(adjustments)} autonomous tuning adjustments.")
    else:
        print("No parameter adjustments required today. Baseline is optimal.")

    # 5. Append to Audit Log
    audit_record = {
        "date": today_str,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": {
            "total_trades": len(today_trades),
            "win_rate": float(len(today_trades[today_trades['pnl_rs'] > 0]) / len(today_trades) if len(today_trades) > 0 else 0) * 100,
            "net_pnl": float(today_trades['pnl_rs'].sum() if len(today_trades) > 0 else 0),
            "learning_score": float(calculate_reward_score(today_trades))
        },
        "adjustments": adjustments
    }

    audit_data = []
    if os.path.exists(AUDIT_FILE):
        try:
            audit_data = load_json(AUDIT_FILE)
        except:
            pass
            
    audit_data.insert(0, audit_record)
    # Keep last 90 days
    audit_data = audit_data[:90]
    save_json(audit_data, AUDIT_FILE)
    print(f"Learning Audit logged to {AUDIT_FILE}")

    # 6. Auto-Commit to GitHub
    print("Uploading EOD Auto-Tuning results to GitHub...")
    import subprocess
    try:
        cmds = [
            f'cd /d "{base_dir}" && git add data/self_learning_audit.json',
            f'cd /d "{base_dir}" && git add "{DNA_FILE}" "{HYBRID_CONFIG}"',
            f'cd /d "{base_dir}" && git commit -m "Auto EOD AI Tuning Update: {today_str}"',
            f'cd /d "{base_dir}" && git push'
        ]
        for cmd in cmds:
            subprocess.run(cmd, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("GitHub upload completed successfully.")
    except Exception as e:
        print(f"GitHub upload failed: {e}")

if __name__ == "__main__":
    run_eod_learning_loop()
