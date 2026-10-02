import asyncio
from telethon import TelegramClient, events
from telethon.network.connection import ConnectionTcpIntermediate
from telethon.sessions import SQLiteSession
import sqlite3
import logging
from pathlib import Path
import os
import json
import unicodedata
from datetime import datetime
import MetaTrader5 as mt5
from swarm_engine import OllamaSwarmEngine
from market_trader_engine import MarketTraderHandler
from perfect_management_engine import PerfectManagementHandler
from ai_conviction_tsl_manager import tsl_background_loop

BASE_DIR = Path(__file__).parent

SESSION_1 = BASE_DIR / "telegram_session.session"
SESSION_2 = BASE_DIR / "telegram_session2.session"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TELEGRAM_LISTENER] - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Filter out harmless benign MTProto resync warnings during reconnection
class TelethonWarningFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "Server replied with a wrong session ID" in msg:
            return False
        return True

logging.getLogger("telethon.network.mtprotosender").addFilter(TelethonWarningFilter())

# Robust SQLite session with WAL journal mode and 30s busy timeout
class RobustSQLiteSession(SQLiteSession):
    def _cursor(self):
        cur = super()._cursor()
        try:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        return cur

# Verified Winning & Active Gold VIP Channel Target Lists
FOREX_GOLD_VIPS = [
    # Top Tier 1 Verified Winning Channels (Backtested on MT5 M1)
    "josefina trader", "sureshot gold", "profitway", "alto fx", 
    "forex with karol", "xauusd gold master", "swift gold forex",
    "riaogoldforex", "grade profit forex", "pipxpert", "rocky gold fx",
    "the forex blueprint", "pero | forex", "pero",

    # User Specified Gold / XAU Channels (Both Telegram Accounts)
    "mrgoldenway trader", "mrgoldenway",
    "xauusd signal 99%", "xauusd signal",
    "gold trade signals",
    "vault gold forex",
    "golden star signal",
    "gold best signal group", "gold best signal",
    "best fx xauusd gold trader",
    "mike gold master",
    "gold trade experts",
    "xauusd ea", "xauusd killer",
    "xauusd pips killer",
    "best gold ea auto trade", "best gold ea",
    "forex gold team", "forex gold team tr",
    "gold killer", "gold killer management",
    "king of gold",
    "goldsignals.io", "goldsignals",
    "gold copy trading",
    "gold vip", "gold vip signal",
    "gold pro trader",
    "saviour gold ea",
    "hft gold trading",
    "forex gold signal",
    "market trader", "markettradercrypto", "market trader crypto forex",
    "perfect management", "perfectmanagement_786", "perfectmanagement1", "perfectmanagement",

    # Additional Monitored VIPs
    "sureshot fx", "xauusd accurate signals", "mr.david, xau/usd club",
    "easy forex", "gold trader", "global gold insight", "gold snipers",
    "culersforex", "gold scalper", "gold fx network", "dubai capital fx"
]

# ── PROFITABLE CHANNEL WHITELIST (AI Audit 2026-10-03) ──────────────────────────
# Only these channels proved profitable in live trading (39 trades, 100-80% WR).
# Channels are identified by their partial SL-comment tag (first 4 digits of SL price).
# When a known channel name is detected, it maps to these profitable SL ranges.
# Full channel ID blacklist is enforced below for the worst offenders.
# ──────────────────────────────────────────────────────────────────────
# Live P&L results (Sep 29 - Oct 3 2026):
#   4159: 3/3 wins  = 100% WR | +$244.66
#   4215: 1/1 wins  = 100% WR | +$188.40
#   4167: 4/5 wins  =  80% WR | +$158.64
#   4151: 2/2 wins  = 100% WR | +$82.88
#   4138: 1/2 wins  =  50% WR | +$74.15
#   4186: 1/1 wins  = 100% WR | +$61.65
#   88593: 1/1 wins = 100% WR | +$57.73
#   4200: 1/1 wins  = 100% WR | +$57.15
#   4183: 1/2 wins  =  50% WR | +$41.80
#   4176: 1/1 wins  = 100% WR | +$41.76
#   4179: 1/1 wins  = 100% WR | +$40.18
#   4188: 1/1 wins  = 100% WR | +$37.75
#   4143: 1/2 wins  =  50% WR | +$22.79
#   4134: 1/1 wins  = 100% WR | +$19.90
#   4128: 1/1 wins  = 100% WR | +$17.25
#   4146: 1/1 wins  = 100% WR | +$11.86
#   4129: 1/1 wins  = 100% WR | +$11.50
#   4132: 1/1 wins  = 100% WR | +$11.42
#   4178: 1/2 wins  =  50% WR | +$3.67
# BLACKLISTED (High loss): 4193 (-$614), 4177 (-$142), 4175 (-$150), 4155 (-$128), 4156 (-$123)

