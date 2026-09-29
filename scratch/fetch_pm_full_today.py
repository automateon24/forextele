import asyncio
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpIntermediate
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
ACC2_API_ID = 36022932
ACC2_API_HASH = "b9d59de22c25223f94f0e513c04279df"
ACC2_SESSION = BASE_DIR / "scratch" / "scrape_session2"

async def get_pm_all_messages():
    client = TelegramClient(
        str(ACC2_SESSION), ACC2_API_ID, ACC2_API_HASH,
        connection=ConnectionTcpIntermediate
    )
    await client.connect()
    
    # Perfect Management channel ID -1001509806486
    entity = await client.get_entity(-1001509806486)
    print(f"Connected to: {entity.title} (ID: {entity.id})")

    today_start = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
    messages = []
    async for msg in client.iter_messages(entity, limit=40):
        if msg.date < today_start:
            break
        messages.append(msg)

    print(f"Total messages today: {len(messages)}")
    for m in reversed(messages):
        reply = f" (Reply to: {m.reply_to_msg_id})" if m.reply_to_msg_id else ""
        print(f"\n[ID: {m.id}] Date: {m.date.strftime('%Y-%m-%d %H:%M:%S UTC')}{reply}")
        print(f"Text:\n{m.text}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(get_pm_all_messages())
