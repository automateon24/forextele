import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

SYMBOL_COOLDOWN = {}

# ------------------------------------------------------------
# Configuration –‑ adjust paths if you move the repo
# ------------------------------------------------------------
BASE_DIR = Path(__file__).parent

# MT5 credentials –‑ stored in a JSON file (already created)
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
MT5_CFG = json.loads(MT5_CFG_PATH.read_text(encoding="utf-8"))

# AI credentials –‑ stored in a JSON file (you must fill the API key)
AI_CFG_PATH = BASE_DIR / "ai_config.json"
AI_CFG = json.loads(AI_CFG_PATH.read_text(encoding="utf-8"))

# Telegram session –‑ will be created automatically if missing
TELEGRAM_API_ID = 15598350          # <<<‑ YOUR TELEGRAM API ID
TELEGRAM_API_HASH = "8cb282656e09b0983a9b71365b0813f4"  # <<<‑ YOUR TELEGRAM API HASH
SESSION_FILE = BASE_DIR / "telegram_session.session"

# Channel list files (you already have them)
CHANNELS_FILE_1 = BASE_DIR / "telegram_channels_list.txt"
CHANNELS_FILE_2 = BASE_DIR / "telegram_channels_list2.txt"

# ------------------------------------------------------------
# Dry‑run toggle –‑ set to False only when you are ready to trade
# ------------------------------------------------------------
DRY_RUN = False   # <<<‑ Set to False to place real orders on MT5

# ------------------------------------------------------------
# Logging –‑ all activity goes to a log file
# ------------------------------------------------------------
logging.basicConfig(
    filename=BASE_DIR / "live_order_executor.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------
# Helper utilities
# ------------------------------------------------------------
def load_channel_map() -> dict:
    mapping = {
        "-1001582520126": "Scalping Gold",
        "goldsnipers11": "GOLD Snipers",
        "Marketradercrypto": "Market Trader Crypto Forex",
        "sureshot_fx": "Sureshot FX",
        "-1001661400724": "SureShot GOLD (VIP)",
        "-1001986940315": "GOLD TRADE SIGNALS",
        "-1001520053536": "Coin Chief",
        "-1001234364040": "Binance Killers VIP",
        "-1001652601224": "Crypto World Updates",
        "-1001553551852": "Binance 360",
        "-1002471742018": "DIL SE TRADER Crypto",
        "-1001737978232": "CryptoSimplicity News",
        "-1001754095061": "Crypto Radar",
        "-1001422000261": "Sureshot FX VIP",
        "GOLD_MAST78": "GOLD_MAST78",
        "forexero": "forexero",
        "forexking1132": "forexking1132",
        "earlypumpdetector": "earlypumpdetector",
        "-1001704062350": "King Crypto Scalp [ LIVE ]",
        "-1001178704438": "GLOBAL PROFIT CLUB",
        "-1002458369770": "EASY FOREX",
        "-1001260601611": "GOLD TRADER",
        "-1001495198097": "GLOBAL GOLD INSIGHT"
    }
    return mapping

def get_active_sessions() -> list:
    now_utc = datetime.utcnow()
    hour = now_utc.hour
    sessions = []
    if 22 <= hour or hour < 7:
        sessions.append("Sydney")
    if 23 <= hour or hour < 8:
        sessions.append("Tokyo")
    if 8 <= hour < 17:
        sessions.append("London")
    if 13 <= hour < 22:
        sessions.append("New York")
    return sessions

def is_forex(symbol: str) -> bool:
    s = symbol.upper()
    return "/" in s or any(cur in s for cur in ("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "XAU", "GOLD"))

# ------------------------------------------------------------
# AI request –‑ simple wrapper (replace with actual Gemini/OpenAI call)
# ------------------------------------------------------------
import httpx
import asyncio

async def ask_ai(prompt: str) -> str:
    for attempt in range(3):
        try:
            if AI_CFG["provider"].lower() == "gemini":
                # Using Ollama Local API
                endpoint = "http://127.0.0.1:11434/api/generate"
                payload = {
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_thread": 4
                    }
                }
                resp = httpx.post(endpoint, json=payload, timeout=45.0)
                resp.raise_for_status()
                return resp.json()["response"].strip()
            else:  # OpenAI fallback
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
        except httpx.HTTPStatusError as e:
            if attempt < 2:
                log.warning(f"AI API Error (Attempt {attempt+1}): {e.response.status_code}. Retrying in 2 seconds...")
                await asyncio.sleep(2)
            else:
                log.error(f"AI API Final Failure: {e}")
                raise
        except Exception as e:
            if attempt < 2:
                log.warning(f"AI API Exception (Attempt {attempt+1}): {e}. Retrying in 2 seconds...")
                await asyncio.sleep(2)
            else:
                raise

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from the channel \"{channel_name}\". "
        f"It may contain a trade signal, a promotion, or just chatter.\n"
        f"If it contains a *real* trade signal, respond with **exactly** one line in the form:\n"
        f"    ACTION SYMBOL ENTRY_PRICE SL TP\n"
        f"where ACTION is BUY or SELL, SYMBOL is like EURUSD or GBPJPY (use GOLD for XAU). ENTRY_PRICE, SL, and TP are numbers. If SL or TP is not given, output 0.\n"
        f"If there is no genuine trade, reply with the single word: NO_TRADE.\n"
        f"Message:\n{message}"
    )

# ------------------------------------------------------------
# MT5 wrappers –‑ respect DRY_RUN
# ------------------------------------------------------------
import importlib
if not DRY_RUN:
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        log.error(f"MetaTrader5 import failed: {e}")
        raise

def init_mt5() -> bool:
    if DRY_RUN:
        log.info("[DRY‑RUN] Skipping MT5 initialisation")
        return True
    if not mt5.initialize(login=MT5_CFG["login"], server=MT5_CFG["server"], password=MT5_CFG["password"]):
        log.error(f"MT5 init failed: {mt5.last_error()}")
        return False
    log.info("MT5 connection established")
    return True

def shutdown_mt5():
    if DRY_RUN:
        log.info("[DRY‑RUN] Skipping MT5 shutdown")
        return
    mt5.shutdown()
    log.info("MT5 connection closed")

def lot_for_crypto(entry_price: float) -> float:
    exposure = 10.0
    leverage = 5.0
    return (exposure * leverage) / entry_price

def calculate_dynamic_lot(symbol, base_allocation=200.0, leverage=1000, risk_pct=0.05):
    """
    Dynamic $200 compounding lot size calculator for Telegram signals.
    """
    info = mt5.symbol_info(symbol)
    if not info: return 0.01
    contract_size = info.trade_contract_size
    price = info.ask
    if price == 0 or contract_size == 0: return 0.01
    
    total_leverage_power = base_allocation * leverage
    max_volume = total_leverage_power / (price * contract_size)
    target_volume = max_volume * risk_pct
    step = info.volume_step
    target_volume = max(info.volume_min, min(round(target_volume / step) * step, info.volume_max))
    return target_volume

def get_atr_fallback(symbol):
    """Fallback ATR calculation if Telegram signal misses SL/TP"""
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 14)
        if rates is None or len(rates) == 0: return 0.0
        tr_sum = sum((r['high'] - r['low']) for r in rates)
        return tr_sum / len(rates)
    except:
        return 0.0

