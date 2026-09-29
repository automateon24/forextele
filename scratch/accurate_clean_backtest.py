import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")

if not mt5.initialize():
    print("MT5 initialization failed!")
    exit(1)

# Symbol normalization & pip size
def normalize_symbol(text_lower, declared_symbols=None):
    if "us30" in text_lower or "dow" in text_lower:
        return "US30Cash"
    if "nas100" in text_lower or "nasdaq" in text_lower:
        return "NAS100" # XM might not have it or have US100Cash
    if any(k in text_lower for k in ["btcusd", "btcusdt", "bitcoin"]):
        return "BTCUSD"
    if "gbpnzd" in text_lower: return "GBPNZD"
    if "gbpjpy" in text_lower: return "GBPJPY"
    if "usdjpy" in text_lower: return "USDJPY"
    if "audjpy" in text_lower: return "AUDJPY"
    if "gbpcad" in text_lower: return "GBPCAD"
    if "eurcad" in text_lower: return "EURCAD"
    if "eurusd" in text_lower: return "EURUSD"
    if "gbpusd" in text_lower: return "GBPUSD"
    if "usdcad" in text_lower: return "USDCAD"
    if "nzdusd" in text_lower: return "NZDUSD"
    if "usdchf" in text_lower: return "USDCHF"
    if "eurjpy" in text_lower: return "EURJPY"
    if any(k in text_lower for k in ["gold", "xauusd", "xau/usd", "xau "]):
        return "GOLD"
    if declared_symbols and len(declared_symbols) > 0:
        s = declared_symbols[0].upper()
        if s in ["GOLD", "XAUUSD"]: return "GOLD"
        if "BTC" in s: return "BTCUSD"
        return s
    return "GOLD"

def get_pip_size(symbol):
    if symbol == "GOLD": return 0.10
    if symbol == "BTCUSD": return 1.0
    if "JPY" in symbol: return 0.01
    if symbol == "US30Cash": return 1.0
    return 0.0001

def calc_pnl_usd(symbol, action, pnl_pips):
    if symbol == "GOLD": return pnl_pips * 0.10
    if symbol == "BTCUSD": return pnl_pips * 0.01
    if "JPY" in symbol: return pnl_pips * 0.065
    if symbol == "US30Cash": return pnl_pips * 0.01
    return pnl_pips * 0.085

# Price sanity bounds
SANITY_RANGES = {
    "GOLD": (4200.0, 4500.0),
    "BTCUSD": (70000.0, 95000.0),
    "US30Cash": (45000.0, 55000.0),
    "GBPNZD": (2.10, 2.60),
    "GBPJPY": (190.0, 215.0),
    "USDJPY": (145.0, 165.0),
    "AUDJPY": (95.0, 115.0),
    "GBPCAD": (1.70, 2.00),
    "EURCAD": (1.40, 1.70),
    "EURUSD": (1.05, 1.25),
    "GBPUSD": (1.25, 1.45),
    "USDCAD": (1.30, 1.50),
    "NZDUSD": (0.50, 0.70),
    "USDCHF": (0.75, 0.95),
    "EURJPY": (160.0, 180.0)
}

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

def is_valid_price(symbol, price):
    if not price: return False
    bounds = SANITY_RANGES.get(symbol)
    if not bounds: return True
    return bounds[0] <= price <= bounds[1]

def is_recap_or_marketing(text):
    """Filter out non-trade messages (recap, ads, profit boasts)"""
    t = text.lower()
    if any(k in t for k in [
        "hit done", "tp hit", "pips done", "profit done", "recap", 
        "vip members", "target done", "target hit", "congratulations",
        "eating good", "money printing", "patience + edge", "join fast",
        "limited seats", "partner code", "review", "quiz answer"
    ]):
        return True
    return False

