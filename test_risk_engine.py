import zmq
import json
import time
import threading
from core_schemas import SignalMessage, PortfolioSnapshotMessage, MessageHeader

def simulate_portfolio_and_signal():
    context = zmq.Context()
    
    # Setup Portfolio Publisher
    port_pub = context.socket(zmq.PUB)
    port_pub.bind("tcp://127.0.0.1:5559")
    
    # Setup Signal Publisher
    signal_pub = context.socket(zmq.PUB)
    signal_pub.bind("tcp://127.0.0.1:5556")
    
    time.sleep(1) # Wait for Risk Engine to connect
    
    print("[MOCK_TESTER] Sending Portfolio Snapshot...")
    port_msg = PortfolioSnapshotMessage(
        header=MessageHeader(message_type="PortfolioSnapshot", source_component="test"),
        equity=1500.0,
        balance=1500.0,
        margin_used=100.0,
        margin_free=1400.0,
        open_positions=[],
        daily_realised_pnl=0.0,
        daily_unrealised_pnl=0.0,
        high_water_mark_equity=1500.0
    )
    port_pub.send_string(f"PORTFOLIO {port_msg.model_dump_json()}")
    time.sleep(0.5)
    
    print("[MOCK_TESTER] Sending Signal (Should be ALLOWED)...")
    sig_msg1 = SignalMessage(
        header=MessageHeader(message_type="Signal", source_component="test"),
        symbol="USDCHF",
        side="BUY",
        strategy_id="TEST",
        suggested_entry_price=1.1,
        suggested_sl_price=1.09,
        suggested_tp_price=1.12
    )
    signal_pub.send_string(f"SIGNAL {sig_msg1.model_dump_json()}")
    time.sleep(1)

    print("[MOCK_TESTER] Sending Portfolio with MAX POSITIONS Breached...")
    port_msg.open_positions = [
        {"symbol": "USDCHF", "side": "BUY", "volume": 0.01, "entry_price": 1.1, "current_price": 1.1, "sl": 1.09, "unrealised_pnl": 0.0, "risk_amount": 10.0},
        {"symbol": "EURUSD", "side": "SELL", "volume": 0.01, "entry_price": 1.1, "current_price": 1.1, "sl": 1.11, "unrealised_pnl": 0.0, "risk_amount": 10.0}
    ]
    port_pub.send_string(f"PORTFOLIO {port_msg.model_dump_json()}")
    time.sleep(0.5)
    
    print("[MOCK_TESTER] Sending Signal (Should be BLOCKED by Max Positions)...")
    signal_pub.send_string(f"SIGNAL {sig_msg1.model_dump_json()}")
    time.sleep(1)

def listen_to_decisions():
    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.connect("tcp://127.0.0.1:5557")
    sub.setsockopt_string(zmq.SUBSCRIBE, "RISK_DECISION")
    
    print("[MOCK_TESTER] Listening for Risk Decisions...")
    for _ in range(2):
        try:
            msg = sub.recv_string(timeout=2000)
            print(f"[MOCK_TESTER] Received Decision: {msg}")
        except Exception:
            pass

if __name__ == "__main__":
    t_listen = threading.Thread(target=listen_to_decisions)
    t_listen.start()
    
    simulate_portfolio_and_signal()
    t_listen.join()
