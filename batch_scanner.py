import json
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
import re

CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"
INPUT_CHANNELS = r"C:\Users\Administrator\.gemini\antigravity\brain\27e19a22-546f-416c-9f28-df7b2de16873\SCANNED_CHANNELS_LIST.md"
OUTPUT_REPORT = r"C:\Users\Administrator\.gemini\antigravity\brain\27e19a22-546f-416c-9f28-df7b2de16873\ALL_CHANNELS_REPORT.md"

def is_trade_signal(text):
    if not text:
        return False
    text = text.upper()
    has_action = "BUY" in text or "SELL" in text or "LONG" in text or "SHORT" in text
    has_target = "TP" in text or "TARGET" in text
    has_sl = "SL" in text or "STOP" in text
    return has_action and (has_target or has_sl)

async def evaluate_channel(client, channel_ref, name_ref, days=10):
    try:
        entity = await client.get_entity(channel_ref)
        name = entity.title if hasattr(entity, 'title') else str(channel_ref)
        name = name.encode('ascii', 'ignore').decode('ascii').strip()
    except Exception as e:
        return f"**Channel:** {name_ref}\n**Verdict:** ❌ Could not access ({e})"
        
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    total_msgs = 0
    trade_signals = 0
    pairs = set()
    pair_regex = re.compile(r'(XAUUSD|GOLD|EURUSD|GBPJPY|BTC|ETH|BTCUSD|ETHUSD)', re.IGNORECASE)
    
    try:
        async for message in client.iter_messages(entity, offset_date=datetime.utcnow(), reverse=False):
            if message.date and message.date.replace(tzinfo=None) < cutoff_date:
                break
            if message.text:
                total_msgs += 1
                for m in pair_regex.findall(message.text):
                    pairs.add(m.upper())
                if is_trade_signal(message.text):
                    trade_signals += 1
    except Exception as e:
         return f"**Channel:** {name}\n**Verdict:** ❌ Error fetching messages ({e})"
         
    if total_msgs == 0:
        return f"**Channel:** {name}\n**Verdict:** ⚠️ No messages in last {days} days"
        
    tpd = trade_signals / days
    ratio = (trade_signals / total_msgs) * 100
    
    rating = "***** (Excellent)" if tpd >= 1 and ratio > 10 else \
             "*** (Moderate)" if tpd >= 0.2 else \
             "* (Mostly Chat/Noise)"
             
    return (
        f"**Channel:** {name}\n"
        f"- **Real Signals:** {trade_signals} (~{tpd:.1f}/day) | **Density:** {ratio:.1f}%\n"
        f"- **Pairs Detected:** {', '.join(pairs) if pairs else 'None'}\n"
        f"**Verdict:** {rating}\n"
    )

async def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client1 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session.session", config["api_id"], config["api_hash"])
    client2 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session2.session", config["api_id"], config["api_hash"])
    
    await client1.start()
    try:
        await client2.start()
    except:
        pass
        
    channels = []
    with open(INPUT_CHANNELS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("*") and "|" in line:
                parts = line.split("|")
                cid_str = parts[0].replace("*", "").replace("-", "").strip()
                if cid_str.isdigit():
                    cid = int("-" + cid_str)
                    cname_clean = parts[1].strip().encode('ascii', 'ignore').decode('ascii')
                    channels.append((cid, cname_clean))
                    
    print(f"Loaded {len(channels)} channels to evaluate.")
    
    results = []
    for cid, cname in channels:
        print(f"Scanning {cname} ({cid})...")
        # Try client1 first, then client2
        res = await evaluate_channel(client1, cid, cname, days=5)
        if "Could not access" in res:
            res = await evaluate_channel(client2, cid, cname, days=5)
        results.append(res)
        
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as out:
        out.write("# Master Channel Evaluation Report\n\n")
        out.write("This report evaluates all shortlisted channels for active trade signals over the last 5 days.\n\n")
        for r in results:
            out.write(r + "\n---\n")
            
    print(f"Done! Report saved to {OUTPUT_REPORT}")
    await client1.disconnect()
    await client2.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
