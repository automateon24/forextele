"""
orchestrate_ollama_1yr_backtest.py
===================================
Feeds the Swarm OS context to a local Ollama model and tasks it with
generating + executing the full 1-year walk-forward backtest & ML pipeline.

Usage:
    C:\Python314\python.exe orchestrate_ollama_1yr_backtest.py

Requirements:
    - Ollama running locally (ollama serve)
    - Model pulled: ollama pull codellama:13b  (or deepseek-coder, llama3.1, etc.)
    - pip install requests
"""

import json
import logging
import subprocess
import time
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
BASE_DIR     = Path(r"C:\anlyzeforex\forextele")
CONTEXT_FILE = BASE_DIR / "OLLAMA_SWARM_CONTEXT.md"
OUTPUT_DIR   = BASE_DIR
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_EXE   = r"C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama.exe"
# llama3:latest (4.7GB) and llama3.2:latest (2.0GB) are installed
OLLAMA_MODEL = "llama3:latest"  # best available for code generation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Load the training context
# --------------------------------------------------------------------------- #
def load_context() -> str:
    with open(CONTEXT_FILE, encoding="utf-8") as f:
        return f.read()

# --------------------------------------------------------------------------- #
# Build the master prompt for Ollama
# --------------------------------------------------------------------------- #
def build_prompt(context: str) -> str:
    return f"""You are an expert algorithmic trading engineer and ML scientist.
You have been handed a Forex Swarm Trading OS that achieved 80% ROI in 1 week.
Your job is to extend it with a full 1-year walk-forward backtest and ML training pipeline.

=== SYSTEM CONTEXT ===
{context}

=== YOUR TASK ===
Write complete, production-ready Python code for the following 4 scripts.
Each script must be fully self-contained and immediately runnable.

---
SCRIPT 1: fetch_1year_m1_data.py
- Connect to MT5 using config at C:\\anlyzeforex\\forextele\\mt5_config.json
- Fetch 365 days of M1 bars for: EURUSD, GBPUSD, USDJPY, AUDUSD, GOLD, SILVER, BTCUSD, ETHUSD
- Also fetch M5, M15, H1 bars for all 8 symbols (needed for indicator computation)
- Save each as parquet: C:\\anlyzeforex\\forextele\\data_1y_<SYMBOL>_<TF>.parquet
- Print progress and row counts

---
SCRIPT 2: backtest_1year_all41.py
- Load the parquet files from Script 1 (no MT5 connection needed)
- Run ALL 41 strategies (same logic as C:\\anlyzeforex\\forextele\\backtest_1week_all41.py)
- For each bar: compute real ATR from rolling 14-bar std of close
- For each signal: scan forward up to 48 M1 bars to see if SL or TP is hit first
- SL = entry - sl_atr_mult * ATR (BUY) | entry + sl_atr_mult * ATR (SELL)
- TP = entry + tp_atr_mult * ATR (BUY) | entry - tp_atr_mult * ATR (SELL)
- atr_mult values come from DNA JSON at C:\\anlyzeforex\\forextele\\25stragy\\ai_optimized_forex_dna.json
- Add features to each signal row: hour, weekday, session (ASIAN/LONDON/NY/US), rsi_at_signal, adx_at_signal, atr_value
- Save results to: C:\\anlyzeforex\\forextele\\backtest_1year_signals.csv
- NO synthetic data, NO hardcoded prices

---
SCRIPT 3: ml_walkforward_trainer.py
- Load backtest_1year_signals.csv
- Walk-forward split: train on first 270 days, validate on last 95 days
- Features: symbol, strategy, direction, hour, weekday, session, rsi_at_signal, adx_at_signal, atr_value, sl_pts, tp_pts
- Target: WIN=1, LOSS=0 (drop EXPIRED rows or treat as LOSS)
- Train 3 models: GradientBoostingClassifier, RandomForestClassifier, XGBClassifier (if available)
- Use GridSearchCV with 3-fold CV for each
- Evaluate: accuracy, weighted F1, ROC-AUC on validation set
- Save best model to: C:\\anlyzeforex\\forextele\\ml_1year_best_model.joblib
- Save feature importances to: C:\\anlyzeforex\\forextele\\ml_feature_importance.json
- Print all metrics to console

---
SCRIPT 4: report_1year_results.py
- Load backtest_1year_signals.csv and ml_1year_best_model.joblib
- Apply ML lot sizing: if win_prob < 0.55: lot = 0.01 else lot = 0.02
- Compute per-trade P&L using real ATR-based SL/TP points × lot × tick_value
- Tick value lookup from MT5 or use: EURUSD/GBPUSD/AUDUSD=10, USDJPY=9.1, GOLD=1, SILVER=50, BTCUSD=1, ETHUSD=0.1 per 0.01 lot
- Aggregate:
  * Daily ROI table (all 365 days)
  * Strategy breakdown: trades, wins, P&L, avg_daily_roi
  * Symbol breakdown: trades, wins, P&L
  * ML model metrics summary
  * Feature importance table
  * Walk-forward equity curve (daily cumulative capital starting at $10,000)
- Write to: C:\\anlyzeforex\\forextele\\ml_1year_backtest_report.md
- Also print summary to console

=== RULES ===
- Use C:\\Python314\\python.exe compatible code (Python 3.14)
- Available packages: pandas, numpy, scikit-learn, joblib, MetaTrader5, requests
- NO mock data, NO hardcoded prices or P&L
- Keep ALL 41 strategies, ALL 8 pairs
- Add proper logging to every script
- Handle MT5 connection errors gracefully

Write all 4 scripts now, complete and ready to run.
"""

