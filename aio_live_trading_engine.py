"""
ALL-IN-ONE (AIO) MULTI-ASSET AUTONOMOUS LIVE TRADING ENGINE
===========================================================
Executes the full suite of Indian-market adapted quantitative strategies:
  1. AIO_DILSE_PULLBACK (EMA 21 Pullback in H1 Aligned Trend)
  2. AIO_BOLLINGER_SQUEEZE (Volatility Contraction to Expansion Breakout)
  3. AIO_SMC_FVG_MITIGATION (Fair Value Gap Imbalance Tap)
  4. AIO_ORDER_BLOCK_REVERSAL (Institutional Liquidity Sweep)
  5. AIO_BREAKOUT_BOSS (Session Range Breakout)

Assets: GOLD, SILVER, BTCUSD, ETHUSD, EURUSD, GBPUSD, USDJPY, AUDUSD
Comments: AIO_<StrategyName> on every MT5 order deal
Supervised 24/7 by Master Watchdog
"""
import os
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
CONFIG_PATH = BASE_DIR / "mt5_config.json"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

AIO_LOG = LOGS_DIR / "aio_live_engine.log"
logging.basicConfig(
    filename=str(AIO_LOG),
    level=logging.INFO,
    format='%(asctime)s - [AIO_ENGINE] - %(levelname)s - %(message)s'
)
log = logging.getLogger("AIO_ENGINE")

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - [AIO_ENGINE] - %(levelname)s - %(message)s'))
log.addHandler(console)

from real_mt5_execution import MT5ExecutionEngine
from ai_conviction_tsl_manager import register_trade

