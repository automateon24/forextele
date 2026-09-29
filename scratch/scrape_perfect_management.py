import sys
import asyncio
import json
import re
from pathlib import Path
from telethon import TelegramClient
from datetime import datetime, timezone, timedelta
import shutil

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
SESSION_SRC = BASE_DIR / "telegram_session2.session"
SESSION_SCRAPE = BASE_DIR / "telegram_session_scrape.session"

# Make a fresh snapshot copy so we never collide with the running engine
shutil.copy2(str(SESSION_SRC), str(SESSION_SCRAPE))

API_ID_2 = 36022932
API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"
CHANNEL_ID = -1001509806486

async def scrape_perfect_management():
    c = TelegramClient(str(SESSION_SCRAPE), API_ID_2, API_HASH_2)
    await c.connect()
    if not await c.is_user_authorized():
        print("Client not authorized on snapshot")
        return

    entity = await c.get_entity(CHANNEL_ID)
    print(f"Connected to '{getattr(entity, 'title', '')}' (@{getattr(entity, 'username', '')})")

    since_date = datetime.now(timezone.utc) - timedelta(days=8)
    print(f"Scraping messages since {since_date.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

    messages_data = []
    async for msg in c.iter_messages(entity, limit=200):
        if not msg.date:
            continue
        msg_dt = msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc)
        if msg_dt < since_date:
            break
        text = msg.raw_text or ""
        if not text.strip():
            continue
            
        messages_data.append({
            "id": msg.id,
            "date": msg_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "text": text
        })

    out_file = BASE_DIR / "perfect_management_scraped.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, indent=2)

    print(f"Scraped {len(messages_data)} messages from Perfect Management.")
    print("\n--- SAMPLE MESSAGES ---")
    for m in messages_data[:12]:
        preview = m['text'].replace('\n', ' -- ')[:100]
        print(f"[{m['date']}] ID {m['id']}: {preview}")

    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(scrape_perfect_management())
