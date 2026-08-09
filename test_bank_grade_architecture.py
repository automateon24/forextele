import time
import zmq
import json
import threading
from core_schemas import SignalMessage, MessageHeader

def simulate_market_data():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://127.0.0.1:5555")
    time.sleep(1)
    
    msg = {
        "event": "BarClosed",
        "symbol": "USDCHF",
        "timeframe": "M15",
        "time": int(time.time()),
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1, # Bullish bar
        "tick_volume": 100
    }
    socket.send_string(f"MARKET_DATA {json.dumps(msg)}")
    print("[MOCK_DATA] Sent BarClosed event")

def listen_to_execution():
    context = zmq.Context()
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect("tcp://127.0.0.1:5558")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "FILL_REPORT")
    
    print("[MOCK_TESTER] Waiting for Fill Report from Execution Gateway...")
    try:
        msg = sub_socket.recv_string(flags=zmq.NOBLOCK)
        print(f"[MOCK_TESTER] Received: {msg}")
    except zmq.Again:
        pass # Handle timeouts in a real test

if __name__ == "__main__":
    print("Testing ZMQ Event Pipeline...")
    t1 = threading.Thread(target=simulate_market_data)
    t1.start()
    t1.join()
    print("Test simulated data sent. The actual engines would now process this if running.")
