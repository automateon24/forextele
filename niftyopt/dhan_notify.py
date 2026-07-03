#!/usr/bin/env python3
"""
Dhan Notification System
Sends Telegram message on token refresh success/failure.
Also logs locally to logs/daily_status.log
"""

import json
import logging
import requests
from datetime import datetime
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

# ── Config ─────────────────────────────────────────────────────────────────
NOTIFY_CONFIG_FILE = Path("config/notify_config.json")

def _load_notify_config():
    if NOTIFY_CONFIG_FILE.exists():
        with open(NOTIFY_CONFIG_FILE) as f:
            return json.load(f)
    return {}

def _log_locally(message: str, level: str = "INFO"):
    log_file = Path("logs/daily_status.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")
    print(f"[{timestamp}] [{level}] {message}")

def send_telegram(message: str) -> bool:
    cfg = _load_notify_config()
    bot_token = cfg.get("telegram_bot_token")
    chat_id   = cfg.get("telegram_chat_id")

    if not bot_token or not chat_id:
        _log_locally("Telegram not configured - skipping notification", "WARN")
        return False

    try:
        url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        if resp.status_code == 200:
            _log_locally("Telegram notification sent", "INFO")
            return True
        else:
            _log_locally(f"Telegram failed: {resp.status_code} {resp.text[:100]}", "ERROR")
            return False
    except Exception as e:
        _log_locally(f"Telegram error: {e}", "ERROR")
        return False

def notify_success(token_expiry: str = ""):
    now = datetime.now().strftime("%d-%b-%Y %H:%M")
    msg = (
        f"<b>Dhan Token Refresh SUCCESS</b>\n"
        f"Time: {now}\n"
        f"Expires: {token_expiry}\n"
        f"Status: Trading system ready for today\n"
        f"IP: 103.180.237.44 (SEBI compliant)"
    )
    _log_locally(f"Token refresh SUCCESS. Expires: {token_expiry}")
    send_telegram(msg)

def notify_failure(error: str = ""):
    now = datetime.now().strftime("%d-%b-%Y %H:%M")
    msg = (
        f"<b>Dhan Token Refresh FAILED</b>\n"
        f"Time: {now}\n"
        f"Error: {error}\n"
        f"Action needed: Check logs/auto_renew.log\n"
        f"Manual fix: Run py dhan_direct_auth.py force"
    )
    _log_locally(f"Token refresh FAILED: {error}", "ERROR")
    send_telegram(msg)

def notify_status(status_msg: str):
    _log_locally(status_msg)
    send_telegram(status_msg)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Sending test notification...")
        notify_success("TEST - 2026-04-28 08:30:00")
        print("Done. Check your Telegram.")
