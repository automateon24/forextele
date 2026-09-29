import asyncio
import json
import shutil
from pathlib import Path
from telethon import TelegramClient

BASE_DIR = Path(__file__).parent.parent
SESSION_2 = BASE_DIR / "telegram_session2.session"
QUERY_SESSION = BASE_DIR / "scratch" / "telegram_session_query.session"

API_ID_2 = 36022932
API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"

async def list_all_dialog_ids():
    shutil.copy2(SESSION_2, QUERY_SESSION)
    client = TelegramClient(str(QUERY_SESSION), API_ID_2, API_HASH_2)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Not authorized on query session")
        return
        
    dialogs = await client.get_dialogs()
    results = []
    for d in dialogs:
        if d.is_channel or d.is_group:
            title = d.title or ""
            username = getattr(d.entity, "username", "") or ""
            cid = d.id
            results.append({
                "id": cid,
                "title": title,
                "username": username,
                "account": "Account 2 (919008400869)"
            })
            
    await client.disconnect()
    
    out_file = BASE_DIR / "all_dialogs_account2.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"Dumped {len(results)} channels/groups to all_dialogs_account2.json")

if __name__ == "__main__":
    asyncio.run(list_all_dialog_ids())
