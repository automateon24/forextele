import pandas as pd
import os

BASE_DIR = r"c:\anlyzeforex\forextele"
CSV_PATH = os.path.join(BASE_DIR, "signals_audit.csv")

def clean_str(s):
    return str(s).encode('ascii', 'ignore').decode('utf-8').strip()

def count_forex_channels():
    print("=" * 80)
    print("  ACTIVE FOREX & GOLD TELEGRAM CHANNELS COUNT (POST-CRYPTO RESTRICTION)")
    print("=" * 80)

    if not os.path.exists(CSV_PATH):
        print("[ERROR] signals_audit.csv not found.")
        return

    df = pd.read_csv(CSV_PATH)
    df['CleanChannel'] = df['Channel'].apply(clean_str)

    all_channels = df['CleanChannel'].unique()
    
    crypto_keywords = ["crypto", "binance", "pump", "coin", "altcoin", "radar", "killers"]

    forex_gold_channels = []
    suspended_crypto_channels = []

    for ch in all_channels:
        if not ch or ch == "Unknown": continue
        ch_lower = ch.lower()
        if any(kw in ch_lower for kw in crypto_keywords):
            suspended_crypto_channels.append(ch)
        else:
            # Count signal volume for this channel
            vol = len(df[df['CleanChannel'] == ch])
            forex_gold_channels.append((ch, vol))

    # Sort by signal volume
    forex_gold_channels.sort(key=lambda x: x[1], reverse=True)

    print(f"\nTOTAL CHANNELS MONITORED IN SYSTEM : {len(all_channels)}")
    print(f"SUSPENDED CRYPTO / ALTCOIN CHANNELS : {len(suspended_crypto_channels)}")
    print(f"ACTIVE FOREX & GOLD CHANNELS LEFT  : {len(forex_gold_channels)}")

    print(f"\n" + "=" * 80)
    print(f"  LIST OF ALL {len(forex_gold_channels)} ACTIVE FOREX & GOLD CHANNELS SCANNING NOW:")
    print(f"  {'#':<4} | {'Channel Name':<35} | {'Historical Signals Monitored'}")
    print(f"  {'-'*70}")

    for idx, (ch, vol) in enumerate(forex_gold_channels, 1):
        print(f"  {idx:<4} | {ch:<35} | {vol:>5} signals")

    print(f"\n" + "=" * 80)
    print(f"  SUSPENDED CRYPTO / ALTCOIN CHANNELS ({len(suspended_crypto_channels)} Total):")
    for ch in suspended_crypto_channels:
        print(f"  - [SUSPENDED] {ch}")
    print("=" * 80)

if __name__ == "__main__":
    count_forex_channels()
