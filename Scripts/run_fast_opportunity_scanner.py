"""
Fast Multi-Pair Opportunity & Strategy DNA Scanner
===================================================
Quickly scans H1 timeframes across all 8 pairs (GOLD, SILVER, EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD)
with session filters, MTF trend bias, and 1:2.5 Risk:Reward dynamic stops.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
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
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment
from src.common.session_filter import is_prime_trading_hour

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ALL_SYMBOLS = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]

def get_base_params(sym: str):
    if "GOLD" in sym or "XAU" in sym:
        return CostModel(spread_points=0.10, commission_per_lot=0.0), 0.02 # 10 cents
    elif "SILVER" in sym or "XAG" in sym:
        return CostModel(spread_points=0.01, commission_per_lot=0.0), 0.005 # 1 cent
    elif "JPY" in sym:
        return CostModel(spread_points=0.002, commission_per_lot=0.0), 0.05 # 0.2 pips
    else:
        return CostModel(spread_points=0.00002, commission_per_lot=0.0), 0.05 # 0.2 pips

def fetch_bars(symbol: str, timeframe: int, count: int = 3000) -> pd.DataFrame:
    if not mt5.initialize():
        return pd.DataFrame()
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def scan_opportunities():
    print("="*100)
    print("  INSTITUTIONAL MULTI-PAIR OPPORTUNITY DISCOVERY SCANNER")
    print("  Symbols: 8 Major Pairs | Timeframe: H1 | Strategy DNA: Trend Momentum + Asian Scalp")
    print("="*100)

    if not mt5.initialize():
        print("MT5 terminal initialization failed.")
        return

    results = []

    for sym in ALL_SYMBOLS:
        df_h1 = fetch_bars(sym, mt5.TIMEFRAME_H1, 3000)
        if df_h1.empty or len(df_h1) < 200:
            continue

        htf_bias = get_htf_trend_bias(df_h1)

        # Asset-specific cost modeling
        cost_m, vol = get_base_params(sym)

        strategies = [
            ("TREND_MOMENTUM", TrendMomentumStrategy(sym)),
            ("ASIAN_RANGE_SCALP", AsianRangeScalpStrategy(sym)),
            ("BOLLINGER_MEAN_REVERSION", BollingerMeanReversionStrategy(sym)),
        ]

        for s_name, strat in strategies:
            try:
                engine = BacktestEngine(
                    df=df_h1,
                    strategies=[strat],
                    cost_model=cost_m,
                    capital=1500.0,
                    volume=vol,
                    use_tsl=False,
                    max_dd_pct=0.30,
                    slippage_usd=0.00
                )
                engine.run()

                valid_trades = []
                for tr in engine.trades:
                    if not is_prime_trading_hour(tr["time"]):
                        continue
                    valid_trades.append(tr)

                if not valid_trades:
                    continue

                n_trades = len(valid_trades)
                wins = [t for t in valid_trades if t["pnl"] > 0]
                losses = [t for t in valid_trades if t["pnl"] <= 0]
                wr = (len(wins) / n_trades) * 100 if n_trades > 0 else 0
                net_pnl = sum(t["pnl"] for t in valid_trades)
                gross_win = sum(t["pnl"] for t in wins)
                gross_loss = abs(sum(t["pnl"] for t in losses))
                pf = gross_win / gross_loss if gross_loss > 0 else 99.0

                avg_win = gross_win / len(wins) if wins else 0
                avg_loss = gross_loss / len(losses) if losses else 0
                rr = avg_win / avg_loss if avg_loss > 0 else 99.0

                roi = (net_pnl / 1500.0) * 100

                peak = 1500.0
                running = 1500.0
                max_dd = 0.0
                for t in valid_trades:
                    running += t["pnl"]
                    if running > peak:
                        peak = running
                    dd = (peak - running) / peak * 100
                    if dd > max_dd:
                        max_dd = dd

                results.append({
                    "symbol": sym,
                    "strategy": s_name,
                    "trades": n_trades,
                    "win_rate": round(wr, 1),
                    "net_pnl": round(net_pnl, 2),
                    "roi": round(roi, 1),
                    "rr": round(rr, 2),
                    "dd": round(max_dd, 1),
                    "profit_factor": round(pf, 2),
                    "is_profitable": net_pnl > 0
                })
            except Exception as e:
                import traceback
                print(f"Exception for {s_name} on {sym}: {e}")
                traceback.print_exc()
                continue

    mt5.shutdown()

    res_df = pd.DataFrame(results)
    print("\n" + "="*120)
    print("  SUMMARY OF DISCOVERED OPPORTUNITIES ACROSS ALL 8 PAIRS (Capital: $1500.0)")
    print("="*120)
    print(f"  {'Symbol':<10} {'Strategy':<30} {'Trades':<8} {'Win %':<8} {'Net PnL':<12} {'ROI %':<8} {'PF':<8} {'RR':<8} {'Max DD %':<10} {'Status'}")
    print("  " + "-"*115)

    for _, r in res_df.iterrows():
        status_str = "[PROFITABLE]" if r["net_pnl"] > 0 else "[LOSS]"
        print(f"  {r['symbol']:<10} {r['strategy']:<30} {r['trades']:<8} {r['win_rate']:>5.1f}%   ${r['net_pnl']:>9.2f}  {r['roi']:>6.1f}%  {r['profit_factor']:>5.2f}   {r['rr']:>4.2f}   {r['dd']:>6.1f}%    {status_str}")

    print("="*120)

if __name__ == "__main__":
    scan_opportunities()
