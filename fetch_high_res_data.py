"""
fetch_high_res_data.py
======================
Fetches maximum available M1 and M5 bars directly by position instead of date range,
avoiding the 'None' returns when 1-year data isn't fully available.
"""
import json
import logging
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
CFG_PATH = BASE_DIR / "mt5_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Focus on all 8 pairs to get true M1 precision for everything
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GOLD", "SILVER", "BTCUSD", "ETHUSD"]
TIMEFRAMES = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
}
# Maximum bars to pull (MT5 usually supports up to 100k-500k depending on terminal)
MAX_BARS = 50_000 

def connect() -> bool:
    if mt5.initialize():
        return True
    with open(CFG_PATH) as f:
        cfg = json.load(f)
    return mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])

def fetch_pos(mt5_sym: str, tf_const, count: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(mt5_sym, tf_const, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    if "tick_volume" in df.columns:
        df["volume"] = df["tick_volume"].astype(float)
    else:
        df["volume"] = 1.0
    return df[["open", "high", "low", "close", "volume"]]

def main():
    if not connect():
        log.error("MT5 connection failed.")
        return

    for mt5_sym in SYMBOLS:
        if not mt5.symbol_select(mt5_sym, True):
            log.warning("Symbol not available: %s", mt5_sym)
            continue
        for tf_name, tf_const in TIMEFRAMES.items():
            out_path = BASE_DIR / f"data_highres_{mt5_sym}_{tf_name}.parquet"
            log.info("Fetching %s %s (up to %d bars)...", mt5_sym, tf_name, MAX_BARS)
            df = fetch_pos(mt5_sym, tf_const, MAX_BARS)
            if df.empty:
                log.warning("No data for %s %s", mt5_sym, tf_name)
                continue
            df.to_parquet(out_path, compression="gzip")
            log.info("  Saved %d bars → %s", len(df), out_path.name)

    mt5.shutdown()
    log.info("Done. High-res data saved.")

if __name__ == "__main__":
    main()
