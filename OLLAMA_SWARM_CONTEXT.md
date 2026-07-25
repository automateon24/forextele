# SWARM TRADING OS — COMPLETE MASTER CONTEXT FOR OLLAMA
# Updated: 2026-07-13 | Continuation from live trading sessions
# This document merges the existing live trading history + today's backtest achievements

---

## SECTION 1: LIVE TRADING HISTORY (What happened before today)

### Live System Background
- System: Forex Swarm Trading OS running on MT5 (XM Global demo account)
- Started live trading: ~July 4, 2026
- Initially struggled with strategies firing in unfavourable conditions
- Identified that not all strategies suit all times — need regime/session awareness
- Strategies need to know WHEN to run and WHAT pattern to enter

### Live Trading Observations
- The system ran 24/7 but many signals fired during low-liquidity periods (ASIAN session for FX)
- PIP_BLAST strategy consistently underperformed in ranging markets (fired too many false signals)
- GOLD and SILVER showed highest reliability due to clear trend behaviour
- ETHUSD had high win rate (66%) but very low pip value, so P&L was low
- The master_swarm_runner.log shows the system ran continuously from July 7-11, 2026
- Live order executor was mostly logging MT5 connection status (not placing large real lots)
- Strategy engine was running on M5/M15 timeframes primarily

### Key Insight from Live Trading
- The human observation: "it is not necessary all strategies match at all time"
- Strategies have different BEHAVIOURS — some work in trends, some in ranges, some at specific sessions
- We need to know WHEN to run each strategy (regime filter) and WHAT pattern to enter
- This led to the regime filter implementation (ADX threshold for trend vs reversion strategies)

---

## SECTION 2: THIS WEEK'S BACKTEST RESULTS (July 4-13, 2026)

### Backtest Parameters
- Capital: $10,000 USD
- Lot size: 0.10 fixed, then 0.02 for ML testing
- Timeframes: M5, M15, H1 (signal generation), M5 (outcome simulation)
- Lookahead bias: NONE — all signals use only past bars
- Outcome: Forward scan 48 bars — first SL or TP hit wins

### Performance Summary (from backtest_1week_results.csv — 4,077 trades)
| Metric | Value |
|--------|-------|
| Total Trades | 4,077 |
| Win Rate | 45.65% |
| Net P&L | $8,048.89 |
| ROI on $10k | 80.49% in 1 week |
| Sharpe Ratio | 19.21 |
| Max Drawdown | -0.80% |
| Daily ROI range | -1.05% to +26.11% |

### Daily Breakdown
| Date | P&L | ROI% |
|------|-----|------|
| Jul 07 | $1,413 | +14.14% |
| Jul 08 | $2,610 | +26.11% |
| Jul 09 | $1,551 | +15.52% |
| Jul 10 | $1,160 | +11.60% |
| Jul 11 | -$29  | -0.30% |
| Jul 12 | -$104 | -1.05% |
| Jul 13 | $1,447| +14.47% |

### Strategy Performance
| Strategy | Trades | Win% | Total P&L | Status |
|----------|--------|------|-----------|--------|
| ORDER_BLOCK_REVERSAL | 448 | 48% | $1,396 | ✅ Keep |
| DAY_LOW_BULLISH | 74 | 59.5% | $1,209 | ✅ Keep |
| ENHANCED_BULLISH | 74 | 59.5% | $1,209 | ✅ Keep |
| INSTITUTIONAL_SUPPORT | 336 | 45.2% | $1,036 | ✅ Keep |
| LONDON_BREAKOUT | 20 | 85% | $800 | ✅ Keep |
| DAY_HIGH_BEARISH | 171 | 52.6% | $678 | ✅ Keep |
| ENHANCED_BEARISH | 171 | 52.6% | $678 | ✅ Keep |
| VOLUME_CLIMAX | 80 | 56.2% | $622 | ✅ Keep |
| BULL_TREND_FOLLOWER | 782 | 50.9% | $598 | ✅ Keep |
| PIP_BLAST | 1921 | 39.9% | -$180 | ⚠️ ML filter needed |

### Symbol Performance
| Symbol | Trades | Win% | Total P&L |
|--------|--------|------|-----------|
| SILVER | 100 | 44% | $3,294 |
| GOLD | 174 | 63.8% | $2,890 |
| BTCUSD | 780 | 49.5% | $1,122 |
| AUDUSD | 549 | 38.1% | $249 |
| USDJPY | 475 | 29.9% | $202 |
| GBPUSD | 621 | 45.2% | $161 |
| EURUSD | 665 | 32% | $110 |
| ETHUSD | 713 | 66.6% | $17 |

---

## SECTION 3: WHAT WAS BUILT TODAY (July 13, 2026)

### Files Created/Modified
- `backtest_1week_all41.py` — Main backtest engine (uses np.searchsorted, no lookahead)
- `ml_classifier_pipeline.py` — GradientBoosting classifier
- `ml_experiment_pipeline.py` — Multi-model trainer (GBM + RF + XGBoost)
- `ml_predictor.py` — Inference wrapper (win_probability function)
- `ml_backtest_report.py` — Backtest report generator
- `ml_backtest_report.md` — Generated report
- `live_strategy_executor.py` — Updated with Kelly criterion + ML lot sizing
- `OLLAMA_SWARM_CONTEXT.md` — This context file
- `orchestrate_ollama_1yr_backtest.py` — Ollama orchestration script

