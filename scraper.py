import asyncio
import sys
from telethon import TelegramClient
from datetime import datetime, timezone
import os
import re

sys.stdout.reconfigure(encoding='utf-8')

API_ID_1 = 15598350
API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"
API_ID_2 = 36022932
API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"

SESSION_1 = 'c:/anlyzeforex/forextele/telegram_session.session'
SESSION_2 = 'c:/anlyzeforex/forextele/telegram_session2.session'
OUT_DIR = 'c:/anlyzeforex/forextele/artifacts/channel_scrapes'
os.makedirs(OUT_DIR, exist_ok=True)

TARGET_DATE = datetime(2026, 7, 15, tzinfo=timezone.utc)
START_OF_DAY = TARGET_DATE.replace(hour=0, minute=0, second=0, microsecond=0)

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

async def scrape_account(session_path, api_id, api_hash, acc_name):
    print(f"\nStarting scrape for {acc_name} using {session_path}...")
    if not os.path.exists(session_path):
        print(f"ERROR: Session file {session_path} not found!")
        return
        
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.start()
    except Exception as e:
        print(f"Failed to start {acc_name}: {e}")
        return
    
    me = await client.get_me()
    acc_owner = f"{me.first_name} {me.last_name or ''}".strip()
    print(f"[{acc_name}] Connected as: {acc_owner} (ID: {me.id})")
    
    try:
        dialogs = await client.get_dialogs()
        for dialog in dialogs:
            if not dialog.is_channel and not dialog.is_group:
                continue
                
            ch_name = dialog.name
            ch_id = dialog.entity.id
            safe_name = clean_filename(ch_name)
            if not safe_name: safe_name = f"Unnamed_{ch_id}"
            
            # Since both accounts might be in the same channel, we will save them separately 
            # to avoid mixing or we can just append. Let's create account-specific files!
            filepath = os.path.join(OUT_DIR, f"[{acc_name}] {safe_name}.md")
            
            messages = []
            try:
                # Fetch up to 100 messages from today
                async for msg in client.iter_messages(dialog, limit=100):
                    if msg.date < START_OF_DAY:
                        break
                    if msg.text and msg.text.strip():
                        messages.append(msg)
            except Exception as e:
                # Silently skip permission errors for chats we can't read
                continue
                
            if messages:
                print(f"[{acc_name}] Scraped {len(messages)} msgs from {ch_name}".encode('ascii', 'ignore').decode())
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Channel Name: {ch_name}\n")
                    f.write(f"# Channel ID: {ch_id}\n")
                    f.write(f"# Telegram Account: {acc_name} ({acc_owner})\n")
                    f.write(f"Scraped for Date: 2026-07-15\n\n")
                    
                    for msg in reversed(messages):
                        time_str = msg.date.strftime('%H:%M:%S UTC')
                        f.write(f"### Message at {time_str}\n")
                        f.write("```text\n")
                        f.write(msg.text + "\n")
                        f.write("```\n\n---\n\n")
    finally:
        await client.disconnect()

async def main():
    print("Starting Telegram Scrape...")
    await scrape_account(SESSION_1, API_ID_1, API_HASH_1, "Account 1")
    await scrape_account(SESSION_2, API_ID_2, API_HASH_2, "Account 2")
    print("\nScrape Complete!")

if __name__ == '__main__':
    asyncio.run(main())
