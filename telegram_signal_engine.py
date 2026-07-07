import asyncio
from telethon import TelegramClient, events
import logging
from pathlib import Path
import os
import json
from swarm_engine import OllamaSwarmEngine

BASE_DIR = Path(__file__).parent
SESSION_1 = BASE_DIR / "telegram_session.session"
SESSION_2 = BASE_DIR / "telegram_session2.session"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TELEGRAM_LISTENER] - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# VIP Channel Target Lists
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

def load_channels():
    # Deprecated: We now use dynamic Title/Username matching for the 23 VIPs
    return {}

async def main():
    log.info("Booting Autonomous Dual-Account Telegram Listener...")
    swarm = OllamaSwarmEngine()
    
    # Account 1 Config
    API_ID_1 = 15598350
    API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"
    client1 = TelegramClient(str(SESSION_1), API_ID_1, API_HASH_1)
    
    # Account 2 Config
    API_ID_2 = 36022932
    API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"
    client2 = TelegramClient(str(SESSION_2), API_ID_2, API_HASH_2)
    
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', '').lower()
            chat_user = getattr(chat, 'username', '').lower()
            
            valid_channel = False
            channel_group = "UNKNOWN"
            
            for vip in FOREX_GOLD_VIPS:
                if vip in chat_title or vip in chat_user:
                    valid_channel = True
                    channel_group = "GOLD_FOREX"
                    break
                    
            if not valid_channel:
                for vip in CRYPTO_VIPS:
                    if vip in chat_title or vip in chat_user:
                        valid_channel = True
                        channel_group = "CRYPTO"
                        break
                
            if not valid_channel:
                return
                
            text = event.raw_text
            if not text:
                return
                
            log.info("=========================================")
            log.info(f"[{channel_group}] Signal Detected from '{getattr(chat, 'title', chat_user)}'! Routing to Swarm...")
            
            asyncio.create_task(swarm.process_telegram_signal(text))
            
        except Exception as e:
            log.error(f"Listener Exception: {e}")

    # Register handler on both clients
    client1.on(events.NewMessage())(handler)
    client2.on(events.NewMessage())(handler)
    
    log.info("Connecting Account 1...")
    await client1.start()
    log.info("Connecting Account 2...")
    await client2.start()
    
    log.info("Dual-Account Telegram Listeners Authenticated and Scanning.")
    
    try:
        await asyncio.gather(
            client1.run_until_disconnected(),
            client2.run_until_disconnected()
        )
    except KeyboardInterrupt:
        log.info("Dual Listener shutting down.")

if __name__ == "__main__":
    asyncio.run(main())
