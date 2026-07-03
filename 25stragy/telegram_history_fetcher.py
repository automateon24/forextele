import json
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Configuration
CONFIG_PATH = r"C:\25stragy\config_telegram.json"
HISTORY_OUTPUT = r"C:\25stragy\telegram_history_90days.json"

CHANNELS = [
    -1002871728862, # ZERO TO HERO
    -1002902210804, # Sensex360
    -1002231238486, # MCX Commodities
    -1002626583811, # BTST VIP+
    -1002115753582, # Premium DIL SE TRADER
    -1002412774015  # Equity Stocks
]

async def fetch_history():
    print("🚀 Starting 3-Month Telegram History Fetcher...")
    
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client = TelegramClient(r"C:\25stragy\telegram_session", config["api_id"], config["api_hash"])
    await client.start()
    
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    all_messages = []
    
    for channel_id in CHANNELS:
        print(f"📥 Fetching messages for Channel ID: {channel_id} since {ninety_days_ago.strftime('%Y-%m-%d')}...")
        try:
            entity = await client.get_entity(channel_id)
            count = 0
            async for message in client.iter_messages(entity, offset_date=datetime.utcnow(), reverse=False):
                if message.date.replace(tzinfo=None) < ninety_days_ago:
                    break
                    
                if message.text:
                    all_messages.append({
                        "channel_id": channel_id,
                        "message_id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text
                    })
                    count += 1
            print(f"✅ Fetched {count} messages from {channel_id}")
        except Exception as e:
            print(f"❌ Failed to fetch from {channel_id}: {e}")
            
    # Sort by date
    all_messages.sort(key=lambda x: x["date"])
    
    with open(HISTORY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_messages, f, indent=4, ensure_ascii=False)
        
    print(f"🎉 Done! Total {len(all_messages)} messages saved to {HISTORY_OUTPUT}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(fetch_history())
