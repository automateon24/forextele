import json
import os
import asyncio
from telethon import TelegramClient

CONFIG_PATH = r"C:\25stragy\config_telegram.json"
CHANNELS = [
    -1002871728862, # ZERO TO HERO PRIMIUM GROUP
    -1002902210804, # Sensex360 by Nitin Murarka
    -1002231238486, # MCX Commodities
    -1002626583811, # BTST VIP+
    -1002115753582, # Premium DIL SE TRADER
    -1002412774015  # Equity Stocks
]

async def main():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        
    client = TelegramClient(r"C:\25stragy\telegram_session", config['api_id'], config['api_hash'])
    await client.start()
    
    samples = {}
    
    for channel_id in CHANNELS:
        try:
            print(f"Fetching messages for {channel_id}...")
            messages = await client.get_messages(channel_id, limit=5)
            samples[channel_id] = [m.text for m in messages if m.text]
        except Exception as e:
            print(f"Error fetching {channel_id}: {e}")
            
    with open(r"C:\25stragy\telegram_sample_messages.json", 'w', encoding='utf-8') as f:
        json.dump(samples, f, indent=4, ensure_ascii=False)
        
    print("Done! Messages saved.")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
