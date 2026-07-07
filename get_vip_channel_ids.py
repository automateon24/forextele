import asyncio
from telethon import TelegramClient
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\Ai_forextele")
SESSION_FILE = BASE_DIR / "telegram_session2.session"

API_ID = 36022932
API_HASH = "b9d59de22c25223f94f0e513c04279df"

FOREX_GOLD_VIPS = [
    "scalping gold", "goldsnipers11", "sureshot fx", "sureshot gold", 
    "gold trade signals", "easy forex", "gold trader", "global gold insight",
    "global profit club", "gold_mast78", "forexero", "forexking1132"
]

CRYPTO_VIPS = [
    "market trader crypto", "coin chief", "binance killers", "crypto world updates",
    "binance 360", "dil se trader crypto", "cryptosimplicity", "crypto radar",
    "king crypto scalp", "earlypumpdetector"
]

async def scan_session(session_name, api_id, api_hash):
    print(f"\n--- Scanning Account: {session_name} ---")
    session_path = BASE_DIR / session_name
    client = TelegramClient(str(session_path), api_id, api_hash)
    
    await client.connect()
    if not await client.is_user_authorized():
        print(f"❌ Session {session_name} is NOT authorized. Cannot scan.")
        await client.disconnect()
        return 0
        
    print("Fetching Dialogs (Channels)...")
    dialogs = await client.get_dialogs()
    found_count = 0
    
    for dialog in dialogs:
        title = dialog.title.lower() if dialog.title else ""
        username = dialog.entity.username.lower() if hasattr(dialog.entity, 'username') and dialog.entity.username else ""
        chat_id = dialog.id
        
        # Check FOREX/GOLD
        for vip in FOREX_GOLD_VIPS:
            if vip in title or vip in username:
                print(f"[GOLD_FOREX] Title: {dialog.title} | ID: {chat_id}")
                found_count += 1
                break
                
        # Check CRYPTO
        for vip in CRYPTO_VIPS:
            if vip in title or vip in username:
                print(f"[CRYPTO] Title: {dialog.title} | ID: {chat_id}")
                found_count += 1
                break

    await client.disconnect()
    return found_count

async def main():
    print("Initiating Dual-Account VIP Scan...")
    
    # Try Account 1
    found_1 = await scan_session("telegram_session.session", 15598350, "8cb282656e09b0983a9b71365b0813f4")
    
    # Try Account 2 (with its known API keys)
    found_2 = await scan_session("telegram_session2.session", 36022932, "b9d59de22c25223f94f0e513c04279df")
    
    print(f"\nTotal VIP Channels Found Across Both Accounts: {found_1 + found_2} / 23")

if __name__ == "__main__":
    asyncio.run(main())
