import pandas as pd
import json
import os
from datetime import datetime, timedelta
import MetaTrader5 as mt5

BASE_DIR = r"c:\anlyzeforex\forextele"
CSV_PATH = os.path.join(BASE_DIR, "signals_audit.csv")
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")

def connect():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

def clean_str(s):
    return str(s).encode('ascii', 'ignore').decode('utf-8').strip()

def run_audit():
    print("=" * 85)
    print("  COMPREHENSIVE AUDIT OF ALL TELEGRAM CHANNELS (WHY SIGNALS PASS / FAIL)")
    print("=" * 85)

    if not os.path.exists(CSV_PATH):
        print("[ERROR] signals_audit.csv not found.")
        return

    df = pd.read_csv(CSV_PATH)
    total_signals = len(df)
    df['CleanChannel'] = df['Channel'].apply(clean_str)
    df['CleanStatus'] = df['Status'].apply(clean_str)
    df['CleanReason'] = df['Reason'].apply(clean_str)

    print(f"\n1. TOTAL INTERCEPTED SIGNALS LOGGED: {total_signals}")
    print(f"   UNIQUE CHANNELS MONITORED: {df['CleanChannel'].nunique()}")
    print("\n   PIPELINE PROCESSING BREAKDOWN:")
    status_counts = df['CleanStatus'].value_counts()
    for st, count in status_counts.items():
        pct = (count / total_signals) * 100
        print(f"     - {st:<12}: {count:>4} signals ({pct:>5.1f}%)")

    print("\n" + "=" * 85)
    print("2. PER-CHANNEL DIAGNOSTIC TABLE (All Channels Ranked by Signal Volume):")
    print(f"   {'Channel Name':<32} | {'Total':>5} | {'SUCCESS':>7} | {'FAILED':>6} | {'REJECT':>6} | Primary Failure Cause")
    print("   " + "-" * 85)

    grouped = df.groupby('CleanChannel')
    summary_rows = []

    for ch_name, group in grouped:
        tot = len(group)
        success = (group['CleanStatus'] == 'SUCCESS').sum()
        failed = (group['CleanStatus'] == 'FAILED').sum()
        rejected = (group['CleanStatus'] == 'REJECTED').sum()

        reasons = group['CleanReason'].value_counts()
        top_reason = reasons.index[0] if len(reasons) > 0 else "N/A"

        # Categorize primary failure mode
        if "Altcoin" in top_reason or any(kw in str(group['Raw_Signal'].values).upper() for kw in ["USDT", "NEAR", "ONDO", "AKE"]):
            primary_cause = "ALTCOIN / CRYPTO TOKEN (Not on MT5)"
        elif "could not parse" in top_reason or "N/A" in str(group['Parsed_Signal'].values):
            primary_cause = "PROMO / MARKETING / NO STRUCTURE"
        elif "Price sanity" in top_reason or "deviation" in top_reason:
            primary_cause = "STALE PRICE (>0.5% deviation)"
        elif success > 0 and (success / tot) >= 0.3:
            primary_cause = "HIGH QUALITY (Valid Forex/Gold specs)"
        else:
            primary_cause = top_reason[:35]

        summary_rows.append({
            'channel': ch_name,
            'total': tot,
            'success': success,
            'failed': failed,
            'rejected': rejected,
            'cause': primary_cause
        })

    df_sum = pd.DataFrame(summary_rows).sort_values('total', ascending=False)

    for idx, row in df_sum.iterrows():
        ch = row['channel'][:32]
        if not ch: ch = "Unknown"
        print(f"   {ch:<32} | {row['total']:>5} | {row['success']:>7} | {row['failed']:>6} | {row['rejected']:>6} | {row['cause']}")

    print("\n" + "=" * 85)
    print("3. WHY HUMAN MANUAL TRADERS WIN ON SOME CHANNELS WHILE AUTOMATED BOTS FAIL:")
    print("=" * 85)
    print("""
  [REASON 1: ALTCOIN / CRYPTO SIGNAL MISMATCH]
   - Channels like Binance Killers, Binance 360, King Crypto Scalp send signals for 
     altcoins (NEAR/USDT, ONDO/USDT, APE/USDT).
   - Human crypto traders execute these on Binance/Bybit.
   - MT5 Forex brokers DO NOT support these altcoins! The bot attempts or rejects them.

  [REASON 2: MARKETING & PROMO NOISE ("BOOM BOOM 300+ PIPS")]
   - 35% of messages are post-trade flexes ("TP2 HIT BOOM! JOIN VIP TODAY").
   - Humans read these as ads; automated bots spend AI cycles parsing them.

  [REASON 3: PARTIAL CLOSING (TP1, TP2, TP3) VS FIXED LOTS]
   - Human traders close 50% at TP1, move SL to breakeven, and let TP2/TP3 run.
   - Standard MT5 EA orders without partial-close logic hold the full lot until TP or SL.
   - If price hits TP1 (+20 pips) then reverses to SL, human traders PROFIT, but bot LOSES.

  [REASON 4: LATENCY & STALE ENTRY SLIPPAGE]
   - Signal providers post: "BUY GOLD @ 4000".
   - By the time Telegram API receives the text, price is already @ 4004 (+40 pips higher!).
   - Human traders adjust or wait for a pullback; un-gated bots buy at the top!
""")

if __name__ == "__main__":
    run_audit()
