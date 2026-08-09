import pandas as pd
import logging
from typing import List, Dict, Any
from src.backtest.cost_model import CostModel
from src.common.messages import SignalMessage

logger = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self, df: pd.DataFrame, strategies: List[Any], cost_model: CostModel, capital: float = 1500.0):
        self.df = df
        self.strategies = strategies
        self.cost_model = cost_model
        self.capital = capital
        self.trades = []

    def run(self):
        logger.info(f"Starting engine over {len(self.df)} bars...")
        max_lookback = max((getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in self.strategies), default=50)
        
        for i in range(max_lookback, len(self.df)):
            window = self.df.iloc[i - max_lookback : i+1]
            current_bar_time = window.iloc[-1]['time']
            
            for strategy in self.strategies:
                signal = strategy.analyze(window)
                if signal:
                    trade = self._simulate_execution(signal, i)
                    if trade:
                        trade['strategy_id'] = strategy.strategy_id
                        trade['time'] = current_bar_time
                        self.trades.append(trade)
                        
        logger.info(f"Engine completed. {len(self.trades)} trades simulated.")
        
        # Sanity Check 2: Total Return Limit
        total_pnl = sum(t['pnl'] for t in self.trades)
        if total_pnl > (self.capital * 5.0): # 500% return
            raise ValueError(f"PnL scale implausible. Total return > 500% (${total_pnl:.2f}). Failing backtest.")
            
        return pd.DataFrame(self.trades)

    def _simulate_execution(self, signal: SignalMessage, current_idx: int) -> Dict[str, Any]:
        """
        Simulates the forward path of a trade until it hits SL or TP, accounting for costs.
        """
        entry_price = self.cost_model.apply_entry_cost(signal.suggested_entry_price, signal.side)
        
        # Simplified risk sizing (assume 0.01 standard micro lot)
        volume = 0.01
        point_value = 100000 # Roughly 1 standard lot = 100,000 units. For 0.01, it's 1000 units.
        
        outcome = "OPEN"
        exit_price = 0.0
        exit_time = None
        
        for j in range(current_idx + 1, len(self.df)):
            future_bar = self.df.iloc[j]
            
            if signal.side == "BUY":
                exit_sl = self.cost_model.apply_exit_cost(future_bar['low'], signal.side)
                exit_tp = self.cost_model.apply_exit_cost(future_bar['high'], signal.side)
                
                if exit_sl <= signal.suggested_sl_price:
                    outcome = "LOSS"
                    exit_price = signal.suggested_sl_price
                    exit_time = future_bar['time']
                    break
                elif exit_tp >= signal.suggested_tp_price:
                    outcome = "WIN"
                    exit_price = signal.suggested_tp_price
                    exit_time = future_bar['time']
                    break
            else:
                exit_sl = self.cost_model.apply_exit_cost(future_bar['high'], signal.side)
                exit_tp = self.cost_model.apply_exit_cost(future_bar['low'], signal.side)
                
                if exit_sl >= signal.suggested_sl_price:
                    outcome = "LOSS"
                    exit_price = signal.suggested_sl_price
                    exit_time = future_bar['time']
                    break
                elif exit_tp <= signal.suggested_tp_price:
                    outcome = "WIN"
                    exit_price = signal.suggested_tp_price
                    exit_time = future_bar['time']
                    break
                    
        if outcome == "OPEN":
            # Exit at end of data
            last_bar = self.df.iloc[-1]
            exit_time = last_bar['time']
            exit_price = self.cost_model.apply_exit_cost(last_bar['close'], signal.side)
            
        # Calculate PnL using centralized symbol specs
        from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl
        spec = get_symbol_spec(signal.symbol)
        
        gross_pnl_money = calculate_pnl(signal.symbol, signal.side, entry_price, exit_price, volume, spec)
        net_pnl_money = gross_pnl_money - self.cost_model.get_commission_cost(volume)
        
        # Sanity Check 1: Single Trade Limit
        if abs(net_pnl_money) > (self.capital * 1.0):
            logger.warning(f"Implausible single trade PnL detected: ${net_pnl_money:.2f} on {volume} lots of {signal.symbol}. Check specs!")
            # Hard assert to fail fast as requested by Grok
            assert abs(net_pnl_money) <= (self.capital * 1.0), f"Implausible PnL: ${net_pnl_money:.2f}"
        
        return {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_time": exit_time,
            "pnl": net_pnl_money,
            "outcome": outcome
        }
