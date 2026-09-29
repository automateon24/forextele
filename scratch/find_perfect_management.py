import sys
import asyncio
from pathlib import Path
from telethon import TelegramClient

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
SESSION_2 = BASE_DIR / "telegram_session2.session"
API_ID_2 = 36022932
API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"

def check_files():
    print("--- Searching in cached channel lists ---")
    for fname in ["telegram_channels_list.txt", "telegram_channels_list2.txt"]:
        p = BASE_DIR / fname
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "perfect management" in line.lower() or "perfectmanagement" in line.lower():
                        print(f"Found in {fname}: {line.strip()}")

async def check_live():
    print("\n--- Connecting to Account 2 ---")
    c = TelegramClient(str(SESSION_2), API_ID_2, API_HASH_2)
    await c.connect()
    if not await c.is_user_authorized():
        print("Not authorized on Account 2")
        return
        
    found = []
    async for d in c.iter_dialogs(limit=400):
        name = d.name.lower()
        username = getattr(d.entity, 'username', '') or ''
        if "perfect management" in name or "perfectmanagement" in name or "perfectmanagement" in username.lower():
            print(f"FOUND IN ACCOUNT 2: ID: {d.id} | Name: '{d.name}' | Username: @{username}")
            found.append(d)
            
    if not found:
        print("Not found in first 400 dialogs. Trying get_entity('PerfectManagement_786')...")
        for target in ["PerfectManagement_786", "PerfectManagement1"]:
            try:
                ent = await c.get_entity(target)
                print(f"SUCCESS resolving '{target}': ID: {ent.id} | Title: '{getattr(ent, 'title', '')}'")
                found.append(ent)
            except Exception as e:
                print(f"Could not resolve '{target}': {e}")
                
    await c.disconnect()

if __name__ == "__main__":
    check_files()
    asyncio.run(check_live())