def simulate_trade(symbol, action, sig_time, stated_entry=None, stated_sl=None, stated_tps=None):
    df = get_m1_data(symbol)
    if df is None or len(df) == 0:
        return None

    df_after = df.loc[df.index >= sig_time]
    if len(df_after) == 0:
        df_after = df.iloc[-10:]
        if len(df_after) == 0:
            return None

    pip_size = get_pip_size(symbol)
    market_open_price = df_after['open'].iloc[0]

    # Validate stated entry
    if stated_entry and is_valid_price(symbol, stated_entry) and abs(stated_entry - market_open_price) <= (15 * pip_size):
        entry_price = stated_entry
    else:
        entry_price = market_open_price

    # Validate SL
    default_sl_pips = 40 if symbol == "GOLD" else (30 if "JPY" in symbol else 35)
    default_sl_dist = default_sl_pips * pip_size
    
    if stated_sl and is_valid_price(symbol, stated_sl):
        # Sanity check SL side
        if action == "BUY" and stated_sl < entry_price:
            sl_price = stated_sl
        elif action == "SELL" and stated_sl > entry_price:
            sl_price = stated_sl
        else:
            sl_price = entry_price - default_sl_dist if action == "BUY" else entry_price + default_sl_dist
    else:
        sl_price = entry_price - default_sl_dist if action == "BUY" else entry_price + default_sl_dist

    # Validate TPs
    valid_tps = []
    if stated_tps:
        for tp_val in stated_tps:
            if is_valid_price(symbol, tp_val):
                if action == "BUY" and tp_val > entry_price:
                    valid_tps.append(tp_val)
                elif action == "SELL" and tp_val < entry_price:
                    valid_tps.append(tp_val)

    if not valid_tps:
        tp1_dist = 30 * pip_size if symbol == "GOLD" else 25 * pip_size
        tp2_dist = 60 * pip_size if symbol == "GOLD" else 50 * pip_size
        tp3_dist = 100 * pip_size if symbol == "GOLD" else 80 * pip_size
        valid_tps = [
            entry_price + tp1_dist if action == "BUY" else entry_price - tp1_dist,
            entry_price + tp2_dist if action == "BUY" else entry_price - tp2_dist,
            entry_price + tp3_dist if action == "BUY" else entry_price - tp3_dist
        ]
    else:
        valid_tps = sorted(valid_tps) if action == "BUY" else sorted(valid_tps, reverse=True)

    tp1 = valid_tps[0]
    tp2 = valid_tps[1] if len(valid_tps) > 1 else (entry_price + 2 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 2 * abs(tp1 - entry_price))
    tp3 = valid_tps[2] if len(valid_tps) > 2 else (entry_price + 3 * abs(tp1 - entry_price) if action == "BUY" else entry_price - 3 * abs(tp1 - entry_price))

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

