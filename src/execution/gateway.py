import zmq
import json
import logging
import MetaTrader5 as mt5
import os
import time
from src.common.messages import RiskDecisionMessage, FillReportMessage, MessageHeader

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "mt5_config.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [EXECUTION] - %(levelname)s - %(message)s')

def init_mt5():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

class ExecutionRouter:
    def __init__(self):
        self.magic = 123456
        self.deviation = 10
        self.max_slippage = 20 # points

    def execute(self, decision: RiskDecisionMessage) -> FillReportMessage:
        symbol = decision.risk_snapshot.get("symbol", "")
        side = decision.risk_snapshot.get("side", "")
        
        # In a real system, the RiskDecision should echo the symbol and side or we fetch it from a shared cache
        # For Phase 3, we will assume the Signal symbol/side is passed through the risk_snapshot for simplicity.
        
        if not symbol or not side:
            return self._fail(decision, "MISSING_SYMBOL_OR_SIDE")
            
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return self._fail(decision, "MT5_TICK_FAILED")

        action = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": decision.approved_volume,
            "type": action,
            "price": price,
            "sl": decision.approved_sl_price,
            "tp": decision.approved_tp_price,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": decision.original_correlation_id[:10],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # FAIL-CLOSED Execution: No retries.
        start_ms = int(time.time() * 1000)
        result = mt5.order_send(request)
        end_ms = int(time.time() * 1000)
        latency = end_ms - start_ms

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return FillReportMessage(
                header=MessageHeader(message_type="FillReport", source_component="svc_execution_gateway"),
                broker_order_id=str(result.order),
                broker_deal_id=str(result.deal),
                symbol=symbol,
                side=side,
                volume=result.volume,
                fill_price=result.price,
                sl=decision.approved_sl_price,
                tp=decision.approved_tp_price,
                status="FILLED",
                latency_ms=latency
            )
        else:
            reason = str(result.retcode) if result else "NONE"
            return self._fail(decision, f"MT5_REJECTED_{reason}", latency=latency, symbol=symbol, side=side)

    def _fail(self, decision: RiskDecisionMessage, reason: str, latency: int=0, symbol: str="UNKNOWN", side: str="BUY") -> FillReportMessage:
        return FillReportMessage(
            header=MessageHeader(message_type="FillReport", source_component="svc_execution_gateway"),
            broker_order_id="NONE",
            broker_deal_id="NONE",
            symbol=symbol,
            side=side,
            volume=decision.approved_volume,
            fill_price=0.0,
            sl=decision.approved_sl_price,
            tp=decision.approved_tp_price,
            status="REJECTED",
            reject_reason=reason,
            latency_ms=latency
        )

def main():
    if not init_mt5():
        logging.error("Failed to connect to MT5. Execution Gateway halting.")
        return

    context = zmq.Context()
    
    # Subscribe to Risk Decisions
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect("tcp://127.0.0.1:5557")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "RISK_DECISION")
    
    # Publish Fill Reports
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://127.0.0.1:5558")
    
    router = ExecutionRouter()
    logging.info("Execution Gateway connected to RiskDecisions and bound to tcp://127.0.0.1:5558 for FillReports")

    while True:
        try:
            message_string = sub_socket.recv_string()
            _, json_data = message_string.split(" ", 1)
            risk_data = json.loads(json_data)
            decision_msg = RiskDecisionMessage(**risk_data)
            
            if decision_msg.decision in ["ALLOW", "ALLOW_REDUCED"]:
                report = router.execute(decision_msg)
                pub_socket.send_string(f"FILL_REPORT {report.model_dump_json()}")
                if report.status == "FILLED":
                    logging.info(f"FILLED order for correlation ID: {decision_msg.original_correlation_id} at {report.fill_price}")
                else:
                    logging.warning(f"REJECTED order for correlation ID: {decision_msg.original_correlation_id} (Reason: {report.reject_reason})")
            else:
                logging.info(f"Risk Blocked trade for correlation ID: {decision_msg.original_correlation_id}")
                
        except KeyboardInterrupt:
            logging.info("Shutting down Execution Gateway.")
            break
        except Exception as e:
            logging.error(f"Error in Execution Gateway loop: {e}")

if __name__ == "__main__":
    main()
