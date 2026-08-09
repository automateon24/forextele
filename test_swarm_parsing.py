import asyncio
from swarm_engine import OllamaSwarmEngine
import json

async def test():
    engine = OllamaSwarmEngine()
    engine.mt5_engine.execute_trade = lambda x: True
    
    msg1 = "👉 XAUUSD Sell 4029-4033📉"
    msg2 = "XAUUSD SELL LIMIT 4026.5\nSL: 4036.5\nTP: 4006.5\n--Trade by William"
    msg3 = "XAUUSD SELL NOW @ 4028\n\nTP-1 4018\nTP-2 4008\nTP-3 3998\n\nCONFIRM SL👇"
    
    print("--- MSG 1 ---")
    res1 = await engine.process_telegram_signal(msg1, "MESSY FOREX")
    print(json.dumps(res1, indent=2))
    
    print("\n--- MSG 2 ---")
    res2 = await engine.process_telegram_signal(msg2, "SureShot GOLD (VIP)")
    print(json.dumps(res2, indent=2))
    
    print("\n--- MSG 3 ---")
    res3 = await engine.process_telegram_signal(msg3, "RIAOGOLDFOREX")
    print(json.dumps(res3, indent=2))

if __name__ == "__main__":
    asyncio.run(test())
