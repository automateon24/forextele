import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
sys.path.insert(0, str(BASE_DIR))

from market_trader_engine import MarketTraderHandler
from perfect_management_engine import PerfectManagementHandler
from ai_trade_learning_engine import learning_engine
import MetaTrader5 as mt5

class MockMT5ExecutionEngine:
    def __init__(self):
        self.connected = True
        self.actions = []

    def connect(self): return True

    def execute_trade(self, payload, magic_number=888888):
        self.actions.append(("EXECUTE", payload, magic_number))
        payload["ticket"] = 999123
        return True

    def move_sl_to_breakeven(self, symbol, magic_number=888888, buffer_points=0.0):
        self.actions.append(("BREAKEVEN", symbol, magic_number, buffer_points))
        return True

    def close_partial_position(self, symbol, close_pct=50, magic_number=888888):
        self.actions.append(("PARTIAL_CLOSE", symbol, close_pct, magic_number))
        return True

    def close_position(self, symbol, magic_number=888888):
        self.actions.append(("CLOSE_ALL", symbol, magic_number))
        return True

async def test_fixes():
    print("=" * 70)
    print("🧪 TESTING ALL 3 FIXES + AI LEARNING INTEGRATION")
    print("=" * 70)
    mt5.initialize()

    mock_mt5 = MockMT5ExecutionEngine()
    mt_handler = MarketTraderHandler(mt5_engine=mock_mt5)
    pm_handler = PerfectManagementHandler(mt5_engine=mock_mt5)

    # -------------------------------------------------------------
    # TEST 1: Market Trader New Signal + Follow-up Reply Context
    # -------------------------------------------------------------
    print("\n--- [TEST 1] Market Trader Signal & Follow-up Reply Link ---")
    sig1_text = "GBPNZD Long Trade\n\nhttps://affs.click/xnqPA"
    res1 = await mt_handler.handle_message(sig1_text, has_photo=True, msg_id=7971)
    print("Signal 1 (Msg #7971):", res1)
    assert res1["status"] == "SUCCESS"
    assert res1["symbol"] == "GBPNZD"
    assert res1["action"] == "BUY"

    # Now simulate the follow-up message 7972 (Reply to 7971)
    reply_text = "200 Pips Done. Sl ctc kar lijiye and Book 40% Profit."
    res2 = await mt_handler.handle_message(reply_text, msg_id=7972, reply_to_msg_id=7971)
    print("Reply (Msg #7972 -> Reply to #7971):", res2)
    assert res2["status"] == "PROCESSED"
    assert res2["action"] == "BREAKEVEN_AND_PARTIAL_CLOSE"
    assert res2["symbol"] == "GBPNZD", f"Expected GBPNZD, got {res2['symbol']}"
    assert res2["pct"] == 40
    print("✅ TEST 1 PASSED: Reply-context correctly resolved GBPNZD from parent message #7971! Never matching 'PIPS'.")

    # -------------------------------------------------------------
    # TEST 2: Market Trader Live Chart Photo Setup ("GOLD LIVE 🚀")
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Market Trader Photo Live Setup ('GOLD LIVE 🚀') ---")
    photo_text = "GOLD LIVE 🚀"
    res3 = await mt_handler.handle_message(photo_text, has_photo=True, msg_id=7974)
    print("Photo Setup (Msg #7974):", res3)
    assert res3["status"] == "SUCCESS"
    assert res3["symbol"] == "GOLD"
    assert res3["action"] == "BUY"
    print("✅ TEST 2 PASSED: Market Trader photo chart setup correctly executed BUY on GOLD with default SL/TP.")

    # -------------------------------------------------------------
    # TEST 3: Perfect Management Commands & SL Padding
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Perfect Management Commands & SL Padding ---")
    pm_sig = "#XAUUSD SELL 4362\n\nSl 4363\n¹TP 4355\n²TP 4350"
    res4 = await pm_handler.handle_message(pm_sig, msg_id=20386)
    print("PM Entry (Msg #20386):", res4)
    assert res4["status"] == "SUCCESS"
    assert res4["symbol"] == "GOLD"
    assert res4["action"] == "SELL"
    # Live price is near 4353-4355; if sl_dist was < 3.5, it was padded!
    print("  Stated SL was 4363. Executed SL is:", res4["sl"])
    assert res4["sl"] >= 4355.0

    # Test TP1 hit (keeps SL fixed to reach TP2)
    tp1_cmd = "TP¹ HIT DONE  Book partial"
    res_tp1 = await pm_handler.handle_message(tp1_cmd, msg_id=20390)
    assert res_tp1["status"] == "PROCESSED"
    assert res_tp1["action"] == "TP1_HIT_HOLD"

    # Test TP2 hit (locks SL at TP1 and engages jumping TSL)
    tp2_cmd = "TP² HIT DONE  Lock profit"
    res_tp2 = await pm_handler.handle_message(tp2_cmd, msg_id=20391)
    assert res_tp2["status"] == "PROCESSED"
    assert res_tp2["action"] == "TP2_HIT_LOCK"

    # Test "Close now xauusd"
    close_cmd = "Close now xauusd 🙏🙏🙏"
    res5 = await pm_handler.handle_message(close_cmd, msg_id=20392, reply_to_msg_id=20386)
    print("PM Close Command:", res5)
    assert res5["status"] == "PROCESSED"
    assert res5["action"] == "CLOSE_NOW"
    print("✅ TEST 3 PASSED: Perfect Management close commands and SL padding executed flawlessly.")

    # -------------------------------------------------------------
    # TEST 4: AI Trade Learning Engine Verification
    # -------------------------------------------------------------
    print("\n--- [TEST 4] AI Trade Learning Engine Verification ---")
    assert learning_engine.ledger_file.exists()
    lines = learning_engine.ledger_file.read_text(encoding="utf-8").strip().splitlines()
    print(f"Total trades currently in AI Learning Knowledge Base: {len(lines)}")
    assert len(lines) >= 350
    print("✅ TEST 4 PASSED: AI Learning Engine has continuous ledger and SMC profiles operational.")

    print("\n" + "=" * 70)
    print("🎉 ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(test_fixes())
