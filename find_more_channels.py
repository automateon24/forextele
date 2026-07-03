import json
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient

CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"

TARGET_NAMES = [
    "EASY FOREX", "E A S Y", "EASY", 
    "Gold Trader", "Gold", 
    "Global Profit", "Global",
    "Global Gold Insight", "Insight"
]

async def search_client(client, client_name):
    print(f"\n--- Searching {client_name} ---")
    dialogs = await client.get_dialogs()
    
    for d in dialogs:
        if d.is_user or not d.name:
            continue
            
        # 1. Check for special font variants by normalizing or just printing if it has keywords
        # The user provided: 𝙀𝘼𝙎𝙔 𝙁𝙊𝙍𝙀𝙓, 𝗚𝗼𝗹𝗱 𝗧𝗿𝗮𝗱𝗲𝗿, 𝗚𝗹𝗼𝗯𝗮𝗹 𝗣𝗿𝗼𝗳𝗶𝘁 𝗖𝘂𝗹𝗯, 𝙂𝙡𝙤𝙗𝙖𝙡 𝙂𝙤𝙡𝙙 𝙄𝙣𝙨𝙞𝙜𝙝𝙩
        # Because special unicode fonts don't match standard ascii easily, we'll try checking 
        # for them directly or manually inspect recently active channels.
        
        name_raw = d.name
        # Just print any channel that has these exact unicode strings
        if "𝙀𝘼𝙎𝙔 𝙁𝙊𝙍𝙀𝙓" in name_raw: print(f"[FOUND] Found: {d.id} | EASY FOREX")
        if "𝗚𝗼𝗹𝗱 𝗧𝗿𝗮𝗱𝗲𝗿" in name_raw: print(f"[FOUND] Found: {d.id} | GOLD TRADER")
        if "𝗚𝗹𝗼𝗯𝗮𝗹 𝗣𝗿𝗼𝗳𝗶𝘁 𝗖𝘂𝗹𝗯" in name_raw: print(f"[FOUND] Found: {d.id} | GLOBAL PROFIT CLUB")
        if "𝙂𝙡𝙤𝙗𝙖𝙡 𝙂𝙤𝙡𝙙 𝙄𝙣𝙨𝙞𝙜𝙝𝙩" in name_raw: print(f"[FOUND] Found: {d.id} | GLOBAL GOLD INSIGHT")
        
        # Also let's find any channel that posted "gold" in the last 48 hours
        try:
            msg = await client.get_messages(d.entity, limit=1)
            if msg and msg[0].text:
                if "gold" in msg[0].text.lower() or "xau" in msg[0].text.lower():
                    if msg[0].date > datetime.now(timezone.utc) - timedelta(days=2):
                        # only print if it contains special chars that might match
                        if any(ord(c) > 127 for c in name_raw):
                            safe_name = name_raw.encode('ascii', 'ignore').decode('ascii')
                            print(f"Possible Match (Active Gold): {d.id} | {safe_name}")
        except:
            pass

async def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client1 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session.session", config["api_id"], config["api_hash"])
    client2 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session2.session", config["api_id"], config["api_hash"])
    
    await client1.start()
    await search_client(client1, "Client 1")
    await client1.disconnect()
    
    try:
        await client2.start()
        await search_client(client2, "Client 2")
        await client2.disconnect()
    except Exception as e:
        pass

if __name__ == "__main__":
    asyncio.run(main())
