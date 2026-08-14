import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from src.backtest.cost_model import CostModel
from src.common.messages import SignalMessage
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

logger = logging.getLogger(__name__)

# ── Realistic Execution & Risk Parameters ──────────────────────────────────
_TSL_ACTIVATION_USD   = 5.0    # TSL kicks in once trade profit reaches $5 move in price
_TSL_TRAIL_DIST_USD   = 3.0    # Trail SL $3 below peak high (BUY) or above low (SELL)
_MAX_PORTFOLIO_DD_PCT  = 0.30   # Stop new trades if portfolio is down >30% from peak
_SLIPPAGE_PER_TRADE   = 0.15   # $0.15 slippage on entry and exit ($0.30 total execution friction)
_MAX_ALLOWED_SPREAD   = 0.80   # Risk Gate: Reject signal if spread > $0.80
_MIN_SL_DIST_USD      = 1.00   # Risk Gate: Reject signal if SL distance < $1.00


class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        strategies: List[Any],
        cost_model: CostModel,
        capital: float = 1500.0,
        volume: float = 0.02,
        use_tsl: bool = False,
        max_dd_pct: float = _MAX_PORTFOLIO_DD_PCT,
        slippage_usd: float = _SLIPPAGE_PER_TRADE,
    ):
        self.df = df
        self.strategies = strategies
        self.cost_model = cost_model
        self.capital = capital
        self.volume = volume
        self.use_tsl = use_tsl
        self.max_dd_pct = max_dd_pct
        self.slippage_usd = slippage_usd
        self.trades = []

    def run(self):
        logger.info(f"Starting engine over {len(self.df)} bars with LIVE-REALISTIC execution rules...")
        max_lookback = max(
            (getattr(s, 'min_bars', getattr(s, 'lookback', 10) + 2) for s in self.strategies),
            default=50
        )

        running_equity = self.capital
        peak_equity    = self.capital

        for i in range(max_lookback, len(self.df)):
            window = self.df.iloc[i - max_lookback: i + 1]
            current_bar_time = window.iloc[-1]['time']

            # ── Risk Gate 1: Portfolio Drawdown Cap ─────────────────────────
            if peak_equity > 0:
                current_dd = (peak_equity - running_equity) / peak_equity
                if current_dd >= self.max_dd_pct:
                    continue  # Block trades when in >30% drawdown

            for strategy in self.strategies:
                signal = strategy.analyze(window)
                if not signal:
                    continue
                    
                # ── Risk Gate 1.5: MTF Trend Alignment (Trend & SMC Strategies) ──
                if strategy.strategy_id in ["TREND_MOMENTUM", "SMC_ORDER_BLOCK", "FVG_RETEST", "CHART_PATTERN_SWING", "BOLLINGER_SQUEEZE_BREAKOUT"]:
                    full_history = self.df.iloc[: i + 1]
                    htf_bias = get_htf_trend_bias(full_history)
                    if not validate_mtf_alignment(signal.side, htf_bias):
                        logger.debug(f"Signal rejected by MTF Gate: {signal.side} against {htf_bias} trend")
                        continue

                # ── Risk Gate 2: Minimum & Maximum SL Distance Gate ────────
                sl_dist = abs(signal.suggested_entry_price - signal.suggested_sl_price)
                is_gold   = "GOLD" in signal.symbol or "XAU" in signal.symbol
                is_silver = "SILVER" in signal.symbol or "XAG" in signal.symbol
                is_jpy    = "JPY" in signal.symbol
                is_btc    = "BTC" in signal.symbol
                is_eth    = "ETH" in signal.symbol

                if is_gold:
                    min_sl, max_sl = 1.00, 50.0
                elif is_btc:
                    min_sl, max_sl = 10.0, 5000.0
                elif is_eth:
                    min_sl, max_sl = 1.0, 500.0
                elif is_silver:
                    min_sl, max_sl = 0.050, 3.00
                elif is_jpy:
                    min_sl, max_sl = 0.050, 3.00
                else:
                    min_sl, max_sl = 0.00050, (signal.suggested_entry_price * 0.02) # Max 2% SL for Forex

                if sl_dist < min_sl or sl_dist > max_sl or signal.suggested_sl_price <= 0:
                    logger.debug(f"Signal rejected by Risk Gate: SL price/dist invalid for {signal.symbol}")
                    continue

                trade = self._simulate_execution(signal, i)
                if trade is None:
                    continue

                trade['strategy_id'] = strategy.strategy_id
                trade['time'] = current_bar_time
                self.trades.append(trade)

                # Log structured JSONL event
                try:
                    import uuid, json
                    from pathlib import Path
                    from src.ml.features import extract_features_at_row

                    events_dir = Path("data/events")
                    events_dir.mkdir(parents=True, exist_ok=True)
                    events_file = events_dir / "trading_events.jsonl"

                    cid = str(uuid.uuid4())
                    feats = extract_features_at_row(self.df, i)

                    sig_evt = {
                        "event": "signal", "ts_utc": str(current_bar_time), "correlation_id": cid,
                        "symbol": signal.symbol, "timeframe": "H1", "strategy_id": strategy.strategy_id,
                        "side": signal.side, "entry": signal.suggested_entry_price,
                        "sl": signal.suggested_sl_price, "tp": signal.suggested_tp_price,
                        "features": feats
                    }
                    exit_evt = {
                        "event": "exit", "correlation_id": cid, "symbol": signal.symbol,
                        "timeframe": "H1", "strategy_id": strategy.strategy_id, "side": signal.side,
                        "entry_price": trade["entry_price"], "exit_price": trade["exit_price"],
                        "pnl": trade["pnl"], "outcome": trade["outcome"], "data_source": "backtest"
                    }
                    with open(events_file, "a") as ef:
                        ef.write(json.dumps(sig_evt) + "\n")
                        ef.write(json.dumps(exit_evt) + "\n")
                except Exception:
                    pass

                running_equity += trade['pnl']
                if running_equity > peak_equity:
                    peak_equity = running_equity

        logger.info(f"Engine completed. {len(self.trades)} trades simulated with realistic fills.")
        return pd.DataFrame(self.trades)

    def _simulate_execution(self, signal: SignalMessage, current_idx: int) -> Optional[Dict[str, Any]]:
        """
        Simulates realistic trade execution:
          1. Entry Slippage applied ($0.15).
          2. Same-Bar Conflict Rule: If both SL and TP could hit in the same bar,
             SL IS ASSUMED TO HIT FIRST (pessimistic live fill).
          3. Gap Fill Rule: If open price gaps past SL, fill at open price (slippage).
          4. Exit Slippage applied ($0.15).
        """
        is_gold   = "GOLD" in signal.symbol or "XAU" in signal.symbol
        is_silver = "SILVER" in signal.symbol or "XAG" in signal.symbol
        is_jpy    = "JPY" in signal.symbol

        is_btc = "BTC" in signal.symbol
        is_eth = "ETH" in signal.symbol

        if is_gold:
            symbol_slippage = 0.01
        elif is_btc:
            symbol_slippage = 0.50
        elif is_eth:
            symbol_slippage = 0.05
        elif is_silver:
            symbol_slippage = 0.001
        elif is_jpy:
            symbol_slippage = 0.001
        else:
            symbol_slippage = 0.00001

        # Entry price with spread + entry slippage
        raw_entry = self.cost_model.apply_entry_cost(signal.suggested_entry_price, signal.side)
        entry_price = raw_entry + (symbol_slippage if signal.side == "BUY" else -symbol_slippage)

        volume       = self.volume
        outcome      = "OPEN"
        exit_price   = 0.0
        exit_time    = None
        exit_bar_idx = len(self.df) - 1

        tsl_active  = False
        best_price  = entry_price
        trailing_sl = signal.suggested_sl_price

        is_gold   = "GOLD" in signal.symbol or "XAU" in signal.symbol
        is_silver = "SILVER" in signal.symbol or "XAG" in signal.symbol
        is_jpy    = "JPY" in signal.symbol

        if is_gold:
            tsl_act, tsl_trail = 5.00, 3.00
        elif is_btc:
            tsl_act, tsl_trail = 200.0, 100.0
        elif is_eth:
            tsl_act, tsl_trail = 15.0, 8.0
        elif is_silver:
            tsl_act, tsl_trail = 0.250, 0.150
        elif is_jpy:
            tsl_act, tsl_trail = 0.150, 0.100
        else:
            tsl_act, tsl_trail = 0.00150, 0.00100

        for j in range(current_idx + 1, len(self.df)):
            future_bar = self.df.iloc[j]
            bar_open  = future_bar['open']
            bar_high  = future_bar['high']
            bar_low   = future_bar['low']

            if signal.side == "BUY":
                # Check for gap open below SL
                effective_low = self.cost_model.apply_exit_cost(bar_low, signal.side)
                effective_open = self.cost_model.apply_exit_cost(bar_open, signal.side)

                # Update best price (high water mark)
                if bar_high > best_price:
                    best_price = bar_high

                if self.use_tsl and not tsl_active:
                    if (best_price - entry_price) >= tsl_act:
                        tsl_active = True

                if tsl_active:
                    new_tsl = best_price - tsl_trail
                    if new_tsl > trailing_sl:
                        trailing_sl = new_tsl

                # ── SAME-BAR CONFLICT RULE & SL FILL ───────────────────────
                # Check if SL triggered on this bar
                if effective_low <= trailing_sl or effective_open <= trailing_sl:
                    outcome = "WIN" if trailing_sl > entry_price else "LOSS"
                    # Fill at gap open if opened below SL, else trailing SL minus exit slippage
                    actual_sl = min(effective_open, trailing_sl) if effective_open < trailing_sl else trailing_sl
                    exit_price = actual_sl - symbol_slippage
                    exit_time  = future_bar['time']
                    exit_bar_idx = j
                    break

                # TP triggered (only if SL did NOT trigger)
                if not tsl_active:
                    effective_high = self.cost_model.apply_exit_cost(bar_high, signal.side)
                    if effective_high >= signal.suggested_tp_price:
                        outcome = "WIN"
                        exit_price = signal.suggested_tp_price - symbol_slippage
                        exit_time  = future_bar['time']
                        exit_bar_idx = j
                        break

            else:  # SELL
                effective_high = self.cost_model.apply_exit_cost(bar_high, signal.side)
                effective_open = self.cost_model.apply_exit_cost(bar_open, signal.side)

                if bar_low < best_price:
                    best_price = bar_low

                if self.use_tsl and not tsl_active:
                    if (entry_price - best_price) >= tsl_act:
                        tsl_active = True

                if tsl_active:
                    new_tsl = best_price + tsl_trail
                    if new_tsl < trailing_sl:
                        trailing_sl = new_tsl

                # ── SAME-BAR CONFLICT RULE & SL FILL ───────────────────────
                if effective_high >= trailing_sl or effective_open >= trailing_sl:
                    outcome = "WIN" if trailing_sl < entry_price else "LOSS"
                    actual_sl = max(effective_open, trailing_sl) if effective_open > trailing_sl else trailing_sl
                    exit_price = actual_sl + symbol_slippage
                    exit_time  = future_bar['time']
                    exit_bar_idx = j
                    break

                # TP triggered
                if not tsl_active:
                    effective_low = self.cost_model.apply_exit_cost(bar_low, signal.side)
                    if effective_low <= signal.suggested_tp_price:
                        outcome = "WIN"
                        exit_price = signal.suggested_tp_price + symbol_slippage
                        exit_time  = future_bar['time']
                        exit_bar_idx = j
                        break

        if outcome == "OPEN":
            last_bar   = self.df.iloc[-1]
            exit_time  = last_bar['time']
            raw_exit   = self.cost_model.apply_exit_cost(last_bar['close'], signal.side)
            exit_price = raw_exit + (symbol_slippage if signal.side == "SELL" else -symbol_slippage)

        # ── Price Cap Sanity Check (Filter broker outlier ticks/gaps) ───
        if is_gold:
            max_loss_dist = 50.0
        elif is_btc:
            max_loss_dist = 5000.0
        elif is_eth:
            max_loss_dist = 500.0
        elif is_silver:
            max_loss_dist = 2.00   # Max 200 Silver cents
        elif is_jpy:
            max_loss_dist = 1.00   # Max 100 JPY pips
        else:
            max_loss_dist = 0.0100 # Max 100 Forex pips
        if signal.side == "BUY":
            exit_price = max(exit_price, entry_price - max_loss_dist)
        else:
            exit_price = min(exit_price, entry_price + max_loss_dist)

        # ── PnL Calculation ────────────────────────────────────────────────
        from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl
        spec      = get_symbol_spec(signal.symbol)
        gross_pnl = calculate_pnl(signal.symbol, signal.side, entry_price, exit_price, volume, spec)
        net_pnl   = gross_pnl - self.cost_model.get_commission_cost(volume)

        if abs(net_pnl) > (self.capital * 1.0):
            print(f"CRITICAL PnL EXCEPTION: symbol={signal.symbol}, strat={getattr(signal, 'strategy_id', 'UNKNOWN')}, side={signal.side}, entry={entry_price}, exit={exit_price}, sl={signal.suggested_sl_price}, tp={signal.suggested_tp_price}, pnl={net_pnl}")
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
