"""
Live Orders CSV Ledger & Trade Lifecycle Tracker
=================================================
Logs every order placement, entry, exit, PnL, and metadata into `logs/live_orders_ledger.csv`.
Tracks open positions in MT5 to automatically record exit price, exit timestamp, and realized profit/loss.
"""

import os
import csv
import logging
from pathlib import Path
from datetime import datetime, timezone
import MetaTrader5 as mt5

logger = logging.getLogger("LIVE_LEDGER")

LEDGER_CSV_PATH = Path("logs/live_orders_ledger.csv")

CSV_HEADER = [
    "order_id",
    "timestamp_utc",
    "symbol",
    "timeframe",
    "strategy_id",
    "side",
    "volume",
    "entry_price",
    "sl_price",
    "tp_price",
    "status",
    "win_probability",
    "entry_reason",
    "exit_price",
    "exit_timestamp",
    "pnl",
    "exit_reason"
]


def init_ledger():
    """Ensures logs directory exists and CSV header is initialized."""
    LEDGER_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LEDGER_CSV_PATH.exists():
        with open(LEDGER_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
        logger.info(f"Initialized CSV Trade Ledger at {LEDGER_CSV_PATH}")


def log_new_order(
    order_id: str,
    symbol: str,
    timeframe: str,
    strategy_id: str,
    side: str,
    volume: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    status: str,
    win_probability: float,
    entry_reason: str
):
    """Logs a newly executed or rejected order into the CSV ledger."""
    init_ledger()
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    row = [
        str(order_id),
        now_utc,
        symbol,
        timeframe,
        strategy_id,
        side,
        f"{volume:.2f}",
        f"{entry_price:.5f}",
        f"{sl_price:.5f}",
        f"{tp_price:.5f}",
        status,
        f"{win_probability:.2%}",
        entry_reason,
        "", # exit_price (empty until closed)
        "", # exit_timestamp (empty until closed)
        "", # pnl (empty until closed)
        ""  # exit_reason (empty until closed)
    ]
    
    try:
        with open(LEDGER_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        logger.info(f"[CSV LEDGER] Logged order #{order_id} [{symbol}][{timeframe}][{strategy_id}] {side} @ {entry_price}")
    except Exception as e:
        logger.error(f"Failed to log order #{order_id} to CSV ledger: {e}")


def update_closed_trades():
    """
    Scans MT5 deal history to update exit_price, exit_timestamp, pnl, and exit_reason
    for any orders in live_orders_ledger.csv that have closed.
    """
    if not LEDGER_CSV_PATH.exists():
        return

    try:
        # Read existing ledger rows
        rows = []
        with open(LEDGER_CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return

        updated = False
        now = datetime.now(timezone.utc)
        # Fetch MT5 deal history for past 7 days
        from_time = datetime.fromtimestamp(now.timestamp() - (7 * 86400), tz=timezone.utc)
        deals = mt5.history_deals_get(from_time, now)

        if deals is None or len(deals) == 0:
            return

        # Map deals by order ID / position ID
        deal_map = {}
        for d in deals:
            # Entry deal or exit deal
            deal_map[str(d.order)] = d
            deal_map[str(d.position_id)] = d

        for row in rows:
            order_id = row.get("order_id", "")
            status = row.get("status", "")
            exit_price = row.get("exit_price", "")

            if status == "FILLED" and not exit_price and order_id in deal_map:
                deal = deal_map[order_id]
                # If deal is an OUT deal (trade closure)
                if deal.entry == mt5.DEAL_ENTRY_OUT:
                    row["exit_price"] = f"{deal.price:.5f}"
                    row["exit_timestamp"] = datetime.fromtimestamp(deal.time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                    row["pnl"] = f"{deal.profit + deal.swap + deal.commission:.2f}"
                    
                    reason_str = "CLOSED"
                    if deal.reason == mt5.DEAL_REASON_SL:
                        reason_str = "SL_HIT"
                    elif deal.reason == mt5.DEAL_REASON_TP:
                        reason_str = "TP_HIT"
                    elif deal.reason == mt5.DEAL_REASON_CLIENT:
                        reason_str = "MANUAL_CLOSE"
                    row["exit_reason"] = reason_str
                    updated = True
                    logger.info(f"[CSV LEDGER] Closed trade #{order_id} updated: Exit {deal.price} | PnL ${row['pnl']} | Reason: {reason_str}")

        if updated:
            with open(LEDGER_CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
                writer.writeheader()
                writer.writerows(rows)

    except Exception as e:
        logger.error(f"Error updating closed trades in CSV ledger: {e}")
