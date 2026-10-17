"""
========================================================================================
INSTITUTIONAL TELEGRAM NOTIFICATION SYSTEM
Direct Telemetry to User Mobile (Bot: dhan_vinay_bot)
========================================================================================
"""
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger("TELEGRAM_NOTIFIER")

BOT_TOKEN = "8716774883:AAFbzhRN8uZPdwCEmUwoepXR1D4BlmZThKA"
CHAT_ID = "1437833304"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_msg(text: str) -> bool:
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        resp = requests.post(API_URL, json=payload, timeout=8)
        if resp.status_code == 200:
            return True
        else:
            log.warning(f"Telegram failed: {resp.status_code} {resp.text[:80]}")
            return False
    except Exception as e:
        log.warning(f"Telegram exception: {e}")
        return False

def notify_trade_opened(ticket: int, symbol: str, action: str, volume: float, entry: float, sl: float, tp1: float, tp2: float, win_prob: float, strategy: str):
    icon = "🟢" if action == "BUY" else "🔴"
    msg = (
        f"<b>{icon} INSTITUTIONAL SIGNAL EXECUTED</b>\n\n"
        f"<b>Ticket:</b> #{ticket}\n"
        f"<b>Asset:</b> <code>{symbol}</code>\n"
        f"<b>Action:</b> {action} | <b>Volume:</b> {volume} lots\n"
        f"<b>Strategy:</b> {strategy}\n"
        f"<b>AI ML Win Probability:</b> <b>{win_prob:.1%}</b>\n\n"
        f"📍 <b>Entry:</b> {entry}\n"
        f"🛡️ <b>Stop Loss:</b> {sl}\n"
        f"🎯 <b>TP1 (1.8R):</b> {tp1}\n"
        f"🚀 <b>TP2 (3.0R):</b> {tp2}\n"
        f"<i>Time: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</i>"
    )
    send_msg(msg)

def notify_trade_tp1(ticket: int, symbol: str, pnl_booked: float):
    msg = (
        f"<b>💰 TP1 REACHED & LOCKED</b>\n\n"
        f"<b>Ticket:</b> #{ticket} (<code>{symbol}</code>)\n"
        f"✅ <b>50% Partial Booked:</b> +${pnl_booked:,.2f} USD\n"
        f"🛡️ <b>Stop Loss:</b> Moved to Breakeven (+Spread)\n"
        f"<i>Position is now 100% Risk-Free. Trailing to TP2...</i>"
    )
    send_msg(msg)

def notify_pyramided(ticket: int, symbol: str, runner_vol: float):
    msg = (
        f"<b>⚡ PYRAMIDED RUNNER ADDED</b>\n\n"
        f"<b>Ticket:</b> #{ticket} (<code>{symbol}</code>)\n"
        f"📈 <b>Add-on Runner:</b> +{runner_vol} lots\n"
        f"🛡️ <b>Stop Loss:</b> Ratcheted to lock add-on profits\n"
        f"<i>Riding trend expansion to TP2 (3.0R+)!</i>"
    )
    send_msg(msg)

def notify_symbol_quarantine(symbol: str, consec_losses: int, redirected_to: str = "GOLD & BTCUSD"):
    msg = (
        f"<b>⚠️ SYMBOL QUARANTINE TRIGGERED</b>\n\n"
        f"<b>Asset:</b> <code>{symbol}</code>\n"
        f"<b>Reason:</b> {consec_losses} consecutive losses this week.\n"
        f"<b>Status:</b> Bypassed for the remainder of this calendar week.\n"
        f"🔄 <b>Capital Allocation:</b> Lot budget redirected into <b>{redirected_to}</b>."
    )
    send_msg(msg)

def notify_weekend_crypto_active(btc_bid: float, eth_bid: float):
    msg = (
        f"<b>🌐 WEEKEND 24/7 CRYPTO ENGINE ACTIVE</b>\n\n"
        f"Forex and Gold markets are currently closed.\n"
        f"<b>Dedicated Scanners:</b>\n"
        f"• <b>BTCUSD:</b> ${btc_bid:,.2f}\n"
        f"• <b>ETHUSD:</b> ${eth_bid:,.2f}\n\n"
        f"⚡ <i>100% Capital & AI scanning allocated to Crypto Breakouts & Pullbacks!</i>"
    )
    send_msg(msg)