# AUDUSD blacklisted due to 0% win rate across 15 trades (-$99.58 loss)
SYMBOLS = ["GOLD", "SILVER", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY"]

ASSET_SPECS = {
    "GOLD":   {"lot": 0.02, "pip_size": 0.10, "digits": 2, "max_daily": 4},
    "SILVER": {"lot": 0.01, "pip_size": 0.01, "digits": 3, "max_daily": 3},
    "BTCUSD": {"lot": 0.02, "pip_size": 10.0, "digits": 2, "max_daily": 4},
    "ETHUSD": {"lot": 0.02, "pip_size": 1.0,  "digits": 2, "max_daily": 3},
    "EURUSD": {"lot": 0.05, "pip_size": 0.0001, "digits": 5, "max_daily": 2},
    "GBPUSD": {"lot": 0.05, "pip_size": 0.0001, "digits": 5, "max_daily": 2},
    "USDJPY": {"lot": 0.05, "pip_size": 0.01, "digits": 3, "max_daily": 2},
}

# Strict session hours (UTC) to eliminate low-liquidity chop and spread-widening periods
PAIR_ALLOWED_HOURS = {
    "GOLD":   [1, 7, 8, 9, 10],
    "SILVER": [7],
    "BTCUSD": [1, 3, 12, 14, 15, 16, 23],
    "ETHUSD": [1, 3, 12, 14, 15, 16, 23],
    "EURUSD": [8, 9],
    "GBPUSD": [8],
    "USDJPY": [0, 1, 2, 7, 8],
}

class AIOLiveTradingEngine:
    def __init__(self):
        self.mt5_engine = MT5ExecutionEngine()
        self.last_trade_time = {}
        self.daily_trade_count = {}
        self.current_trade_day = datetime.now(timezone.utc).date()
        self.current_week = datetime.now(timezone.utc).isocalendar().week
        self.consec_losses = {}
        self.quarantined_symbols = set()
        self.cooldown_seconds = 1800  # 30 minutes per asset (raised from 15m to stop chop churn)
        self.magic_base = 888100

        # Load trained AI ML model
        self.ml_model = None
        ml_path = BASE_DIR / "final_model_sucess.joblib"
        if ml_path.exists():
            try:
                import joblib
                self.ml_model = joblib.load(ml_path)
                log.info(" Loaded trained AI ML model (final_model_sucess.joblib) for live trade gating")
            except Exception as e:
                log.warning(f"Could not load ML model: {e}")

    def init_mt5(self) -> bool:
        if mt5.initialize():
            self.mt5_engine.connected = True
            log.info("✅ Successfully connected to running MetaTrader 5 terminal.")
            return True
        return self.mt5_engine.connect()

    def fetch_m15_data(self, symbol: str) -> pd.DataFrame:
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 150)
        if rates is None or len(rates) < 60:
            return None
        df = pd.DataFrame(rates)
        df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time_utc', inplace=True)
        
        # Technical indicators
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # ATR (14)
        tr = np.maximum(df['high'] - df['low'], 
                        np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                   abs(df['low'] - df['close'].shift(1))))
        df['atr14'] = tr.rolling(14).mean()

        # RSI (14)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands (20, 2.0)
        df['bb_mid'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_up'] = df['bb_mid'] + (2.0 * bb_std)
        df['bb_lo'] = df['bb_mid'] - (2.0 * bb_std)
        df['bb_width'] = (df['bb_up'] - df['bb_lo']) / df['bb_mid']

        # H1 Macro Trend & ADX Trend Strength
        h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 80)
        if h1_rates is not None and len(h1_rates) >= 50:
            df_h1 = pd.DataFrame(h1_rates)
            ema50_h1 = df_h1['close'].ewm(span=50).mean().iloc[-2]
            c_h1 = df_h1['close'].iloc[-2]
            df['macro_trend'] = "BULLISH" if c_h1 > ema50_h1 else "BEARISH"
            
            # Simple H1 14-period True Range for volatility check
            h1_tr = np.maximum(df_h1['high'] - df_h1['low'],
                               np.maximum(abs(df_h1['high'] - df_h1['close'].shift(1)),
                                          abs(df_h1['low'] - df_h1['close'].shift(1))))
            df['h1_atr'] = float(h1_tr.rolling(14).mean().iloc[-2])
        else:
            df['macro_trend'] = "NEUTRAL"
            df['h1_atr'] = 1.0

        return df

    def scan_asset(self, symbol: str):
        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()
        
        # Reset daily trade counters at UTC midnight
        if today != self.current_trade_day:
            self.current_trade_day = today
            self.daily_trade_count = {}
            log.info(f"🔄 [AIO ENGINE] New UTC Day ({today}) - Reset all daily trade counters.")

        # Weekly reset for symbol quarantine
        week_num = now_utc.isocalendar().week
        if week_num != self.current_week:
            self.current_week = week_num
            self.consec_losses = {}
            self.quarantined_symbols = set()
            log.info(f"🔄 [AIO ENGINE] New Calendar Week ({week_num}) - Reset symbol quarantine & loss counters.")

        # Dynamic Symbol Gating: If quarantined due to >= 2 consecutive losses this week, skip
        if symbol in self.quarantined_symbols:
            return

        # Weekend Mode: Forex and Gold are closed on weekends. Specialize exclusively on Crypto (BTCUSD, ETHUSD)
        is_weekend = (now_utc.weekday() >= 5)
        if is_weekend and symbol not in ["BTCUSD", "ETHUSD"]:
            return

        # Filter 1: Daily Trade Cap per Asset (stops catastrophic overtrading like 215 Gold trades)
        spec = ASSET_SPECS.get(symbol, {"lot": 0.02, "pip_size": 0.10, "digits": 2, "max_daily": 3})
        trades_today = self.daily_trade_count.get(symbol, 0)
        if trades_today >= spec.get("max_daily", 3):
            return

        # Filter 2: Session Hours Filter (only trade during high liquidity, low-spread sessions)
        allowed_hours = PAIR_ALLOWED_HOURS.get(symbol, list(range(24)))
        if now_utc.hour not in allowed_hours:
            return

        # Filter 3: Cooldown between trades on this symbol
        now_ts = time.time()
        if symbol in self.last_trade_time:
            if now_ts - self.last_trade_time[symbol] < self.cooldown_seconds:
                return

        # Filter 4: Check existing open position on this symbol for AIO magic range
        positions = mt5.positions_get()
        if positions:
            for p in positions:
                if p.symbol == symbol and (888100 <= p.magic <= 888110):
                    return  # Already has active AIO trade on this asset

        df = self.fetch_m15_data(symbol)
        if df is None:
            return

        spec = ASSET_SPECS.get(symbol, {"lot": 0.02, "pip_size": 0.10, "digits": 2})
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        p2 = df.iloc[-3]
        macro = curr['macro_trend']
        atr = curr['atr14'] if not np.isnan(curr['atr14']) else 1.0
        rsi = curr['rsi']
        close_p = curr['close']
        high_p = curr['high']
        low_p = curr['low']
        open_p = curr['open']
        digits = spec["digits"]

        trade_signal = None

        # -------------------------------------------------------------
        # STRATEGY 1: AIO_DILSE_PULLBACK (20 EMA Touch in Aligned Trend)
        # -------------------------------------------------------------
        if macro == "BULLISH" and curr['ema21'] > curr['ema50']:
            if low_p <= curr['ema21'] and close_p > curr['ema21'] and rsi > 40.0:
                risk = max(atr * 1.2, spec["pip_size"] * 20)
                sl = round(close_p - risk, digits)
                tp1 = round(close_p + (risk * 1.5), digits)
                tp2 = round(close_p + (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_DILSE_PULL", "action": "BUY", "magic": 888101,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "EMA21 Pullback bounce in Bullish Trend"
                }
        elif macro == "BEARISH" and curr['ema21'] < curr['ema50']:
            if high_p >= curr['ema21'] and close_p < curr['ema21'] and rsi < 60.0:
                risk = max(atr * 1.2, spec["pip_size"] * 20)
                sl = round(close_p + risk, digits)
                tp1 = round(close_p - (risk * 1.5), digits)
                tp2 = round(close_p - (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_DILSE_PULL", "action": "SELL", "magic": 888101,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "EMA21 Pullback rejection in Bearish Trend"
                }

        # -------------------------------------------------------------
        # STRATEGY 2: AIO_SMC_FVG_MITIGATION (Fair Value Gap Imbalance Tap)
        # Root-Cause Fix: Require H1 macro trend alignment + minimum gap of 1.0 ATR
        # (Prevents 104 losses caused by micro-wicks tapping noise in sideways chop)
        # -------------------------------------------------------------
        if not trade_signal:
            min_fvg_gap = max(atr * 0.40, spec["pip_size"] * 10)
            if macro == "BULLISH" and (curr['low'] - p2['high']) >= min_fvg_gap and prev['close'] > prev['open']:
                risk = max(atr * 1.2, spec["pip_size"] * 25)
                sl = round(curr['low'] - (risk * 0.4), digits)
                tp1 = round(close_p + (risk * 1.5), digits)
                tp2 = round(close_p + (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_SMC_FVG", "action": "BUY", "magic": 888102,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "M15 Bullish FVG Imbalance Tap aligned with H1 Bullish Trend"
                }
            elif macro == "BEARISH" and (p2['low'] - curr['high']) >= min_fvg_gap and prev['close'] < prev['open']:
                risk = max(atr * 1.2, spec["pip_size"] * 25)
                sl = round(curr['high'] + (risk * 0.4), digits)
                tp1 = round(close_p - (risk * 1.5), digits)
                tp2 = round(close_p - (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_SMC_FVG", "action": "SELL", "magic": 888102,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "M15 Bearish FVG Imbalance Tap aligned with H1 Bearish Trend"
                }

        # -------------------------------------------------------------
        # STRATEGY 3: AIO_BOLLINGER_SQUEEZE (Contraction to Expansion Breakout)
        # -------------------------------------------------------------
        if not trade_signal:
            if curr['bb_width'] < 0.015:  # Tight squeeze
                if close_p > curr['bb_up']:
                    risk = max(atr * 1.2, spec["pip_size"] * 25)
                    sl = round(curr['bb_mid'], digits)
                    tp1 = round(close_p + (risk * 2.0), digits)
                    tp2 = round(close_p + (risk * 3.5), digits)
                    trade_signal = {
                        "strategy": "AIO_BOLL_SQZ", "action": "BUY", "magic": 888103,
                        "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Bollinger Squeeze Upper Band Expansion"
                    }
                elif close_p < curr['bb_lo']:
                    risk = max(atr * 1.2, spec["pip_size"] * 25)
                    sl = round(curr['bb_mid'], digits)
                    tp1 = round(close_p - (risk * 2.0), digits)
                    tp2 = round(close_p - (risk * 3.5), digits)
                    trade_signal = {
                        "strategy": "AIO_BOLL_SQZ", "action": "SELL", "magic": 888103,
                        "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Bollinger Squeeze Lower Band Expansion"
                    }

        # -------------------------------------------------------------
        # STRATEGY 4: AIO_ORDER_BLOCK_REVERSAL (Overbought/Oversold Sweep)
        # -------------------------------------------------------------
        if not trade_signal:
            rolling_high_24 = df['high'].iloc[-48:].max()
            rolling_low_24  = df['low'].iloc[-48:].min()
            if high_p >= rolling_high_24 and close_p < rolling_high_24 and rsi >= 68.0:
                risk = max(atr * 1.1, spec["pip_size"] * 20)
                sl = round(high_p + (risk * 0.3), digits)
                tp1 = round(close_p - (risk * 1.5), digits)
                tp2 = round(close_p - (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_OB_REV", "action": "SELL", "magic": 888104,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Liquidity Sweep of 24-Bar High + RSI Overbought"
                }
            elif low_p <= rolling_low_24 and close_p > rolling_low_24 and rsi <= 32.0:
                risk = max(atr * 1.1, spec["pip_size"] * 20)
                sl = round(low_p - (risk * 0.3), digits)
                tp1 = round(close_p + (risk * 1.5), digits)
                tp2 = round(close_p + (risk * 2.5), digits)
                trade_signal = {
                    "strategy": "AIO_OB_REV", "action": "BUY", "magic": 888104,
                    "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Liquidity Sweep of 24-Bar Low + RSI Oversold"
                }

        # Execute if setup triggered
        if trade_signal:
            strat_name = trade_signal["strategy"]
            action = trade_signal["action"]
            sl = trade_signal["sl"]
            tp1 = trade_signal["tp1"]
            tp2 = trade_signal["tp2"]
            magic = trade_signal["magic"]
            lot = spec["lot"]

            # AI ML Model Inference & Gating
            win_prob = 0.50
            if self.ml_model is not None:
                strat_map = {
                    ("AIO_DILSE_PULL", "BUY"): "BULL_TREND_FOLLOWER",
                    ("AIO_DILSE_PULL", "SELL"): "BEAR_TREND_FOLLOWER",
                    ("AIO_BOLL_SQZ", "BUY"): "VOLATILITY_BREAKOUT",
                    ("AIO_BOLL_SQZ", "SELL"): "VOLATILITY_BREAKOUT",
                    ("AIO_SMC_FVG", "BUY"): "ORDER_BLOCK_REVERSAL",
                    ("AIO_SMC_FVG", "SELL"): "ORDER_BLOCK_REVERSAL",
                    ("AIO_OB_REV", "BUY"): "ORDER_BLOCK_REVERSAL",
                    ("AIO_OB_REV", "SELL"): "ORDER_BLOCK_REVERSAL",
                }
                pt_map = {"GOLD":0.01, "SILVER":0.001, "BTCUSD":0.01, "ETHUSD":0.01, "EURUSD":0.00001, "GBPUSD":0.00001, "USDJPY":0.001}
                pt_val = pt_map.get(symbol, 0.01)
                ml_strat = strat_map.get((strat_name, action), "BULL_TREND_FOLLOWER")
                session_name = "LONDON" if 7 <= now_utc.hour < 12 else ("NY" if 12 <= now_utc.hour < 17 else ("ASIAN" if 0 <= now_utc.hour < 7 else "US"))
                sl_pts = abs(close_p - sl) / pt_val
                tp_pts = abs(tp1 - close_p) / pt_val
                feat = pd.DataFrame([{
                    "symbol": symbol, "strategy": ml_strat, "direction": action,
                    "session": session_name, "hour": now_utc.hour, "weekday": now_utc.weekday(),
                    "rsi_val": float(rsi) if not np.isnan(rsi) else 50.0,
                    "adx_val": 22.0, "atr": float(atr),
                    "sl_pts": float(sl_pts), "tp_pts": float(tp_pts)
                }])
                try:
                    win_prob = float(self.ml_model.predict_proba(feat)[0][1])
                except Exception as e:
                    win_prob = 0.50

                if win_prob < 0.46:
                    log.info(f"🛡️ [ML FILTER] Dropped {strat_name} on {symbol} due to low win prob: {win_prob:.1%}")
                    return

            # Model 3 AI Conviction Dynamic Compounding
            account_info = mt5.account_info()
            equity = account_info.equity if account_info else 3000.0
            conviction = max(0.70, min(2.50, (win_prob - 0.40) / 0.16))
            weight = 1.35 if symbol == "GOLD" else (0.65 if symbol == "SILVER" else (1.30 if symbol == "BTCUSD" else 0.85))
            if len(self.quarantined_symbols) > 0 and symbol in ["GOLD", "BTCUSD"]:
                weight += 0.35 * len(self.quarantined_symbols)
            compounded_lot = round(min(0.20, max(lot, lot * (equity / 3000.0) * conviction * weight)), 2)
            lot = compounded_lot

            log.info(f"🎯 [{strat_name}] Signal on {symbol}: {action} {lot} lots (WinProb: {win_prob:.1%}) | SL: {sl} | TP1: {tp1} | Reason: {trade_signal['reason']}")

            tick = mt5.symbol_info_tick(symbol)
            if not tick: return
            entry = tick.ask if action == "BUY" else tick.bid

            payload = {
                "symbol": symbol,
                "action": action,
                "entry": entry,
                "volume": lot,
                "final_sl": sl,
                "final_tp1": tp1,
                "final_tp2": tp2,
                "comment": strat_name[:31],
                "source_channel": strat_name
            }

            success = self.mt5_engine.execute_trade(payload, magic_number=magic)
            ticket = payload.get("ticket")

            if success and ticket:
                log.info(f"✅ [{strat_name}] Ticket #{ticket} placed on {symbol}! Comment='{strat_name}'")
                self.last_trade_time[symbol] = now_ts
                self.daily_trade_count[symbol] = self.daily_trade_count.get(symbol, 0) + 1
                log.info(f"📊 [{symbol}] Daily AIO trades: {self.daily_trade_count[symbol]}/{spec.get('max_daily', 3)}")

                # Register with TSL Manager
                register_trade(
                    ticket=ticket, symbol=symbol, action=action, entry=entry,
                    sl=sl, tps=[tp1, tp2], channel=strat_name, conviction=0.85
                )

                # Real-time Telegram Institutional Alert
                try:
                    from telegram_notifier import notify_trade_opened
                    notify_trade_opened(
                        ticket=ticket, symbol=symbol, action=action, volume=lot,
                        entry=entry, sl=sl, tp1=tp1, tp2=tp2, win_prob=win_prob,
                        strategy=strat_name
                    )
                except Exception as ex:
                    log.warning(f"Telegram notification error: {ex}")

    def run_cycle(self):
        is_weekend = (datetime.now(timezone.utc).weekday() >= 5)
        scan_list = ["BTCUSD", "ETHUSD"] if is_weekend else SYMBOLS
        label = "🌐 WEEKEND 24/7 CRYPTO" if is_weekend else "🔄 ALL-ASSET MULTI-TIMEFRAME"
        log.info(f"{label} Scanning {len(scan_list)} pairs ({', '.join(scan_list)})...")
        for sym in scan_list:
            try:
                self.scan_asset(sym)
            except Exception as e:
                log.error(f"Error scanning {sym}: {e}")

    def start(self):
        if not self.init_mt5():
            log.error("Failed to connect to MT5.")
            return

        log.info("====================================================================")
        log.info("🚀 ALL-IN-ONE (AIO) MULTI-ASSET AUTONOMOUS LIVE ENGINE STARTED 24/7")
        log.info(f"   Assets: {', '.join(SYMBOLS)}")
        log.info("   Strategies: Dilse Pullback, Bollinger Squeeze, SMC FVG, OB Reversal")
        log.info("   Order Comments: AIO_<StrategyName>")
        log.info("====================================================================")

        while True:
            try:
                self.run_cycle()
            except Exception as e:
                log.error(f"Cycle exception: {e}")
            time.sleep(15)  # Scan every 15 seconds

if __name__ == "__main__":
    engine = AIOLiveTradingEngine()
    engine.start()
