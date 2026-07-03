import json
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Channel, Chat
import re

CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"

# We will evaluate the two specific channels the user requested on the second account.
TARGET_CHANNELS = [
    "goldsnipers11", 
    "Marketradercrypto"
]

async def find_missing_channels(client):
    print("\n[Search] Searching for missing channels: 'Market Trader Crypto Forex' and 'gold sniper'")
    dialogs = await client.get_dialogs()
    found = []
    for d in dialogs:
        name_lower = d.name.lower() if d.name else ""
        if "market trader" in name_lower or "gold sniper" in name_lower:
            found.append(d)
            print(f"Found match: {d.id} | {d.name}")
    return [f.id for f in found]

def is_trade_signal(text):
    if not text:
        return False
    text = text.upper()
    # Basic logic to see if it's a trade signal rather than just chatter
    has_action = "BUY" in text or "SELL" in text or "LONG" in text or "SHORT" in text
    has_target = "TP" in text or "TARGET" in text or "TAKE PROFIT" in text
    has_sl = "SL" in text or "STOP" in text or "STOPLOSS" in text
    
    return has_action and (has_target or has_sl)

async def evaluate_channel(client, channel_id, days=10):
    try:
        entity = await client.get_entity(channel_id)
        name = entity.title if hasattr(entity, 'title') else str(channel_id)
    except Exception as e:
        return f"Channel {channel_id}: [ERROR] Could not access ({e})"
        
    name = name.encode('ascii', 'ignore').decode('ascii').strip()
    print(f"\n[Scan] Scanning: {name} (ID: {channel_id}) for the last {days} days...")
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    total_msgs = 0
    trade_signals = 0
    pairs_mentioned = set()
    
    pair_regex = re.compile(r'(XAUUSD|GOLD|EURUSD|GBPJPY|BTC|ETH|BTCUSD|ETHUSD)', re.IGNORECASE)
    
    try:
        async for message in client.iter_messages(entity, offset_date=datetime.utcnow(), reverse=False):
            if message.date and message.date.replace(tzinfo=None) < cutoff_date:
                break
                
            if message.text:
                total_msgs += 1
                
                # Check for pairs
                matches = pair_regex.findall(message.text)
                for m in matches:
                    pairs_mentioned.add(m.upper())
                    
                if is_trade_signal(message.text):
                    trade_signals += 1
    except Exception as e:
         return f"Channel {name}: [ERROR] Error fetching messages ({e})"
         
    if total_msgs == 0:
        return f"Channel {name}: [WARN] No messages in the last {days} days."
        
    trades_per_day = trade_signals / days
    signal_ratio = (trade_signals / total_msgs) * 100 if total_msgs > 0 else 0
    
    rating = "***** (Excellent)" if trades_per_day >= 1 and signal_ratio > 10 else \
             "*** (Moderate)" if trades_per_day >= 0.2 else \
             "* (Mostly Chat/Discussion)"
             
    report = (
        f"**Channel:** {name}\n"
        f"**Analysis (Last 10 Days):**\n"
        f"- Total Messages: {total_msgs}\n"
        f"- Real Trade Signals: {trade_signals} (~{trades_per_day:.1f} trades/day)\n"
        f"- Signal Density: {signal_ratio:.1f}%\n"
        f"- Pairs Detected: {', '.join(pairs_mentioned) if pairs_mentioned else 'None'}\n"
        f"**Verdict:** {rating}\n"
    )
    return report

async def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session2.session", config["api_id"], config["api_hash"])
    await client.start()
    
    channels_to_scan = TARGET_CHANNELS
    
    reports = []
    print("\n==================================================")
    print("      STARTING CHANNEL EVALUATION (BATCH 1)       ")
    print("==================================================\n")
    
    for cid in channels_to_scan:
        rep = await evaluate_channel(client, cid, days=10)
        reports.append(rep)
        print(rep)
        print("-" * 50)
        
    # Save the batch report
    with open(r"C:\anlyzeforex\forextele\batch_1_evaluation.md", "w", encoding="utf-8") as f:
        f.write("# Channel Evaluation - Batch 1\n\n")
        for r in reports:
            f.write(r + "\n---\n")
            
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
