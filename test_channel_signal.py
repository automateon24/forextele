import asyncio
from telethon import TelegramClient
from scrape_and_ollama import ask_ollama
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / "telegram_session2.session"
API_ID = 26508933
API_HASH = "8a3d54025a1e74fec9de848a6552a425"

async def main():
    async with TelegramClient(str(SESSION_FILE), API_ID, API_HASH) as client:
        channel = None
        async for dialog in client.iter_dialogs():
            if "SureShot" in dialog.name or "Sureshot" in dialog.name:
                channel = dialog.entity
                break
        if not channel:
            print("Channel not found")
            return
            
        print(f"Fetching messages from {channel.title}...")
        
        messages = await client.get_messages(channel, limit=3)
        async with httpx.AsyncClient(timeout=30) as http_client:
            for msg in messages:
                if msg.text:
                    print(f"--- MESSAGE ---\n{msg.text}")
                    ai_response = await ask_ollama(http_client, msg.text)
                    print(f"AI RESPONSE: {ai_response}\n")

if __name__ == "__main__":
    asyncio.run(main())
