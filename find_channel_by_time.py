import json
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient

CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"

# Local time provided by user: 17:50 on 2026-07-03 (IST +5:30)
# UTC time: 12:20 on 2026-07-03
target_utc = datetime(2026, 7, 3, 12, 20, tzinfo=timezone.utc)
time_window = timedelta(minutes=5) # 12:15 to 12:25 UTC

async def search_client(client, client_name):
    print(f"\n--- Searching {client_name} ---")
    dialogs = await client.get_dialogs()
    
    # 1. Search by name first
    print("Searching for 'sureshot' in names...")
    for d in dialogs:
        if d.name and "sureshot" in d.name.lower():
            print(f"[FOUND] Found by Name: {d.id} | {d.name.encode('ascii', 'ignore').decode('ascii')}")
            
    # 2. Search by message time
    print(f"Searching for GOLD messages around {target_utc.strftime('%H:%M')} UTC...")
    count = 0
    for d in dialogs:
        # Optimization: only check channels/groups
        if d.is_user:
            continue
            
        try:
            # We just fetch the last 15 messages to see if they fall in the time window
            async for msg in client.iter_messages(d.entity, limit=15):
                if not msg.date or not msg.text:
                    continue
                
                msg_time = msg.date # tz-aware UTC
                if target_utc - time_window <= msg_time <= target_utc + time_window:
                    if "gold" in msg.text.lower() or "xau" in msg.text.lower():
                        cname = d.name.encode('ascii', 'ignore').decode('ascii') if d.name else str(d.id)
                        print(f"[FOUND] Found message in {cname} (ID: {d.id}) at {msg_time.strftime('%H:%M:%S')} UTC:\n  {msg.text[:50].replace(chr(10), ' ')}...")
        except Exception as e:
            pass
        count += 1
        if count >= 150: # limit to top 150 dialogs to save time
            break

async def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    client1 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session.session", config["api_id"], config["api_hash"])
    client2 = TelegramClient(r"C:\anlyzeforex\forextele\telegram_session2.session", config["api_id"], config["api_hash"])
    
    await client1.start()
    await search_client(client1, "Client 1 (Primary)")
    await client1.disconnect()
    
    try:
        await client2.start()
        await search_client(client2, "Client 2 (9008400969)")
        await client2.disconnect()
    except Exception as e:
        print(f"Could not start Client 2: {e}")

if __name__ == "__main__":
    asyncio.run(main())