def log_trade_event(source, symbol, action, entry_price, lot, sl, tp, reason):
    """Centralized logging for entry/exit reasoning"""
    log_file = BASE_DIR / "master_trade_ledger.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = "Timestamp,Source,Symbol,Action,EntryPrice,Lot,SL,TP,Reason\n"
    if not log_file.exists():
        with open(log_file, "w") as f:
            f.write(header)
    with open(log_file, "a") as f:
        f.write(f"{timestamp},{source},{symbol},{action},{entry_price},{lot},{sl},{tp},{reason}\n")

def place_order(symbol: str, action: str, volume: float, sl: float=0.0, tp: float=0.0, channel_name: str=""):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        log.error(f"[{symbol}] Failed to get tick data (Market Closed?)")
        return 0
    price = tick.ask if action == "BUY" else tick.bid
    
    if DRY_RUN:
        log.info(f"[DRY‑RUN] Would place {action} {symbol} volume={volume}")
        return 1
    # Autonomous ATR Fallback if SL/TP is missing
    if sl == 0.0 or tp == 0.0:
        atr = get_atr_fallback(symbol)
        point = mt5.symbol_info(symbol).point
        atr_points = atr / point if point > 0 else 0
        if sl == 0.0 and atr_points > 0:
            sl = price - (atr_points * 1.5 * point) if action == "BUY" else price + (atr_points * 1.5 * point)
        if tp == 0.0 and atr_points > 0:
            tp = price + (atr_points * 3.0 * point) if action == "BUY" else price - (atr_points * 3.0 * point)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 10,
        "magic": 777777,
        "comment": f"Telegram : {channel_name}"[:31] if channel_name else "TelegramSignal",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log.error(f"Order failed (retcode {result.retcode}): {result.comment}")
        return 0
        
    ticket = result.order
    
    # Step 2: Apply Hard Stop Loss and Take Profit
    if sl > 0 or tp > 0:
        digits = mt5.symbol_info(symbol).digits
        sl_request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": round(float(sl), digits) if sl > 0 else 0.0,
            "tp": round(float(tp), digits) if tp > 0 else 0.0,
            "magic": 777777
        }
        sl_res = mt5.order_send(sl_request)
        if sl_res.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"SL/TP modification failed for ticket {ticket}: {sl_res.comment}")
        else:
            log.info(f"SL/TP successfully applied to ticket {ticket}")

    log_trade_event(f"Telegram ({channel_name})", symbol, action, price, volume, sl, tp, "AI Signal Parse")
    log.info(f"Order placed – ticket {ticket}, {action} {symbol} {volume} (SL: {sl}, TP: {tp})")
    return ticket

