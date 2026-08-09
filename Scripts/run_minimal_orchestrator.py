import os
import sys
import pandas as pd
import logging

# Ensure we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategy.london_breakout import LondonBreakoutStrategy
from src.risk.engine import RiskEvaluator
from src.execution.gateway import ExecutionRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MinimalOrchestrator")

def run():
    logger.info("Starting Minimal Orchestrator...")
    
    # 1. Instantiate Strategy
    strategy = LondonBreakoutStrategy(symbol="EURUSD", lookback=3)
    
    # 2. Mock Data to trigger a Buy
    data = {
        'time': [1, 2, 3, 4],
        'open': [1.1, 1.1, 1.1, 1.1],
        'high': [1.11, 1.12, 1.10, 1.15],
        'low': [1.09, 1.08, 1.09, 1.11],
        'close': [1.1, 1.1, 1.1, 1.14]
    }
    df = pd.DataFrame(data)
    
    logger.info("Executing Strategy: LONDON_BREAKOUT")
    signal = strategy.analyze(df)
    if not signal:
        logger.error("Failed to generate signal.")
        return
    logger.info(f"Signal Generated: {signal.model_dump()}")
    
    # 3. Risk Engine
    risk_engine = RiskEvaluator()
    
    # Mocking portfolio state
    from src.common.messages import PortfolioSnapshotMessage, MessageHeader
    import uuid
    from datetime import datetime, timezone
    
    risk_engine.portfolio = PortfolioSnapshotMessage(
        header=MessageHeader(
            message_id=str(uuid.uuid4()),
            timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source_component="portfolio",
            message_type="PortfolioSnapshot"
        ),
        equity=1500.0,
        balance=1500.0,
        margin_used=0.0,
        margin_free=1500.0,
        open_positions=[],
        daily_realised_pnl=0.0,
        daily_unrealised_pnl=0.0,
        high_water_mark_equity=1500.0
    )
    
    logger.info("Evaluating Risk...")
    decision = risk_engine.evaluate(signal)
    logger.info(f"Risk Decision: {decision.model_dump()}")
    
    # 4. Execution Gateway
    if decision.decision in ["ALLOW", "ALLOW_REDUCED"]:
        logger.info("Risk approved. Sending to Execution Gateway...")
        gateway = ExecutionRouter()
        
        try:
            fill_report = gateway.execute(decision)
            logger.info(f"Fill Report: {fill_report.model_dump()}")
        except Exception as e:
            logger.warning(f"Execution failed (expected if MT5 not connected): {e}")
    else:
        logger.warning("Risk blocked the signal. Skipping Execution.")
        
    logger.info("Checking Audit Log (last entry)...")
    audit_file = os.path.join(os.path.dirname(__file__), "..", "logs", "audit.jsonl")
    if os.path.exists(audit_file):
        with open(audit_file, "r") as f:
            lines = f.readlines()
            if lines:
                logger.info(f"Audit Log Entry: {lines[-1].strip()}")
    
if __name__ == "__main__":
    run()
