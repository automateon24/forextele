"""
====================================================================
LIVE CIRCUIT BREAKER & PENDING ORDER PURGE GUARDIAN
====================================================================
Protects the live account (167573094) against rogue days and stale orders:
1. Hard Daily Drawdown Stop: If realized net loss today <= -$150.00 (~3% of capital),
   all new trade entries across all 3 engines are immediately BLOCKED until 00:00 UTC.
2. Stale Pending Order Purge: Any Limit/Stop order older than 4 hours is auto-cancelled.
3. Weekend Purge: Within 15 minutes of Friday market close (20:45 UTC), all pending
   orders are immediately cancelled to prevent Sunday rollover gap slippage.
====================================================================
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = DATA_DIR / "circuit_breaker_status.json"

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CB_LOG = LOGS_DIR / "circuit_breaker.log"

log = logging.getLogger("CIRCUIT_BREAKER")
if not log.handlers:
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(str(CB_LOG), encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - [CIRCUIT_BREAKER] - %(levelname)s - %(message)s'))
    log.addHandler(fh)

import MetaTrader5 as mt5

HARD_MAX_DAILY_LOSS_USD = 150.0  # Max acceptable daily loss in USD
MAX_PENDING_ORDER_AGE_HOURS = 4.0

def get_today_realized_pnl() -> float:
    """Calculates today's net realized PnL (profit + swap + commission) from 00:00 UTC to now."""
    if not mt5.initialize():
        return 0.0
    try:
        now_utc = datetime.now(timezone.utc)
        start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, tzinfo=timezone.utc)
        deals = mt5.history_deals_get(start_of_day, now_utc)
        if not deals:
            return 0.0
        closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
        total_pnl = sum((d.profit + d.swap + d.commission) for d in closed_deals)
        return round(float(total_pnl), 2)
    except Exception as e:
        log.error(f"Error calculating today's PnL: {e}")
        return 0.0

def is_circuit_breaker_active(max_daily_loss: float = HARD_MAX_DAILY_LOSS_USD) -> bool:
    """
    Returns True if trading MUST BE HALTED (daily loss limit reached).
    Returns False if account is healthy to take new trades.
    """
    try:
        daily_pnl = get_today_realized_pnl()
        tripped = daily_pnl <= -abs(max_daily_loss)
        
        status_data = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "today_realized_pnl": daily_pnl,
            "max_daily_loss_limit": max_daily_loss,
            "circuit_breaker_tripped": tripped,
            "status": "HALTED" if tripped else "ACTIVE"
        }
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        if tripped:
            log.warning(f"🛑 [CIRCUIT BREAKER ACTIVE] Today's net PnL is ${daily_pnl:.2f} <= -${max_daily_loss:.2f}! All new entries HALTED until 00:00 UTC.")
            return True
        return False
    except Exception as e:
        log.error(f"Error evaluating circuit breaker: {e}")
        return False

def clean_stale_pending_orders(max_age_hours: float = MAX_PENDING_ORDER_AGE_HOURS) -> int:
    """
    Scans MT5 open orders and cancels:
    1. Any pending order with age > max_age_hours.
    2. ALL pending orders if Friday >= 20:45 UTC (weekend protection).
    """
    if not mt5.initialize():
        return 0

    now_utc = datetime.now(timezone.utc)
    is_friday_closing = (now_utc.weekday() == 4 and (now_utc.hour > 20 or (now_utc.hour == 20 and now_utc.minute >= 45)))
    is_weekend = (now_utc.weekday() == 5 or (now_utc.weekday() == 6 and now_utc.hour < 20))

    orders = mt5.orders_get()
    if not orders:
        return 0

    removed_count = 0
    for o in orders:
        age_hours = (now_utc.timestamp() - o.time_setup) / 3600.0 if o.time_setup else 0.0
        
        reason = None
        if is_friday_closing or is_weekend:
            reason = f"Weekend Rollover Protection (Market Closes in <15m)"
        elif age_hours > max_age_hours:
            reason = f"Order Expired (Age: {age_hours:.1f}h > Max: {max_age_hours}h)"

        if reason:
            req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"🗑️ [AUTO-REMOVE PENDING] Ticket #{o.ticket} ({o.symbol} {o.volume_current} lots @ {o.price_open}) REMOVED. Reason: {reason}")
                removed_count += 1
            else:
                err_msg = res.comment if res else "Unknown"
                log.warning(f"Failed to remove pending order #{o.ticket}: {err_msg}")

    return removed_count

if __name__ == "__main__":
    pnl = get_today_realized_pnl()
    tripped = is_circuit_breaker_active()
    cleaned = clean_stale_pending_orders()
    print(f"Today Realized PnL: ${pnl:.2f}")
    print(f"Circuit Breaker Tripped: {tripped}")
    print(f"Pending Orders Cleaned: {cleaned}")