### Key Code Patterns (CORRECT MT5 Usage)
```python
import MetaTrader5 as mt5   # CORRECT import — NOT 'from mt5 import *'
import json, pandas as pd, numpy as np
from pathlib import Path

def connect():
    if mt5.initialize(): return True
    with open('mt5_config.json') as f: cfg = json.load(f)
    return mt5.initialize(login=int(cfg['login']), server=cfg['server'], password=cfg['password'])

def fetch(symbol, tf, bars=2000):
    r = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# For date range fetch:
def fetch_range(symbol, tf, days=365):
    from datetime import datetime, timedelta
    utc_to = datetime.utcnow()
    utc_from = utc_to - timedelta(days=days)
    r = mt5.copy_rates_range(symbol, tf, utc_from, utc_to)
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df
```

### Indicator Helpers (already implemented in backtest engine)
```python
def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean()
    return 100-100/(1+g/l.replace(0,np.nan))

def bollinger(s, p=20, std=2.0):
    m=s.rolling(p).mean(); b=s.rolling(p).std()*std
    return m, m+b, m-b

def macd_line(s):
    return s.ewm(span=12).mean() - s.ewm(span=26).mean()

def adx_series(df, p=14):
    tr=pd.concat([df['high']-df['low'],(df['high']-df['close'].shift()).abs(),(df['low']-df['close'].shift()).abs()],axis=1).max(axis=1)
    dmp=((df['high']-df['high'].shift())>(df['low'].shift()-df['low'])).astype(float)*(df['high']-df['high'].shift()).clip(lower=0)
    dmn=((df['low'].shift()-df['low'])>(df['high']-df['high'].shift())).astype(float)*(df['low'].shift()-df['low']).clip(lower=0)
    atr_s=tr.rolling(p).mean()
    di_p=100*(dmp.rolling(p).mean()/atr_s); di_n=100*(dmn.rolling(p).mean()/atr_s)
    dx=(abs(di_p-di_n)/(di_p+di_n).replace(0,1))*100
    return dx.rolling(p).mean()
```

---

## SECTION 4: THE NEXT TASK — 1-YEAR WALK-FORWARD BACKTEST + ML PIPELINE

### What we want Ollama to build (4 scripts):

**SCRIPT 1: fetch_1year_m1_data.py**
- Use `import MetaTrader5 as mt5` (NOT `from mt5 import *`)
- Use `mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)` for M1 data
- Also fetch M5 (`mt5.TIMEFRAME_M5`), M15 (`mt5.TIMEFRAME_M15`), H1 (`mt5.TIMEFRAME_H1`)
- Save to parquet: `data_1y_{symbol}_{TF}.parquet` in BASE_DIR
- Symbols: EURUSD, GBPUSD, USDJPY, AUDUSD, GOLD, SILVER, BTCUSD, ETHUSD
- Python exe: C:\Python314\python.exe

**SCRIPT 2: backtest_1year_all41.py**
- Load parquet files from Script 1 (no MT5 needed for this)
- Run the same signal generation logic as backtest_1week_all41.py
- ATR = rolling 14-bar std of close × 0.5 (same formula as current engine)
- For each signal: scan forward 48 M1 bars for SL/TP hit
- Save: `backtest_1year_signals.csv` with columns: time, symbol, strategy, direction, entry, sl_pts, tp_pts, atr, hour, weekday, session, rsi_val, adx_val, outcome

**SCRIPT 3: ml_walkforward_trainer.py**
- Load backtest_1year_signals.csv
- Walk-forward: train first 270 days, validate last 95 days
- Features: symbol, strategy, direction, hour, weekday, session, rsi_val, adx_val, atr, sl_pts, tp_pts
- Target: WIN=1, LOSS=0
- Try: GradientBoostingClassifier, RandomForestClassifier, XGBClassifier
- Use GridSearchCV cv=3, scoring='f1_weighted'
- Save best: `ml_1year_best_model.joblib`
- Save importances: `ml_feature_importance.json`

**SCRIPT 4: report_1year_results.py**
- Load signals CSV + best model
- Apply ML sizing: prob>=0.55 → lot=0.02, else lot=0.01
- Tick values per 0.01 lot: EURUSD/GBPUSD/AUDUSD=0.10, USDJPY=0.091, GOLD=0.01, SILVER=0.50, BTCUSD=0.01, ETHUSD=0.001
- Compute real P&L: pnl = pnl_pts × lot × (tick_value / point)
- Output: `ml_1year_backtest_report.md` with daily ROI, strategy breakdown, equity curve, ML metrics

### CRITICAL: Common mistakes to avoid
1. WRONG: `from mt5 import *` → CORRECT: `import MetaTrader5 as mt5`
2. WRONG: `mt5.copy_rates_range(symbol, 'M1', ...)` → CORRECT: `mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, ...)`
3. WRONG: Hardcoded P&L values → CORRECT: Always compute from real ATR × sl/tp multiplier
4. WRONG: `import pyarrow.parquet as pq` for saving → CORRECT: `df.to_parquet(path, compression='gzip')`
5. WRONG: Reading parquet with pyarrow → CORRECT: `pd.read_parquet(path)`
6. WRONG: `model.predict([row.drop('direction',...)])` → CORRECT: build feature dict, use pd.DataFrame([feature_dict])

---

## SECTION 5: SYSTEM PATHS
- Base: `C:\anlyzeforex\forextele\`
- Python: `C:\Python314\python.exe`
- MT5 config: `C:\anlyzeforex\forextele\mt5_config.json`
- DNA config: `C:\anlyzeforex\forextele\25stragy\ai_optimized_forex_dna.json`
- Backtest CSV: `C:\anlyzeforex\forextele\backtest_1week_results.csv`
- Live executor: `C:\anlyzeforex\forextele\live_strategy_executor.py`
- Installed packages: pandas, numpy, scikit-learn, joblib, MetaTrader5, requests
