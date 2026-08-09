import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategy.london_breakout import LondonBreakoutStrategy
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.portfolio.manager import init_mt5

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

def run_batch_backtest(symbol="EURUSD", days=90, timeframe=mt5.TIMEFRAME_H1):
    if not init_mt5():
        print("Failed to initialize MT5")
        return
        
    print(f"Fetching {days} days of {symbol} data...")
    utc_from = datetime.now() - timedelta(days=days)
    utc_to = datetime.now()
    
    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print("No data retrieved.")
        mt5.shutdown()
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    strategies = [
        LondonBreakoutStrategy(symbol=symbol),
        MeanReversionStrategy(symbol=symbol),
        TrendMomentumStrategy(symbol=symbol),
        SMCOrderBlockStrategy(symbol=symbol)
    ]
    
    trades = []
    
    print(f"Running simulation over {len(df)} candles...")
    
    # We need a max lookback to prime the pump
    max_lookback = max(s.min_bars for s in strategies)
    
    for i in range(max_lookback, len(df)):
        window = df.iloc[i - max_lookback : i+1] # Pass data up to current index
        
        for strategy in strategies:
            signal = strategy.analyze(window)
            if signal:
                # Simulate execution
                # We assume fill at suggested entry price, but add a 1-pip spread cost
                spread = 0.00010
                fill_price = signal.suggested_entry_price + (spread if signal.side == "BUY" else -spread)
                
                # Assume a fixed outcome for ranking purposes based on hit/miss of SL vs TP in future candles
                # (A true backtester would track the position forward, but for expectancy ranking, 
                # we can approximate or track forward simply).
                # Here we'll do a simple forward simulation for the next 20 bars to see what hits first: SL or TP
                outcome = "OPEN"
                pnl = 0.0
                
                for j in range(i+1, min(i+20, len(df))):
                    future_bar = df.iloc[j]
                    if signal.side == "BUY":
                        if future_bar['low'] <= signal.suggested_sl_price:
                            outcome = "LOSS"
                            pnl = signal.suggested_sl_price - fill_price
                            break
                        elif future_bar['high'] >= signal.suggested_tp_price:
                            outcome = "WIN"
                            pnl = signal.suggested_tp_price - fill_price
                            break
                    else:
                        if future_bar['high'] >= signal.suggested_sl_price:
                            outcome = "LOSS"
                            pnl = fill_price - signal.suggested_sl_price
                            break
                        elif future_bar['low'] <= signal.suggested_tp_price:
                            outcome = "WIN"
                            pnl = fill_price - signal.suggested_tp_price
                            break
                
                if outcome == "OPEN":
                    # Time exit
                    last_price = df.iloc[min(i+19, len(df)-1)]['close']
                    pnl = (last_price - fill_price) if signal.side == "BUY" else (fill_price - last_price)
                
                trades.append({
                    "time": window.iloc[-1]['time'],
                    "strategy_id": strategy.strategy_id,
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "pnl": pnl * 100000 # Convert to points/pips roughly
                })

    mt5.shutdown()
    
    if trades:
        results_df = pd.DataFrame(trades)
        os.makedirs(LOGS_DIR, exist_ok=True)
        out_path = os.path.join(LOGS_DIR, "backtest_results.csv")
        results_df.to_csv(out_path, index=False)
        print(f"Backtest complete. {len(trades)} simulated trades logged to {out_path}.")
    else:
        print("No trades generated.")

if __name__ == "__main__":
    run_batch_backtest()
