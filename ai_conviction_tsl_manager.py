import asyncio
import json
import logging
import MetaTrader5 as mt5
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
REGISTRY_FILE = BASE_DIR / "active_trades_registry.json"
TSL_LOG_FILE = BASE_DIR / "logs" / "tsl_manager.log"
TSL_LOG_FILE.parent.mkdir(exist_ok=True)

log = logging.getLogger("TSL_MANAGER")
file_handler = logging.FileHandler(TSL_LOG_FILE, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [TSL] - %(levelname)s - %(message)s'))
log.addHandler(file_handler)
log.setLevel(logging.INFO)

# High Conviction Channel Database (Calibrated from 48h Live Deals & Historical Backtests)
HIGH_CONVICTION_CHANNELS = {
    # Tier 1 Elite Channels (Verified Positive Expectancy in 48h Audit)
    "swich gold forex": 0.95,
    "swich gold": 0.95,
    "market trader": 0.92,
    "markettrader": 0.92,
    "market trader crypto forex": 0.92,
    "perfect management": 0.90,
    "perfectmanagement": 0.90,
    "perfectmanagement1": 0.90,
    "perfectmanagement_786": 0.90,
    "josefina trader0": 0.88,
    "josefina trader": 0.88,
    "forex with karol": 0.88,
    "gold vip": 0.85,
    "swift gold forex": 0.84,
    "profitway": 0.80,
    "alto fx": 0.78,
    "xauusd gold master": 0.75,
    "gold pro trader": 0.72,

    # Standard Calibrated Channels
    "mrgoldenway": 0.70,
    "xauusd signal 99%": 0.70,
    "xauusd signal": 0.70,
    "gold trade signals": 0.70,
    "golden star signal": 0.70,
    "gold best signal": 0.70,
    "best fx xauusd gold trader": 0.70,
    "mike gold master": 0.70,
    "gold trade experts": 0.70,
    "xauusd ea": 0.70,
    "xauusd killer": 0.70,
    "xauusd pips killer": 0.70,
    "best gold ea": 0.70,
    "forex gold team": 0.70,
    "gold killer": 0.70,
    "king of gold": 0.70,
    "goldsignals": 0.70,
    "gold copy trading": 0.70,
    "saviour gold ea": 0.70,
    "hft gold trading": 0.70,
    "forex gold signal": 0.70,

    # Low-Conviction / High-Spam Channels (Strict Trend Confluence Required)
    "sureshot gold": 0.55,
    "vault gold forex": 0.55,
    "mr.david": 0.50,
    "riaogoldforex": 0.45,
    "dubai capital": 0.45
}

def get_channel_conviction(channel_name: str) -> float:
    ch_clean = channel_name.lower()
    for key, score in HIGH_CONVICTION_CHANNELS.items():
        if key in ch_clean:
            return score
    return 0.65  # Default baseline conviction

def load_trade_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_trade_registry(reg: dict):
    try:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2)
    except Exception as e:
        log.error(f"Error saving trade registry: {e}")

def register_trade(ticket: int, symbol: str, action: str, entry: float, sl: float, tps: list, channel: str, conviction: float = None):
    reg = load_trade_registry()
    if conviction is None:
        conviction = get_channel_conviction(channel)
        
    mode = "RUNNER_HIGH_CONVICTION" if conviction >= 0.75 else ("STANDARD_TSL" if conviction >= 0.50 else "TIGHT_SCALP")
    
    reg[str(ticket)] = {
        "ticket": ticket,
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "initial_sl": sl,
        "current_sl": sl,
        "tps": tps or [],
        "channel": channel,
        "conviction": conviction,
        "mode": mode,
        "open_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "highest_tp_reached": 0,
        "extension_step": 10.0
    }
    save_trade_registry(reg)
    log.info(f"Registered Trade {ticket} ({action} {symbol} @ {entry}) | Conviction: {conviction:.2f} | Mode: {mode} | Targets: {tps}")

def activate_extension_tsl(symbol: str, magic_number: int = 888888, step_pips: float = 10.0) -> bool:
    """
    Switches an open position into a hyper-tight trailing stop mode that trails
    `step_pips` (default 10 pips) behind market price, jumping with each new extension.
    Used when channels signal 'Book 100% Profit' to milk macro extension runs.
    """
    if not mt5.initialize():
        return False
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if not positions:
        return False
        
    reg = load_trade_registry()
    activated = False
    for p in positions:
        if magic_number and p.magic != magic_number:
            continue
        ticket_str = str(p.ticket)
        if ticket_str not in reg:
            register_trade(p.ticket, p.symbol, "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL", p.price_open, p.sl, [], "Market Trader", 0.90)
            reg = load_trade_registry()
            
        reg[ticket_str]["mode"] = "EXTENSION_10PIP_TSL"
        reg[ticket_str]["extension_step"] = step_pips
        log.info(f"⚡ [EXTENSION 10-PIP TSL ACTIVATED] Ticket {p.ticket} ({p.symbol}): Trailing step locked to {step_pips} pips jumps!")
        activated = True
        
    if activated:
        save_trade_registry(reg)
    return activated

