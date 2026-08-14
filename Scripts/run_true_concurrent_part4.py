import sys, json, logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TRUE_CONCURRENT_PART4")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5
from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment
from src.common.session_filter import is_prime_trading_hour

from src.strategy.chart_pattern_swing import ChartPatternSwingStrategy
from src.strategy.macd_momentum      import MACDMomentumStrategy
from src.strategy.ema_crossover      import EMACrossoverStrategy

SYMBOLS = ["GOLD", "EURUSD"]

def fetch(symbol, tf, count):
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def build_strategies(sym):
    strats = {}
    # Chart Patterns (runs on H1, 120-bar lookback)
    strats["CHART_PATTERN"] = ChartPatternSwingStrategy(symbol=sym)
    # MACD — only Classic (12/26/9) and Slow (19/39/9); Fast (8/21/5) removed (too noisy)
    strats["MACD_12_26_9"] = MACDMomentumStrategy(symbol=sym, fast=12, slow=26, signal=9)
    strats["MACD_19_39_9"] = MACDMomentumStrategy(symbol=sym, fast=19, slow=39, signal=9)
    # EMA — only Swing (21/55) and Macro (50/200); Scalp (9/21) removed (too reactive)
    strats["EMA_21_55"]  = EMACrossoverStrategy(symbol=sym, fast=21, slow=55)
    strats["EMA_50_200"] = EMACrossoverStrategy(symbol=sym, fast=50, slow=200)
    return strats

