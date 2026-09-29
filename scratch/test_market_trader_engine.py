import asyncio
import sys
from market_trader_engine import MarketTraderHandler

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

async def test():
    handler = MarketTraderHandler()
    print("Testing MarketTraderHandler...")
    
    # Test 1: New Trade Chart Caption
    res1 = await handler.handle_message("AUDJPY Long Trade\n\nCheck chart setup", has_photo=True)
    print("Test 1 Result (AUDJPY Long):", res1)
    
    # Test 2: Breakeven / CTC Follow-up
    res2 = await handler.handle_message("AUDJPY sl ctc kar lijiye and Book 60% Profit.", has_photo=False)
    print("Test 2 Result (Breakeven):", res2)
    
    # Test 3: Profit Book Follow-up
    res3 = await handler.handle_message("AUDJPY Book 100% Profit. 300 Pips Done.", has_photo=False)
    print("Test 3 Result (Book):", res3)
    
    # Test 4: Text Alert
    res4 = await handler.handle_message("GOLD BUY - 4388\nSL - 90 PIPS\nTARGET - 250 PIPS\nWAIT FOR CONFIRMATION", has_photo=False)
    print("Test 4 Result (Gold Text):", res4)

if __name__ == "__main__":
    asyncio.run(test())
