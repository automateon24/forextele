import pandas as pd
import logging
from typing import List, Dict, Any
from src.backtest.cost_model import CostModel
from src.common.messages import SignalMessage

logger = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        strategies: List[Any],
        cost_model: CostModel,
        capital: float = 1500.0,
        volume: float = 0.02,
        max_open_positions: int = 2,
        max_per_symbol: int = 1,
    ):
        self.df = df
        self.strategies = strategies
        self.cost_model = cost_model
        self.capital = capital
        self.volume = volume
        self.max_open_positions = max_open_positions
        self.max_per_symbol = max_per_symbol
        self.trades = []

    def run(self):
        logger.info(f"Starting engine over {len(self.df)} bars...")
        max_lookback = max(
            (getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in self.strategies),
            default=50
        )

        # Track open positions: list of {symbol, exit_bar_idx}
        open_positions: List[Dict] = []

        for i in range(max_lookback, len(self.df)):
            window = self.df.iloc[i - max_lookback: i + 1]
            current_bar = window.iloc[-1]
            current_bar_time = current_bar['time']

            # --- Clean up expired open positions ---
            open_positions = [p for p in open_positions if p['exit_bar_idx'] > i]

            # --- Count open positions per symbol ---
            open_count = len(open_positions)
            symbol_counts: Dict[str, int] = {}
            for p in open_positions:
                symbol_counts[p['symbol']] = symbol_counts.get(p['symbol'], 0) + 1

            for strategy in self.strategies:
                # --- Position limit checks ---
                if open_count >= self.max_open_positions:
                    break  # No more new positions allowed right now

                sig_symbol = getattr(strategy, 'symbol', 'GOLD')
                if symbol_counts.get(sig_symbol, 0) >= self.max_per_symbol:
                    continue  # Already have a position on this symbol

                signal = strategy.analyze(window)
                if not signal:
                    continue

                trade = self._simulate_execution(signal, i)
                if trade is None:
                    continue

                trade['strategy_id'] = strategy.strategy_id
                trade['time'] = current_bar_time
                self.trades.append(trade)

                # Register open position
                open_positions.append({
                    'symbol': sig_symbol,
                    'exit_bar_idx': trade.get('exit_bar_idx', i + 1),
                })
                open_count += 1
                symbol_counts[sig_symbol] = symbol_counts.get(sig_symbol, 0) + 1

        logger.info(f"Engine completed. {len(self.trades)} trades simulated.")
        return pd.DataFrame(self.trades)

    def _simulate_execution(self, signal: SignalMessage, current_idx: int) -> Dict[str, Any]:
        """
        Simulates the forward path of a trade until it hits SL or TP, accounting for costs.
        Returns the trade dict including exit_bar_idx for position tracking.
        """
        entry_price = self.cost_model.apply_entry_cost(signal.suggested_entry_price, signal.side)

        volume = self.volume
        outcome = "OPEN"
        exit_price = 0.0
        exit_time = None
        exit_bar_idx = len(self.df) - 1

        for j in range(current_idx + 1, len(self.df)):
            future_bar = self.df.iloc[j]

            if signal.side == "BUY":
                exit_sl = self.cost_model.apply_exit_cost(future_bar['low'], signal.side)
                exit_tp = self.cost_model.apply_exit_cost(future_bar['high'], signal.side)

                if exit_sl <= signal.suggested_sl_price:
                    outcome = "LOSS"
                    exit_price = signal.suggested_sl_price
                    exit_time = future_bar['time']
                    exit_bar_idx = j
                    break
                elif exit_tp >= signal.suggested_tp_price:
                    outcome = "WIN"
                    exit_price = signal.suggested_tp_price
                    exit_time = future_bar['time']
                    exit_bar_idx = j
                    break
            else:
                exit_sl = self.cost_model.apply_exit_cost(future_bar['high'], signal.side)
                exit_tp = self.cost_model.apply_exit_cost(future_bar['low'], signal.side)

                if exit_sl >= signal.suggested_sl_price:
                    outcome = "LOSS"
                    exit_price = signal.suggested_sl_price
                    exit_time = future_bar['time']
                    exit_bar_idx = j
                    break
                elif exit_tp <= signal.suggested_tp_price:
                    outcome = "WIN"
                    exit_price = signal.suggested_tp_price
                    exit_time = future_bar['time']
                    exit_bar_idx = j
                    break

        if outcome == "OPEN":
            last_bar = self.df.iloc[-1]
            exit_time = last_bar['time']
            exit_price = self.cost_model.apply_exit_cost(last_bar['close'], signal.side)

        # PnL using centralized symbol specs
        from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl
        spec = get_symbol_spec(signal.symbol)

        gross_pnl_money = calculate_pnl(signal.symbol, signal.side, entry_price, exit_price, volume, spec)
        net_pnl_money = gross_pnl_money - self.cost_model.get_commission_cost(volume)

        # Sanity: single trade cannot exceed 100% of capital
        if abs(net_pnl_money) > (self.capital * 1.0):
            logger.warning(f"Implausible single trade PnL: ${net_pnl_money:.2f} on {volume} lots of {signal.symbol}.")
            assert abs(net_pnl_money) <= (self.capital * 1.0), f"Implausible PnL: ${net_pnl_money:.2f}"

        return {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_time": exit_time,
            "exit_bar_idx": exit_bar_idx,
            "pnl": net_pnl_money,
            "outcome": outcome,
        }

