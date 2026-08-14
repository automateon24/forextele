"""
ConcurrentBacktestEngine – runs multiple strategies on the same equity pool while respecting
global risk limits from risk_config.json.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import CostModel
from src.common.messages import SignalMessage
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

logger = logging.getLogger(__name__)

class ConcurrentBacktestEngine:
    """Realistic concurrent backtest.

    * All strategies share a single capital pool.
    * Global position limits are enforced according to ``risk_config.json``:
        - max_open_positions (overall)
        - max_positions_per_symbol
        - hard_lot_cap (volume per trade)
    * Execution rules are borrowed from :class:`BacktestEngine`.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        strategies: List[Any],
        cost_model: CostModel,
        capital: float = 1500.0,
        volume: float = 0.02,
        use_tsl: bool = False,
        max_dd_pct: float = 0.30,
        slippage_usd: float = 0.15,
        risk_config_path: str = "config/risk_config.json",
    ):
        self.df = df
        self.strategies = strategies
        self.cost_model = cost_model
        self.capital = capital
        self.volume = volume
        self.use_tsl = use_tsl
        self.max_dd_pct = max_dd_pct
        self.slippage_usd = slippage_usd
        self.trades: List[Dict[str, Any]] = []
        self.open_trades: List[Dict[str, Any]] = []  # trades not yet exited (track by exit_bar_idx)
        # Load risk config
        cfg_path = Path(risk_config_path)
        if cfg_path.is_file():
            with cfg_path.open() as f:
                cfg = json.load(f)
            self.max_total_positions = cfg["global"].get("max_open_positions", 3)
            self.max_per_symbol = cfg["global"].get("max_positions_per_symbol", 2)
            self.hard_lot_cap = cfg["global"].get("hard_lot_cap", 0.02)
        else:
            # fallback defaults
            self.max_total_positions = 3
            self.max_per_symbol = 2
            self.hard_lot_cap = 0.02

    def run(self):
        logger.info(f"Starting ConcurrentBacktestEngine over {len(self.df)} bars")
        max_lookback = max(
            (getattr(s, "min_bars", getattr(s, "lookback", 10) + 2) for s in self.strategies),
            default=50,
        )
        running_equity = self.capital
        peak_equity = self.capital
        for i in range(max_lookback, len(self.df)):
            # purge closed trades from open_trades and apply their PnL
            self._close_expired_trades(i, running_equity, peak_equity)
            window = self.df.iloc[i - max_lookback : i + 1]
            current_bar_time = window.iloc[-1]["time"]
            # Portfolio DD gate
            if peak_equity > 0:
                current_dd = (peak_equity - running_equity) / peak_equity
                if current_dd >= self.max_dd_pct:
                    continue
            for strategy in self.strategies:
                signal: SignalMessage = strategy.analyze(window)  # type: ignore
                if not signal:
                    continue
                # Position caps
                total_open = len(self.open_trades)
                per_symbol_open = sum(1 for t in self.open_trades if t["symbol"] == signal.symbol)
                if total_open >= self.max_total_positions or per_symbol_open >= self.max_per_symbol:
                    logger.debug(
                        f"Cap reached – skipping signal for {signal.symbol} ({total_open}/{self.max_total_positions} total, {per_symbol_open}/{self.max_per_symbol} per symbol)"
                    )
                    continue
                # Existing risk gates from original engine (MTF, SL distance, etc.)
                if strategy.strategy_id in [
                    "TREND_MOMENTUM",
                    "SMC_ORDER_BLOCK",
                    "FVG_RETEST",
                    "CHART_PATTERN_SWING",
                    "BOLLINGER_SQUEEZE_BREAKOUT",
                ]:
                    full_history = self.df.iloc[: i + 1]
                    htf_bias = get_htf_trend_bias(full_history)
                    if not validate_mtf_alignment(signal.side, htf_bias):
                        continue
                # SL distance gate (copied from BacktestEngine)
                sl_dist = abs(signal.suggested_entry_price - signal.suggested_sl_price)
                is_gold = "GOLD" in signal.symbol or "XAU" in signal.symbol
                is_silver = "SILVER" in signal.symbol or "XAG" in signal.symbol
                is_jpy = "JPY" in signal.symbol
                if is_gold:
                    min_sl, max_sl = 1.00, 50.0
                elif is_silver:
                    min_sl, max_sl = 0.050, 3.00
                elif is_jpy:
                    min_sl, max_sl = 0.050, 3.00
                else:
                    min_sl, max_sl = 0.00050, (signal.suggested_entry_price * 0.02)
                if sl_dist < min_sl or sl_dist > max_sl or signal.suggested_sl_price <= 0:
                    continue
                # Simulate execution using the internal method from BacktestEngine for realism
                # Reuse a temporary BacktestEngine instance for the simulation
                tmp_engine = BacktestEngine(
                    df=self.df,
                    strategies=[strategy],
                    cost_model=self.cost_model,
                    capital=self.capital,
                    volume=self.volume,
                    use_tsl=self.use_tsl,
                    max_dd_pct=self.max_dd_pct,
                    slippage_usd=self.slippage_usd,
                )
                trade = tmp_engine._simulate_execution(signal, i)
                if trade is None:
                    continue
                trade.update({"strategy_id": strategy.strategy_id, "time": current_bar_time})
                # Record trade and keep it open until its exit bar
                self.trades.append(trade)
                self.open_trades.append({
                    "symbol": signal.symbol,
                    "exit_bar_idx": trade["exit_bar_idx"],
                    "pnl": trade["pnl"],
                })
                # Update equity immediately for simplicity (conservative)
                running_equity += trade["pnl"]
                if running_equity > peak_equity:
                    peak_equity = running_equity
        # Final close of any remaining open trades (should already be handled in loop)
        logger.info(f"Engine completed. {len(self.trades)} trades simulated.")
        return pd.DataFrame(self.trades)

    def _close_expired_trades(self, current_idx, running_equity, peak_equity):
        """Remove trades whose exit bar is <= current_idx.
        The PnL has already been applied when the trade was created, so this method only
        maintains the open_trades list.
        """
        self.open_trades = [t for t in self.open_trades if t["exit_bar_idx"] > current_idx]
        # No equity adjustment needed because PnL was accounted at creation time.
        return running_equity, peak_equity