def main():
    if not mt5.initialize():
        logger.error("MT5 init failed"); return

    capital = 1500.0
    volume  = 0.02

    risk_path = ROOT / "config" / "risk_config.json"
    max_total = 3
    max_sym   = 2
    if risk_path.exists():
        with open(risk_path) as f:
            cfg = json.load(f)
        max_total = cfg["global"].get("max_open_positions", 3)
        max_sym   = cfg["global"].get("max_positions_per_symbol", 2)
    logger.info(f"Risk Caps: Max Total={max_total}, Max Per Symbol={max_sym}, TSL=ON")

    asset_data = {}
    for sym in SYMBOLS:
        # M15 for chart patterns — smaller ATR = tighter SL = manageable loss per trade
        tf_entry  = mt5.TIMEFRAME_M15
        h_count   = 10000

        df_m5  = fetch(sym, mt5.TIMEFRAME_M5, 30000)
        df_h1  = fetch(sym, mt5.TIMEFRAME_M15, h_count)   # reusing df_h1 var as entry df
        df_h4  = fetch(sym, mt5.TIMEFRAME_H1,  5000)       # H1 used as HTF bias

        if df_m5.empty or df_h1.empty or df_h4.empty:
            logger.error(f"{sym}: data fetch failed, skipping."); continue

        if "GOLD" in sym:
            cost_m = CostModel(spread_points=0.30)
            vol = 0.01   # 0.01 lots for Gold on M15 — max loss per trade ~$12-24
        else:
            cost_m = CostModel(spread_points=0.00015)
            vol = 0.02   # 0.02 lots for Forex

        engine = BacktestEngine(
            df=df_h1, strategies=[], cost_model=cost_m,
            capital=capital, volume=vol, slippage_usd=0.15,
            use_tsl=True  # SL + TSL hybrid
        )

        asset_data[sym] = {
            "m5":     df_m5,
            "h1":     df_h1,
            "h4":     df_h4,
            "strats": build_strategies(sym),
            "engine": engine,
        }

    if "GOLD" not in asset_data:
        logger.error("GOLD missing. Abort."); return

    active_trades = []
    trade_history = []
    running_equity = capital
    peak_equity    = capital

    master = asset_data["GOLD"]["m5"]
    logger.info(f"Part 4 timeline start: {master.iloc[3000]['time']}")

    for i in range(3000, len(master)):
        current_time = master.iloc[i]["time"]

        # 1. Close expired trades
        still_open = []
        for tr in active_trades:
            if current_time >= tr["exit_time"]:
                running_equity += tr["pnl"]
                peak_equity     = max(peak_equity, running_equity)
                trade_history.append(tr)
            else:
                still_open.append(tr)
        active_trades = still_open

        # Drawdown killswitch
        if peak_equity > 0 and (peak_equity - running_equity) / peak_equity >= 0.30:
            logger.warning("30% drawdown — halt."); break

        if len(active_trades) >= max_total: continue
        # For chart patterns on H1, only block dead Asian hours (00-05 UTC) + 11 UTC whipsaw
        # This keeps London+NY open for pattern breakout entries
        hour = current_time.hour
        if 0 <= hour <= 5 or hour == 11:
            continue

        # M15 bar boundary
        if current_time.minute % 15 == 0:
            for sym, data in asset_data.items():
                sym_open = sum(1 for t in active_trades if t["symbol"] == sym)
                if sym_open >= max_sym: continue

                window_h1 = data["h1"][data["h1"]["time"] <= current_time]
                window_h4 = data["h4"][data["h4"]["time"] <= current_time]
                if len(window_h1) < 210 or len(window_h4) < 50: continue

                htf_bias = get_htf_trend_bias(window_h4)  # Use H4 as HTF bias

                for sid, strat in data["strats"].items():
                    sig = strat.analyze(window_h1)
                    if not sig: continue
                    if not validate_mtf_alignment(sig.side, htf_bias): continue

                    # 1 open per (sym, strategy)
                    if any(t["strategy_id"] == sid and t["symbol"] == sym for t in active_trades): continue
                    if sum(1 for t in active_trades if t["symbol"] == sym) >= max_sym: continue
                    if len(active_trades) >= max_total: continue

                    idx   = len(window_h1) - 1
                    trade = data["engine"]._simulate_execution(sig, idx)
                    if trade:
                        trade["strategy_id"] = sid
                        trade["entry_time"]  = current_time
                        trade["exit_time"]   = data["engine"].df.iloc[trade["exit_bar_idx"]]["time"]
                        active_trades.append(trade)
                        tsl_flag = "[TSL]" if trade.get("tsl_active") else "[SL ]"
                        pnl_val = trade['pnl']
                        logger.info(f"{tsl_flag} [{sym} {sid}] {sig.side} @ {current_time} | PnL: ${pnl_val:.2f}")

    # ─── Final Report ────────────────────────────────────────────────────────
    logger.info("=== TRUE CONCURRENT PART 4 COMPLETE ===")
    total_pnl = sum(t["pnl"] for t in trade_history)
    wins  = sum(1 for t in trade_history if t["pnl"] > 0)
    losses = len(trade_history) - wins
    wr = wins / len(trade_history) * 100 if trade_history else 0

    logger.info(f"Trades: {len(trade_history)} | Wins: {wins} | Losses: {losses} | WR: {wr:.1f}%")
    logger.info(f"Final PnL: ${total_pnl:.2f}")

    # Per-asset
    for sym in SYMBOLS:
        sym_t = [t for t in trade_history if t["symbol"] == sym]
        if not sym_t: continue
        sym_pnl = sum(t['pnl'] for t in sym_t)
        logger.info(f"  {sym:<8} | Trades: {len(sym_t):<3} | PnL: ${sym_pnl:.2f}")

    # Per-strategy config — THE KEY COMPARISON
    logger.info("--- Strategy Config Breakdown ---")
    all_sids = sorted(set(t["strategy_id"] for t in trade_history))
    for sid in all_sids:
        sid_t = [t for t in trade_history if t["strategy_id"] == sid]
        s_pnl = sum(t["pnl"] for t in sid_t)
        s_wr  = sum(1 for t in sid_t if t["pnl"] > 0) / len(sid_t) * 100
        logger.info(f"  {sid:<20} | Trades: {len(sid_t):<3} | WR: {s_wr:.0f}% | PnL: ${s_pnl:.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