# --------------------------------------------------------------------------- #
# Call Ollama and stream response
# --------------------------------------------------------------------------- #
def call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    log.info("Calling Ollama model: %s", model)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_ctx": 32768,
            "temperature": 0.1,
            "top_p": 0.9,
        }
    }
    full_response = []
    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    full_response.append(token)
                    print(token, end="", flush=True)
                    if chunk.get("done"):
                        break
    except requests.ConnectionError:
        log.error("Cannot connect to Ollama. Is it running? Start with: ollama serve")
        return ""
    except Exception as exc:
        log.error("Ollama call failed: %s", exc)
        return ""
    print()
    return "".join(full_response)

# --------------------------------------------------------------------------- #
# Parse and save generated scripts from Ollama response
# --------------------------------------------------------------------------- #
def extract_and_save_scripts(response: str):
    """Extract Python code blocks and save as files."""
    script_names = [
        "fetch_1year_m1_data.py",
        "backtest_1year_all41.py",
        "ml_walkforward_trainer.py",
        "report_1year_results.py",
    ]
    # Split on python code fences
    parts = response.split("```python")
    scripts_saved = []
    for i, name in enumerate(script_names):
        idx = i + 1
        if idx < len(parts):
            code = parts[idx].split("```")[0].strip()
            if code and len(code) > 100:
                out = OUTPUT_DIR / name
                with open(out, "w", encoding="utf-8") as f:
                    f.write(code)
                log.info("Saved script: %s (%d chars)", out, len(code))
                scripts_saved.append(name)
    return scripts_saved

# --------------------------------------------------------------------------- #
# Run saved scripts in sequence
# --------------------------------------------------------------------------- #
def run_script(name: str):
    path = OUTPUT_DIR / name
    if not path.is_file():
        log.warning("Script not found: %s — skipping", name)
        return False
    log.info("=" * 60)
    log.info("Running: %s", name)
    log.info("=" * 60)
    result = subprocess.run(
        [r"C:\Python314\python.exe", str(path)],
        cwd=str(OUTPUT_DIR),
        capture_output=False,
        text=True,
    )
    if result.returncode != 0:
        log.error("%s exited with code %d", name, result.returncode)
        return False
    log.info("%s completed successfully.", name)
    return True

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    # 1. Load context
    if not CONTEXT_FILE.is_file():
        log.error("Context file not found: %s", CONTEXT_FILE)
        return
    context = load_context()
    log.info("Context loaded: %d chars", len(context))

    # 2. Build prompt
    prompt = build_prompt(context)
    log.info("Prompt built: %d chars", len(prompt))

    # 3. Call Ollama to generate all 4 scripts
    log.info("Sending to Ollama — this may take 3-10 minutes depending on model…")
    response = call_ollama(prompt)

    if not response:
        log.error("No response from Ollama. Check that Ollama is running.")
        log.info("Start Ollama: ollama serve")
        log.info("Pull model:   ollama pull codellama:13b")
        return

    # 4. Save response for reference
    resp_file = OUTPUT_DIR / "ollama_generated_pipeline.txt"
    with open(resp_file, "w", encoding="utf-8") as f:
        f.write(response)
    log.info("Full response saved to: %s", resp_file)

    # 5. Extract and save individual scripts
    saved = extract_and_save_scripts(response)
    log.info("Scripts saved: %s", saved)

    if not saved:
        log.warning("Could not auto-extract scripts. Review ollama_generated_pipeline.txt manually.")
        return

    # 6. Run scripts in sequence
    pipeline = [
        "fetch_1year_m1_data.py",
        "backtest_1year_all41.py",
        "ml_walkforward_trainer.py",
        "report_1year_results.py",
    ]
    for script in pipeline:
        ok = run_script(script)
        if not ok:
            log.error("Pipeline stopped at: %s", script)
            log.info("Fix the issue and re-run: C:\\Python314\\python.exe %s", script)
            break
        time.sleep(2)

    # 7. Check if report was generated
    report = OUTPUT_DIR / "ml_1year_backtest_report.md"
    if report.is_file():
        log.info("=" * 60)
        log.info("SUCCESS! Report ready at:")
        log.info("  %s", report)
        log.info("=" * 60)
    else:
        log.warning("Report not yet generated. Pipeline may still be running.")

if __name__ == "__main__":
    main()
