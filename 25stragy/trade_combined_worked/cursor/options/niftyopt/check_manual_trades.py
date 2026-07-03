import sys
sys.path.insert(0, 'c:/cursor/options/niftyopt')
import pandas as pd

# Manual trade data
manual_trades = [
    {'date':'2026-04-30','dir':'Buy', 'entry':23820,'sl':23779,'exit':24019,'entry_t':'11:00','exit_t':'15:30','pnl':12935,'logic':'Day Low green candle'},
    {'date':'2026-05-04','dir':'Sell','entry':24232,'sl':24262,'exit':24061,'entry_t':'11:35','exit_t':'13:25','pnl':11115,'logic':'Day High red candle'},
    {'date':'2026-05-05','dir':'Buy', 'entry':23952,'sl':23893,'exit':23893,'entry_t':'11:15','exit_t':'11:50','pnl':-3835,'logic':'Day Low green candle - SL hit'},
    {'date':'2026-05-05','dir':'Buy', 'entry':23919,'sl':23862,'exit':24072,'entry_t':'12:10','exit_t':'13:10','pnl':9945,'logic':'Re-entry Day Low green candle'},
    {'date':'2026-05-06','dir':'Buy', 'entry':24098,'sl':24053,'exit':24053,'entry_t':'11:10','exit_t':'12:25','pnl':-2925,'logic':'Day Low green candle - SL hit'},
    {'date':'2026-05-06','dir':'Buy', 'entry':24038,'sl':23977,'exit':24250,'entry_t':'13:10','exit_t':'14:25','pnl':13780,'logic':'Re-entry Day Low green - Target Day High'},
    {'date':'2026-05-07','dir':'Buy', 'entry':24305,'sl':24264,'exit':24423,'entry_t':'11:50','exit_t':'12:40','pnl':7670,'logic':'Day Low green - Target Day High'},
    {'date':'2026-05-08','dir':'Buy', 'entry':24148,'sl':24106,'exit':24215,'entry_t':'14:05','exit_t':'15:00','pnl':4355,'logic':'Day Low green - EOD exit'},
    {'date':'2026-05-11','dir':'Buy', 'entry':23871,'sl':23825,'exit':23986,'entry_t':'10:25','exit_t':'13:35','pnl':7475,'logic':'Day Low green - Target Day High'},
    {'date':'2026-05-11','dir':'Sell','entry':23966,'sl':24017,'exit':23845,'entry_t':'14:00','exit_t':'15:05','pnl':7865,'logic':'Day High red + 1H RSI<40 - Target Day Low'},
    {'date':'2026-05-12','dir':'Buy', 'entry':23628,'sl':23576,'exit':23576,'entry_t':'10:45','exit_t':'11:05','pnl':-3380,'logic':'Day Low green - SL hit'},
    {'date':'2026-05-13','dir':'Sell','entry':23481,'sl':23529,'exit':23529,'entry_t':'11:50','exit_t':'12:55','pnl':-3120,'logic':'Day High red - SL hit'},
    {'date':'2026-05-14','dir':'Buy', 'entry':23473,'sl':23406,'exit':23589,'entry_t':'10:55','exit_t':'11:35','pnl':7540,'logic':'Day Low green - Target Day High'},
]

print("="*80)
print("MANUAL TRADE ANALYSIS")
print("="*80)
total = sum(t['pnl'] for t in manual_trades)
wins = [t for t in manual_trades if t['pnl'] > 0]
losses = [t for t in manual_trades if t['pnl'] < 0]
print(f"Total trades: {len(manual_trades)}")
print(f"Wins: {len(wins)} | Losses: {len(losses)} | Win rate: {100*len(wins)//len(manual_trades)}%")
print(f"Total PnL: Rs {total:,.0f}")
print(f"Avg win: Rs {sum(t['pnl'] for t in wins)/len(wins):,.0f}")
print(f"Avg loss: Rs {sum(t['pnl'] for t in losses)/len(losses):,.0f}")
print(f"RR ratio: {abs(sum(t['pnl'] for t in wins)/len(wins)) / abs(sum(t['pnl'] for t in losses)/len(losses)):.2f}")
print()

# Compute SL % and target % per trade
print("Per-trade SL/Target analysis:")
print(f"{'Date':<12} {'Dir':<5} {'Entry':>7} {'SL':>7} {'Exit':>7} {'SL%':>6} {'Move%':>6} {'PnL':>9}")
print("-"*70)
for t in manual_trades:
    sl_pct = abs(t['entry'] - t['sl']) / t['entry'] * 100
    move_pct = abs(t['exit'] - t['entry']) / t['entry'] * 100
    print(f"{t['date']:<12} {t['dir']:<5} {t['entry']:>7} {t['sl']:>7} {t['exit']:>7} {sl_pct:>5.2f}% {move_pct:>5.2f}% {t['pnl']:>9,.0f}")

print()
print("KEY PATTERNS:")
sl_pcts = [abs(t['entry']-t['sl'])/t['entry']*100 for t in manual_trades]
print(f"  SL avg: {sum(sl_pcts)/len(sl_pcts):.2f}% | min: {min(sl_pcts):.2f}% | max: {max(sl_pcts):.2f}%")
buy_trades = [t for t in manual_trades if t['dir']=='Buy']
sell_trades = [t for t in manual_trades if t['dir']=='Sell']
print(f"  Buy (CE): {len(buy_trades)} trades, win={sum(1 for t in buy_trades if t['pnl']>0)}")
print(f"  Sell (PE): {len(sell_trades)} trades, win={sum(1 for t in sell_trades if t['pnl']>0)}")
print()
print("ENTRY LOGIC RULES:")
print("  CE (Buy): Spot touches day low + green candle confirmation")
print("  PE (Sell): Spot touches day high + red candle confirmation")  
print("  SL: Low/High +/- 20 points on spot (not % based)")
print("  Target: Opposite day extreme (day_high for buys, day_low for sells)")
print("  Re-entry: Allowed after SL hit if setup re-forms")
print("  Special: 1H RSI < 40 for additional PE entries at day high")
