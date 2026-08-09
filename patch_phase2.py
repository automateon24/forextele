import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Modify calculate_dynamic_lot for Phase 2
calc_lot_def = "def calculate_dynamic_lot(symbol, sl_points_count, risk_pct=0.01):"
new_calc_lot = '''def calculate_dynamic_lot(symbol, sl_points_count, risk_pct=0.01):
    """
    PHASE 2: Anti-Martingale Asymmetric Risk Sizing.
    Base Risk is 0.5%.
    If the last 2 trades were wins -> double risk to 1.0%.
    If the last 2 trades were losses -> half risk to 0.25% (recovery mode).
    STRICT CAP at 2.0%.
    """
    info = mt5.symbol_info(symbol)
    if not info: return 0.01
    
    account = mt5.account_info()
    if not account: return 0.01
        
    equity = account.equity
    
    # Analyze MT5 History for Streak
    from datetime import datetime, timedelta
    try:
        now = datetime.now()
        yesterday = now - timedelta(days=7) # Look back a week for closed trades
        deals = mt5.history_deals_get(yesterday, now)
        if deals:
            # Filter for closed deals with our magic number
            closed_deals = [d for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT]
            # Sort by time
            closed_deals = sorted(closed_deals, key=lambda x: x.time)
            if len(closed_deals) >= 2:
                last_deal = closed_deals[-1]
                prev_deal = closed_deals[-2]
                if last_deal.profit > 0 and prev_deal.profit > 0:
                    risk_pct = min(0.02, risk_pct * 2.0)
                    logging.info(f"[{symbol}] Anti-Martingale: 2 Wins in a row! Doubling risk to {risk_pct:.2%}")
                elif last_deal.profit < 0 and prev_deal.profit < 0:
                    risk_pct = max(0.0025, risk_pct * 0.5)
                    logging.info(f"[{symbol}] Anti-Martingale: 2 Losses in a row! Halving risk to {risk_pct:.2%}")
    except Exception as e:
        logging.error(f"[{symbol}] Anti-Martingale Error: {e}")
        pass # Default to passed risk_pct
        
    risk_amount = equity * risk_pct
    
    tick_value = info.trade_tick_value
    if tick_value == 0 or sl_points_count <= 0:
        return 0.01
        
    true_volume = risk_amount / (sl_points_count * tick_value)
    
    step = info.volume_step if info.volume_step > 0 else 0.01
    scaled_lot = round(true_volume / step) * step
    
    raw_lot = max(info.volume_min, min(scaled_lot, info.volume_max))
    
    # ── HARD SAFETY CAP: Never exceed 0.50 lots per trade ─────────────────
    MAX_LOT_CAP = 0.50
    capped_lot = min(raw_lot, MAX_LOT_CAP)
    if raw_lot > MAX_LOT_CAP:
        logging.warning(f"[{symbol}] [RISK_CAP] Lot size {raw_lot:.2f} capped to {MAX_LOT_CAP} for safety.")
    return capped_lot
'''

start_idx = code.find(calc_lot_def)
end_idx = code.find("def calculate_adx(", start_idx)

code = code[:start_idx] + new_calc_lot + "\n\n" + code[end_idx:]

# Modify circuit breaker
circuit_breaker_def = "def is_daily_loss_breaker_hit(max_loss_pct=0.03):"
new_circuit_breaker = '''def is_daily_loss_breaker_hit(max_loss_pct=0.02):
    """
    PHASE 2: 2% Strict Daily Circuit Breaker
    Returns True if today's strategy losses (realized + floating) exceeded max_loss_pct of balance.
    Halts new trades for the day if triggered.
    """
    try:
        account = mt5.account_info()
        if not account: return False
        
        from datetime import datetime, timedelta
        # Calculate start of current UTC day
        now_utc = datetime.utcnow()
        start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day)
        
        deals = mt5.history_deals_get(start_of_day, now_utc)
        realized_pnl = 0.0
        if deals:
            realized_pnl = sum(d.profit for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT)
            
        # Add open floating P&L
        floating_pnl = 0.0
        positions = mt5.positions_get()
        if positions:
            floating_pnl = sum(p.profit for p in positions if p.magic == 888888)
            
        total_daily_pnl = realized_pnl + floating_pnl
        
        if total_daily_pnl < 0:
            loss_pct = abs(total_daily_pnl) / account.balance
            if loss_pct >= max_loss_pct:
                logging.warning(f"[CIRCUIT_BREAKER] 🛑 Daily Loss {loss_pct:.1%} >= Limit {max_loss_pct:.0%}. HALTING NEW TRADES.")
                return True
    except Exception as e:
        logging.error(f"[CIRCUIT_BREAKER] Error checking daily loss: {e}")
    return False
'''

start_idx_cb = code.find(circuit_breaker_def)
end_idx_cb = code.find("def place_order(", start_idx_cb)

code = code[:start_idx_cb] + new_circuit_breaker + "\n" + code[end_idx_cb:]

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched live_strategy_executor.py for Phase 2!")
