import os
import sys
import time
import logging
import pandas as pd
from datetime import datetime, timezone
import MetaTrader5 as mt5

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategy.london_breakout import LondonBreakoutStrategy
from src.risk.engine import RiskEvaluator
from src.execution.gateway import ExecutionRouter
from src.portfolio.manager import init_mt5, get_daily_realised_pnl, load_high_water_mark
from src.common.messages import PortfolioSnapshotMessage, MessageHeader, OpenPosition
import uuid

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [PRODUCTION_ORCHESTRATOR] - %(levelname)s - %(message)s')
logger = logging.getLogger("ProdOrchestrator")

def build_live_portfolio_snapshot() -> PortfolioSnapshotMessage:
    account_info = mt5.account_info()
    if account_info is None:
        raise Exception("Failed to get MT5 account info")
    
    positions = mt5.positions_get()
    open_pos = []
    if positions:
        for p in positions:
            open_pos.append(OpenPosition(
                symbol=p.symbol,
                side="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                volume=p.volume,
                entry_price=p.price_open,
                current_price=p.price_current,
                sl=p.sl,
                unrealised_pnl=p.profit,
                risk_amount=abs(p.price_open - p.sl) * p.volume if p.sl > 0 else 0.0
            ))
            
    equity = account_info.equity
    daily_realised = get_daily_realised_pnl()
    
    return PortfolioSnapshotMessage(
        header=MessageHeader(
            message_id=str(uuid.uuid4()),
            timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source_component="portfolio",
            message_type="PortfolioSnapshot"
        ),
        equity=equity,
        balance=account_info.balance,
        margin_used=account_info.margin,
        margin_free=account_info.margin_free,
        open_positions=open_pos,
        daily_realised_pnl=daily_realised,
        daily_unrealised_pnl=sum(p.unrealised_pnl for p in open_pos),
        high_water_mark_equity=load_high_water_mark(equity)
    )

def fetch_live_candles(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "active_strategies.json")

def load_active_strategies():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    strategies = []
    symbols = config.get("active_symbols", ["EURUSD"])
    
    for symbol in symbols:
        if "LONDON_BREAKOUT" in config.get("active_strategies", []):
            strategies.append(LondonBreakoutStrategy(symbol=symbol))
        if "MEAN_REVERSION" in config.get("active_strategies", []):
            from src.strategy.mean_reversion import MeanReversionStrategy
            strategies.append(MeanReversionStrategy(symbol=symbol))
        if "TREND_MOMENTUM" in config.get("active_strategies", []):
            from src.strategy.trend_momentum import TrendMomentumStrategy
            strategies.append(TrendMomentumStrategy(symbol=symbol))
        if "SMC_ORDER_BLOCK" in config.get("active_strategies", []):
            from src.strategy.smc_order_block import SMCOrderBlockStrategy
            strategies.append(SMCOrderBlockStrategy(symbol=symbol))
        if "ASIAN_RANGE_SCALP" in config.get("active_strategies", []):
            from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
            strategies.append(AsianRangeScalpStrategy(symbol=symbol))
        if "LONDON_BREAKOUT_V2" in config.get("active_strategies", []):
            from src.strategy.london_breakout_v2 import LondonBreakoutV2Strategy
            strategies.append(LondonBreakoutV2Strategy(symbol=symbol))
            
    return strategies, symbols

def run_session():
    logger.info("Initializing Live MT5 Connection...")
    if not init_mt5():
        logger.error("MT5 Initialization failed. Halting.")
        return
        
    strategies, symbols = load_active_strategies()
    logger.info(f"Loaded {len(strategies)} strategies across symbols: {', '.join(symbols)}")
    
    risk_engine = RiskEvaluator()
    execution_gateway = ExecutionRouter()
    
    # We fetch enough candles to satisfy the hungriest strategy
    max_lookback = max(s.min_bars for s in strategies) if strategies else 50
    
    logger.info("Starting infinite orchestrator loop. Press Ctrl+C to stop.")
    
    loop_count = 0
    while True:
        try:
            loop_count += 1
            if loop_count % 12 == 0: # Every ~60 seconds
                logger.info(f"Heartbeat: Loop {loop_count} completed. No new signals.")
                
            # 1. Live Portfolio Snapshot
            portfolio = build_live_portfolio_snapshot()
            risk_engine.portfolio = portfolio
            
            # 2. Process each symbol
            for symbol in symbols:
                df = fetch_live_candles(symbol, mt5.TIMEFRAME_H1, max_lookback + 5)
                
                if len(df) < max_lookback:
                    logger.warning(f"Not enough candles fetched for {symbol}.")
                    continue
                    
                # 3. Strategy Evaluation (Multi-Strategy)
                symbol_strategies = [s for s in strategies if s.symbol == symbol]
                
                for strategy in symbol_strategies:
                    signal = strategy.analyze(df)
                    if signal:
                        logger.info(f"[{strategy.strategy_id}] Signal Generated: {signal.side} {signal.symbol} @ {signal.suggested_entry_price}")
                        
                        # 4. Risk Evaluation
                        decision = risk_engine.evaluate(signal)
                        logger.info(f"[{strategy.strategy_id}] Risk Decision: {decision.decision} ({decision.reason_code})")
                        
                        # 5. Execution
                        if decision.decision in ["ALLOW", "ALLOW_REDUCED"]:
                            logger.info(f"[{strategy.strategy_id}] Sending to Execution Gateway...")
                            fill_report = execution_gateway.execute(decision)
                            logger.info(f"[{strategy.strategy_id}] Execution Report: {fill_report.status} (Reason: {fill_report.reject_reason})")
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
            
        time.sleep(5)
        
    mt5.shutdown()
    logger.info("Session complete.")

if __name__ == "__main__":
    run_session()
