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

def run_session(iterations: int = 5):
    logger.info("Initializing Live MT5 Connection...")
    if not init_mt5():
        logger.error("MT5 Initialization failed. Halting.")
        return
        
    strategy = LondonBreakoutStrategy(symbol="EURUSD", lookback=10)
    risk_engine = RiskEvaluator()
    execution_gateway = ExecutionRouter()
    
    for i in range(iterations):
        logger.info(f"--- Orchestrator Loop {i+1}/{iterations} ---")
        try:
            # 1. Live Portfolio Snapshot
            portfolio = build_live_portfolio_snapshot()
            risk_engine.portfolio = portfolio
            
            # 2. Live Market Data
            df = fetch_live_candles(strategy.symbol, mt5.TIMEFRAME_H1, strategy.lookback + 3)
            
            if len(df) < strategy.lookback + 2:
                logger.warning("Not enough candles fetched.")
                continue
                
            # 3. Strategy Evaluation
            signal = strategy.analyze(df)
            if signal:
                logger.info(f"Signal Generated: {signal.side} {signal.symbol} @ {signal.suggested_entry_price}")
                
                # 4. Risk Evaluation
                decision = risk_engine.evaluate(signal)
                logger.info(f"Risk Decision: {decision.decision} ({decision.reason_code})")
                
                # 5. Execution
                if decision.decision in ["ALLOW", "ALLOW_REDUCED"]:
                    logger.info("Sending to Execution Gateway...")
                    fill_report = execution_gateway.execute(decision)
                    logger.info(f"Execution Report: {fill_report.status} (Reason: {fill_report.reject_reason})")
            else:
                logger.info("No signal generated.")
                
        except Exception as e:
            logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
            
        # Sleep for a short while during paper testing
        time.sleep(5)
        
    mt5.shutdown()
    logger.info("Session complete.")

if __name__ == "__main__":
    run_session()