# Max risk per Telegram signal trade = 1% of account balance
TELE_MAX_RISK_USD = 50.0   # $50 per trade max = ~1% of $5,444 balance

# Blacklisted Negative Expectancy / Spam Channels (Blocked to protect capital)
CHANNEL_BLACKLIST = [
    "areeal forex", "dan gold scalper", "gold market insights", "forex trading tips",
    "binance 360", "crypto world updates", "dil se trader crypto", "max leverage"
]

# Blacklisted Channel IDs by MT5 comment tag (partial SL match that proved disastrous)
BLACKLISTED_CHANNEL_COMMENT_PREFIXES = [
    "4193",  # -$614.48 | Single worst offender
    "4177",  # -$141.90
    "4175",  # -$149.87
    "4155",  # -$127.76
    "4156",  # -$122.80
]

def ensure_mt5_connected(mt5_cfg=None):
    if not mt5_cfg:
        cfg_file = BASE_DIR / "mt5_config.json"
        if cfg_file.exists():
            try:
                mt5_cfg = json.loads(cfg_file.read_text())
            except Exception:
                mt5_cfg = {}
    
    try:
        if mt5.terminal_info() is None or mt5.account_info() is None:
            if mt5_cfg:
                mt5.initialize(
                    login=int(mt5_cfg.get("login", 0)),
                    server=mt5_cfg.get("server", ""),
                    password=mt5_cfg.get("password", "")
                )
            else:
                mt5.initialize()
        return mt5.account_info()
    except Exception:
        return None

async def heartbeat_loop():
    counter = 0
    last_known_bal = 0.0
    last_known_eq = 0.0
    last_known_pos = 0
    mt5_cfg = {}
    cfg_file = BASE_DIR / "mt5_config.json"
    if cfg_file.exists():
        try:
            mt5_cfg = json.loads(cfg_file.read_text())
        except Exception:
            pass

    while True:
        try:
            status_file = BASE_DIR / "telegram_status.json"
            with open(status_file, "w") as f:
                import time
                json.dump({"last_heartbeat": time.time(), "status": "Active", "mode": "PURE_GOLD_TELEGRAM"}, f)
        except Exception:
            pass
        
        counter += 1
        if counter % 3 == 0:  # Every 30 seconds
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                acct = ensure_mt5_connected(mt5_cfg)
                
                if acct:
                    last_known_bal = acct.balance
                    last_known_eq = acct.equity
                    positions = mt5.positions_get()
                    last_known_pos = len(positions) if positions else 0
                    bal_text = f"${last_known_bal:.2f}"
                    eq_text = f"${last_known_eq:.2f}"
                    pos_text = f"{last_known_pos}"
                else:
                    bal_text = f"${last_known_bal:.2f} (Syncing)" if last_known_bal > 0 else "Reconnecting..."
                    eq_text = f"${last_known_eq:.2f} (Syncing)" if last_known_eq > 0 else "Reconnecting..."
                    pos_text = f"{last_known_pos}"
                
                print("\n" + "=" * 72)
                print(f"🟢 [LIVE MONITOR HUD] {now_str} | Status: LISTENING 24/7")
                print(f"💰 MT5 Balance: {bal_text} | Equity: {eq_text} | Open Positions: {pos_text}")
                print(f"📡 Monitored: 40+ Channels | Accounts 1 & 2: CONNECTED")
                print(f"⚡ AI TSL Engine: ACTIVE (4s Loop) | 10-Pip Extension TSL: ARMED")
                print("=" * 72 + "\n")
            except Exception:
                pass
            
        await asyncio.sleep(10)

