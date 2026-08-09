import asyncio
import csv
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
import unicodedata
from swarm_engine import OllamaSwarmEngine
from telegram_signal_engine import FOREX_GOLD_VIPS, CRYPTO_VIPS, SESSION_1, SESSION_2
import json

API_ID_1 = 15598350
API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"
API_ID_2 = 36022932
API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"

OUTPUT_CSV = "ollama_2day_verification.csv"

async def fetch_and_test():
    engine = OllamaSwarmEngine()
    # Mock MT5 execution so we don't accidentally place live trades
    engine.mt5_engine.execute_trade = lambda x: True
    
    clients = [
        TelegramClient("telegram_session_copy.session", API_ID_1, API_HASH_1),
        TelegramClient("telegram_session2_copy.session", API_ID_2, API_HASH_2)
    ]
    
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    
    with open(OUTPUT_CSV, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "Channel", "Raw_Message", "Status", "Reason", "Symbol", "Action", "Entry", "SL", "TP"])
        writer.writeheader()
        
        for client in clients:
            await client.start()
            dialogs = await client.get_dialogs()
            
            for dialog in dialogs:
                chat = dialog.entity
                raw_title = getattr(chat, 'title', '')
                raw_user = getattr(chat, 'username', '')
                
                chat_title = unicodedata.normalize('NFKC', raw_title).lower() if raw_title else ''
                chat_user = unicodedata.normalize('NFKC', raw_user).lower() if raw_user else ''
                
                valid_channel = False
                for vip in FOREX_GOLD_VIPS + CRYPTO_VIPS:
                    if vip in chat_title or vip in chat_user:
                        valid_channel = True
                        break
                        
                if not valid_channel:
                    continue
                    
                safe_title = raw_title.encode("ascii", "ignore").decode()
                print(f"Fetching from: {safe_title}")
                
                try:
                    async for msg in client.iter_messages(chat, offset_date=datetime.now(timezone.utc)):
                        if msg.date < two_days_ago:
                            break
                        
                        if msg.text:
                            res = await engine.process_telegram_signal(msg.text, channel_name=raw_title)
                            row = {
                                "Date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                                "Channel": raw_title,
                                "Raw_Message": msg.text.replace("\n", " "),
                                "Status": res.get("status", "UNKNOWN"),
                                "Reason": res.get("reason", ""),
                                "Symbol": res.get("symbol", ""),
                                "Action": res.get("action", ""),
                                "Entry": res.get("entry", ""),
                                "SL": res.get("final_sl", res.get("sl", "")),
                                "TP": res.get("final_tp1", res.get("tp1", ""))
                            }
                            writer.writerow(row)
                            f.flush()
                except Exception as e:
                    print(f"Error fetching {safe_title}: {e}")
                    
            await client.disconnect()
            
    print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(fetch_and_test())
