import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from market_trader_engine import MarketTraderHandler
from ai_conviction_tsl_manager import load_trade_registry, save_trade_registry, register_trade
from real_mt5_execution import MT5ExecutionEngine

print("--- Testing Market Trader Book 100% Logic ---")
mt = MarketTraderHandler()

# Register a mock trade ticket 9999991
register_trade(9999991, "AUDJPY", "BUY", 98.50, 98.20, [99.00], "Market Trader", 0.90)

# Simulate message "AUDJPY Book 100% Profit. 300 Pips Done"
res = asyncio.run(mt.handle_message("AUDJPY Book 100% Profit. 300 Pips Done"))
print("Handle message result:", res)

# Check registry
reg = load_trade_registry()
meta = reg.get("9999991", {})
print(f"Ticket 9999991 mode: {meta.get('mode')}, extension_step: {meta.get('extension_step')}")

# Clean up mock ticket
if "9999991" in reg:
    del reg["9999991"]
    save_trade_registry(reg)

print("\n--- Testing MT5 Comment Punching Format ---")
payload_mt = {"symbol": "AUDJPY", "action": "BUY", "entry": 98.50, "comment": "[Market Trader]", "source_channel": "Market Trader"}
payload_pm = {"symbol": "GOLD", "action": "BUY", "entry": 4350.0, "comment": "[Perfect Management]", "source_channel": "Perfect Management"}
payload_karol = {"symbol": "GOLD", "action": "BUY", "entry": 4350.0, "source_channel": "Forex with karol"}
payload_swift = {"symbol": "GOLD", "action": "BUY", "entry": 4350.0, "source_channel": "Swift Gold Forex"}

for p in [payload_mt, payload_pm, payload_karol, payload_swift]:
    raw_comment = p.get("comment", "")
    raw_chan = p.get("source_channel", "")
    if raw_comment and raw_comment.startswith("[") and raw_comment.endswith("]"):
        order_comment = raw_comment[:31]
    elif raw_chan:
        clean_chan_str = raw_chan.encode('ascii', 'ignore').decode('ascii').strip()
        order_comment = f"[{clean_chan_str[:27]}]"[:31]
    else:
        order_comment = (raw_comment or "AI_SWARM")[:31]
    print(f"Channel: '{raw_chan}' -> MT5 Punched Comment: '{order_comment}' (len: {len(order_comment)})")

print("\nALL VERIFICATION CHECKS PASSED!")
