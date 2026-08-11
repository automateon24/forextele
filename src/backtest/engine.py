import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from src.backtest.cost_model import CostModel
from src.common.messages import SignalMessage

logger = logging.getLogger(__name__)

# ── Trailing Stop Loss (TSL) settings for Gold ─────────────────────────────
_TSL_ACTIVATION_USD  = 5.0   # TSL kicks in once trade profit reaches $5 move in price
_TSL_TRAIL_DIST_USD  = 3.0   # Trail SL $3 below the peak high (for BUY) or above low (for SELL)
# ── Portfolio drawdown cap ─────────────────────────────────────────────────
_MAX_PORTFOLIO_DD_PCT = 0.30  # Stop new trades if portfolio is down >30% from its peak


class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        strategies: List[Any],
        cost_model: CostModel,
        capital: float = 1500.0,
        volume: float = 0.02,
        use_tsl: bool = True,
        max_dd_pct: float = _MAX_PORTFOLIO_DD_PCT,
    ):
        self.df = df
        self.strategies = strategies
        self.cost_model = cost_model
        self.capital = capital
        self.volume = volume
        self.use_tsl = use_tsl
        self.max_dd_pct = max_dd_pct
        self.trades = []

    def run(self):
        logger.info(f"Starting engine over {len(self.df)} bars...")
        max_lookback = max(
            (getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in self.strategies),
            default=50
        )

        # ── Portfolio equity tracking for 30% DD cap ──────────────────────
        running_equity = self.capital
        peak_equity    = self.capital

        for i in range(max_lookback, len(self.df)):
            window = self.df.iloc[i - max_lookback: i + 1]
            current_bar_time = window.iloc[-1]['time']

            # ── 30% portfolio drawdown cap ─────────────────────────────────
            if peak_equity > 0:
                current_dd = (peak_equity - running_equity) / peak_equity
                if current_dd >= self.max_dd_pct:
                    continue  # Portfolio in 30% DD — no new trades until it recovers

            for strategy in self.strategies:
                signal = strategy.analyze(window)
                if not signal:
                    continue

                trade = self._simulate_execution(signal, i)
                if trade is None:
                    continue

                trade['strategy_id'] = strategy.strategy_id
                trade['time'] = current_bar_time
                self.trades.append(trade)

                # Update equity curve
                running_equity += trade['pnl']
                if running_equity > peak_equity:
                    peak_equity = running_equity

        logger.info(f"Engine completed. {len(self.trades)} trades simulated.")
        return pd.DataFrame(self.trades)

    def _simulate_execution(self, signal: SignalMessage, current_idx: int) -> Optional[Dict[str, Any]]:
        """
        Simulates forward trade execution with Trailing Stop Loss (TSL).

        TSL Logic (Gold-optimised):
          - Fixed SL protects downside from the start.
          - Once price moves >= _TSL_ACTIVATION_USD in our favour, TSL activates.
          - TSL trails _TSL_TRAIL_DIST_USD behind the best price achieved.
          - Fixed TP is only used before TSL activates; after that, TSL exits the trade.
        """
        entry_price   = self.cost_model.apply_entry_cost(signal.suggested_entry_price, signal.side)
        volume        = self.volume
        outcome       = "OPEN"
        exit_price    = 0.0
        exit_time     = None
        exit_bar_idx  = len(self.df) - 1

        # TSL state
        tsl_active    = False
        best_price    = entry_price          # tracks high-water (BUY) or low-water (SELL)
        trailing_sl   = signal.suggested_sl_price   # starts as the strategy's fixed SL

        for j in range(current_idx + 1, len(self.df)):
            future_bar = self.df.iloc[j]

            if signal.side == "BUY":
                bar_high = future_bar['high']
                bar_low  = self.cost_model.apply_exit_cost(future_bar['low'], signal.side)

                # Advance best price
                if bar_high > best_price:
                    best_price = bar_high

                # Activate TSL when profit target hit
                if self.use_tsl and not tsl_active:
                    if (best_price - entry_price) >= _TSL_ACTIVATION_USD:
                        tsl_active = True
                        logger.debug(f"TSL activated at best_price={best_price:.2f}")

                # Ratchet up the trailing SL
                if tsl_active:
                    new_tsl = best_price - _TSL_TRAIL_DIST_USD
                    if new_tsl > trailing_sl:
                        trailing_sl = new_tsl

                # Check if current bar low hits the active SL/TSL
                if bar_low <= trailing_sl:
                    outcome    = "WIN" if trailing_sl > entry_price else "LOSS"
                    exit_price = trailing_sl
                    exit_time  = future_bar['time']
                    exit_bar_idx = j
                    break

                # Fixed TP (only before TSL takes over)
                if not tsl_active:
                    exit_tp = self.cost_model.apply_exit_cost(bar_high, signal.side)
                    if exit_tp >= signal.suggested_tp_price:
                        outcome    = "WIN"
                        exit_price = signal.suggested_tp_price
                        exit_time  = future_bar['time']
                        exit_bar_idx = j
                        break

            else:  # SELL
                bar_low  = future_bar['low']
                bar_high = self.cost_model.apply_exit_cost(future_bar['high'], signal.side)

                # Advance best price (lowest low for SELL)
                if bar_low < best_price:
                    best_price = bar_low

                # Activate TSL
                if self.use_tsl and not tsl_active:
                    if (entry_price - best_price) >= _TSL_ACTIVATION_USD:
                        tsl_active = True

                # Ratchet down the trailing SL
                if tsl_active:
                    new_tsl = best_price + _TSL_TRAIL_DIST_USD
                    if new_tsl < trailing_sl:
                        trailing_sl = new_tsl

                # Check if current bar high hits the active SL/TSL
                if bar_high >= trailing_sl:
                    outcome    = "WIN" if trailing_sl < entry_price else "LOSS"
                    exit_price = trailing_sl
                    exit_time  = future_bar['time']
                    exit_bar_idx = j
                    break

                # Fixed TP (only before TSL takes over)
                if not tsl_active:
                    exit_tp = self.cost_model.apply_exit_cost(bar_low, signal.side)
                    if exit_tp <= signal.suggested_tp_price:
                        outcome    = "WIN"
                        exit_price = signal.suggested_tp_price
                        exit_time  = future_bar['time']
                        exit_bar_idx = j
                        break

        # End-of-data exit
        if outcome == "OPEN":
            last_bar   = self.df.iloc[-1]
            exit_time  = last_bar['time']
            exit_price = self.cost_model.apply_exit_cost(last_bar['close'], signal.side)

        # ── PnL calculation ────────────────────────────────────────────────
        from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl
        spec          = get_symbol_spec(signal.symbol)
        gross_pnl     = calculate_pnl(signal.symbol, signal.side, entry_price, exit_price, volume, spec)
        net_pnl       = gross_pnl - self.cost_model.get_commission_cost(volume)

        # Sanity check
        if abs(net_pnl) > (self.capital * 1.0):
            logger.warning(f"Implausible PnL ${net_pnl:.2f} on {volume} lots of {signal.symbol}.")
            assert abs(net_pnl) <= (self.capital * 1.0), f"Implausible PnL: ${net_pnl:.2f}"

        return {
            "symbol":       signal.symbol,
            "side":         signal.side,
            "entry_price":  entry_price,
            "exit_price":   exit_price,
            "exit_time":    exit_time,
            "exit_bar_idx": exit_bar_idx,
            "tsl_active":   tsl_active,
            "pnl":          net_pnl,
            "outcome":      outcome,
        }
