import zmq
import json
import logging
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime
from src.common.messages import SignalMessage, MessageHeader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [STRATEGY] - %(levelname)s - %(message)s')

class AlphaEngine:
    def __init__(self):
        self.active_strategies = [
            "LONDON_BREAKOUT",
            "ASIAN_RANGE_SCALP",
            "MEAN_REVERSION",
            "RSI_REVERSAL",
            "PURE_SMC_LIQUIDITY_ORDER_BLOCK_RETEST",
            "SMC_SWEEP_RETEST"
        ]

    def evaluate(self, symbol: str, history: list) -> list[SignalMessage]:
        if not history or len(history) < 20:
            return []

        df = pd.DataFrame(history)
        # Ensure correct types
        for col in ['open', 'high', 'low', 'close', 'tick_volume']:
            df[col] = pd.to_numeric(df[col])
            
        pr = df['close'].iloc[-1]
        
        # Calculate Indicators
        try:
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['ema9'] = ta.ema(df['close'], length=9)
            df['ema21'] = ta.ema(df['close'], length=21)
        except Exception as e:
            logging.error(f"Error calculating indicators: {e}")
            return []

        now_utc = datetime.utcnow()
        utc_h = now_utc.hour
        
        is_london = 7 <= utc_h <= 15
        is_asian = 22 <= utc_h or utc_h <= 6
        
        signals = []

        # 1. LONDON_BREAKOUT
        if "LONDON_BREAKOUT" in self.active_strategies and 7 <= utc_h <= 10:
            ah = df['high'].iloc[-9:-1].max()
            al = df['low'].iloc[-9:-1].min()
            rng = ah - al
            if pr > ah + rng * 0.05:
                signals.append(self._create_signal(symbol, "BUY", "LONDON_BREAKOUT", pr, al, pr + (pr - al)*2))
            elif pr < al - rng * 0.05:
                signals.append(self._create_signal(symbol, "SELL", "LONDON_BREAKOUT", pr, ah, pr - (ah - pr)*2))

        # 2. ASIAN_RANGE_SCALP
        if "ASIAN_RANGE_SCALP" in self.active_strategies and is_asian:
            ah = df['high'].iloc[-4:].max()
            al = df['low'].iloc[-4:].min()
            mid = (ah + al) / 2
            if pr < mid:
                signals.append(self._create_signal(symbol, "BUY", "ASIAN_RANGE_SCALP", pr, al, mid))
            elif pr > mid:
                signals.append(self._create_signal(symbol, "SELL", "ASIAN_RANGE_SCALP", pr, ah, mid))

        # 3. MEAN_REVERSION & RSI_REVERSAL
        if "MEAN_REVERSION" in self.active_strategies or "RSI_REVERSAL" in self.active_strategies:
            r = df['rsi'].iloc[-1]
            if pd.notna(r):
                if r < 30:
                    sl = df['low'].min()
                    signals.append(self._create_signal(symbol, "BUY", "MEAN_REVERSION", pr, sl, pr + (pr-sl)*2))
                elif r > 70:
                    sl = df['high'].max()
                    signals.append(self._create_signal(symbol, "SELL", "MEAN_REVERSION", pr, sl, pr - (sl-pr)*2))
                    
        # 4. PURE_SMC_LIQUIDITY_ORDER_BLOCK_RETEST
        if "PURE_SMC_LIQUIDITY_ORDER_BLOCK_RETEST" in self.active_strategies or "SMC_SWEEP_RETEST" in self.active_strategies:
            asian_high = df['high'].iloc[-30:-10].max()
            asian_low = df['low'].iloc[-30:-10].min()
            
            # Sweep logic: Did we break asian high then close below it? (Bearish SMC)
            if df['high'].iloc[-2] > asian_high and df['close'].iloc[-1] < asian_high:
                signals.append(self._create_signal(symbol, "SELL", "SMC_SWEEP_RETEST", pr, df['high'].iloc[-2], pr - (df['high'].iloc[-2]-pr)*3))
            elif df['low'].iloc[-2] < asian_low and df['close'].iloc[-1] > asian_low:
                signals.append(self._create_signal(symbol, "BUY", "SMC_SWEEP_RETEST", pr, df['low'].iloc[-2], pr + (pr-df['low'].iloc[-2])*3))

        return signals

    def _create_signal(self, symbol, side, strat_id, entry, sl, tp):
        return SignalMessage(
            header=MessageHeader(message_type="Signal", source_component="svc_strategy_engine"),
            symbol=symbol,
            side=side,
            strategy_id=strat_id,
            suggested_entry_price=entry,
            suggested_sl_price=sl,
            suggested_tp_price=tp,
            metadata={"suggested_volume": 0.01} # Strict micro-lot default
        )

def main():
    context = zmq.Context()
    
    # Subscribe to Market Data
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect("tcp://127.0.0.1:5555")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "MARKET_DATA")
    
    # Publish Signals
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://127.0.0.1:5556")
    
    engine = AlphaEngine()
    logging.info("Strategy Engine running, subscribed to Market Data, publishing Signals")

    while True:
        try:
            message_string = sub_socket.recv_string()
            _, json_data = message_string.split(" ", 1)
            data = json.loads(json_data)
            
            if data.get("event") == "BarClosed":
                symbol = data["symbol"]
                history = data.get("history", [])
                
                signals = engine.evaluate(symbol, history)
                
                for sig in signals:
                    pub_socket.send_string(f"SIGNAL {sig.model_dump_json()}")
                    logging.info(f"Emitted {sig.side} Signal for {symbol} via {sig.strategy_id}")
                    
        except KeyboardInterrupt:
            logging.info("Shutting down Strategy Engine.")
            break
        except Exception as e:
            logging.error(f"Error in Strategy Engine loop: {e}")

if __name__ == "__main__":
    main()
