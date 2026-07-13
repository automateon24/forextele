"""
fetch_1year_m1_data.py
======================
Fetches 365 days of M1, M5, M15, H1 data for all 8 symbols from MT5.
Saves as compressed parquet files for fast loading during backtest.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
CFG_PATH = BASE_DIR / "mt5_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = {
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "AUDUSD": "AUDUSD", "GOLD": "GOLD", "SILVER": "SILVER",
    "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
}
TIMEFRAMES = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
}
DAYS = 365


def connect() -> bool:
    if mt5.initialize():
        return True
    with open(CFG_PATH) as f:
        cfg = json.load(f)
    return mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])


def fetch_range(mt5_sym: str, tf_const, days: int) -> pd.DataFrame:
    utc_to   = datetime.utcnow()
    utc_from = utc_to - timedelta(days=days)
    rates = mt5.copy_rates_range(mt5_sym, tf_const, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    if "tick_volume" in df.columns:
        df["volume"] = df["tick_volume"].astype(float)
    elif "real_volume" in df.columns:
        df["volume"] = df["real_volume"].astype(float)
    else:
        df["volume"] = 1.0
    return df[["open", "high", "low", "close", "volume"]]


def main():
    if not connect():
        log.error("MT5 connection failed. Check mt5_config.json")
        return

    for label, mt5_sym in SYMBOLS.items():
        if not mt5.symbol_select(mt5_sym, True):
            log.warning("Symbol not available: %s — skipping", mt5_sym)
            continue
        for tf_name, tf_const in TIMEFRAMES.items():
            out_path = BASE_DIR / f"data_1y_{label}_{tf_name}.parquet"
            if out_path.is_file():
                log.info("Already exists, skipping: %s", out_path.name)
                continue
            log.info("Fetching %s %s (%d days)...", label, tf_name, DAYS)
            df = fetch_range(mt5_sym, tf_const, DAYS)
            if df.empty:
                log.warning("No data for %s %s", label, tf_name)
                continue
            df.to_parquet(out_path, compression="gzip")
            log.info("  Saved %d bars → %s", len(df), out_path.name)

    mt5.shutdown()
    log.info("Done. All parquet files saved to %s", BASE_DIR)


if __name__ == "__main__":
    main()