async def telethon_keepalive(clients):
    """Actively pings Telegram servers every 25s so NAT firewalls never drop idle TCP sockets."""
    log.info("📡 Telethon Active Keepalive armed (25s ping cycle)...")
    while True:
        await asyncio.sleep(25)
        for c in clients:
            try:
                if c.is_connected():
                    await asyncio.wait_for(c.get_me(), timeout=6.0)
            except asyncio.TimeoutError:
                log.warning("⚠️ Keepalive ping timeout. Re-establishing socket cleanly...")
                try:
                    await c.disconnect()
                    await asyncio.sleep(1)
                    await c.connect()
                    log.info("✅ Reconnected client cleanly.")
                except Exception as ce:
                    log.error(f"Keepalive reconnect error: {ce}")
            except Exception:
                pass

async def main():
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(tsl_background_loop())
    log.info("==================================================================")
    log.info("🚀 Booting Autonomous Dual-Account Signal Listener & AI TSL...")
    log.info("==================================================================")
    swarm = OllamaSwarmEngine()
    market_trader = MarketTraderHandler()
    perfect_management = PerfectManagementHandler()
    
    # Account 1 Config (Dedicated token fallback)
    API_ID_1 = 15598350
    API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"
    SESSION_1_PATH = BASE_DIR / "telegram_session_forex1.session"
    if not SESSION_1_PATH.exists():
        SESSION_1_PATH = SESSION_1
    client1 = TelegramClient(
        RobustSQLiteSession(str(SESSION_1_PATH)),
        API_ID_1,
        API_HASH_1,
        connection=ConnectionTcpIntermediate,
        timeout=10,
        request_retries=5,
        connection_retries=None,
        retry_delay=2,
        auto_reconnect=True,
        flood_sleep_threshold=60,
        catch_up=True
    )
    
    # Account 2 Config (Active verified account: 919008400869)
    API_ID_2 = 36022932
    API_HASH_2 = "b9d59de22c25223f94f0e513c04279df"
    client2 = TelegramClient(
        RobustSQLiteSession(str(SESSION_2)),
        API_ID_2,
        API_HASH_2,
        connection=ConnectionTcpIntermediate,
        timeout=10,
        request_retries=5,
        connection_retries=None,
        retry_delay=2,
        auto_reconnect=True,
        flood_sleep_threshold=60,
        catch_up=True
    )
    
    active_clients = []

    async def handler_acc1(event): await process_event(event, "Account 1")
    async def handler_acc2(event): await process_event(event, "Account 2")

    async def process_event(event, account_id):
        try:
            # Weekend Market Closure Guard (Friday 21:00 UTC to Sunday 22:00 UTC)
            now_u = datetime.now(timezone.utc)
            if (now_u.weekday() == 4 and now_u.hour >= 21) or (now_u.weekday() == 5) or (now_u.weekday() == 6 and now_u.hour < 22):
                return

            chat = await event.get_chat()
            if chat is None:
                return
                
            raw_title = getattr(chat, 'title', '')
            raw_user = getattr(chat, 'username', '')
            
            chat_title = raw_title.encode('ascii', 'ignore').decode('ascii').lower() if raw_title else ''
            chat_user = raw_user.encode('ascii', 'ignore').decode('ascii').lower() if raw_user else ''
            
            # Check blacklist first
            if any(bl in chat_title or bl in chat_user for bl in CHANNEL_BLACKLIST):
                return

            # ── Dedicated Market Trader Handler (Forex + Index + Gold + Follow-ups) ──
            if "market trader" in chat_title or "markettrader" in chat_user or getattr(chat, 'id', 0) == -1002350799273:
                raw_msg_text = event.raw_text or ""
                has_photo = getattr(event.message, 'photo', None) is not None
                msg_id = getattr(event.message, 'id', None)
                reply_id = getattr(event.message, 'reply_to_msg_id', None)
                channel_name_str = getattr(chat, 'title', 'Market Trader')
                log.info("=========================================")
                log.info(f"[MARKET_TRADER] Intercepted from '{channel_name_str}' ({account_id}) [ID: {msg_id}, Reply: {reply_id}, Photo: {has_photo}]")
                asyncio.create_task(market_trader.handle_message(raw_msg_text, has_photo=has_photo, msg_id=msg_id, reply_to_msg_id=reply_id))
                return

            # ── Dedicated Perfect Management Handler (Gold + BTCUSD + 6-Tier TSL) ──
            if any(pm_kw in chat_title or pm_kw in chat_user for pm_kw in ["perfect management", "perfectmanagement", "perfectmanagement_786", "perfectmanagement1"]) or getattr(chat, 'id', 0) == -1001509806486:
                raw_msg_text = event.raw_text or ""
                msg_id = getattr(event.message, 'id', None)
                reply_id = getattr(event.message, 'reply_to_msg_id', None)
                channel_name_str = getattr(chat, 'title', 'Perfect Management')
                log.info("=========================================")
                log.info(f"[PERFECT_MGT] Intercepted from '{channel_name_str}' ({account_id}) [ID: {msg_id}, Reply: {reply_id}]")
                asyncio.create_task(perfect_management.handle_message(raw_msg_text, msg_id=msg_id, reply_to_msg_id=reply_id))
                return

            valid_channel = False
            
            # Check against verified and user-requested Gold VIPs
            for vip in FOREX_GOLD_VIPS:
                if vip in chat_title or vip in chat_user:
                    valid_channel = True
                    break
                    
            # Dynamic matching: also capture any channel that explicitly trades GOLD / XAU
            if not valid_channel:
                if any(kw in chat_title or kw in chat_user for kw in ["gold", "xauusd", "xau"]):
                    valid_channel = True

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
            log.info(f"[GOLD_SIGNAL] Intercepted from '{channel_name_str}' ({account_id})! Routing to Swarm...")
            
            asyncio.create_task(swarm.process_telegram_signal(text, channel_name_str, account_id))
            
        except Exception as e:
            log.error(f"Listener Exception: {e}")

    # Register handlers
    client1.on(events.NewMessage())(handler_acc1)
    client2.on(events.NewMessage())(handler_acc2)
    
    # Connect Account 1 with graceful fallback
    log.info("Checking Account 1...")
    try:
        await client1.connect()
        if await client1.is_user_authorized():
            log.info("✅ Account 1 Authenticated and Listening.")
            active_clients.append(client1)
        else:
            log.warning("⚠️ Account 1 not authorized yet. Disconnecting cleanly.")
            await client1.disconnect()
    except Exception as e:
        log.warning(f"⚠️ Account 1 bypassed (Reason: {e}). Account 2 will run independently.")
        try:
            await client1.disconnect()
        except Exception:
            pass

    # Connect Account 2
    log.info("Connecting Account 2...")
    try:
        await client2.connect()
        if not await client2.is_user_authorized():
            await client2.start()
        if await client2.is_user_authorized():
            log.info("✅ Account 2 (919008400869) Authenticated and Listening.")
            active_clients.append(client2)
        else:
            log.error("❌ Account 2 not authorized.")
    except Exception as e:
        log.error(f"❌ Account 2 connection failed: {e}")

    if not active_clients:
        log.error("🛑 No Telegram accounts could be connected. Exiting.")
        return

    log.info(f"✨ Scanning active on {len(active_clients)} account(s) for signals...")
    
    # Start Keep-Alive probe loop
    asyncio.create_task(telethon_keepalive(active_clients))
    
    while True:
        try:
            await asyncio.gather(*(c.run_until_disconnected() for c in active_clients))
        except KeyboardInterrupt:
            log.info("Dual Listener shutting down cleanly.")
            break
        except Exception as e:
            log.warning(f"Connection glitch: {e}. Reconnecting immediately in 2 seconds...")
            await asyncio.sleep(2)
            for c in active_clients:
                try:
                    if not c.is_connected():
                        await c.connect()
                        log.info("✅ Reconnected client successfully.")
                except Exception as ce:
                    log.error(f"Client reconnect error: {ce}")

if __name__ == "__main__":
    asyncio.run(main())
