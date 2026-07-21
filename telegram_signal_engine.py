import asyncio
from telethon import TelegramClient, events
import logging
from pathlib import Path
import os
import json
import unicodedata
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
    "global profit club", "gold_mast78", "forexero", "forexking1132",
    "xauusd signal 99%", "josefina trader", "forex trading master",
    "gold sniper pips", "messy forex", "forex trading tips", "rasrasanforex",
    "riaogoldforex", "gold snipers", "michael gold trader", "grade profit forex",
    "forex market", "gold dreams trader", "xau profit zone", "saviour gold ea",
    "culersforex", "global profit culb", "gold scalper", "victory forex", 
    "source fx hub", "mr.david, xau/usd club", "gold fx network",
    "dubai capital fx group 3", "onyx alpha trades", "xauusd accurate signals",
    "mrgoldenway trader", "vip-mrgoldencircle", "max leverage"
]

CRYPTO_VIPS = [
    "market trader crypto", "coin chief", "binance killers", "crypto world updates",
    "binance 360", "dil se trader crypto", "cryptosimplicity", "crypto radar",
    "king crypto scalp", "earlypumpdetector"
]

def load_channels():
    # Deprecated: We now use dynamic Title/Username matching for the 23 VIPs
    return {}

async def heartbeat_loop():
    while True:
        try:
            status_file = BASE_DIR / "telegram_status.json"
            with open(status_file, "w") as f:
                import time
                json.dump({"last_heartbeat": time.time(), "status": "Active"}, f)
        except: pass
        await asyncio.sleep(10)

async def main():
    asyncio.create_task(heartbeat_loop())
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
    
    async def handler_acc1(event): await process_event(event, "Account 1")
    async def handler_acc2(event): await process_event(event, "Account 2")

    async def process_event(event, account_id):
        try:
            chat = await event.get_chat()
            if chat is None:
                return
                
            raw_title = getattr(chat, 'title', '')
            raw_user = getattr(chat, 'username', '')
            
            chat_title = raw_title.encode('ascii', 'ignore').decode('ascii').lower() if raw_title else ''
            chat_user = raw_user.encode('ascii', 'ignore').decode('ascii').lower() if raw_user else ''
            
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
                
            raw_msg_text = event.raw_text
            if not raw_msg_text:
                return
                
            text = raw_msg_text.encode('ascii', 'ignore').decode('ascii')
            if not text.strip():
                return
                
            channel_name_str = getattr(chat, 'title', chat_user)
            log.info("=========================================")
            log.info(f"[{channel_group}] Signal Detected from '{channel_name_str}'! Routing to Swarm...")
            
            asyncio.create_task(swarm.process_telegram_signal(text, channel_name_str, account_id))
            
        except Exception as e:
            log.error(f"Listener Exception: {e}")

    # Register handler on both clients
    client1.on(events.NewMessage())(handler_acc1)
    client2.on(events.NewMessage())(handler_acc2)
    
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
