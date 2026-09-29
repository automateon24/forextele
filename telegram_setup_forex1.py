import asyncio
from telethon import TelegramClient
from pathlib import Path

BASE_DIR = Path(__file__).parent
SESSION_1_PATH = BASE_DIR / "telegram_session_forex1.session"

API_ID_1 = 15598350
API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"

async def main():
    print("=================================================================")
    print("  TELEGRAM ACCOUNT 1 AUTHENTICATION (FOREX DEDICATED SESSION)    ")
    print("=================================================================")
    print("This will create a dedicated session file: telegram_session_forex1.session")
    print("It will NOT conflict with SepPro or Indian trading systems.")
    print("Please enter your Phone Number and the OTP received on Telegram:\n")

    client = TelegramClient(str(SESSION_1_PATH), API_ID_1, API_HASH_1)
    await client.start()
    
    me = await client.get_me()
    print(f"\nSUCCESS! Account 1 Authenticated as: {getattr(me, 'first_name', '')} (Phone: {getattr(me, 'phone', '')})")
    print(f"Session saved to: {SESSION_1_PATH}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
