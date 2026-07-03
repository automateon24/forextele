#!/usr/bin/env python3
"""
Dhan Direct Auth - Zero Touch Daily Token Refresh
================================================
Single HTTP call with PIN + auto-TOTP. No browser. No Selenium. No manual input.

Usage:
  python dhan_direct_auth.py          # refresh only if expiring soon
  python dhan_direct_auth.py force    # force fresh token now
  python dhan_direct_auth.py status   # show current token status

Import in trading scripts:
  from dhan_direct_auth import ensure_valid_token
  ensure_valid_token()
"""

import json
import yaml
import pyotp
import time
import logging
import base64
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_renew.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE  = Path("config/dhan_totp_config.yaml")
TOKEN_FILE   = Path("config/dhan_tokens.json")
CLIENT_ID    = "1101936133"
REFRESH_MINS = 90   # refresh when less than 90 min remain


def _load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def _decode_expiry(access_token: str):
    """Decode JWT payload to get expiry datetime."""
    try:
        payload_b64 = access_token.split('.')[1]
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += '=' * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get('exp')
        if exp:
            return datetime.fromtimestamp(exp)
    except Exception:
        pass
    return None


def _save_token(access_token: str, expiry_time):
    """Save token + expiry to dhan_tokens.json."""
    if isinstance(expiry_time, datetime):
        expiry_str = expiry_time.isoformat()
    elif expiry_time:
        expiry_str = str(expiry_time)
    else:
        expiry_str = (datetime.now() + timedelta(hours=24)).isoformat()

    data = {
        "access_token": access_token,
        "expiry_time": expiry_str,
        "generated_at": datetime.now().isoformat()
    }
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    log.info(f"[SAVED] Token saved. Expires: {expiry_str}")


def _get_totp(secret: str) -> str:
    """Generate current TOTP code, wait for fresh window if expiring in <5s."""
    remaining = 30 - (int(time.time()) % 30)
    if remaining < 5:
        log.info(f"[TOTP] Waiting {remaining + 2}s for fresh TOTP window...")
        time.sleep(remaining + 2)
    code = pyotp.TOTP(secret).now()
    log.info(f"[TOTP] Code generated (valid for ~{30 - (int(time.time()) % 30)}s)")
    return code


