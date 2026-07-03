import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import MetaTrader5 as mt5
import httpx
from telethon import TelegramClient

# ------------------------------------------------------------
# Configuration (paths are relative to this script's directory)
# ------------------------------------------------------------
BASE_DIR = Path(__file__).parent

MT5_CFG = json.loads((BASE_DIR / "mt5_config.json").read_text(encoding="utf-8"))
AI_CFG = json.loads((BASE_DIR / "ai_config.json").read_text(encoding="utf-8"))

TELEGRAM_API_ID = 15598350
TELEGRAM_API_HASH = "8cb282656e09b0983a9b71365b0813f4"
SESSION_FILE = BASE_DIR / "telegram_session.session"

CHANNELS_FILE_1 = BASE_DIR / "telegram_channels_list.txt"
CHANNELS_FILE_2 = BASE_DIR / "telegram_channels_list2.txt"

# ------------------------------------------------------------
# Helper utilities – same logic as live_order_executor
# ------------------------------------------------------------
def load_channel_map() -> dict:
    mapping = {}
    def _read(p: Path):
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 2:
                    continue
                cid = parts[0].strip().lstrip("-")
                name = parts[1].strip()
                mapping[cid] = name
    _read(CHANNELS_FILE_1)
    _read(CHANNELS_FILE_2)
    return mapping

def is_forex(symbol: str) -> bool:
    s = symbol.upper()
    return "/" in s or any(cur in s for cur in ("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "XAU", "GOLD"))

def lot_for_crypto(entry_price: float) -> float:
    exposure = 10.0
    leverage = 5.0
    return (exposure * leverage) / entry_price

# ------------------------------------------------------------
# MT5 connection helpers
# ------------------------------------------------------------
def init_mt5():
    if not mt5.initialize(login=MT5_CFG["login"], server=MT5_CFG["server"], password=MT5_CFG["password"]):
        st.error(f"MT5 init failed: {mt5.last_error()}")
        return False
    return True

def shutdown_mt5():
    mt5.shutdown()

def place_order(symbol: str, action: str, volume: float):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).ask if action == "BUY" else mt5.symbol_info_tick(symbol).bid,
        "deviation": 10,
        "magic": 999999,
        "comment": "DashboardTest",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        st.error(f"Order failed (retcode {result.retcode}): {result.comment}")
        return None
    st.success(f"Order placed – ticket {result.order}, {action} {symbol} {volume}")
    return result.order

# ------------------------------------------------------------
# AI request – simple wrapper (Gemini / OpenAI)
# ------------------------------------------------------------
async def ask_ai(prompt: str) -> str:
    if AI_CFG["provider"].lower() == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        url = f"{endpoint}?key={AI_CFG['api_key']}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        resp = httpx.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {AI_CFG['api_key']}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        resp = httpx.post(endpoint, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from the channel '{channel_name}'.\n"
        f"It may contain a trade signal. If it contains a real BUY/SELL signal, output exactly one line: ACTION SYMBOL ENTRY_PRICE [LOT].\n"
        f"IMPORTANT: If the signal is for Gold (XAUUSD, XAU, etc), use the symbol GOLD.\n"
        f"If there is no trade, reply with NO_TRADE.\nMessage:\n{message}"
    )

# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------
st.title("📈 Telegram ↔ MT5 Live Dashboard")

# ---- Telegram connection status ----
st.subheader("Telegram connection")
telegram_status_placeholder = st.empty()

async def check_telegram():
    client = TelegramClient(str(SESSION_FILE), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    try:
        await client.connect()
        if await client.is_user_authorized():
            telegram_status_placeholder.success("✅ Connected and authorised")
        else:
            telegram_status_placeholder.error("❌ Not authorised – run telegram_setup2 to login")
    except Exception as e:
        telegram_status_placeholder.error(f"❌ Connection error: {e}")
    finally:
        await client.disconnect()

# Run the async check (Streamlit runs in sync, so we use asyncio.run)
asyncio.run(check_telegram())

# ---- Manual test trades ----
st.subheader("Manual test trades (Gold & EUR/USD)")
col1, col2 = st.columns(2)
with col1:
    if st.button("Buy Gold (GOLD)"):
        if init_mt5():
            place_order("GOLD", "BUY", 0.01)
            shutdown_mt5()
with col2:
    if st.button("Sell Gold (GOLD)"):
        if init_mt5():
            place_order("GOLD", "SELL", 0.01)
            shutdown_mt5()
col3, col4 = st.columns(2)
with col3:
    if st.button("Buy EUR/USD"):
        if init_mt5():
            place_order("EURUSD", "BUY", 0.01)
            shutdown_mt5()
with col4:
    if st.button("Sell EUR/USD"):
        if init_mt5():
            place_order("EURUSD", "SELL", 0.01)
            shutdown_mt5()

# ---- Recent Telegram messages and AI actions ----
st.subheader("Recent Telegram signals (AI analysed)")
# Load a simple JSON log that live_order_executor would write (if not present, show placeholder)
log_path = BASE_DIR / "message_ai_log.json"
if log_path.exists():
    with log_path.open("r", encoding="utf-8") as f:
        logs = json.load(f)
else:
    logs = []

# Show the last 5 entries in a table
if logs:
    recent = logs[-5:][::-1]
    for entry in recent:
        st.markdown(f"**Channel:** {entry.get('channel_name','?')}  ")
        st.markdown(f"**Message:** {entry.get('message','')[:120]}…  ")
        st.markdown(f"**AI reply:** {entry.get('ai_reply','')}  ")
        order_status = entry.get('order_status','Pending')
        if order_status == 'Success':
            st.success(f"Order placed – ticket {entry.get('ticket')}")
        elif order_status == 'Failed':
            st.error(f"Order failed – {entry.get('error_msg')}")
        else:
            st.info(order_status)
        st.divider()
else:
    st.info("No message log found – live_order_executor will create \`message_ai_log.json\` when it processes signals.")

# ---- Helper to force a manual AI analysis on a custom text ----
st.subheader("Manual AI analysis & order test")
custom_msg = st.text_area("Enter a sample Telegram message", height=150)
custom_channel = st.text_input("Channel name (for context)")
if st.button("Analyse & place order"):
    if custom_msg.strip():
        prompt = build_prompt(custom_msg, custom_channel or "Custom")
        try:
            ai_reply = asyncio.run(ask_ai(prompt))
            st.write("AI reply:", ai_reply)
            if ai_reply.upper().strip() != "NO_TRADE":
                parts = ai_reply.split()
                if len(parts) >= 3:
                    action, symbol, entry_str = parts[0].upper(), parts[1].upper(), parts[2]
                    if symbol in ["XAUUSD", "XAU", "XAU/USD"]:
                        symbol = "GOLD"
                    try:
                        entry_val = float(entry_str)
                    except:
                        entry_val = 1.0
                    lot = float(parts[3]) if len(parts) >= 4 else (0.01 if is_forex(symbol) else lot_for_crypto(entry_val))
                    if init_mt5():
                        ticket = place_order(symbol, action, lot)
                        shutdown_mt5()
                else:
                    st.warning("AI reply format unexpected.")
        except Exception as e:
            st.error(f"AI request failed: {e}")

st.caption("*Live Order Executor will write to `message_ai_log.json` each time it processes a signal, allowing this dashboard to display the latest activity.*")
