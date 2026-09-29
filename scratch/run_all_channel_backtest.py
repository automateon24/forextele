import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")

# Connect MT5
if not mt5.initialize():
    print("MT5 initialization failed!")
    exit(1)

# Symbol normalization & pip multipliers
SYMBOL_MAP = {
    "XAUUSD": "GOLD", "GOLD": "GOLD", "XAU": "GOLD",
    "BTCUSD": "BTCUSD", "BTCUSDT": "BTCUSD", "BITCOIN": "BTCUSD", "BTC": "BTCUSD",
    "GBPNZD": "GBPNZD", "GBPJPY": "GBPJPY", "USDJPY": "USDJPY",
    "AUDJPY": "AUDJPY", "GBPCAD": "GBPCAD", "EURCAD": "EURCAD",
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDCAD": "USDCAD",
    "NZDUSD": "NZDUSD", "USDCHF": "USDCHF", "EURJPY": "EURJPY",
    "US30": "US30Cash", "US30CASH": "US30Cash", "DJ30": "US30Cash"
}

def get_pip_size(symbol):
    if symbol == "GOLD":
        return 0.10  # 1 pip = $0.10 price change (10 points)
    elif symbol == "BTCUSD":
        return 1.0   # $1 change
    elif "JPY" in symbol:
        return 0.01  # 2nd decimal
    elif symbol == "US30Cash":
        return 1.0
    else:
        return 0.0001 # 4th decimal for standard forex

def calc_pnl_usd(symbol, action, pnl_pips, lot_size=0.01):
    """Calculate exact USD PnL for 0.01 lot on XM Global MT5."""
    if symbol == "GOLD":
        # 0.01 lot = 1.0 oz. 1 pip ($0.10 move) = $0.10 USD
        return pnl_pips * 0.10
    elif symbol == "BTCUSD":
        # 0.01 lot = 0.01 BTC. $1 move = $0.01 USD
        return pnl_pips * 0.01
    elif "JPY" in symbol:
        # 0.01 lot = 1,000 units. 1 pip (0.01 JPY) * 1000 = 10 JPY = ~$0.065 USD
        return pnl_pips * 0.065
    elif symbol == "US30Cash":
        # 0.01 contract * 1 pt = $0.01 USD
        return pnl_pips * 0.01
    else:
        # Standard Forex (EURUSD, GBPNZD, USDCAD, etc.) ~ $0.08 - $0.10 per pip on 0.01
        return pnl_pips * 0.085

# Cache for M1 price data
M1_CACHE = {}

def get_m1_data(symbol):
    if symbol in M1_CACHE:
        return M1_CACHE[symbol]
    mt5.symbol_select(symbol, True)
    start = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, now)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('datetime', inplace=True)
    M1_CACHE[symbol] = df
    return df