# ── Method 1: Direct generateAccessToken (PIN + TOTP) ─────────────────────────
def _generate_token_direct(cfg: dict) -> str | None:
    """
    Dhan direct token endpoint - single POST, no browser.
    Requires TOTP to be enabled on the account.
    POST https://auth.dhan.co/app/generateAccessToken
         ?dhanClientId=...&pin=...&totp=...
    """
    totp_secret = cfg.get('totp_secret')
    pin         = str(cfg.get('pin', ''))
    client_id   = cfg.get('client_id', CLIENT_ID)

    if not totp_secret:
        log.error("[ERROR] totp_secret missing in config")
        return None
    if not pin or pin == 'your_pin_here':
        log.error("[ERROR] pin missing in config")
        return None

    totp_code = _get_totp(totp_secret)

    url = (
        f"https://auth.dhan.co/app/generateAccessToken"
        f"?dhanClientId={client_id}&pin={pin}&totp={totp_code}"
    )

    log.info(f"[AUTH] Calling generateAccessToken for client {client_id}...")

    for attempt in range(1, 4):
        try:
            resp = requests.post(url, timeout=15)
            log.info(f"[AUTH] Attempt {attempt}: HTTP {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                token = data.get('accessToken')
                if token:
                    expiry = _decode_expiry(token) or data.get('expiryTime')
                    log.info("[AUTH] generateAccessToken SUCCESS")
                    return token, expiry

            # Dhan rate limit: once every 2 minutes
            if attempt < 3 and 'once every 2 minutes' in resp.text:
                log.warning("[AUTH] Rate limited - waiting 2 minutes before retry...")
                time.sleep(122)
                totp_code = _get_totp(totp_secret)
                url = (
                    f"https://auth.dhan.co/app/generateAccessToken"
                    f"?dhanClientId={client_id}&pin={pin}&totp={totp_code}"
                )
                continue

            # TOTP already used - wait for NEXT full 30s window
            if attempt < 3 and 'Invalid TOTP' in resp.text:
                remaining = 30 - (int(time.time()) % 30)
                wait = remaining + 2
                log.warning(f"[AUTH] TOTP used already - waiting {wait}s for next window...")
                time.sleep(wait)
                totp_code = _get_totp(totp_secret)
                url = (
                    f"https://auth.dhan.co/app/generateAccessToken"
                    f"?dhanClientId={client_id}&pin={pin}&totp={totp_code}"
                )
                continue

            log.error(f"[AUTH] generateAccessToken failed: {resp.status_code} {resp.text[:200]}")
            break

        except requests.RequestException as e:
            log.error(f"[AUTH] Network error attempt {attempt}: {e}")
            time.sleep(3)

    return None, None


# ── Method 2: RenewToken (extend existing valid token) ────────────────────────
def _renew_existing_token(current_token: str) -> str | None:
    """
    Renew an existing active token for another 24 hours.
    Only works if token is still valid (not yet expired).
    """
    log.info("[RENEW] Attempting to renew existing token...")
    try:
        resp = requests.get(
            "https://api.dhan.co/v2/RenewToken",
            headers={
                "access-token": current_token,
                "dhanClientId": CLIENT_ID
            },
            timeout=15
        )
        log.info(f"[RENEW] HTTP {resp.status_code}: {resp.text[:120]}")
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('accessToken') or data.get('access_token')
            if token:
                expiry = _decode_expiry(token) or data.get('expiryTime')
                log.info("[RENEW] Token renewed successfully")
                return token, expiry
    except Exception as e:
        log.warning(f"[RENEW] Renew failed: {e}")
    return None, None


# ── Token Status ──────────────────────────────────────────────────────────────
def get_token_status():
    """Returns dict with token info: valid, minutes_remaining, token, expiry."""
    if not TOKEN_FILE.exists():
        return {"valid": False, "minutes_remaining": 0, "token": None, "expiry": None}

    with open(TOKEN_FILE) as f:
        data = json.load(f)

    token  = data.get('access_token')
    expiry = data.get('expiry_time')

    if not token or not expiry:
        return {"valid": False, "minutes_remaining": 0, "token": None, "expiry": None}

    try:
        expiry_dt = datetime.fromisoformat(str(expiry).replace('Z', ''))
        remaining = (expiry_dt - datetime.now()).total_seconds() / 60
        return {
            "valid": remaining > 0,
            "minutes_remaining": max(0, remaining),
            "token": token,
            "expiry": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "generated_at": data.get('generated_at', 'unknown')
        }
    except Exception as e:
        log.warning(f"[STATUS] Could not parse expiry: {e}")
        return {"valid": False, "minutes_remaining": 0, "token": token, "expiry": expiry}


# ── Main Public API ───────────────────────────────────────────────────────────
def fetch_fresh_token() -> str:
    """
    Get a brand new token using PIN + TOTP.
    Tries direct generation first, falls back to error.
    Returns the access token string.
    """
    try:
        from dhan_notify import notify_success, notify_failure
    except ImportError:
        notify_success = notify_failure = lambda *a, **k: None

    cfg = _load_config()

    # Try Method 1: direct generateAccessToken
    token, expiry = _generate_token_direct(cfg)
    if token:
        _save_token(token, expiry)
        expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S") if hasattr(expiry, 'strftime') else str(expiry)
        notify_success(expiry_str)
        return token

    err = "generateAccessToken failed - check TOTP/PIN/internet"
    log.error("[FATAL] All token generation methods failed.")
    notify_failure(err)
    raise RuntimeError(
        "Could not generate Dhan access token.\n"
        "Check: 1) TOTP secret correct  2) PIN correct  3) Internet working\n"
        "Logs: logs/auto_renew.log"
    )


def ensure_valid_token(force: bool = False) -> str:
    """
    Main function to call from trading scripts.
    - If token valid and >90 min remaining: returns existing token (no API call)
    - If token valid but <90 min: tries renew first, then generates fresh
    - If token missing/expired: generates fresh token
    - force=True: always generates fresh token regardless

    Returns: valid access token string
    """
    if not force:
        status = get_token_status()
        mins = status['minutes_remaining']

        if status['valid'] and mins > REFRESH_MINS:
            log.info(f"[OK] Token valid for {mins:.0f} more minutes. No refresh needed.")
            return status['token']

        if status['valid'] and mins > 0:
            log.info(f"[REFRESH] Token expires in {mins:.0f} min - refreshing proactively...")
            # Try renew first (cheaper, no TOTP needed)
            token, expiry = _renew_existing_token(status['token'])
            if token:
                _save_token(token, expiry)
                return token
            # Renew failed, generate fresh
            log.info("[REFRESH] Renew failed, generating fresh token...")
        else:
            log.info("[EXPIRED] Token expired or missing - generating fresh token...")

    return fetch_fresh_token()


def get_valid_token() -> str:
    """Alias for ensure_valid_token() - drop-in for trading scripts."""
    return ensure_valid_token()


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"

    if cmd == "status":
        s = get_token_status()
        print("\n" + "=" * 50)
        print("  DHAN TOKEN STATUS")
        print("=" * 50)
        if s['valid']:
            h = int(s['minutes_remaining'] // 60)
            m = int(s['minutes_remaining'] % 60)
            print(f"  Status  : VALID")
            print(f"  Expires : {s['expiry']}")
            print(f"  Remaining: {h}h {m}m")
            print(f"  Generated: {s['generated_at']}")
        else:
            print(f"  Status  : EXPIRED / MISSING")
            print(f"  Expiry  : {s['expiry']}")
        print("=" * 50 + "\n")

    elif cmd == "force":
        print("\n[FORCE] Generating fresh token...")
        token = fetch_fresh_token()
        print(f"[SUCCESS] New token: {token[:60]}...")
        s = get_token_status()
        print(f"[INFO] Expires: {s['expiry']}\n")

    else:
        # Default: auto refresh if needed
        token = ensure_valid_token()
        s = get_token_status()
        h = int(s['minutes_remaining'] // 60)
        m = int(s['minutes_remaining'] % 60)
        print(f"\n[OK] Token valid for {h}h {m}m (expires {s['expiry']})\n")