def ensure_mt5():
    if mt5.terminal_info() is None or mt5.account_info() is None:
        cfg_file = BASE_DIR / "mt5_config.json"
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text())
                return mt5.initialize(
                    login=int(cfg.get("login", 0)),
                    server=cfg.get("server", ""),
                    password=cfg.get("password", "")
                )
            except Exception:
                pass
        return mt5.initialize()
    return True

async def run_tsl_monitoring_cycle():
    """Single cycle of trailing stop loss management across all open MT5 positions."""
    if not ensure_mt5():
        return

    positions = mt5.positions_get()
    if not positions:
        return

    reg = load_trade_registry()
    updated = False

    for p in positions:
        # Check Monitored magic numbers: 777777 (Pure Gold), 786786 (Perfect Mgt), 888888 (Market Trader), 999999 (Swarm Engine), 999001 (Autonomous AI Scanner)
        if p.magic not in (777777, 786786, 888888, 999999, 999001):
            continue

        ticket_str = str(p.ticket)
        
        # ── Auto-Register Guard: Never leave any open position unmonitored ──
        if ticket_str not in reg:
            ch_guess = "Autonomous AI Scanner" if p.magic == 999001 else ("Perfect Mgt" if p.magic == 786786 else ("Market Trader" if p.magic == 888888 else ("Gold VIP" if p.magic == 777777 else "Swarm AI")))
            conv_guess = 0.95 if p.magic == 999001 else (0.92 if p.magic == 786786 else (0.90 if p.magic == 888888 else 0.75))
            register_trade(p.ticket, p.symbol, "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL", p.price_open, p.sl, [], ch_guess, conv_guess)
            reg = load_trade_registry()
            updated = True

        meta = reg.get(ticket_str, {})
        conviction = meta.get("conviction", 0.70)
        mode = meta.get("mode", "RUNNER_HIGH_CONVICTION" if conviction >= 0.75 else "STANDARD_TSL")
        tps = meta.get("tps", [])
        
        info = mt5.symbol_info(p.symbol)
        if not info: continue
        
        tick = mt5.symbol_info_tick(p.symbol)
        if not tick: continue
        
        point = info.point
        digits = info.digits
        if point <= 0: continue
        
        current_price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
        open_price = p.price_open
        profit_dist = (current_price - open_price) if p.type == mt5.ORDER_TYPE_BUY else (open_price - current_price)
        
        # Asset-Specific Pip Sizing & Breathing Room Buffers
        sym_upper = p.symbol.upper()
        if "BTC" in sym_upper:
            pip_size = 10.0  # $10 = 1 BTC pip
            fee_buffer = 45.0  # $45 covers $40 spread + comm
            be_pips = 50.0  # +$500 profit triggers breakeven (extended breathing room)
            step1_pips = 100.0 # +$1000 profit -> lock +$400
            step2_pips = 180.0
            step3_pips = 280.0
            trail_dist = 350.0 # $350 trailing distance for max runner
        elif "US30" in sym_upper or "DJ30" in sym_upper:
            pip_size = 1.0  # 1 Index Point = 1 pip
            fee_buffer = 6.0
            be_pips = 80.0  # +80 pts before BE
            step1_pips = 140.0
            step2_pips = 220.0
            step3_pips = 320.0
            trail_dist = 90.0 # 90 pts breathing room
        elif "GOLD" in sym_upper or "XAU" in sym_upper:
            pip_size = 0.10  # $0.10 = 1 Gold Pip (10 points)
            fee_buffer = 0.50  # $0.50 covers gold spread
            be_pips = 50.0  # +50 pips ($5.00 move) triggers BE lock (Prevents premature wicking!)
            step1_pips = 80.0 # +80 pips ($8.00 move) -> lock +$3.50
            step2_pips = 140.0 # +140 pips ($14.00 move) -> lock +$7.00
            step3_pips = 220.0 # +220 pips ($22.00 move) -> lock +$12.00
            # ── ATR-Dynamic Trail Distance: fetch live M15 ATR(14) ──
            try:
                _atr_rates = mt5.copy_rates_from_pos(p.symbol, mt5.TIMEFRAME_M15, 0, 20)
                if _atr_rates is not None and len(_atr_rates) >= 14:
                    import numpy as _np
                    _h = [r["high"] for r in _atr_rates]
                    _l = [r["low"] for r in _atr_rates]
                    _c = [r["close"] for r in _atr_rates]
                    _trs = [max(_h[i]-_l[i], abs(_h[i]-_c[i-1]), abs(_l[i]-_c[i-1]))
                            for i in range(1, len(_atr_rates))]
                    _live_atr = float(_np.mean(_trs[-14:]))
                    # Trail at 1.80x ATR (Gold ATR ~2.5 → trail 4.5 pts breathing room, min 3.50 pts)
                    trail_dist = max(3.50, round(_live_atr * 1.80, 2))
                    log.debug(f"[ATR_TSL] Gold M15 ATR={_live_atr:.2f} → trail_dist={trail_dist:.2f}")
                else:
                    trail_dist = 4.50  # fallback 45 pips
            except Exception:
                trail_dist = 4.50  # fallback 45 pips
        else:
            # Standard Forex (AUDJPY, USDJPY, EURCAD, GBPJPY, etc.)
            pip_size = 10.0 * point
            fee_buffer = 3.0 * pip_size
            be_pips = 45.0
            step1_pips = 80.0
            step2_pips = 130.0
            step3_pips = 190.0
            trail_dist = 40.0 * pip_size

        profit_pips = profit_dist / pip_size
        new_sl = p.sl

        # ── Mandatory Stop Loss Shield: NEVER leave a position naked (SL == 0.0) ──
        if p.sl == 0.0:
            emergency_dist = 40.0 * pip_size
            emergency_sl = round(open_price - emergency_dist, digits) if p.type == mt5.ORDER_TYPE_BUY else round(open_price + emergency_dist, digits)
            new_sl = emergency_sl
            log.warning(f"🚨 [SAFETY SHIELD] Ticket {p.ticket} ({p.symbol}) had NO SL! Auto-injecting protective SL @ {new_sl}")

        # ── Determine TP1 and TP2 Targets ──
        sorted_tps = sorted(tps) if p.type == mt5.ORDER_TYPE_BUY else sorted(tps, reverse=True)
        if len(sorted_tps) >= 2:
            tp1_target = sorted_tps[0]
            tp2_target = sorted_tps[1]
        elif len(sorted_tps) == 1:
            tp1_target = sorted_tps[0]
            dist1 = abs(tp1_target - open_price)
            tp2_target = open_price + (2.0 * dist1) if p.type == mt5.ORDER_TYPE_BUY else open_price - (2.0 * dist1)
        else:
            # Default Targets: TP1 = 30 pips, TP2 = 60 pips
            tp1_dist = 30.0 * pip_size
            tp2_dist = 60.0 * pip_size
            tp1_target = open_price + tp1_dist if p.type == mt5.ORDER_TYPE_BUY else open_price - tp1_dist
            tp2_target = open_price + tp2_dist if p.type == mt5.ORDER_TYPE_BUY else open_price - tp2_dist

        # Check if price has reached TP2
        has_reached_tp2 = meta.get("has_reached_tp2", False)
        if not has_reached_tp2:
            if p.type == mt5.ORDER_TYPE_BUY and current_price >= tp2_target:
                has_reached_tp2 = True
                meta["has_reached_tp2"] = True
                updated = True
                log.info(f"🎯 [TP2 ACHIEVED] Ticket {p.ticket} ({p.symbol}) hit TP2 ({tp2_target})! Engaging 10-Pip Jumping TSL...")
            elif p.type == mt5.ORDER_TYPE_SELL and current_price <= tp2_target:
                has_reached_tp2 = True
                meta["has_reached_tp2"] = True
                updated = True
                log.info(f"🎯 [TP2 ACHIEVED] Ticket {p.ticket} ({p.symbol}) hit TP2 ({tp2_target})! Engaging 10-Pip Jumping TSL...")

        # ── FIXED SL UNTIL TP2: SL stays 100% UNTOUCHED until TP2 is reached! ──
        if not has_reached_tp2:
            # Keep original stated SL - zero premature wicking, zero breakeven choke!
            pass
        else:
            # ── AT OR BEYOND TP2: Put TSL at TP2 and Jump 10 Pips from there ──
            jump_gap = 10.0 * pip_size  # 10 pips ($1.00 on Gold, 10 pips on FX, $10 on BTC, 10 pts on US30)
            if p.type == mt5.ORDER_TYPE_BUY:
                calc_trail = round(current_price - jump_gap, digits)
                # Base TSL at TP2 minus minor spread buffer to guarantee no 10016 reject
                base_tp2_sl = round(tp2_target - (fee_buffer * 0.5), digits)
                candidate_sl = max(base_tp2_sl, calc_trail)
                if candidate_sl > p.sl and candidate_sl < current_price:
                    new_sl = candidate_sl
                    log.info(f"⚡ [10-PIP JUMP TSL] Ticket {p.ticket} ({p.symbol}): SL jumping {p.sl} -> {new_sl} (Current: {current_price}, TP2: {tp2_target})")
            else:
                calc_trail = round(current_price + jump_gap, digits)
                # Base TSL at TP2 plus minor spread buffer
                base_tp2_sl = round(tp2_target + (fee_buffer * 0.5), digits)
                candidate_sl = min(base_tp2_sl, calc_trail)
                if (p.sl == 0.0 or candidate_sl < p.sl) and candidate_sl > current_price:
                    new_sl = candidate_sl
                    log.info(f"⚡ [10-PIP JUMP TSL] Ticket {p.ticket} ({p.symbol}): SL jumping {p.sl} -> {new_sl} (Current: {current_price}, TP2: {tp2_target})")

        # Validate and Execute SL Modification
        new_sl = round(new_sl, digits)
        should_modify = False
        
        if p.type == mt5.ORDER_TYPE_BUY:
            if new_sl > p.sl and new_sl < current_price:
                should_modify = True
        else:
            if (p.sl == 0.0 or new_sl < p.sl) and new_sl > current_price:
                should_modify = True

        # Broker TP Extension: If broker TP is at or tighter than TP2, push it out to extension
        # so broker doesn't auto-close the trade at TP2, allowing 10-pip jumping TSL to run!
        target_broker_tp = float(p.tp)
        if p.type == mt5.ORDER_TYPE_BUY:
            if 0.0 < target_broker_tp <= tp2_target:
                ext_dist = abs(tp2_target - open_price) * 1.5
                target_broker_tp = round(tp2_target + ext_dist, digits)
                should_modify = True
                log.info(f"🚀 [TP EXTENSION] Widening Ticket {p.ticket} broker TP {p.tp} -> {target_broker_tp} to let 10-pip TSL run!")
        else:
            if target_broker_tp > 0.0 and target_broker_tp >= tp2_target:
                ext_dist = abs(open_price - tp2_target) * 1.5
                target_broker_tp = round(tp2_target - ext_dist, digits)
                should_modify = True
                log.info(f"🚀 [TP EXTENSION] Widening Ticket {p.ticket} broker TP {p.tp} -> {target_broker_tp} to let 10-pip TSL run!")

        if should_modify and (new_sl != p.sl or target_broker_tp != p.tp):
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": p.ticket,
                "symbol": p.symbol,
                "sl": float(new_sl),
                "tp": float(target_broker_tp),
                "magic": p.magic
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"[{p.symbol} TSL SUCCESS] Ticket {p.ticket}: SL moved {p.sl} -> {new_sl} | TP -> {target_broker_tp} (Profit: +{profit_pips:.1f}p | Mode: {mode})")
                meta["current_sl"] = new_sl
                updated = True
            else:
                log.error(f"[{p.symbol} TSL FAIL] Ticket {p.ticket}: {res.comment if res else mt5.last_error()}")

    # Clean up closed tickets from registry & feed outcome to AI Learning Engine
    open_tickets = {str(p.ticket) for p in positions}
    for t_str in list(reg.keys()):
        if t_str not in open_tickets:
            # Query closed deal outcome from MT5 history
            try:
                ticket_int = int(t_str)
                hist_deals = mt5.history_deals_get(position=ticket_int)
                if hist_deals:
                    total_pnl = sum(d.profit for d in hist_deals)
                    outcome = "WIN" if total_pnl > 0 else "LOSS"
                    from ai_trade_learning_engine import learning_engine
                    learning_engine.update_trade_result(ticket_int, round(total_pnl, 2), 0.0, outcome)
                    log.info(f"🧠 [AI LEARNING OUTCOME] Ticket {ticket_int} closed: PnL=${total_pnl:.2f} ({outcome}) -> Knowledge Base Updated!")
            except Exception as e:
                log.debug(f"Learning update error for {t_str}: {e}")

            del reg[t_str]
            updated = True

    if updated:
        save_trade_registry(reg)

async def tsl_background_loop():
    """Runs continuously alongside Telegram listener."""
    log.info("Started Autonomous AI-Conviction Dynamic TSL Manager Loop...")
    while True:
        try:
            await run_tsl_monitoring_cycle()
        except Exception as e:
            log.error(f"Error in TSL cycle: {e}")
        await asyncio.sleep(4)  # Check every 4 seconds for maximum responsiveness
