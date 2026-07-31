import pandas as pd
import json
import os
from datetime import datetime, timedelta

BASE_DIR = r"c:\anlyzeforex\forextele"
CSV_PATH = os.path.join(BASE_DIR, "signals_audit.csv")

FOREX_GOLD_CHANNELS = [
    "RaSrasanForex", "RIAOGOLDFOREX", "JOSEFINA TRADER0", "Max Leverage",
    "Sureshot FX VIP", "SureShot GOLD (VIP)", "Forex Trading Tips",
    "GOLD DREAMS TRADER", "XAUUSD ACCURATE SiGNALS", "DUBAI CAPITAL FX GROUP 3",
    "Forexero - Forex Signals", "GOLD Scalper", "CULERSFOREX", "GOLD Snipers",
    "Mr.DAVID, XAU/USD CLUB", "GOLD Trader Dan", "Sureshot FX",
    "GOLD SCALPER", "Scalping Gold"
]

def clean_str(s):
    return str(s).encode('ascii', 'ignore').decode('utf-8').strip()

def run_2day_audit():
    print("=" * 85)
    print("  48-HOUR TELEGRAM SIGNAL AUDIT & MISSED TRADES ANALYSIS (19 FOREX & GOLD CHANNELS)")
    print("=" * 85)

    if not os.path.exists(CSV_PATH):
        print("[ERROR] signals_audit.csv not found.")
        return

    df = pd.read_csv(CSV_PATH)
    df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

    # Filter for past 48 hours (July 29 - July 31)
    two_days_ago = datetime.now() - timedelta(days=2)
    df_2d = df[df['dt'] >= two_days_ago].copy()

    df_2d['CleanChannel'] = df_2d['Channel'].apply(clean_str)
    df_2d['CleanStatus'] = df_2d['Status'].apply(clean_str)
    df_2d['CleanReason'] = df_2d['Reason'].apply(clean_str)

    # Filter for target channels
    target_clean = [clean_str(c).lower() for c in FOREX_GOLD_CHANNELS]
    df_target = df_2d[df_2d['CleanChannel'].str.lower().apply(lambda x: any(tc in x for tc in target_clean))].copy()

    print(f"\n1. 48-HOUR SIGNAL INTERCEPTION METRICS:")
    print(f"   Time Period                 : {two_days_ago.strftime('%Y-%m-%d %H:%M')} to {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Total Messages Intercepted : {len(df_target)}")
    print(f"   Channels Reporting Signals  : {df_target['CleanChannel'].nunique()} out of 19")

    executed_trades = []
    missed_price_gate = []
    missed_parser_fail = []
    junk_marketing = []

    for _, row in df_target.iterrows():
        raw_msg = str(row['Raw_Signal'])
        ch = row['CleanChannel']
        status = row['CleanStatus']
        reason = row['CleanReason']

        txt_u = raw_msg.upper()
        has_action = "BUY" in txt_u or "SELL" in txt_u
        has_sym = any(kw in txt_u for kw in ["XAUUSD", "GOLD", "EURUSD", "GBPUSD", "GBPJPY", "USDCHF", "AUDUSD"])
        has_nums = any(char.isdigit() for char in raw_msg)
        is_trade_structure = (has_action and has_sym and has_nums)

        if status == 'SUCCESS':
            executed_trades.append({'ch': ch, 'msg': raw_msg[:65], 'status': status})
        elif is_trade_structure:
            if "Price sanity" in reason or "deviation" in reason or "REJECTED" in status:
                missed_price_gate.append({'ch': ch, 'msg': raw_msg[:65], 'reason': 'Price Gate / Stale Entry'})
            else:
                missed_parser_fail.append({'ch': ch, 'msg': raw_msg[:65], 'reason': reason[:45]})
        else:
            junk_marketing.append({'ch': ch, 'msg': raw_msg[:65]})

    print("\n" + "=" * 85)
    print("2. 48-HOUR AUDIT RESULTS & BREAKDOWN:")
    print("=" * 85)
    print(f"  [EXECUTED ON MT5]           : {len(executed_trades)} trades")
    print(f"  [MISSED: Price Gate / Stale]: {len(missed_price_gate)} trades")
    print(f"  [MISSED: Parser / Scanner] : {len(missed_parser_fail)} trades")
    print(f"  [REJECTED: Ads / Promo]     : {len(junk_marketing)} messages")

    if missed_parser_fail:
        print(f"\n3. DETAIL OF TRADES MISSED BY PARSER / SCANNER ({len(missed_parser_fail)} Total):")
        for m in missed_parser_fail:
            print(f"    - [{m['ch']}] Raw: {m['msg']}... | Reason: {m['reason']}")

    if missed_price_gate:
        print(f"\n4. DETAIL OF TRADES MISSED DUE TO PRICE GATE / STALE ENTRY ({len(missed_price_gate)} Total):")
        for m in missed_price_gate:
            print(f"    - [{m['ch']}] Raw: {m['msg']}... | Reason: {m['reason']}")

    if executed_trades:
        print(f"\n5. DETAIL OF EXECUTED TRADES ({len(executed_trades)} Total):")
        for m in executed_trades:
            print(f"    - [{m['ch']}] Raw: {m['msg']}...")

    print("\n" + "=" * 85)

if __name__ == "__main__":
    run_2day_audit()
