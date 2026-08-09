import json
import logging
from pathlib import Path
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

BASE_DIR = Path(r"c:\anlyzeforex\forextele")

def test_pure_smc_liquidity_engine():
    print("=" * 85)
    print("  OUT-OF-THE-BOX PURE SMC LIQUIDITY SWEEP & ORDER BLOCK ENGINE BACKTEST")
    print("=" * 85)

    if not mt5.initialize():
        print("[ERROR] Could not initialize MT5.")
        return

    pairs = ["GOLD", "SILVER", "GBPJPY", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
    results = {}
    overall_trades = []

    for sym in pairs:
        tf = mt5.TIMEFRAME_M5 if "GOLD" in sym else mt5.TIMEFRAME_M15
        rates = mt5.copy_rates_from_pos(sym, tf, 0, 500)
        if rates is None or len(rates) < 100:
            continue

        df = pd.DataFrame(rates)
        df['time_dt'] = pd.to_datetime(df['time'], unit='s')
        info = mt5.symbol_info(sym)
        point = info.point if info else 0.0001

        df['tr'] = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift()).abs(), (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        df['bull_fvg'] = df['low'] > df['high'].shift(2)
        df['bear_fvg'] = df['high'] < df['low'].shift(2)

        sym_trades = []
        open_trade = None

        for i in range(50, len(df)-2):
            if open_trade is not None:
                c_high = df['high'].iloc[i]
                c_low = df['low'].iloc[i]
                pos_type = open_trade['type']
                entry_p = open_trade['entry']
                tp1_p = open_trade['tp1']
                tp2_p = open_trade['tp2']

                if pos_type == "BUY":
                    if not open_trade['tp1_hit'] and c_high >= tp1_p:
                        p1 = abs(tp1_p - entry_p) * 0.02 * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p1
                        open_trade['tp1_hit'] = True
                        open_trade['sl'] = entry_p # Breakeven

                    if c_low <= open_trade['sl']:
                        rem_lot = 0.03 if open_trade['tp1_hit'] else 0.05
                        p2 = (open_trade['sl'] - entry_p) * rem_lot * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p2
                        sym_trades.append(open_trade)
                        open_trade = None
                        continue

                    if c_high >= tp2_p and open_trade['tp1_hit']:
                        p2 = abs(tp2_p - entry_p) * 0.03 * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p2
                        sym_trades.append(open_trade)
                        open_trade = None
                        continue

                elif pos_type == "SELL":
                    if not open_trade['tp1_hit'] and c_low <= tp1_p:
                        p1 = abs(entry_p - tp1_p) * 0.02 * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p1
                        open_trade['tp1_hit'] = True
                        open_trade['sl'] = entry_p

                    if c_high >= open_trade['sl']:
                        rem_lot = 0.03 if open_trade['tp1_hit'] else 0.05
                        p2 = (entry_p - open_trade['sl']) * rem_lot * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p2
                        sym_trades.append(open_trade)
                        open_trade = None
                        continue

                    if c_low <= tp2_p and open_trade['tp1_hit']:
                        p2 = abs(entry_p - tp2_p) * 0.03 * (100 if "GOLD" in sym else 10000)
                        open_trade['profit'] += p2
                        sym_trades.append(open_trade)
                        open_trade = None
                        continue

            if open_trade is None:
                asian_high = df['high'].iloc[i-30:i-10].max()
                asian_low = df['low'].iloc[i-30:i-10].min()

                pr_curr = df['close'].iloc[i-1]
                atr = df['atr'].iloc[i-1] if not pd.isna(df['atr'].iloc[i-1]) else (10 * point)

                sig_type = None

                if df['low'].iloc[i-2] < asian_low and pr_curr > asian_low and df['bull_fvg'].iloc[i-5:i-1].any():
                    sig_type = "BUY"
                elif df['high'].iloc[i-2] > asian_high and pr_curr < asian_high and df['bear_fvg'].iloc[i-5:i-1].any():
                    sig_type = "SELL"

                if sig_type:
                    is_gold = "GOLD" in sym or "XAU" in sym
                    sl_dist = (atr * 1.2) if atr > 0 else (12.0 if is_gold else 0.0020)
                    tp1_dist = (atr * 2.5) if atr > 0 else (30.0 if is_gold else 0.0050)
                    tp2_dist = (atr * 5.0) if atr > 0 else (60.0 if is_gold else 0.0100)

                    entry_p = df['close'].iloc[i]
                    sl_p = entry_p - sl_dist if sig_type == "BUY" else entry_p + sl_dist
                    tp1_p = entry_p + tp1_dist if sig_type == "BUY" else entry_p - tp1_dist
                    tp2_p = entry_p + tp2_dist if sig_type == "BUY" else entry_p - tp2_dist

                    open_trade = {
                        "symbol": sym,
                        "type": sig_type,
                        "strat": "PURE_SMC_LIQUIDITY_SWEEP",
                        "entry": entry_p,
                        "sl": sl_p,
                        "tp1": tp1_p,
                        "tp2": tp2_p,
                        "tp1_hit": False,
                        "profit": 0.0
                    }

        wins = [t for t in sym_trades if t['profit'] > 0]
        losses = [t for t in sym_trades if t['profit'] <= 0]
        net_pnl = sum(t['profit'] for t in sym_trades)
        wr = (len(wins) / len(sym_trades) * 100) if sym_trades else 0.0

        results[sym] = {
            "trades": len(sym_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": wr,
            "net_profit": net_pnl
        }
        overall_trades.extend(sym_trades)

    total_t = len(overall_trades)
    total_w = len([t for t in overall_trades if t['profit'] > 0])
    total_l = len([t for t in overall_trades if t['profit'] <= 0])
    total_p = sum(t['profit'] for t in overall_trades)
    overall_wr = (total_w / total_t * 100) if total_t > 0 else 0.0

    print("\n" + "=" * 85)
    print("  PURE SMC LIQUIDITY SWEEP & ORDER BLOCK BACKTEST RESULTS")
    print("=" * 85)
    print(f"  TOTAL TRADES EXECUTED : {total_t}")
    print(f"  WINNING TRADES        : {total_w}")
    print(f"  LOSING TRADES         : {total_l}")
    print(f"  OVERALL WIN RATE      : {overall_wr:.1f}%")
    print(f"  TOTAL NET PROFIT      : +${total_p:.2f} USD")
    print("=" * 85)

    print(f"\n{'Symbol':<10} | {'Trades':<8} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | Net Profit ($ USD)")
    print("-" * 75)
    for sym, res in results.items():
        print(f"{sym:<10} | {res['trades']:<8} | {res['wins']:<6} | {res['losses']:<6} | {res['win_rate']:>5.1f}%     | +${res['net_profit']:>7.2f}")

    print("\n" + "=" * 85)

if __name__ == "__main__":
    test_pure_smc_liquidity_engine()