def close_position(ticket: int, symbol: str, action: str, volume: float) -> bool:
    if DRY_RUN:
        log.info(f"[DRY‑RUN] Would close ticket {ticket} ({action} {symbol}) volume={volume}")
        return True
    opposite = "SELL" if action == "BUY" else "BUY"
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask,
        "deviation": 10,
        "magic": 777777,
        "comment": "CloseSignalBot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        log.error(f"Close order failed: {res.retcode} – {res.comment}")
        return False
    log.info(f"Position closed – ticket {ticket}")
    return True

# ------------------------------------------------------------
# Main async processing –‑ called for each incoming Telegram msg
# ------------------------------------------------------------
async def handle_message(event, channel_map: dict):
    chat = await event.get_chat()
    chat_id = str(chat.id).lstrip("-")
    channel_name = channel_map.get(chat_id, "Unknown")
    text = event.message.message
    if not text:
        return
    
    active_sessions = get_active_sessions()
    session_str = "/".join(active_sessions) if active_sessions else "Off-Hours"
    
    log.info(f"[{session_str}] New message from {channel_name} ({chat_id}): {text[:120]}")

    # ---- AI analysis ----
    prompt = build_prompt(text, channel_name)
    try:
        ai_reply = await ask_ai(prompt)
    except Exception as exc:
        log.error(f"AI request failed: {exc}")
        return
    if ai_reply.upper().strip() == "NO_TRADE":
        log.info("AI reports no trade")
        return

    parts = ai_reply.split()
    if len(parts) < 3:
        log.warning(f"Unexpected AI format: {ai_reply}")
        return
    
    action, symbol, entry_str = parts[0].upper(), parts[1].upper(), parts[2]
            
    # Map standard symbols
    if symbol in ["XAUUSD", "XAU", "XAU/USD"]: symbol = "GOLD"
    elif symbol in ["XAGUSD", "XAG", "XAG/USD"]: symbol = "SILVER"
    elif symbol in ["BTC", "BTC/USD"]: symbol = "BTCUSD"
    elif symbol in ["ETH", "ETH/USD"]: symbol = "ETHUSD"
    
    # ---- Safeguard 1: Signal Spam Cooldown ----
    now = time.time()
    if now - SYMBOL_COOLDOWN.get(symbol, 0) < 3600:
        log.warning(f"Rejecting {symbol} signal - active 60-minute cooldown!")
        return
        
    # ---- Safeguard 2: Global Position Limit ----
    if init_mt5():
        positions = mt5.positions_get()
        if positions and len(positions) >= 3:
            log.warning("Rejecting signal - Global Position Limit (3) reached!")
            shutdown_mt5()
            return
        shutdown_mt5()
    
    try:
        entry_price = float(entry_str)
    except ValueError:
        log.error(f"Invalid entry price from AI: {entry_str}")
        return
        
    # Dynamic Lot Sizing allocating $200 per Telegram channel trade
    volume = calculate_dynamic_lot(symbol, base_allocation=200.0, leverage=1000)
    
    # SL / TP parsed from AI (Format: ACTION SYMBOL ENTRY SL TP)
    sl_val = float(parts[3]) if len(parts) >= 4 else 0.0
    tp_val = float(parts[4]) if len(parts) >= 5 else 0.0

    # ---- Place order ----
    if not init_mt5():
        return
    mt5.symbol_select(symbol, True)
    ticket = place_order(symbol, action, volume, sl=sl_val, tp=tp_val, channel_name=channel_name)
    shutdown_mt5()
    if ticket == 0:
        return
        
    # Mark symbol as traded to activate 60-minute cooldown
    SYMBOL_COOLDOWN[symbol] = time.time()

