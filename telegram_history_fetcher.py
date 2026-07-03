import json
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Configuration
CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"
HISTORY_OUTPUT = r"C:\anlyzeforex\forextele\telegram_history_15days.json"

def get_target_channels():
    channels = [
        -1001582520126, # Scalping Gold
        "goldsnipers11", 
        "Marketradercrypto",
        "sureshot_fx",  # Added at user request
        -1001661400724, # SureShot GOLD (VIP)
        -1001986940315, # GOLD TRADE SIGNALS
        -1002871728862, # ZERO TO HERO PRIMIUM GROUP
        -1001520053536, # Coin Chief
        -1001234364040, # Binance Killers VIP
        -1001652601224, # Crypto World Updates
        -1001553551852, # Binance 360
        -1002471742018, # DIL SE TRADER Crypto
        -1001737978232, # CryptoSimplicity News
        -1001754095061, # Crypto Radar
        -1001422000261, # Sureshot FX VIP
        "tradebussunessfx_007",
        "GOLD_MAST78",
        "forexero",
        "forexking1132",
        "earlypumpdetector",
        -1001704062350, # King Crypto Scalp [ LIVE ]
        -1001178704438, # GLOBAL PROFIT CLUB
        -1002458369770, # EASY FOREX
        -1001260601611, # GOLD TRADER
        -1001495198097  # GLOBAL GOLD INSIGHT
    ]
    return channels

CHANNELS = get_target_channels()
print(f"Found {len(CHANNELS)} Crypto/Forex channels to scan.")

async def fetch_history():
    print("🚀 Starting 15-Day Telegram History Fetcher (Dual Account Scan)...")
    
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client1 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session.session", config["api_id"], config["api_hash"])
    client2 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session2.session", config["api_id"], config["api_hash"])
    
    await client1.start()
    try:
        await client2.start()
        clients = [client1, client2]
    except Exception as e:
        print(f"⚠️ Could not start client2 (9008400969): {e}")
        clients = [client1]
    
    fifteen_days_ago = datetime.utcnow() - timedelta(days=15)
    all_messages = []
    
    for client_idx, client in enumerate(clients):
        print(f"\n🔄 Scanning with Client {client_idx + 1}...")
        for channel_id in CHANNELS:
            print(f"📥 Fetching messages for Channel ID: {channel_id} since {fifteen_days_ago.strftime('%Y-%m-%d')}...")
            try:
                entity = await client.get_entity(channel_id)
                count = 0
                async for message in client.iter_messages(entity, offset_date=datetime.utcnow(), reverse=False):
                    if message.date and message.date.replace(tzinfo=None) < fifteen_days_ago:
                        break
                        
                    if message.text:
                        all_messages.append({
                            "channel_id": channel_id,
                            "message_id": message.id,
                            "date": message.date.isoformat(),
                            "text": message.text,
                            "client_source": client_idx + 1
                        })
                        count += 1
                print(f"✅ Fetched {count} messages from {channel_id}")
            except Exception as e:
                print(f"⚠️ Skipped {channel_id} on Client {client_idx + 1}: {e}")
                
        await client.disconnect()
            
    # Sort by date and remove exact duplicates based on channel_id and message_id
    all_messages.sort(key=lambda x: x["date"])
    
    unique_msgs = []
    seen = set()
    for msg in all_messages:
        identifier = f"{msg['channel_id']}_{msg['message_id']}"
        if identifier not in seen:
            seen.add(identifier)
            unique_msgs.append(msg)
    
    with open(HISTORY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(unique_msgs, f, indent=4, ensure_ascii=False)
        
    print(f"\n🎉 Done! Total {len(unique_msgs)} unique messages saved to {HISTORY_OUTPUT}")

if __name__ == "__main__":
    asyncio.run(fetch_history())
