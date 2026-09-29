import asyncio
from telethon import TelegramClient
import os

API_ID = 15598350
API_HASH = "8cb282656e09b0983a9b71365b0813f4"
SESSION = "telegram_session"

async def main():
    if os.path.exists(SESSION + ".session"):
        os.remove(SESSION + ".session")
        print("Deleted old corrupted session file.")
    
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    
    phone = input("Please enter the Phone Number for Account 1 (with country code, e.g., +1234567890): \n")
    print(f"Requesting code for {phone}...")
    await client.send_code_request(phone)
    
    code = input("Please enter the 5-digit code Telegram just sent you: \n")
    try:
        await client.sign_in(phone, code)
        print("\n✅ Successfully authenticated! The new telegram_session.session is ready.")
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Disable Windows ProactorEventLoop which can cause issues with input
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