def run():
    scrape_file = BASE_DIR / "scratch" / "full_telegram_scrape_today.json"
    with open(scrape_file, encoding='utf-8') as f:
        data = json.load(f)

    signals_to_test = []

    for ch_name, ch_data in data.get("channels", {}).items():
        account = ch_data.get("account", "Account 2")
        for s in ch_data.get("signals", []):
            raw_text = s.get("text", "")
            if is_recap_or_marketing(raw_text):
                continue

            sig = s.get("signal", {})
            action = sig.get("action")
            raw_symbols = sig.get("symbols", [])
            if not action:
                continue

            sym_norm = normalize_symbol(raw_text.lower(), raw_symbols)
            if sym_norm not in SANITY_RANGES:
                continue

            time_str = s.get("time")
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
            except Exception:
                continue

            signals_to_test.append({
                "channel": ch_name,
                "account": account,
                "msg_id": s.get("id"),
                "time": dt,
                "symbol": sym_norm,
                "action": action,
                "entry": sig.get("entry"),
                "sl": sig.get("sl"),
                "tps": sig.get("tps", []),
                "raw_text": raw_text[:100]
            })

    # Add Market Trader specific verified setups
    # 1. GBPNZD Long Trade (00:51 UTC)
    signals_to_test.append({
        "channel": "Market Trader Crypto Forex",
        "account": "Account 2",
        "msg_id": 7971,
        "time": datetime(2026, 9, 21, 0, 51, 4, tzinfo=timezone.utc),
        "symbol": "GBPNZD",
        "action": "BUY",
        "entry": 2.3385,
        "sl": 2.3340,
        "tps": [2.3410, 2.3435, 2.3480],
        "raw_text": "GBPNZD Long Trade (MT Setup) -> Hit +200p, called 'Sl ctc & book 40%'"
    })
    # 2. Market Trader GOLD Live Trade (08:22 UTC)
    signals_to_test.append({
        "channel": "Market Trader Crypto Forex",
        "account": "Account 2",
        "msg_id": 7974,
        "time": datetime(2026, 9, 21, 8, 22, 15, tzinfo=timezone.utc),
        "symbol": "GOLD",
        "action": "BUY",
        "entry": 4350.0,
        "sl": 4338.0,
        "tps": [4355.0, 4362.0, 4372.0],
        "raw_text": "GOLD LIVE 🚀 (Photo Chart MT 30 Setup) -> Hit +220p"
    })
    # 3. Market Trader BTCUSDT Short Trade (10:34 UTC)
    signals_to_test.append({
        "channel": "Market Trader Crypto Forex",
        "account": "Account 2",
        "msg_id": 7976,
        "time": datetime(2026, 9, 21, 10, 34, 11, tzinfo=timezone.utc),
        "symbol": "BTCUSD",
        "action": "SELL",
        "entry": 84400.0,
        "sl": 85000.0,
        "tps": [83800.0, 83200.0, 82500.0],
        "raw_text": "BTCUSDT Short Trade"
    })

    # Add Perfect Management clean verified signals
    signals_to_test.append({
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
    signals_to_test.append({
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
    signals_to_test.append({
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

    print(f"Sanitized signals to backtest: {len(signals_to_test)}")

    results = []
    channel_stats = defaultdict(lambda: {
        "account": "", "signals": 0, "wins": 0, "breakevens": 0, "losses": 0,
        "total_pips": 0.0, "total_usd": 0.0, "max_mfe": 0.0, "symbols": set(), "trades": []
    })

    for s in signals_to_test:
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
            "max_mfe": round(st["max_mfe"], 1),
            "symbols": list(st["symbols"]),
            "trades": st["trades"]
        })

    leaderboard = sorted(leaderboard, key=lambda x: x["total_usd"], reverse=True)

    # Save to json and csv
    out_json = BASE_DIR / "scratch" / "clean_channel_backtest_today.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tested_signals": len(results),
            "total_channels": len(leaderboard),
            "leaderboard": leaderboard
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 98)
    print("🏆 ACCURATE BACKTEST LEADERBOARD — TODAY (ALL CHANNELS ACCOUNTS 1 & 2)")
    print("=" * 98)
    print(f"{'Rank':>3} {'Channel':<38} {'Account':<10} {'Sigs':>5} {'W/BE/L':>8} {'Win%':>6} {'Pips':>8} {'Max MFE':>8} {'Net USD (0.01)':>15}")
    print("-" * 98)

    for rank, item in enumerate(leaderboard, 1):
        w_str = f"{item['wins']}/{item['be']}/{item['losses']}"
        print(f"{rank:>3} {item['channel'][:37]:<38} {item['account']:<10} {item['signals']:>5} {w_str:>8} {item['win_rate']:>5.1f}% {item['total_pips']:>8.1f}p {item['max_mfe']:>7.1f}p ${item['total_usd']:>14.2f}")

    print("-" * 98)
    total_all_usd = sum(x["total_usd"] for x in leaderboard)
    total_all_pips = sum(x["total_pips"] for x in leaderboard)
    total_all_sigs = sum(x["signals"] for x in leaderboard)
    total_all_wins = sum(x["wins"] for x in leaderboard)
    print(f"{'TOTAL':<52} {total_all_sigs:>5} {total_all_wins} wins | {total_all_pips:>8.1f}p | ${total_all_usd:>14.2f}")

if __name__ == '__main__':
    run()
