import sys
from pathlib import Path
BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
mt5.initialize()

from autonomous_ai_market_scanner import AutonomousAIMarketScanner

scanner = AutonomousAIMarketScanner()
print("=== SCANNER INITIALIZATION TEST ===")
print("Symbols monitored:", scanner.symbols)
print("Cooldown minutes:", scanner.cooldown_minutes)
print("Max daily trades:", scanner.max_daily_trades)
print("Learned channel profiles count:", len(scanner.learned_rules))

print("\n=== LIVE MARKET CONTEXT EVALUATION ===")
for sym in scanner.symbols:
    ctx = scanner.analyze_symbol(sym)
    print(f"Symbol: {sym}")
    print(f"  Live Bid: {ctx.get('live_bid')} | Live Ask: {ctx.get('live_ask')} | Spread: {ctx.get('spread')}")
    print(f"  H1 Trend: {ctx.get('h1_trend')}")
    print(f"  M15 ATR14: {ctx.get('atr14'):.2f}")
    print(f"  M5 RSI: {ctx.get('rsi')}")
    print(f"  Sweep High: {ctx.get('sweep_high')} | Sweep Low: {ctx.get('sweep_low')}")
    print(f"  Bull FVG: {ctx.get('has_bull_fvg')} | Bear FVG: {ctx.get('has_bear_fvg')}")
    setup = scanner.evaluate_signals(ctx)
    if setup:
        print(f"  🎯 RESULT: APPROVED -> {setup['action']} {setup['pattern']} (Confidence: {setup['confidence']:.2f})")
        print(f"     Reason: {setup['reason']}")
    else:
        print("  🛡️ RESULT: BLOCKED / WAITING (Protected by Macro Trend / Volatility Gate)")
    print("-" * 50)
