import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ALGO_ENGINE] - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
DNA_PATH = BASE_DIR / "strategy_dna.json"

import time
from real_mt5_execution import MT5ExecutionEngine

from datetime import datetime

class ForexAlgorithmicEngine:
    def __init__(self):
        self.symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
        self.timeframes = {
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4
        }
        self.dna = self.load_dna()
        self.executor = MT5ExecutionEngine()
        self.connect()

    def load_dna(self):
        try:
            with open(DNA_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load strategy DNA: {e}")
            return {}

    def connect(self):
        if not mt5.initialize():
            try:
                with open(MT5_CFG_PATH, "r") as f:
                    cfg = json.load(f)
                mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
            except Exception as e:
                log.error(f"MT5 Init Error: {e}")

    def is_in_session(self, symbol, dt):
        hour = dt.hour
        if symbol in ["EURUSD", "GBPUSD"]: return 7 <= hour <= 18
        elif symbol in ["GOLD"]: return 13 <= hour <= 20 # Gold NY Session Focus
        elif symbol in ["USDJPY", "AUDUSD"]: return hour >= 22 or hour <= 8
        elif symbol in ["USDCAD", "BTCUSD", "ETHUSD"]: return 12 <= hour <= 20
        return True

    def get_macro_trends(self, symbol):
        # Fetch both H1 and H4 to calculate AI Confidence Sizing (Golden Setups)
        tf_h1 = self.timeframes["H1"]
        tf_h4 = self.timeframes["H4"]
        
        rates_h1 = mt5.copy_rates_from_pos(symbol, tf_h1, 0, 100)
        rates_h4 = mt5.copy_rates_from_pos(symbol, tf_h4, 0, 50)
        
        if rates_h1 is None or rates_h4 is None: return "UNKNOWN", "UNKNOWN"
        
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['EMA_50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
        h1_trend = "BULLISH" if df_h1.iloc[-1]['close'] > df_h1.iloc[-1]['EMA_50'] else "BEARISH"
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h4['EMA_50'] = df_h4['close'].ewm(span=50, adjust=False).mean()
        h4_trend = "BULLISH" if df_h4.iloc[-1]['close'] > df_h4.iloc[-1]['EMA_50'] else "BEARISH"
        
        # Gold executes based on H4 primarily, Forex on H1. 
        # But we return both for Dynamic Sizing.
        return h1_trend, h4_trend

    def compute_indicators(self, df):
        # SMC Structure
        swing_len = 8
        df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
        df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
        df['last_sh'] = df['high'].where(df['swing_high']).ffill()
        df['last_sl'] = df['low'].where(df['swing_low']).ffill()
        
        # Volatility / ATR
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR'] = df['tr'].rolling(window=14).mean()
        df['ATR_MA_50'] = df['ATR'].rolling(window=50).mean()
        
        # RSI & VWAP for Mean Reversion
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['typ'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typ']).rolling(window=50).mean() # Proxy intraday VWAP for engine
        
        # Bollinger Bands for Volatility Breakout
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['STD_20'] = df['close'].rolling(window=20).std()
        df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
        df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
        
        # EMA Momentum
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        # Daily High/Low for Gold Liquidity Sweep
        df['date'] = pd.to_datetime(df['time'], unit='s').dt.date
        df['PDH'] = df.groupby('date')['high'].transform('max').shift(1)
        df['PDL'] = df.groupby('date')['low'].transform('min').shift(1)
        df['sweep_high'] = (df['high'] > df['PDH']) & (df['close'] < df['PDH'])
        df['sweep_low'] = (df['low'] < df['PDL']) & (df['close'] > df['PDL'])
        
        # Fair Value Gap (FVG) Detection Array
        df['bullish_fvg'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['open'].shift(1))
        df['bearish_fvg'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['open'].shift(1))
        df['fvg_top'] = np.where(df['bullish_fvg'], df['low'], np.where(df['bearish_fvg'], df['low'].shift(2), np.nan))
        df['fvg_bot'] = np.where(df['bullish_fvg'], df['high'].shift(2), np.where(df['bearish_fvg'], df['high'], np.nan))
        
        return df

    def scan_market(self):
        log.info("Scanning Forex Market Structure using Guided Swarm Intelligence...")
        signals = []
        now = datetime.utcnow()
        
        for symbol in self.symbols:
            if not self.is_in_session(symbol, now):
                continue # Skip pairs outside their Kill Zone
                
            # Time Zones and Session Vetoes
            if symbol == "GOLD":
                if now.weekday() == 4: # Friday Veto
                    log.debug("Skipping GOLD: Friday Veto Active")
                    continue
            elif symbol == "USDJPY":
                if not (13 <= now.hour <= 20): # NY Session Only for JPY Breakouts
                    log.debug("Skipping USDJPY: Outside NY Session")
                    continue
                
            # Timeframe scaling
            tf = self.timeframes["M15"] if symbol in ["GOLD", "AUDUSD"] else mt5.TIMEFRAME_M5
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 100)
            if rates is None or len(rates) < 100: continue
                
            df = pd.DataFrame(rates)
            df = self.compute_indicators(df)
            h1_trend, h4_trend = self.get_macro_trends(symbol)
            macro_trend = h4_trend if symbol == "GOLD" else h1_trend
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Volatility Filter (Avoid Chop)
            if pd.isna(last['ATR']) or pd.isna(last['ATR_MA_50']) or last['ATR'] < last['ATR_MA_50']:
                continue
                
            raw_signal = None
            strategy_used = ""
            
            # DNA MODULES (V2 UNIFIED ARCHITECTURE)
            if symbol in ["GOLD", "AUDUSD"]:
                # Pure SMC / Fair Value Gap Engine
                # Scan last 20 candles for an active FVG zone
                recent_fvgs = df.iloc[-20:-1]
                bullish_fvgs = recent_fvgs[recent_fvgs['bullish_fvg']]
                bearish_fvgs = recent_fvgs[recent_fvgs['bearish_fvg']]
                
                if macro_trend == 'BULLISH' and not bullish_fvgs.empty:
                    # Tap into nearest bullish FVG
                    latest_fvg = bullish_fvgs.iloc[-1]
                    if last['low'] <= latest_fvg['fvg_top'] and last['close'] > latest_fvg['fvg_bot']:
                        raw_signal, strategy_used = "BUY", "FVG_PULLBACK"
                elif macro_trend == 'BEARISH' and not bearish_fvgs.empty:
                    # Tap into nearest bearish FVG
                    latest_fvg = bearish_fvgs.iloc[-1]
                    if last['high'] >= latest_fvg['fvg_bot'] and last['close'] < latest_fvg['fvg_top']:
                        raw_signal, strategy_used = "SELL", "FVG_PULLBACK"
            
            elif symbol == "USDJPY":
                # NY Volatility Breakout Matrix
                if last['close'] > last['last_sh'] and prev['close'] <= prev['last_sh']:
                    raw_signal, strategy_used = "BUY", "NY_BREAKOUT"
                elif last['close'] < last['last_sl'] and prev['close'] >= prev['last_sl']:
                    raw_signal, strategy_used = "SELL", "NY_BREAKOUT"
                    
            else:
                # 45 STRATEGY SWARM FOR STANDARD FOREX/CRYPTO
                if last['RSI'] < 30 and last['close'] < last['Lower_BB']:
                    raw_signal, strategy_used = "BUY", "MEAN_REVERSION"
                elif last['RSI'] > 70 and last['close'] > last['Upper_BB']:
                    raw_signal, strategy_used = "SELL", "MEAN_REVERSION"
                elif last['EMA_9'] > last['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']:
                    raw_signal, strategy_used = "BUY", "MOMENTUM_CROSS"
                elif last['EMA_9'] < last['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']:
                    raw_signal, strategy_used = "SELL", "MOMENTUM_CROSS"
                    
            if not raw_signal: continue
                
            # SMC GUIDANCE (The Veto)
            smc_approved = False
            if raw_signal == "BUY" and macro_trend == 'BULLISH' and last['close'] > last['last_sl']:
                smc_approved = True
            elif raw_signal == "SELL" and macro_trend == 'BEARISH' and last['close'] < last['last_sh']:
                smc_approved = True
                
            if not smc_approved: continue
                
            # AI Confidence Sizing (Path 1)
            risk_modifier = 2.5 if h1_trend == h4_trend else 1.0
            
            # Whipsaw Armor & FVG Tuning
            sl_multiplier = 0.2
            if symbol in ["GOLD", "AUDUSD"]:
                sl_multiplier = 0.5 # FVGs require slightly wider structural stops
            elif symbol == "USDJPY" and (13 <= now.hour <= 16):
                sl_multiplier = 1.0 # Protect against NY Open chop
                
            signals.append({
                "symbol": symbol,
                "action": raw_signal,
                "strategy": strategy_used,
                "price": last['close'],
                "risk_modifier": risk_modifier,
                "sl_multiplier": sl_multiplier
            })
            
        return signals

    def execute_signals(self, signals):
        for sig in signals:
            log.info(f"🚨 ALGO TRIGGER: {sig['strategy']} on {sig['symbol']} -> {sig['action']} (Risk: {sig['risk_modifier']}x)")
            payload = {
                "symbol": sig["symbol"],
                "action": sig["action"],
                "entry": sig["price"],
                "final_sl": 0, # Executor will calculate based on ATR * sl_multiplier
                "final_tp1": 0,
                "risk_modifier": sig["risk_modifier"], 
                "comment": f"SWARM:{sig['strategy']}"
            }
            self.executor.execute_trade(payload, magic_number=999999)

    def run_loop(self):
        log.info("FOREX SWARM ENGINE ONLINE. Scanning with Institutional Guardrails...")
        while True:
            signals = self.scan_market()
            if signals:
                self.execute_signals(signals)
            else:
                log.info("No active algorithmic setups passing SMC constraints. Waiting...")
                
            time.sleep(300)

if __name__ == "__main__":
    engine = ForexAlgorithmicEngine()
    engine.run_loop()
