import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta
import MetaTrader5 as mt5

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.portfolio.manager import init_mt5
from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.backtest.ranking import calculate_metrics_and_rank
from src.backtest.report import generate_reports

from src.strategy.london_breakout import LondonBreakoutStrategy
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
from src.strategy.rsi_reversal import RSIReversalStrategy
from src.strategy.ema_trend_pullback import EMATrendPullbackStrategy
from src.strategy.ny_open_breakout import NYOpenBreakoutStrategy
from src.strategy.bollinger_mean_reversion import BollingerMeanReversionStrategy
from src.strategy.london_breakout_v2 import LondonBreakoutV2Strategy
from src.strategy.vwap_mean_reversion import VWAPMeanReversionStrategy
from src.strategy.orb_opening_range_breakout import ORBOpeningRangeBreakoutStrategy
from src.strategy.supertrend_pullback import SupertrendPullbackStrategy
from src.strategy.fvg_retest import FVGRetestStrategy

def parse_args():
    parser = argparse.ArgumentParser(description="Automated Batch Backtest Runner")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Symbol to test (e.g., XAUUSD)")
    parser.add_argument("--timeframe", type=str, default="H1", help="Timeframe (e.g., M15, H1)")
    parser.add_argument("--bars", type=int, default=3000, help="Number of historical bars to fetch")
    parser.add_argument("--strategies", type=str, default="LONDON_BREAKOUT,MEAN_REVERSION,TREND_MOMENTUM,SMC_ORDER_BLOCK,ASIAN_RANGE_SCALP,RSI_REVERSAL,EMA_TREND_PULLBACK,NY_OPEN_BREAKOUT,BOLLINGER_MEAN_REVERSION,LONDON_BREAKOUT_V2,VWAP_MEAN_REVERSION,ORB_OPENING_RANGE_BREAKOUT,SUPERTREND_PULLBACK,FVG_RETEST", help="Comma-separated strategy IDs")
    parser.add_argument("--capital", type=float, default=1500.0, help="Initial capital")
    parser.add_argument("--spread", type=float, default=0.00010, help="Spread in points/pips")
    parser.add_argument("--commission", type=float, default=7.0, help="Commission per lot round-turn")
    parser.add_argument("--out", type=str, default="reports", help="Output directory base path")
    return parser.parse_args()

def get_timeframe_enum(tf_str):
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    return mapping.get(tf_str.upper(), mt5.TIMEFRAME_H1)

def main():
    args = parse_args()
    
    if not init_mt5():
        print("Failed to initialize MT5")
        return
        
    print(f"Fetching {args.bars} bars of {args.symbol} ({args.timeframe})...")
    tf_enum = get_timeframe_enum(args.timeframe)
    rates = mt5.copy_rates_from_pos(args.symbol, tf_enum, 0, args.bars)
    
    if rates is None or len(rates) == 0:
        print("No data retrieved.")
        mt5.shutdown()
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()
    
    strategy_names = [s.strip() for s in args.strategies.split(",")]
    strategies = []
    if "LONDON_BREAKOUT" in strategy_names:
        strategies.append(LondonBreakoutStrategy(symbol=args.symbol))
    if "MEAN_REVERSION" in strategy_names:
        strategies.append(MeanReversionStrategy(symbol=args.symbol))
    if "TREND_MOMENTUM" in strategy_names:
        strategies.append(TrendMomentumStrategy(symbol=args.symbol))
    if "SMC_ORDER_BLOCK" in strategy_names:
        strategies.append(SMCOrderBlockStrategy(symbol=args.symbol))
    if "ASIAN_RANGE_SCALP" in strategy_names:
        strategies.append(AsianRangeScalpStrategy(symbol=args.symbol))
    if "RSI_REVERSAL" in strategy_names:
        strategies.append(RSIReversalStrategy(symbol=args.symbol))
    if "EMA_TREND_PULLBACK" in strategy_names:
        strategies.append(EMATrendPullbackStrategy(symbol=args.symbol))
    if "NY_OPEN_BREAKOUT" in strategy_names:
        strategies.append(NYOpenBreakoutStrategy(symbol=args.symbol))
    if "BOLLINGER_MEAN_REVERSION" in strategy_names:
        strategies.append(BollingerMeanReversionStrategy(symbol=args.symbol))
    if "LONDON_BREAKOUT_V2" in strategy_names:
        strategies.append(LondonBreakoutV2Strategy(symbol=args.symbol))
    if "VWAP_MEAN_REVERSION" in strategy_names:
        strategies.append(VWAPMeanReversionStrategy(symbol=args.symbol))
    if "ORB_OPENING_RANGE_BREAKOUT" in strategy_names:
        strategies.append(ORBOpeningRangeBreakoutStrategy(symbol=args.symbol))
    if "SUPERTREND_PULLBACK" in strategy_names:
        strategies.append(SupertrendPullbackStrategy(symbol=args.symbol))
    if "FVG_RETEST" in strategy_names:
        strategies.append(FVGRetestStrategy(symbol=args.symbol))
        
    cost_model = CostModel(spread_points=args.spread, commission_per_lot=args.commission)
    
    print(f"Initializing BacktestEngine for {len(strategies)} strategies...")
    engine = BacktestEngine(df, strategies, cost_model, capital=args.capital)
    trades_df = engine.run()
    
    if trades_df.empty:
        print("No trades generated during the backtest.")
        return
        
    print("Calculating metrics and ranking...")
    metrics_df, correlation_matrix = calculate_metrics_and_rank(trades_df, initial_capital=args.capital)
    
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), args.out)
    report_path = generate_reports(trades_df, metrics_df, correlation_matrix, out_dir)
    
    print(f"\nBacktest complete. Reports generated at: {os.path.dirname(report_path)}")
    print("\n--- Strategy Ranking ---")
    print(metrics_df.to_string(index=False))

if __name__ == "__main__":
    main()