def simulate_trade(symbol, action, sig_time, stated_entry=None, stated_sl=None, stated_tps=None):
    """
    Simulates trade execution from sig_time onwards using actual M1 bars.
    Returns:
      outcome: 'WIN_TP1', 'WIN_TP2', 'WIN_TP3', 'LOSS_SL', 'OPEN'
      pnl_pips: realized pips under conservative TP1 / BE / SL management
      max_favorable_pips: maximum profit reached
      max_adverse_pips: maximum drawdown experienced
      entry_price: actual fill price
      exit_price: price at exit
      duration_mins: minutes held
    """
    df = get_m1_data(symbol)
    if df is None or len(df) == 0:
        return None

    # Slice from signal time onwards
    df_after = df.loc[df.index >= sig_time]
    if len(df_after) == 0:
        # If signal time is slightly ahead or no bars yet, take last 5 bars
        df_after = df.iloc[-10:]
        if len(df_after) == 0:
            return None

    pip_size = get_pip_size(symbol)
    market_open_price = df_after['open'].iloc[0]
    
    # Fill price: use stated entry if realistic (within 10 pips of market open), else market price
    if stated_entry and abs(stated_entry - market_open_price) <= (10 * pip_size):
        entry_price = stated_entry
    else:
        entry_price = market_open_price

    # Determine SL and TPs if not stated
    if not stated_sl:
        default_sl_dist = 40 * pip_size if symbol == "GOLD" else (30 * pip_size if "JPY" in symbol else 35 * pip_size)
        sl_price = entry_price - default_sl_dist if action == "BUY" else entry_price + default_sl_dist
    else:
        sl_price = stated_sl

    if not stated_tps or len(stated_tps) == 0:
        tp1_dist = 30 * pip_size if symbol == "GOLD" else 25 * pip_size
        tp2_dist = 60 * pip_size if symbol == "GOLD" else 50 * pip_size
        tp3_dist = 100 * pip_size if symbol == "GOLD" else 80 * pip_size
        tps = [
            entry_price + tp1_dist if action == "BUY" else entry_price - tp1_dist,
            entry_price + tp2_dist if action == "BUY" else entry_price - tp2_dist,
            entry_price + tp3_dist if action == "BUY" else entry_price - tp3_dist
        ]
    else:
        tps = sorted(stated_tps) if action == "BUY" else sorted(stated_tps, reverse=True)

    tp1 = tps[0]
    tp2 = tps[1] if len(tps) > 1 else (entry_price + 2 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 2 * abs(tp1 - entry_price))
    tp3 = tps[2] if len(tps) > 2 else (entry_price + 3 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 3 * abs(tp1 - entry_price))

    max_fav_dist = 0.0
    max_adv_dist = 0.0
    hit_tp1 = False
    hit_tp2 = False
    hit_tp3 = False
    hit_sl = False
    exit_price = entry_price
    outcome = "OPEN"
    hold_mins = 0

    current_sl = sl_price

    for idx, (bar_time, row) in enumerate(df_after.iterrows()):
        high = row['high']
        low = row['low']
        close = row['close']
        hold_mins = idx + 1

        if action == "BUY":
            fav = high - entry_price
            adv = entry_price - low
            max_fav_dist = max(max_fav_dist, fav)
            max_adv_dist = max(max_adv_dist, adv)

            # Check SL hit
            if low <= current_sl:
                hit_sl = True
                exit_price = current_sl
                outcome = "LOSS_SL" if not hit_tp1 else "BREAKEVEN"
                break

            # Check TP1 hit
            if not hit_tp1 and high >= tp1:
                hit_tp1 = True
                current_sl = entry_price  # Move SL to breakeven after TP1!
                outcome = "WIN_TP1"
                exit_price = tp1

            # Check TP2 hit
            if hit_tp1 and not hit_tp2 and high >= tp2:
                hit_tp2 = True
                outcome = "WIN_TP2"
                exit_price = tp2
                current_sl = tp1  # Trail SL to TP1

            # Check TP3 hit
            if hit_tp2 and not hit_tp3 and high >= tp3:
                hit_tp3 = True
                outcome = "WIN_TP3"
                exit_price = tp3
                break

        else: # SELL
            fav = entry_price - low
            adv = high - entry_price
            max_fav_dist = max(max_fav_dist, fav)
            max_adv_dist = max(max_adv_dist, adv)

            # Check SL hit
            if high >= current_sl:
                hit_sl = True
                exit_price = current_sl
                outcome = "LOSS_SL" if not hit_tp1 else "BREAKEVEN"
                break

            # Check TP1 hit
            if not hit_tp1 and low <= tp1:
                hit_tp1 = True
                current_sl = entry_price  # Move SL to breakeven after TP1!
                outcome = "WIN_TP1"
                exit_price = tp1

            # Check TP2 hit
            if hit_tp1 and not hit_tp2 and low <= tp2:
                hit_tp2 = True
                outcome = "WIN_TP2"
                exit_price = tp2
                current_sl = tp1  # Trail SL to TP1

            # Check TP3 hit
            if hit_tp2 and not hit_tp3 and low <= tp3:
                hit_tp3 = True
                outcome = "WIN_TP3"
                exit_price = tp3
                break

    if outcome == "OPEN":
        exit_price = df_after['close'].iloc[-1]

    # Calculate realized pips
    if action == "BUY":
        realized_dist = exit_price - entry_price
    else:
        realized_dist = entry_price - exit_price

    pnl_pips = round(realized_dist / pip_size, 1)
    mfe_pips = round(max_fav_dist / pip_size, 1)
    mae_pips = round(max_adv_dist / pip_size, 1)
    pnl_usd = round(calc_pnl_usd(symbol, action, pnl_pips), 2)

    return {
        "symbol": symbol,
        "action": action,
        "entry_price": round(entry_price, 4),
        "exit_price": round(exit_price, 4),
        "outcome": outcome,
        "pnl_pips": pnl_pips,
        "pnl_usd": pnl_usd,
        "mfe_pips": mfe_pips,
        "mae_pips": mae_pips,
        "hold_mins": hold_mins
    }

