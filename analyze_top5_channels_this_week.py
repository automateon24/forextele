import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime, timedelta

BASE_DIR = r"c:\anlyzeforex\forextele"
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")
CSV_PATH = os.path.join(BASE_DIR, "ml_training_data.csv")

def connect():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

def analyze_top5():
    print("=" * 80)
    print("  WEEKLY AUDIT: TOP 5 TELEGRAM VIP CHANNELS PERFORMANCE (THIS WEEK)")
    print("=" * 80)

    if not connect():
        print("[ERROR] MT5 connection failed.")
        return

    # Pull deal history for the last 7 days (Week 31: July 25 - July 31)
    now = datetime.now()
    week_start = now - timedelta(days=7)
    deals = mt5.history_deals_get(week_start, now)

    target_channels = [
        "Sureshot FX VIP", "SureShot GOLD", "JOSEFINA TRADER",
        "RIAOGOLDFOREX", "RaSrasanForex"
    ]

    tele_deals = []
    if deals:
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_OUT:
                comment = d.comment or ""
                magic = d.magic
                if magic == 777777 or "Tele:" in comment:
                    pnl = d.profit + d.swap + d.commission
                    tele_deals.append({
                        'ticket': d.ticket,
                        'symbol': d.symbol,
                        'profit': pnl,
                        'comment': comment,
                        'time': datetime.fromtimestamp(d.time)
                    })

    df_deals = pd.DataFrame(tele_deals) if tele_deals else pd.DataFrame()

    # Also analyze intercepted signal audit log (ml_training_data.csv)
    df_audit = pd.DataFrame()
    if os.path.exists(CSV_PATH):
        try:
            df_csv = pd.read_csv(CSV_PATH)
            df_csv['dt'] = pd.to_datetime(df_csv['timestamp'], errors='coerce')
            df_audit = df_csv[df_csv['dt'] >= (datetime.now() - timedelta(days=7))]
        except Exception as e:
            print(f"[WARN] Error reading audit CSV: {e}")

    print("\n--- 1. TELEGRAM SIGNAL INTERCEPTION & PASS RATE (PAST 7 DAYS) ---")
    if not df_audit.empty:
        for ch in target_channels:
            sub = df_audit[df_audit['channel'].astype(str).str.contains(ch, case=False, na=False)]
            total_sig = len(sub)
            passed = len(sub[sub['status'] == 'PASSED'])
            rejected = total_sig - passed
            pass_rate = (passed / total_sig * 100) if total_sig > 0 else 0
            print(f"  {ch:<25} | Signals Sent: {total_sig:>3} | Approved: {passed:>3} | Price Gate Rejects: {rejected:>3} | Pass Rate: {pass_rate:.1f}%")
    else:
        print("  No audit records found for the past 7 days.")

    print("\n--- 2. REALIZED P&L ON MT5 EXECUTED TELEGRAM TRADES (THIS WEEK) ---")
    if not df_deals.empty:
        print(f"  Total Telegram Trades Executed This Week: {len(df_deals)}")
        print(f"  Total Net Telegram P&L This Week         : ${df_deals['profit'].sum():,.2f} USD")
        print("\n  Trade Log Breakdown:")
        for idx, row in df_deals.iterrows():
            print(f"    [{row['time'].strftime('%Y-%m-%d %H:%M')}] {row['symbol']:<8} | P&L: ${row['profit']:>7.2f} | Comment: {row['comment']}")
    else:
        print("  No executed Telegram trades closed on MT5 in the last 7 days.")
        print("  (Note: Telegram signals are strictly filtered by Price Gate and Governor risk parameters).")

    print("\n" + "=" * 80)
    print("  AUDIT VERDICT & WORTHINESS ANALYSIS")
    print("=" * 80)

if __name__ == "__main__":
    analyze_top5()
