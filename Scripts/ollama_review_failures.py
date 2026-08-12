"""
Ollama Offline Failure Reviewer & Feature Ideation Engine
=========================================================
Loads losing trades from recent backtests or paper trading logs, passes
compact trade feature snapshots to local Ollama (llama3.2:3b), and generates
a structured failure analysis report with new candidate feature ideas.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("OLLAMA_REVIEW")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ml.ollama_client import OllamaClient

CACHE_DIR = ROOT / "data" / "ollama_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS_DIR = ROOT / "prompts"


def load_losing_trades(dataset_file: Path, max_samples: int = 30) -> list:
    if not dataset_file.exists():
        return []

    if dataset_file.suffix == ".parquet":
        df = pd.read_parquet(dataset_file)
    else:
        df = pd.read_csv(dataset_file)

    if "outcome" in df.columns:
        losing_df = df[df["outcome"] == "LOSS"].tail(max_samples)
        if losing_df.empty:
            losing_df = df.tail(max_samples)
    elif "ml_oos_ret" in df.columns:
        losing_df = df[df["ml_oos_ret"] <= 0].tail(max_samples)
        if losing_df.empty:
            losing_df = df.tail(max_samples)
    else:
        losing_df = df.tail(max_samples)

    records = []
    for _, r in losing_df.iterrows():
        rec = {}
        for c in df.columns:
            if isinstance(r[c], (int, float, np.floating)):
                rec[c] = round(float(r[c]), 4) if pd.notna(r[c]) else 0.0
            else:
                rec[c] = str(r[c])
        records.append(rec)

    return records


def run_failure_review(dataset_file: Optional[Path] = None):
    client = OllamaClient()

    if not client.is_server_online():
        logger.warning("Local Ollama server is offline at http://127.0.0.1:11434.")
        logger.warning("To run offline LLM failure reviews, install and start Ollama (e.g., 'ollama run llama3.2:3b').")
        return

    # Find latest dataset
    if dataset_file is None:
        datasets = list((ROOT / "data" / "datasets").glob("*.csv")) + list((ROOT / "reports").glob("*.csv"))
        if not datasets:
            logger.info("No trade dataset files found for review.")
            return
        dataset_file = sorted(datasets, key=lambda x: x.stat().st_mtime)[-1]

    logger.info(f"Loading trades from {dataset_file.name} for Ollama review...")
    trades = load_losing_trades(dataset_file, max_samples=30)
    if not trades:
        logger.info("No losing trades found in dataset.")
        return

    prompt_template_file = PROMPTS_DIR / "failure_analysis.txt"
    if prompt_template_file.exists():
        with open(prompt_template_file, "r") as f:
            template = f.read()
        prompt = template.replace("{{n}}", str(len(trades))).replace("{{trades_json}}", json.dumps(trades, indent=2))
        system_prompt = "You are a quantitative trading failure analyst. Output clean markdown."
    else:
        prompt = f"Analyze these {len(trades)} losing trades:\n" + json.dumps(trades, indent=2)
        system_prompt = None

    logger.info("Calling local Ollama API for failure analysis and feature ideation...")
    analysis = client.generate(prompt, system_prompt=system_prompt)

    if analysis:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        report_file = CACHE_DIR / f"ollama_failure_review_{timestamp_str}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# 🤖 Ollama AI Failure & Feature Analysis Report\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Dataset Reviewed**: `{dataset_file.name}` ({len(trades)} trades)  \n\n")
            f.write(analysis)

        logger.info(f"Ollama review report saved: {report_file}")
        print("\n" + "="*80)
        print("  OLLAMA AI FAILURE REVIEW SUMMARY")
        print("="*80)
        print(analysis[:1500])
        print("="*80 + "\n")


if __name__ == "__main__":
    run_failure_review()
