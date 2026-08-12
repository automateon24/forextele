"""
Pair-Specific Opportunity & DNA Optimizer
==========================================
Discovers exact profitable strategy configurations for all 8 pairs (GOLD, SILVER, EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD)
by applying pair-tailored ATR dynamic stops, session filters, and MTF trend confirmation.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import CostModel
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
from src.strategy.bollinger_mean_reversion import BollingerMeanReversionStrategy
from src.strategy.london_breakout import LondonBreakoutStrategy
from src.strategy.ema_trend_pullback import EMATrendPullbackStrategy
from src.strategy.supertrend_pullback import SupertrendPullbackStrategy
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment
from src.common.session_filter import is_prime_trading_hour

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OPPORTUNITY_FINDER")

ALL_SYMBOLS = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]

def fetch_bars(symbol: str, timeframe: int, count: int = 3000) -> pd.DataFrame:
    if not mt5.initialize():
        return pd.DataFrame()
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def run_opportunity_search():
    print("="*100)
    print("  MULTI-PAIR TRADING OPPORTUNITY & DNA DISCOVERY ENGINE")
    print("  Targeting POSITIVE NET PROFITS Across All 8 Pairs ($1,500 Capital)")
    print("="*100)

    if not mt5.initialize():
        print("MT5 initialization failed.")
        return

    winning_opportunities = []

    for sym in ALL_SYMBOLS:
        df_h1 = fetch_bars(sym, mt5.TIMEFRAME_H1, 3000)
        if df_h1.empty or len(df_h1) < 200:
            continue

        htf_bias = get_htf_trend_bias(df_h1)

        # Asset-specific cost and volume modeling
        if "GOLD" in sym:
            cost_m = CostModel(spread_points=30.0)
            vol = 0.02
        elif "SILVER" in sym:
            cost_m = CostModel(spread_points=3.0)
            vol = 0.005 # Silver micro lot
        else:
            cost_m = CostModel(spread_points=15.0) # 1.5 pips for Forex majors
            vol = 0.02

        strategies = [
            ("TREND_MOMENTUM", TrendMomentumStrategy(sym)),
            ("ASIAN_RANGE_SCALP", AsianRangeScalpStrategy(sym)),
            ("BOLLINGER_MEAN_REVERSION", BollingerMeanReversionStrategy(sym)),
            ("LONDON_BREAKOUT", LondonBreakoutStrategy(sym)),
            ("EMA_TREND_PULLBACK", EMATrendPullbackStrategy(sym)),
            ("SUPERTREND_PULLBACK", SupertrendPullbackStrategy(sym)),
        ]

        for s_name, strat in strategies:
            try:
                engine = BacktestEngine(
                    df=df_h1,
                    strategies=[strat],
                    cost_model=cost_m,
                    capital=1500.0,
                    volume=vol,
                    use_tsl=True,
                    max_dd_pct=0.30,
                    slippage_usd=0.10
                )
                engine.run()

                valid_trades = []
                for tr in engine.trades:
                    if not validate_mtf_alignment(tr.get("side", "BUY"), htf_bias):
                        continue
                    if not is_prime_trading_hour(tr["time"]):
                        continue
                    valid_trades.append(tr)
            except Exception as e:
                continue

            if not valid_trades:
                continue

            # Calculate filtered performance
            n_trades = len(valid_trades)
            wins = [t for t in valid_trades if t["pnl"] > 0]
            losses = [t for t in valid_trades if t["pnl"] <= 0]
            wr = (len(wins) / n_trades) * 100 if n_trades > 0 else 0
            net_pnl = sum(t["pnl"] for t in valid_trades)
            gross_win = sum(t["pnl"] for t in wins)
            gross_loss = abs(sum(t["pnl"] for t in losses))
            pf = gross_win / gross_loss if gross_loss > 0 else 99.0

            if net_pnl > 0 and n_trades >= 5:
                winning_opportunities.append({
                    "symbol": sym,
                    "strategy": s_name,
                    "trades": n_trades,
                    "win_rate": round(wr, 1),
                    "net_pnl": round(net_pnl, 2),
                    "profit_factor": round(pf, 2)
                })

    mt5.shutdown()

    print("\n" + "="*100)
    print("  DISCOVERED PROFITABLE STRATEGY KEYS PER PAIR (H1 TIMEFRAME)")
    print("="*100)
    print(f"  {'Symbol':<10} {'Strategy':<30} {'Trades':<8} {'Win Rate %':<12} {'Net PnL ($)':<14} {'Profit Factor'}")
    print("  " + "-"*85)

    if not winning_opportunities:
        print("  No positive combinations found under standard parameters.")
    else:
        for opp in winning_opportunities:
            print(f"  {opp['symbol']:<10} {opp['strategy']:<30} {opp['trades']:<8} {opp['win_rate']:>6.1f}%      ${opp['net_pnl']:>9.2f}    {opp['profit_factor']:>6.2f}")

    print("="*100)

if __name__ == "__main__":
    run_opportunity_search()
