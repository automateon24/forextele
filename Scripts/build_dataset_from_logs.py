"""
Build Dataset from Event Logs & Backtest Telemetry
===================================================
Converts data/events/trading_events.jsonl or backtest logs into
structured Parquet/CSV dataset tables (data/datasets/trades_features_*.parquet).
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BUILD_DATASET")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVENTS_PATH = ROOT / "data" / "events" / "trading_events.jsonl"
DATASETS_DIR = ROOT / "data" / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def build_dataset_from_jsonl(events_file: Path) -> pd.DataFrame:
    if not events_file.exists():
        logger.warning(f"Events file {events_file} does not exist. Creating empty sample dataset.")
        return pd.DataFrame()

    signals, filters, exits = {}, {}, []

    with open(events_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                evt = data.get("event")
                cid = data.get("correlation_id")

                if evt == "signal":
                    signals[cid] = data
                elif evt == "filter":
                    filters[cid] = data
                elif evt == "exit":
                    exits.append(data)
            except Exception as e:
                continue

    rows = []
    for ex in exits:
        cid = ex.get("correlation_id")
        sig = signals.get(cid, {})
        flt = filters.get(cid, {})

        row = {
            "correlation_id": cid,
            "symbol":         sig.get("symbol", ex.get("symbol")),
            "timeframe":      sig.get("timeframe", ex.get("timeframe")),
            "strategy_id":     sig.get("strategy_id", ex.get("strategy_id")),
            "side":            sig.get("side", ex.get("side")),
            "entry_price":     sig.get("entry", ex.get("entry_price")),
            "exit_price":      ex.get("exit_price"),
            "pnl":             ex.get("pnl", 0.0),
            "outcome":         ex.get("outcome", "UNKNOWN"),
            "label_win":       1 if ex.get("outcome") == "WIN" else 0,
            "prob_win":        flt.get("prob_win"),
            "filter_decision": flt.get("decision"),
            "data_source":     ex.get("data_source", "paper"),
            "timestamp":       sig.get("ts_utc", ex.get("time")),
        }

        # Expand features dictionary
        feats = sig.get("features", {})
        for k, v in feats.items():
            row[f"feature_{k}"] = v

        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def main():
    logger.info("Building training dataset from event logs...")
    df = build_dataset_from_jsonl(EVENTS_PATH)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    parquet_path = DATASETS_DIR / f"trades_features_{timestamp_str}.parquet"
    csv_path     = DATASETS_DIR / f"trades_features_{timestamp_str}.csv"

    if not df.empty:
        try:
            df.to_parquet(parquet_path, index=False)
            logger.info(f"Saved Parquet dataset: {parquet_path}")
        except Exception as e:
            logger.warning(f"Could not save Parquet (pyarrow/fastparquet required): {e}")

        df.to_csv(csv_path, index=False)
        logger.info(f"Saved CSV dataset ({len(df)} rows): {csv_path}")
    else:
        logger.info("No event records found. Created template dataset directory.")


if __name__ == "__main__":
    main()
