import os
import sys
import glob
import json
import shutil
import asyncio
import psutil
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpIntermediate

SESSION_BASE = r"C:\anlyzeforex\forextele\telegram_session2_live"
CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"

TARGET_CHANNELS = {
    -1002350799273: "Market Trader Crypto Forex",
    -1001509806486: "Perfect Management",
    -1001721819841: "Trading with karol",
    -1002064435712: "JOSEFINA TRADER0",
    -1001218714411: "Profitway Trading Official",
    -1001661400724: "SureShot GOLD (VIP)"
}

def kill_stale_listeners():
    curr_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid == curr_pid:
                continue
            cmd = " ".join(p.cmdline() or [])
            if "telegram_signal_engine" in cmd and "SepPro" not in cmd:
                print(f"Stopping active listener (PID {p.pid}) to release session locks...")
                p.kill()
        except Exception:
            pass

def get_phone():
    p = input("\nEnter phone number [Press ENTER for +919008400869]: ").strip()
    if not p:
        p = "+919008400869"
    elif not p.startswith("+"):
        if len(p) == 10:
            p = "+91" + p
        else:
            p = "+" + p
    print(f"👉 Connecting with phone: {p}\n")
    return p

async def authenticate():
    kill_stale_listeners()

    if not os.path.exists(CONFIG_PATH):
        print("ERROR: config_telegram.json not found.")
        return

    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)

    api_id = cfg["api_id"]
    api_hash = cfg["api_hash"]

    print("=" * 70)
    print("🚀 TELEGRAM ACCOUNT 2 RE-AUTHENTICATION WIZARD")
    print("=" * 70)
    print("Target Channels to Arm:")
    for cid, name in TARGET_CHANNELS.items():
        print(f"  • {name} (ID: {cid})")
    print("=" * 70)

    client = TelegramClient(
        SESSION_BASE,
        api_id,
        api_hash,
        connection=ConnectionTcpIntermediate
    )

    print("\nInitiating Telegram login...")
    print("NOTE: You will be asked for the 5-digit verification code sent to your Telegram app.")
    
    await client.start(phone=get_phone)

    if await client.is_user_authorized():
        me = await client.get_me()
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS! Logged in as: {me.first_name} (@{me.username}) | Phone: +{me.phone}")
        print("=" * 70)

        print("\nVerifying dialogs for target Elite channels...")
        dialogs = await client.get_dialogs()
        dialog_dict = {d.id: d.title for d in dialogs if d.is_channel or d.is_group}

        found_count = 0
        for cid, name in TARGET_CHANNELS.items():
            if cid in dialog_dict:
                print(f"  ✅ FOUND & ARMED: {name} ({dialog_dict[cid]})")
                found_count += 1
            else:
                matched = [title for did, title in dialog_dict.items() if name.lower() in title.lower()]
                if matched:
                    print(f"  ✅ FOUND (Matched by name): {matched[0]}")
                    found_count += 1
                else:
                    print(f"  ⚠️ Not directly in top dialogs: {name}")

        print(f"\nTotal Elite channels verified: {found_count}/{len(TARGET_CHANNELS)}")
        
        # Mirror to telegram_session2.session as well
        try:
            shutil.copy2(SESSION_BASE + ".session", r"C:\anlyzeforex\forextele\telegram_session2.session")
        except Exception:
            pass

        print("\n🎉 Account 2 session file created successfully at:")
        print(f"   {SESSION_BASE}.session")
        print("TelegramSignalEngine will now automatically connect and listen to both accounts!")
    else:
        print("\n❌ Failed to authorize Account 2.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(authenticate())
