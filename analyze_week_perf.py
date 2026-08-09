import json
import pandas as pd
from pathlib import Path
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import sys

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
CONFIG_PATH = BASE_DIR / "mt5_config.json"

def main():
    if not mt5.initialize():
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))

    now = datetime.now()
    start_time = now - timedelta(days=7) # Last 7 days
    deals = mt5.history_deals_get(start_time, now)
    
    if deals is None:
        print(json.dumps({"error": "No deals found or MT5 connection failed."}))
        return

    strat_pnl = {}
    tele_pnl = {}
    tele_channels = {}
    
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_OUT:
            comment = d.comment or ""
            pnl = d.profit + d.swap + d.commission
            
            # AI Strategies (Magic 888888)
            if d.magic == 888888 or "AI:" in comment:
                strat_name = comment.replace("AI: ", "").split()[0] if "AI:" in comment else "UNKNOWN_STRAT"
                if strat_name not in strat_pnl:
                    strat_pnl[strat_name] = {'wins': 0, 'losses': 0, 'profit': 0.0}
                if pnl > 0: strat_pnl[strat_name]['wins'] += 1
                else: strat_pnl[strat_name]['losses'] += 1
                strat_pnl[strat_name]['profit'] += pnl
                
            # Telegram Signals (Magic 777777 or Tele:)
            elif d.magic == 777777 or "Tele:" in comment:
                tele_name = comment.replace("Tele:", "").strip()
                if not tele_name: tele_name = "UNKNOWN_CHANNEL"
                if tele_name not in tele_pnl:
                    tele_pnl[tele_name] = {'wins': 0, 'losses': 0, 'profit': 0.0}
                if pnl > 0: tele_pnl[tele_name]['wins'] += 1
                else: tele_pnl[tele_name]['losses'] += 1
                tele_pnl[tele_name]['profit'] += pnl

    # ML Veto Analysis from Log/CSV
    ml_csv = BASE_DIR / "ml_training_data.csv"
    ml_stats = {"total_scanned": 0, "approved": 0, "vetoed": 0, "avg_slippage": 0.0}
    if ml_csv.exists():
        try:
            df = pd.read_csv(ml_csv)
            ml_stats["total_scanned"] = len(df)
            ml_stats["approved"] = len(df) # Since this CSV only logs executed trades currently
            if 'price_deviation_pct' in df.columns:
                ml_stats["avg_slippage"] = df['price_deviation_pct'].mean()
        except: pass
        
    # Signals Audit
    audit_csv = BASE_DIR / "signals_audit.csv"
    channel_stats = {}
    if audit_csv.exists():
        try:
            df_audit = pd.read_csv(audit_csv)
            if 'Channel' in df_audit.columns and 'Status' in df_audit.columns:
                for index, row in df_audit.iterrows():
                    ch = str(row['Channel'])
                    st = str(row['Status'])
                    if ch not in channel_stats: channel_stats[ch] = {'tp': 0, 'sl': 0, 'missed': 0}
                    if 'TP' in st or 'WIN' in st: channel_stats[ch]['tp'] += 1
                    elif 'SL' in st or 'LOSS' in st: channel_stats[ch]['sl'] += 1
                    else: channel_stats[ch]['missed'] += 1
        except: pass

    report = {
        "strategies": strat_pnl,
        "telegram_live": tele_pnl,
        "telegram_audit": channel_stats,
        "ml_impact": ml_stats
    }
    
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
