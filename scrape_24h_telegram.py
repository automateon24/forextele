import asyncio
from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
import json
import re

# Use existing anon session
api_id = 15598350
api_hash = "8cb282656e09b0983a9b71365b0813f4"

channel_map = {
    "-1001582520126": "Scalping Gold",
    "goldsnipers11": "GOLD Snipers",
    "Marketradercrypto": "Market Trader Crypto Forex",
    "sureshot_fx": "Sureshot FX",
    "-1001661400724": "SureShot GOLD (VIP)",
    "-1001986940315": "GOLD TRADE SIGNALS",
    "-1002871728862": "ZERO TO HERO PRIMIUM GROUP",
    "-1001520053536": "Coin Chief",
    "-1001234364040": "Binance Killers VIP",
    "-1001652601224": "Crypto World Updates",
    "-1001553551852": "Binance 360",
    "-1002471742018": "DIL SE TRADER Crypto",
    "-1001737978232": "CryptoSimplicity News",
    "-1001754095061": "Crypto Radar",
    "-1001422000261": "Sureshot FX VIP",
    "GOLD_MAST78": "GOLD_MAST78",
    "forexero": "forexero",
    "forexking1132": "forexking1132",
    "earlypumpdetector": "earlypumpdetector",
    "-1001704062350": "King Crypto Scalp [ LIVE ]",
    "-1001178704438": "GLOBAL PROFIT CLUB",
    "-1002458369770": "EASY FOREX",
    "-1001260601611": "GOLD TRADER",
    "-1001495198097": "GLOBAL GOLD INSIGHT"
}

# Regex to detect simple signals
SIGNAL_RE = re.compile(r"\b(BUY|SELL)\s+([A-Z]{3,6}(?:/[A-Z]{3,6})?)\b", re.IGNORECASE)

async def main():
    print("Connecting to Telegram...")
    client = TelegramClient('c:/anlyzeforex/forextele/telegram_session_backup', api_id, api_hash)
    await client.start()
    
    print("Connected! Fetching past 24 hours of messages...")
    time_limit = datetime.now(timezone.utc) - timedelta(hours=24)
    
    report = []
    
    for channel_id, channel_name in channel_map.items():
        try:
            # Parse ID if it's numeric
            try:
                entity = int(channel_id)
            except ValueError:
                entity = channel_id
                
            messages = await client.get_messages(entity, limit=200)
            
            for msg in messages:
                if msg.date < time_limit:
                    continue # Skip older messages
                
                if msg.text:
                    match = SIGNAL_RE.search(msg.text)
                    if match:
                        action = match.group(1).upper()
                        symbol = match.group(2).upper()
                        
                        # Basic parsing of TP/SL
                        tp = "N/A"
                        sl = "N/A"
                        
                        tp_match = re.search(r"TP\s*[:=]?\s*(\d+(?:\.\d+)?)", msg.text, re.IGNORECASE)
                        if tp_match: tp = tp_match.group(1)
                            
                        sl_match = re.search(r"SL\s*[:=]?\s*(\d+(?:\.\d+)?)", msg.text, re.IGNORECASE)
                        if sl_match: sl = sl_match.group(1)
                            
                        report.append(f"[{channel_name}] [{msg.date.strftime('%Y-%m-%d %H:%M:%S UTC')}] {action} {symbol} | SL: {sl} | TP: {tp}")
                        
        except Exception as e:
            print(f"Skipping {channel_name}: {e}")
            
    await client.disconnect()
    
    # Save report
    with open("c:/anlyzeforex/forextele/telegram_24h_report.txt", "w", encoding="utf-8") as f:
        f.write("=== TELEGRAM SIGNALS (LAST 24 HOURS) ===\n\n")
        if not report:
            f.write("No explicit BUY/SELL signals found in the last 24 hours.\n")
        else:
            f.write("\n".join(report))
            
    print(f"\nDone! Extracted {len(report)} signals. Check telegram_24h_report.txt")

if __name__ == "__main__":
    asyncio.run(main())
