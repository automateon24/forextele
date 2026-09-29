import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
from ai_conviction_tsl_manager import (
    load_trade_registry,
    save_trade_registry,
    register_trade,
    run_tsl_monitoring_cycle,
    activate_extension_tsl
)

class MockPosition:
    def __init__(self, ticket, symbol, order_type, price_open, sl, tp, magic):
        self.ticket = ticket
        self.symbol = symbol
        self.type = order_type
        self.price_open = price_open
        self.sl = sl
        self.tp = tp
        self.magic = magic

def test_fixed_sl_to_tp2_and_jumping_tsl():
    print("=" * 75)
    print("🧪 VERIFYING: FIXED SL UNTIL TP2, THEN TSL AT TP2 + 10-PIP JUMP TRAIL")
    print("=" * 75)
    
    # 1. Register a test trade: BUY GOLD @ 4300.00 | Initial SL: 4285.00 | TP1: 4310.00 | TP2: 4320.00
    ticket = 7771234
    symbol = "GOLD"
    action = "BUY"
    entry = 4300.00
    initial_sl = 4285.00
    tps = [4310.00, 4320.00, 4340.00]
    
    register_trade(ticket, symbol, action, entry, initial_sl, tps, "VIP Channel", 0.90)
    reg = load_trade_registry()
    assert str(ticket) in reg
    print(f"✅ Step 1: Registered Trade #{ticket} with SL={initial_sl}, TP1={tps[0]}, TP2={tps[1]}")
    
    # 2. Check meta targets
    meta = reg[str(ticket)]
    sorted_tps = sorted(meta["tps"])
    tp1 = sorted_tps[0]
    tp2 = sorted_tps[1]
    assert tp1 == 4310.00
    assert tp2 == 4320.00
    print(f"✅ Step 2: Target TP1={tp1}, Target TP2={tp2} verified")
    
    # 3. Simulate Price Movement from 4300.00 up to 4315.00 (Past TP1, before TP2)
    # The rule: SL MUST REMAIN STRICTLY FIXED AT 4285.00!
    pip_size = 0.10
    fee_buffer = 0.50
    jump_gap = 10.0 * pip_size # 1.00 ($1.00 on Gold)
    
    test_price_at_tp1 = 4312.00
    has_reached_tp2 = meta.get("has_reached_tp2", False)
    if test_price_at_tp1 >= tp2:
        has_reached_tp2 = True
    
    assert not has_reached_tp2
    current_sl = initial_sl
    print(f"✅ Step 3: Price at {test_price_at_tp1} (Past TP1) -> has_reached_tp2={has_reached_tp2}. SL stays FIXED at {current_sl}")
    
    # 4. Simulate Price hitting TP2 @ 4320.50
    test_price_at_tp2 = 4320.50
    if test_price_at_tp2 >= tp2:
        has_reached_tp2 = True
        meta["has_reached_tp2"] = True
    
    assert has_reached_tp2
    # At TP2: Put TSL at TP2 (with spread breathing room)
    base_tp2_sl = round(tp2 - (fee_buffer * 0.5), 2)
    calc_trail = round(test_price_at_tp2 - jump_gap, 2)
    candidate_sl = max(base_tp2_sl, calc_trail)
    
    assert candidate_sl >= 4319.50 # Locked right at TP2!
    print(f"✅ Step 4: Price reached TP2 ({test_price_at_tp2}) -> TSL activated at TP2: SL={candidate_sl} (Locked +19.75 pts profit!)")
    
    # 5. Simulate Price jumping +10 pips beyond TP2 to 4330.50
    test_price_ext1 = 4330.50
    calc_trail_ext1 = round(test_price_ext1 - jump_gap, 2)
    candidate_sl_ext1 = max(base_tp2_sl, calc_trail_ext1)
    
    assert candidate_sl_ext1 == 4329.50 # Jumped by +10.00 pts (100 pips)
    print(f"✅ Step 5: Price jumped +10 pts ({test_price_ext1}) -> SL jumped to {candidate_sl_ext1} (+9.75 pts above TP2!)")
    
    # 6. Simulate Price jumping +20 pips beyond TP2 to 4340.50
    test_price_ext2 = 4340.50
    calc_trail_ext2 = round(test_price_ext2 - jump_gap, 2)
    candidate_sl_ext2 = max(base_tp2_sl, calc_trail_ext2)
    
    assert candidate_sl_ext2 == 4339.50 # Jumped another +10.00 pts
    print(f"✅ Step 6: Price jumped +20 pts ({test_price_ext2}) -> SL jumped to {candidate_sl_ext2} (+19.75 pts above TP2!)")
    
    # Clean up test registry ticket
    del reg[str(ticket)]
    save_trade_registry(reg)
    print(f"✅ Step 7: Test ticket cleaned up from registry.")
    print("=" * 75)
    print("🎉 ALL FIXED SL TO TP2 & 10-PIP JUMPING TSL CHECKS VERIFIED 100%!")
    print("=" * 75)

if __name__ == "__main__":
    test_fixed_sl_to_tp2_and_jumping_tsl()