def run_all_channel_backtest():
    scrape_file = BASE_DIR / "scratch" / "full_telegram_scrape_today.json"
    with open(scrape_file, encoding='utf-8') as f:
        data = json.load(f)

    all_signals_to_test = []

    # 1. From scraped channels
    for ch_name, ch_data in data.get("channels", {}).items():
        account = ch_data.get("account", "Account 2")
        for s in ch_data.get("signals", []):
            sig = s.get("signal", {})
            action = sig.get("action")
            raw_symbols = sig.get("symbols", [])
            if not action or not raw_symbols:
                continue

            # Parse timestamp
            time_str = s.get("time") # '2026-09-21 10:34:11 UTC'
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
            except Exception:
                continue

            for sym_raw in raw_symbols:
                sym_norm = SYMBOL_MAP.get(sym_raw.upper(), None)
                if not sym_norm:
                    continue

                all_signals_to_test.append({
                    "channel": ch_name,
                    "account": account,
                    "msg_id": s.get("id"),
                    "time": dt,
                    "symbol": sym_norm,
                    "action": action,
                    "entry": sig.get("entry"),
                    "sl": sig.get("sl"),
                    "tps": sig.get("tps", []),
                    "raw_text": s.get("text", "")[:100]
                })

    # 2. Add Market Trader's specific signals that had photos or specific setups
    # GBPNZD Long Trade at 00:51 UTC
    # BTCUSDT Short Trade at 10:34 UTC
    # Market Trader Gold live trade at 08:22 UTC
    all_signals_to_test.append({
        "channel": "Market Trader Crypto Forex",
        "account": "Account 2",
        "msg_id": 7974,
        "time": datetime(2026, 9, 21, 8, 22, 15, tzinfo=timezone.utc),
        "symbol": "GOLD",
        "action": "BUY",
        "entry": 4350.0,
        "sl": 4338.0,
        "tps": [4355.0, 4362.0, 4372.0],
        "raw_text": "GOLD LIVE 🚀 (Photo Chart MT 30 Setup)"
    })

    # 3. Add Perfect Management's clean signals
    all_signals_to_test.append({
        "channel": "Perfect Management",
        "account": "Account 2",
        "msg_id": 20386,
        "time": datetime(2026, 9, 21, 6, 20, 27, tzinfo=timezone.utc),
        "symbol": "GOLD",
        "action": "SELL",
        "entry": 4355.0,
        "sl": 4368.0,
        "tps": [4351.0, 4347.0, 4343.0, 4339.0, 4335.0, 4331.0],
        "raw_text": "#XAUUSD SELL 4355 SL 4368 TP 4351..4331"
    })
    all_signals_to_test.append({
        "channel": "Perfect Management",
        "account": "Account 2",
        "msg_id": 20393,
        "time": datetime(2026, 9, 21, 11, 58, 36, tzinfo=timezone.utc),
        "symbol": "GOLD",
        "action": "BUY",
        "entry": 4363.0,
        "sl": 4352.0,
        "tps": [4367.0, 4371.0, 4373.0, 4377.0, 4381.0, 4383.0],
        "raw_text": "#XAUUSD BUY 4363 SL 4352 TP 4367..4383"
    })
    all_signals_to_test.append({
        "channel": "Perfect Management",
        "account": "Account 2",
        "msg_id": 20399,
        "time": datetime(2026, 9, 21, 13, 36, 3, tzinfo=timezone.utc),
        "symbol": "GOLD",
        "action": "SELL",
        "entry": 4355.0,
        "sl": 4368.0,
        "tps": [4351.0, 4347.0, 4343.0, 4339.0, 4335.0, 4331.0],
        "raw_text": "#XAUUSD SELL 4355 SL 4368 TP 4351..4331"
    })

    print(f"Total trade signals to backtest: {len(all_signals_to_test)}")

    results = []
    channel_stats = defaultdict(lambda: {
        "account": "", "signals": 0, "wins": 0, "breakevens": 0, "losses": 0,
        "total_pips": 0.0, "total_usd": 0.0, "max_mfe": 0.0, "symbols": set(), "trades": []
    })

    for s in all_signals_to_test:
        sim = simulate_trade(
            s["symbol"], s["action"], s["time"],
            stated_entry=s["entry"], stated_sl=s["sl"], stated_tps=s["tps"]
        )
        if not sim:
            continue

        ch = s["channel"]
        acc = s["account"]
        st = channel_stats[ch]
        st["account"] = acc
        st["signals"] += 1
        st["symbols"].add(s["symbol"])
        st["total_pips"] += sim["pnl_pips"]
        st["total_usd"] += sim["pnl_usd"]
        st["max_mfe"] = max(st["max_mfe"], sim["mfe_pips"])

        if "WIN" in sim["outcome"]:
            st["wins"] += 1
        elif sim["outcome"] == "BREAKEVEN":
            st["breakevens"] += 1
        else:
            st["losses"] += 1

        trade_record = {
            "channel": ch,
            "account": acc,
            "time": s["time"].strftime('%H:%M:%S UTC'),
            "symbol": s["symbol"],
            "action": s["action"],
            "entry": sim["entry_price"],
            "exit": sim["exit_price"],
            "outcome": sim["outcome"],
            "pips": sim["pnl_pips"],
            "usd": sim["pnl_usd"],
            "mfe_pips": sim["mfe_pips"],
            "mae_pips": sim["mae_pips"],
            "raw": s["raw_text"]
        }
        st["trades"].append(trade_record)
        results.append(trade_record)

    # Convert to leaderboard
    leaderboard = []
    for ch, st in channel_stats.items():
        total = st["signals"]
        if total == 0:
            continue
        win_rate = (st["wins"] / total) * 100
        leaderboard.append({
            "channel": ch,
            "account": st["account"],
            "signals": total,
            "wins": st["wins"],
            "be": st["breakevens"],
            "losses": st["losses"],
            "win_rate": round(win_rate, 1),
            "total_pips": round(st["total_pips"], 1),
            "total_usd": round(st["total_usd"], 2),
            "symbols": list(st["symbols"]),
            "trades": st["trades"]
        })

    leaderboard = sorted(leaderboard, key=lambda x: x["total_usd"], reverse=True)

    # Save to json and csv
    out_json = BASE_DIR / "scratch" / "comprehensive_channel_backtest_today.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tested_signals": len(results),
            "total_channels": len(leaderboard),
            "leaderboard": leaderboard
        }, f, indent=2, ensure_ascii=False)

    df_res = pd.DataFrame(results)
    df_res.to_csv(BASE_DIR / "scratch" / "comprehensive_signals_backtest_today.csv", index=False)

    print("\n" + "=" * 90)
    print("🏆 FULL DAY BACKTEST LEADERBOARD — ALL TELEGRAM CHANNELS (ACCOUNTS 1 & 2)")
    print("=" * 90)
    print(f"{'Rank':>3} {'Channel':<38} {'Account':<10} {'Sigs':>5} {'W/BE/L':>8} {'Win%':>6} {'Pips':>8} {'Net USD (0.01)':>15}")
    print("-" * 90)

    for rank, item in enumerate(leaderboard[:30], 1):
        w_str = f"{item['wins']}/{item['be']}/{item['losses']}"
        print(f"{rank:>3} {item['channel'][:37]:<38} {item['account']:<10} {item['signals']:>5} {w_str:>8} {item['win_rate']:>5.1f}% {item['total_pips']:>8.1f}p ${item['total_usd']:>14.2f}")

    print("-" * 90)
    total_all_usd = sum(x["total_usd"] for x in leaderboard)
    total_all_pips = sum(x["total_pips"] for x in leaderboard)
    total_all_sigs = sum(x["signals"] for x in leaderboard)
    total_all_wins = sum(x["wins"] for x in leaderboard)
    print(f"{'TOTAL':<52} {total_all_sigs:>5} {total_all_wins} wins | {total_all_pips:>8.1f}p | ${total_all_usd:>14.2f}")

if __name__ == '__main__':
    run_all_channel_backtest()
