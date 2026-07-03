import json
import os
import asyncio
from telethon import TelegramClient

CONFIG_PATH = r"C:\25stragy\config_telegram.json"

async def main():
    if not os.path.exists(CONFIG_PATH):
        print("Error: config_telegram.json not found.")
        return
        
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        
    api_id = config['api_id']
    api_hash = config['api_hash']
    
    print(f"Connecting to Telegram with API ID: {api_id}...")
    
    # This will securely create a session file and ask for your phone/OTP
    client = TelegramClient(r"C:\25stragy\telegram_session", api_id, api_hash)
    await client.start()
    
    print("\n✅ --- SUCCESSFULLY LOGGED IN --- ✅\n")
    print("Fetching your Groups and Channels...")
    
    dialogs = await client.get_dialogs()
    
    output_file = r"C:\25stragy\telegram_channels_list.txt"
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("--- YOUR TELEGRAM CHANNELS ---\n")
        out.write("Format: [Chat ID] | [Name]\n\n")
        
        for d in dialogs:
            if d.is_channel or d.is_group:
                line = f"{d.id} | {d.name}\n"
                out.write(line)
                
    print(f"\n✅ Done! I have saved all your Channel IDs to: {output_file}")
    print("Please open that file, find the 10 vendor channels, and send me their Chat IDs.")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
