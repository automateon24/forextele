import json
import logging
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from pathlib import Path
from backtest_1week_all41 import (
    connect, load_dna, fetch, rsi, adx_series, macd_line, bollinger,
    generate_signals, simulate, SYMBOLS
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

DNA_PATH = Path(r"c:\anlyzeforex\forextele\25stragy\ai_optimized_forex_dna.json")

def precompute_indicators(mt5_sym):
    log.info("    Fetching M5...")
    df5  = fetch(mt5_sym, mt5.TIMEFRAME_M5,  2000)
    log.info("    Fetching M15...")
    df15 = fetch(mt5_sym, mt5.TIMEFRAME_M15, 2000)
    log.info("    Fetching H1...")
    df1h = fetch(mt5_sym, mt5.TIMEFRAME_H1,  500)
    
    if df5 is None or df15 is None: 
        log.warning("    M5 or M15 fetch failed.")
        return None, None, None

    log.info("    Calculating indicators...")
    df15['rsi']   = rsi(df15['close'])
    df15['adx']   = adx_series(df15)
    df15['macd']  = macd_line(df15['close'])
    df15['msig']  = df15['macd'].ewm(span=9).mean()
    df15['ema9']  = df15['close'].ewm(span=9).mean()
    df15['ema21'] = df15['close'].ewm(span=21).mean()
    df15['ema50'] = df15['close'].ewm(span=50).mean()
    _,df15['bb_up'],df15['bb_lo'] = bollinger(df15['close'])
    df15['bb_mid'] = df15['close'].rolling(20).mean()
    df15['vol_avg'] = df15['volume'].rolling(20).mean()

    df5['rsi']   = rsi(df5['close'])
    df5['ema9']  = df5['close'].ewm(span=9).mean()
    df5['ema21'] = df5['close'].ewm(span=21).mean()
    df5['tp_vwap'] = (df5['high']+df5['low']+df5['close'])/3
    df5['vwap']  = (df5['tp_vwap']*df5['volume']).cumsum()/df5['volume'].cumsum()

    if df1h is not None:
        df1h['range'] = df1h['high'] - df1h['low']
        df1h['mean_24'] = df1h['close'].rolling(24).mean()
        df1h['std_24'] = df1h['close'].rolling(24).std()
        df1h['dh_24'] = df1h['high'].rolling(24).max()
        df1h['dl_24'] = df1h['low'].rolling(24).min()
        df1h['ah_8'] = df1h['high'].rolling(8).max().shift(1)
        df1h['al_8'] = df1h['low'].rolling(8).min().shift(1)
        df1h['ph_12'] = df1h['high'].rolling(8).max().shift(4)
        df1h['pl_12'] = df1h['low'].rolling(8).min().shift(4)
        
        df1h['pc'] = df1h['close'].shift(1)
        df1h['co'] = df1h['open']
        df1h['cc'] = df1h['close']
        
        df1h['lr'] = df1h['range']
        df1h['ar'] = df1h['range'].rolling(10).mean()
        df1h['range_mean_5'] = df1h['range'].rolling(5).mean()
        
        df1h['ah_4'] = df1h['high'].rolling(4).max()
        df1h['al_4'] = df1h['low'].rolling(4).min()
        
        bull_highs = df1h['high'].where(df1h['close'] > df1h['open'], np.nan)
        df1h['ob_bob'] = bull_highs.rolling(20, min_periods=1).max()
        bear_lows = df1h['low'].where(df1h['close'] < df1h['open'], np.nan)
        df1h['ob_bok'] = bear_lows.rolling(20, min_periods=1).min()
        
        df1h_ended = df1h.copy()
        df1h_ended.index = df1h_ended.index + pd.Timedelta(hours=1)
    else:
        df1h_ended = None
        
    log.info("    Indicators calculated successfully.")
    return df5, df15, df1h_ended

def save_dna(dna_db):
    with open(DNA_PATH, 'w') as f:
        json.dump({"strategies": dna_db}, f, indent=2)

def run_optimization():
    if not connect():
        log.error("MT5 Connection Failed")
        return

    log.info("Loading active DNA database...")
    dna_db = load_dna()

    # Find active strategies
    active_keys = [k for k, v in dna_db.items() if v.get("active", True)]
    log.info(f"Found {len(active_keys)} active strategy-symbol combinations to optimize.")

    # Cache pre-computed dataframes by symbol
    df_cache = {}

    optimized_db = dna_db.copy()

    for key in active_keys:
        parts = key.split(":")
        symbol_label = parts[0]
        strategy_name = parts[1]
        timeframe = parts[2]
        mt5_sym = "GOLD" if symbol_label == "XAUUSD" else ("SILVER" if symbol_label == "XAGUSD" else symbol_label)

        log.info(f"Optimizing {key} on {mt5_sym}...")

        # Get MT5 Point and Tick Value
        if not mt5.symbol_select(mt5_sym, True):
            log.warning(f"Symbol {mt5_sym} not available — skipping"); continue
        info = mt5.symbol_info(mt5_sym)
        if not info: continue
        tick_val = info.trade_tick_value
        point = info.point

        # Precompute or pull from cache
        if mt5_sym not in df_cache:
            log.info(f"  Precomputing indicators for {mt5_sym}...")
            df5, df15, df1h_ended = precompute_indicators(mt5_sym)
            df_cache[mt5_sym] = (df5, df15, df1h_ended)
        else:
            df5, df15, df1h_ended = df_cache[mt5_sym]

        if df5 is None or df15 is None:
            log.warning(f"  Insufficient data for {mt5_sym} — skipping"); continue

        # Define search space based on strategy type
        if "DAY_LOW" in strategy_name or "DAY_HIGH" in strategy_name or "ENHANCED" in strategy_name:
            thresh_grid = [-2.2, -1.8, -1.2, 0.8, 1.2, 1.8]
        else:
            thresh_grid = [0.7, 0.85, 1.0, 1.3, 1.7]

        sl_grid = [0.3, 0.5, 0.8, 1.2, 1.5]
        tgt_grid = [0.6, 1.0, 1.8, 2.5, 3.0]

        best_pnl = -99999.0
        best_params = {}

        # Run grid search (100% in-memory fast loop)
        trials = 0
        for sl in sl_grid:
            for tgt in tgt_grid:
                for thresh in thresh_grid:
                    trials += 1
                    # Temporarily update DNA parameters in memory
                    dna_db[key]["sl"] = sl
                    dna_db[key]["tgt"] = tgt
                    dna_db[key]["thresh"] = thresh

                    # Run signal generation and simulation
                    signals = generate_signals(
                        symbol_label, mt5_sym, dna_db,
                        target_key=key, pre_df5=df5, pre_df15=df15, pre_df1h=df1h_ended
                    )
                    if not signals:
                        continue

                    results = simulate(signals, df5, tick_val, point)
                    if not results:
                        continue

                    wins = [r for r in results if r["pnl_usd"] > 0]
                    losses = [r for r in results if r["pnl_usd"] < 0]
                    
                    win_rate = len(wins) / len(results) if len(results) > 0 else 0.0
                    
                    avg_win = np.mean([r["pnl_usd"] for r in wins]) if len(wins) > 0 else 0.0
                    avg_loss = abs(np.mean([r["pnl_usd"] for r in losses])) if len(losses) > 0 else 0.0
                    avg_rr = (avg_win / avg_loss) if avg_loss > 0 else (tgt / sl if sl > 0 else 1.5)

                    pnl = sum(r["pnl_usd"] for r in results)
                    
                    if pnl > best_pnl:
                        best_pnl = pnl
                        best_params = {
                            "sl": sl, 
                            "tgt": tgt, 
                            "thresh": thresh,
                            "win_rate": win_rate,
                            "avg_rr": avg_rr
                        }

        if best_params:
            log.info(f"  Best params for {key}: {best_params} -> Net PnL: ${best_pnl:.2f} (from {trials} trials)")
            optimized_db[key]["sl"] = best_params["sl"]
            optimized_db[key]["tgt"] = best_params["tgt"]
            optimized_db[key]["thresh"] = best_params["thresh"]
            # Save optimization performance stats for Kelly sizing
            optimized_db[key]["win_rate"] = round(best_params["win_rate"], 3)
            optimized_db[key]["avg_rr"] = round(best_params["avg_rr"], 3)
        else:
            log.warning(f"  No successful trials for {key}, keeping default parameters.")

    # Save optimal parameters back to the DNA database
    log.info("Saving optimized DNA database...")
    save_dna(optimized_db)
    log.info("DNA Database successfully updated with optimized parameters!")
    mt5.shutdown()

if __name__ == "__main__":
    run_optimization()