# ------------------------------------------------------------
# Safeguard 3: Robust Orphan Trade Monitor
# ------------------------------------------------------------
async def monitor_orphans():
    log.info("Starting background orphan monitor (30-min auto-close)")
    counter = 0
    while True:
        try:
            # Write Telegram Engine Heartbeat
            try:
                with open(BASE_DIR / "telegram_status.json", "w") as f:
                    json.dump({"last_heartbeat": time.time(), "status": "Active"}, f)
            except:
                pass
                
            if counter % 6 == 0:
                if init_mt5():
                    positions = mt5.positions_get()
                    if positions:
                        now = time.time()
                        for pos in positions:
                            if pos.magic == 777777: # Only manage Telegram bot trades
                                # --- DYNAMIC TP1 / TP2 / TP3 STEP-TRAILING LOGIC ---
                                point = mt5.symbol_info(pos.symbol).point
                                digits = mt5.symbol_info(pos.symbol).digits
                                tick = mt5.symbol_info_tick(pos.symbol)
                                
                                if tick and point > 0:
                                    current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                                    open_price = pos.price_open
                                    profit_points = (current_price - open_price)/point if pos.type == mt5.ORDER_TYPE_BUY else (open_price - current_price)/point
                                    
                                    atr = get_atr_fallback(pos.symbol)
                                    atr_points = (atr / point) if point > 0 and atr > 0 else 150 # Fallback 150 points
                                    
                                    tp1 = atr_points * 1.0
                                    tp2 = atr_points * 2.0
                                    
                                    new_sl = pos.sl
                                    if profit_points >= tp2:
                                        # Hit TP2 (2x ATR), move SL to TP1
                                        new_sl = open_price + (tp1 * point) if pos.type == mt5.ORDER_TYPE_BUY else open_price - (tp1 * point)
                                    elif profit_points >= tp1:
                                        # Hit TP1 (1x ATR), move SL to Breakeven (+15 points for fees)
                                        new_sl = open_price + (15 * point) if pos.type == mt5.ORDER_TYPE_BUY else open_price - (15 * point)
                                        
                                    new_sl = round(new_sl, digits)
                                    # Update if the new SL is tighter than current SL
                                    should_update = False
                                    if pos.type == mt5.ORDER_TYPE_BUY and new_sl > pos.sl and new_sl < current_price:
                                        should_update = True
                                    elif pos.type == mt5.ORDER_TYPE_SELL and (pos.sl == 0.0 or new_sl < pos.sl) and new_sl > current_price:
                                        should_update = True
                                        
                                    if should_update and new_sl != pos.sl:
                                        req = {
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": pos.ticket,
                                            "symbol": pos.symbol,
                                            "sl": new_sl,
                                            "tp": pos.tp
                                        }
                                        res = mt5.order_send(req)
                                        if res.retcode == mt5.TRADE_RETCODE_DONE:
                                            log.info(f"[{pos.symbol}] Dynamic Step-Trail (TP Logic): Locked SL to {new_sl}")

                                # --- TIME-BASED AUTO CLOSE ---
                                if (now - pos.time) > 1800:
                                    action_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                                    log.info(f"Auto-closing orphaned position {pos.ticket} ({pos.symbol}) after 30 mins")
                                    close_position(pos.ticket, pos.symbol, action_type, pos.volume)
                    shutdown_mt5()
            counter += 1
        except Exception as e:
            log.error(f"Orphan monitor error: {e}")
        await asyncio.sleep(10)

# ------------------------------------------------------------
# Entry point –‑ start Telethon client and listen
# ------------------------------------------------------------
async def main():
    channel_map = load_channel_map()
    log.info(f"Loaded {len(channel_map)} channels")

    if not init_mt5():
        log.error("Cannot continue without MT5 connection")
        return

    from telethon import TelegramClient, events
    SESSION_FILE_2 = BASE_DIR / "telegram_session2.session"
    
    client1 = TelegramClient(str(SESSION_FILE), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    client2 = TelegramClient(str(SESSION_FILE_2), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    
    await client1.start()
    log.info("Telegram client 1 started")
    
    # Start client2 conditionally (if it has been authorized)
    try:
        await client2.start()
        log.info("Telegram client 2 started (9008400969)")
    except Exception as e:
        log.warning(f"Could not start client 2: {e}")
        client2 = None

    @client1.on(events.NewMessage())
    async def on_new1(event):
        chat = await event.get_chat()
        chat_id_str = str(chat.id)
        chat_id_str_100 = f"-100{abs(chat.id)}"
        if chat_id_str in channel_map or chat_id_str_100 in channel_map:
            await handle_message(event, channel_map)
        elif hasattr(chat, "username") and chat.username and chat.username in channel_map:
            await handle_message(event, channel_map)
        
    if client2:
        @client2.on(events.NewMessage())
        async def on_new2(event):
            chat = await event.get_chat()
            chat_id_str = str(chat.id)
            chat_id_str_100 = f"-100{abs(chat.id)}"
            if chat_id_str in channel_map or chat_id_str_100 in channel_map:
                await handle_message(event, channel_map)
            elif hasattr(chat, "username") and chat.username and chat.username in channel_map:
                await handle_message(event, channel_map)

    log.info("Listening for new signals on all active accounts… (press Ctrl+C to stop)")
    tasks = [client1.run_until_disconnected(), monitor_orphans()]
    if client2:
        tasks.append(client2.run_until_disconnected())
    
    await asyncio.gather(*tasks)
    shutdown_mt5()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Interrupted by user – shutting down")
        shutdown_mt5()
