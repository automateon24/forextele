import zmq
import json
import logging
import time
import os
from datetime import datetime, timezone
from src.common.messages import SignalMessage, RiskDecisionMessage, MessageHeader, PortfolioSnapshotMessage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RISK_CONFIG_PATH = os.path.join(BASE_DIR, "config", "risk_config.json")
KILL_SWITCH_PATH = os.path.join(BASE_DIR, "config", "kill_switch.json")
AUDIT_LOG_PATH = os.path.join(BASE_DIR, "logs", "audit.jsonl")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [RISK_ENGINE] - %(levelname)s - %(message)s')

class RiskEvaluator:
    def __init__(self):
        self.portfolio: PortfolioSnapshotMessage = None
        self.config = {}
        self.kill_switch = {}

    def load_config(self):
        try:
            with open(RISK_CONFIG_PATH, "r") as f:
                self.config = json.load(f).get("global", {})
        except Exception as e:
            logging.error(f"Failed to load risk config: {e}")
            self.config = {}

        try:
            with open(KILL_SWITCH_PATH, "r") as f:
                self.kill_switch = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load kill switch: {e}")
            self.kill_switch = {"global": True} # Fail-closed

    def evaluate(self, signal: SignalMessage) -> RiskDecisionMessage:
        self.load_config()
        decision = "ALLOW"
        reason = "OK"
        
        # 1. Kill Switch
        if self.kill_switch.get("global", False):
            return self._block(signal, "KILL_SWITCH_ACTIVE")
        if signal.symbol in self.kill_switch.get("symbols", {}):
            if self.kill_switch["symbols"][signal.symbol]:
                return self._block(signal, "KILL_SWITCH_ACTIVE_SYMBOL")

        # 2. Data Freshness
        if not self.portfolio:
            return self._block(signal, "DATA_STALE")
        
        try:
            port_time = datetime.fromisoformat(self.portfolio.header.timestamp_utc.replace("Z", "+00:00"))
            now_time = datetime.now(timezone.utc)
            staleness_ms = (now_time - port_time).total_seconds() * 1000
            if staleness_ms > self.config.get("data_staleness_ms", 10000):
                return self._block(signal, "DATA_STALE")
        except Exception:
            pass

        # Calculate proposed risk amount
        # Formula: risk_amount = abs(entry - sl) * volume * tick_value_per_point
        # Note: We need tick_value and point. For safety in Phase 2, if we don't have it, we use a conservative estimate or block.
        # Let's assume a default safe micro-lot size first.
        volume = signal.metadata.get("suggested_volume", 0.01)
        
        # 12. Daily Loss Limit
        daily_loss_pct = 0.0
        if self.portfolio.high_water_mark_equity > 0:
            daily_loss_pct = (self.portfolio.daily_realised_pnl + self.portfolio.daily_unrealised_pnl) / self.portfolio.high_water_mark_equity
        if daily_loss_pct < -self.config.get("max_daily_loss_pct", 0.02):
            return self._block(signal, "DAILY_LOSS_LIMIT")

        # 10. Max Positions
        current_open_positions = len(self.portfolio.open_positions)
        if current_open_positions >= self.config.get("max_open_positions", 2):
            return self._block(signal, "MAX_OPEN_POSITIONS")

        symbol_positions = len([p for p in self.portfolio.open_positions if p.symbol == signal.symbol])
        if symbol_positions >= self.config.get("max_positions_per_symbol", 1):
            return self._block(signal, "MAX_SYMBOL_POSITIONS")

        # 11. Margin Check
        if self.portfolio.margin_used > 0:
            margin_ratio = self.portfolio.margin_free / self.portfolio.margin_used
            if margin_ratio < self.config.get("margin_buffer_mult", 1.5):
                return self._block(signal, "INSUFFICIENT_MARGIN")

        # 8 & 9. Risk & Portfolio Heat Sizing
        # Here we scale the volume to fit the 0.6% limit.
        max_risk_pct = self.config.get("max_risk_per_trade_pct", 0.006)
        
        # If the risk amount is known from MT5 via the signal metadata, we check it. 
        # For this skeleton, we just enforce the hard lot cap.
        hard_cap = self.config.get("hard_lot_cap", 0.05)
        volume = min(volume, hard_cap)

        return RiskDecisionMessage(
            header=MessageHeader(message_type="RiskDecision", source_component="svc_risk_engine"),
            original_correlation_id=signal.header.correlation_id,
            decision="ALLOW",
            reason_code="OK",
            approved_volume=volume,
            approved_sl_price=signal.suggested_sl_price,
            approved_tp_price=signal.suggested_tp_price,
            risk_snapshot={
                "symbol": signal.symbol,
                "side": signal.side,
                "equity": self.portfolio.equity,
                "positions": current_open_positions,
                "daily_loss_pct": daily_loss_pct
            }
        )
        self._audit_log(decision)
        return decision

    def _audit_log(self, decision: RiskDecisionMessage):
        try:
            with open(AUDIT_LOG_PATH, "a") as f:
                f.write(decision.model_dump_json() + "\n")
        except Exception as e:
            logging.error(f"Failed to write to audit log: {e}")

    def _block(self, signal: SignalMessage, reason: str) -> RiskDecisionMessage:
        decision = RiskDecisionMessage(
            header=MessageHeader(message_type="RiskDecision", source_component="svc_risk_engine"),
            original_correlation_id=signal.header.correlation_id,
            decision="BLOCK",
            reason_code=reason
        )
        self._audit_log(decision)
        return decision

def main():
    context = zmq.Context()
    
    # Subscribe to Signals
    signal_sub = context.socket(zmq.SUB)
    signal_sub.connect("tcp://127.0.0.1:5556")
    signal_sub.setsockopt_string(zmq.SUBSCRIBE, "SIGNAL")

    # Subscribe to Portfolio
    port_sub = context.socket(zmq.SUB)
    port_sub.connect("tcp://127.0.0.1:5559")
    port_sub.setsockopt_string(zmq.SUBSCRIBE, "PORTFOLIO")
    
    # Publish Risk Decisions
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://127.0.0.1:5557")

    poller = zmq.Poller()
    poller.register(signal_sub, zmq.POLLIN)
    poller.register(port_sub, zmq.POLLIN)
    
    evaluator = RiskEvaluator()
    logging.info("Risk Engine running, connected to Signals & Portfolio, publishing RiskDecisions")

    while True:
        try:
            socks = dict(poller.poll(1000))
            
            if port_sub in socks and socks[port_sub] == zmq.POLLIN:
                msg = port_sub.recv_string()
                _, json_data = msg.split(" ", 1)
                port_data = json.loads(json_data)
                evaluator.portfolio = PortfolioSnapshotMessage(**port_data)
            
            if signal_sub in socks and socks[signal_sub] == zmq.POLLIN:
                msg = signal_sub.recv_string()
                _, json_data = msg.split(" ", 1)
                signal_data = json.loads(json_data)
                signal = SignalMessage(**signal_data)
                
                decision = evaluator.evaluate(signal)
                pub_socket.send_string(f"RISK_DECISION {decision.model_dump_json()}")
                logging.info(f"Emitted {decision.decision} for {signal.symbol} (Reason: {decision.reason_code})")
                
        except KeyboardInterrupt:
            logging.info("Shutting down Risk Engine.")
            break
        except Exception as e:
            logging.error(f"Error in Risk Engine loop: {e}")

if __name__ == "__main__":
    main()
