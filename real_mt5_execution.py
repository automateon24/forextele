import MetaTrader5 as mt5
import json
import logging
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"

log = logging.getLogger(__name__)
file_handler = logging.FileHandler(BASE_DIR / 'mt5_orders.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
log.addHandler(file_handler)
log.setLevel(logging.INFO)

class MT5ExecutionEngine:
    def __init__(self):
        self.connected = False
        self.config = {}
        self.load_config()

    def load_config(self):
        if MT5_CFG_PATH.exists():
            with open(MT5_CFG_PATH, "r") as f:
                self.config = json.load(f)
        else:
            log.warning("mt5_config.json not found! Cannot connect to broker.")

    def connect(self):
        """Establish connection to MetaTrader 5"""
        if not mt5.initialize():
            log.info("MT5 initialization failed. Attempting with config credentials...")
            if not self.config:
                return False
            
            if not mt5.initialize(
                login=int(self.config.get("login", 0)),
                server=self.config.get("server", ""),
                password=self.config.get("password", "")
            ):
                log.error(f"MT5 final connection failed: {mt5.last_error()}")
                return False
                
        self.connected = True
        log.info("Successfully connected to MetaTrader 5 Broker.")
        return True

    def get_available_symbols(self) -> list:
        if not self.connected:
            if not self.connect(): return []
        symbols = mt5.symbols_get()
        if symbols:
            # Filter common ones to keep context small, or just return names
            return [s.name for s in symbols if "USD" in s.name or "EUR" in s.name or "GBP" in s.name or "JPY" in s.name or "GOLD" in s.name or "BTC" in s.name or "ETH" in s.name][:50]
        return []

    def calculate_lot_size(self, symbol: str, entry_price: float, sl_price: float, risk_pct: float = 0.01) -> float:
        """
        Dynamically calculate the lot size based on 1% equity risk and exact Stop-Loss distance.
        """
        if not self.connected:
            return 0.01
            
        account_info = mt5.account_info()
        if account_info is None:
            return 0.01
            
        equity = account_info.equity
        risk_amount = equity * risk_pct
        
        info = mt5.symbol_info(symbol)
        if info is None or info.trade_tick_value == 0:
            return 0.01
            
        # Calculate distance in points
        sl_distance_points = abs(entry_price - sl_price) / info.point
        if sl_distance_points <= 0:
            return 0.01
            
        # true_volume = risk_amount / (sl_distance_points * tick_value)
        # Note: tick_value is usually per lot per point.
        tick_value = info.trade_tick_value
        true_volume = risk_amount / (sl_distance_points * tick_value)
        
        # Round to step
        step = info.volume_step if info.volume_step > 0 else 0.01
        scaled_lot = round(true_volume / step) * step
        
        # ABSOLUTE HARD SAFETY GOVERNOR CAP: Never exceed 1.00 lot under any circumstances
        HARD_MAX_LOT = 1.00
        calculated_lot = max(max(0.02, info.volume_min), min(scaled_lot, info.volume_max, HARD_MAX_LOT))
        log.info(f"[{symbol}] Calculated lot size: {calculated_lot:.2f} (raw={scaled_lot:.2f}, max_cap={HARD_MAX_LOT})")
        return calculated_lot

    def execute_trade(self, swarm_payload: dict, magic_number: int = 999999) -> bool:
        """
        Executes the exact parameters determined by the AI Swarm Governor.
        """
        if not self.connected:
            if not self.connect():
                return False
                
        symbol = swarm_payload.get("symbol")
        action = swarm_payload.get("action", "BUY").upper()
        
        # ── USER DIRECTIVE: TELEGRAM SIGNALS RESTRICTED TO GOLD, EXCEPT MARKET TRADER (MAGIC 888888) ──
        if magic_number in (777777, 999999):
            sym_upper = str(symbol).upper()
            if not any(k in sym_upper for k in ["GOLD", "XAU"]):
                log.warning(f"[GOLD_RESTRICTION] Blocking trade execution for non-gold symbol '{symbol}'. Pure Gold only.")
                return False
        elif magic_number == 888888:
            # Market Trader Whitelist (Gold + Forex + US30)
            whitelisted = ["GOLD", "XAU", "AUDJPY", "USDJPY", "GBPJPY", "GBPCAD", "EURCAD", "GBPNZD", "US30", "US30CASH", "BTC", "ETH"]
            sym_upper = str(symbol).upper()
            if not any(k in sym_upper for k in whitelisted):
                log.warning(f"[MARKET_TRADER_RESTRICTION] Symbol '{symbol}' not in whitelisted Forex/Index/Gold pairs.")
                return False


        # WEEKEND SCHEDULE GUARD: Protect Forex/Metals from weekend order rejection loops
        from datetime import datetime
        utc_now = datetime.utcnow()
        if utc_now.weekday() >= 5 and symbol not in ("BTCUSD", "ETHUSD", "BTC", "ETH", "SOLUSD", "XRPUSD", "BNBUSD"):
            log.warning(f"[WEEKEND GUARD] Blocking Telegram execution for {symbol}. Traditional markets are closed on weekends until Monday Open.")
            return False

        # PREVENT REPEATED ORDERS: Check if position already exists
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for p in positions:
                if p.magic == magic_number:
                    log.warning(f"Blocking duplicate {action} for {symbol}. Order {p.ticket} is already active.")
                    return False
        
        # Select symbol
        if not mt5.symbol_select(symbol, True):
            log.error(f"Symbol {symbol} not found in Market Watch.")
            return False
            
        info = mt5.symbol_info(symbol)
        if not info:
            log.error(f"Symbol {symbol} info not available.")
            return False

        # Get exact current price
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error(f"Tick data unavailable for {symbol}.")
            return False
            
        price = tick.ask if action == "BUY" else tick.bid
            
        entry_val = swarm_payload.get("entry")
        extracted_entry = float(entry_val) if entry_val is not None else 0.0
        
        # If no entry provided, use Market
        if extracted_entry <= 0:
            extracted_entry = price
            
        action_type = mt5.TRADE_ACTION_DEAL
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        final_price = price
        
        # Extract sentiment modifier
        risk_modifier = float(swarm_payload.get("risk_modifier", 1.0))
        final_risk_pct = 0.01 * risk_modifier
        
        # Determine Pending Order Logic
        point = info.point
        min_dist = info.trade_stops_level * point  # broker minimum stop distance
        entry_diff = abs(extracted_entry - price)
        
        if entry_diff > max(30 * point, min_dist):  # Widened from 10 to 30 points
            action_type = mt5.TRADE_ACTION_PENDING
            final_price = extracted_entry
            if action == "BUY":
                order_type = mt5.ORDER_TYPE_BUY_STOP if extracted_entry > price else mt5.ORDER_TYPE_BUY_LIMIT
            else:
                order_type = mt5.ORDER_TYPE_SELL_STOP if extracted_entry < price else mt5.ORDER_TYPE_SELL_LIMIT
            log.info(f"[MT5] Placing PENDING order at {final_price} (Market={price:.5f}, type={'STOP' if (action=='BUY' and extracted_entry > price) or (action=='SELL' and extracted_entry < price) else 'LIMIT'})")
        else:
            log.info(f"[MT5] Placing MARKET order at {price:.5f} (signal entry={extracted_entry}")
                
        # Validate Stops against final_price to prevent Retcode 10016 (Invalid Stops)
        sl = round(swarm_payload.get("final_sl", 0.0), info.digits)

        # Broker TP Setup:
        # Fixed SL until TP2, and 10-pip jumping TSL from TP2 onwards.
        # NEVER place hard broker TP at TP1 or TP2 (which would close the trade before runner TSL).
        raw_tp3 = swarm_payload.get("final_tp3") or swarm_payload.get("tp3")
        raw_tp2 = swarm_payload.get("final_tp2") or swarm_payload.get("tp2")
        raw_tp1 = swarm_payload.get("final_tp1") or swarm_payload.get("tp1") or swarm_payload.get("tp")

        if raw_tp3 and float(raw_tp3) > 0:
            tp = round(float(raw_tp3), info.digits)
        elif raw_tp2 and float(raw_tp2) > 0:
            tp2_val = float(raw_tp2)
            ext_dist = abs(tp2_val - final_price) * 1.6
            tp = round(final_price + ext_dist if action == "BUY" else final_price - ext_dist, info.digits)
        elif raw_tp1 and float(raw_tp1) > 0:
            tp1_val = float(raw_tp1)
            ext_dist = abs(tp1_val - final_price) * 2.5
            tp = round(final_price + ext_dist if action == "BUY" else final_price - ext_dist, info.digits)
        else:
            tp = 0.0
        
        if action == "BUY":
            if tp > 0 and tp <= final_price: tp = 0 # Invalid TP
            if sl > 0 and sl >= final_price: sl = 0 # Invalid SL
        else:
            if tp > 0 and tp >= final_price: tp = 0
            if sl > 0 and sl <= final_price: sl = 0
            
        # AUTO DYNAMIC INJECTION FOR MISSING STOPS (Guarantees NO naked trades on MT5)
        # Fallback TP is wide extension to prevent premature broker exit
        if sl == 0 or tp == 0:
            sym_u = symbol.upper()
            if "BTC" in sym_u:
                fallback_sl_dist = 400.0
                fallback_tp_dist = 1500.0
            elif "US30" in sym_u or "DJ30" in sym_u:
                fallback_sl_dist = 60.0
                fallback_tp_dist = 200.0
            elif "GOLD" in sym_u or "XAU" in sym_u:
                fallback_sl_dist = 3.50   # 35 Gold Pips
                fallback_tp_dist = 18.00  # 180 Gold Pips (Wide ceiling, dynamic TSL manages exit)
            else:
                pip_unit = 10.0 * point if point > 0 else 0.0001
                fallback_sl_dist = 35.0 * pip_unit
                fallback_tp_dist = 150.0 * pip_unit

            if action == "BUY":
                if sl == 0: sl = round(final_price - fallback_sl_dist, info.digits)
                if tp == 0: tp = round(final_price + fallback_tp_dist, info.digits)
            else:
                if sl == 0: sl = round(final_price + fallback_sl_dist, info.digits)
                if tp == 0: tp = round(final_price - fallback_tp_dist, info.digits)
                
        # --- LIQUIDITY SWEEP PROTECTION (V-Shape Defense) ---
        # Fetch Daily High and Low
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
        if rates is not None and len(rates) > 0:
            daily_high = rates[-1]['high']
            daily_low = rates[-1]['low']
            
            if action == "BUY" and abs(final_price - daily_high) / daily_high < 0.0015:
                log.warning(f"🚨 LIQUIDITY SWEEP RISK: Buying near Daily High ({daily_high}). Cutting SL in half.")
                sl = round(final_price - (abs(final_price - sl) / 2), info.digits)
            elif action == "SELL" and abs(final_price - daily_low) / daily_low < 0.0015:
                log.warning(f"🚨 LIQUIDITY SWEEP RISK: Selling near Daily Low ({daily_low}). Cutting SL in half.")
                sl = round(final_price + (abs(sl - final_price) / 2), info.digits)
                
        # Calculate Lot Size (Governor approved the trade, we scale it accurately using validated SL)
        if swarm_payload.get("volume") and float(swarm_payload.get("volume")) > 0:
            volume = float(swarm_payload.get("volume"))
        else:
            volume = self.calculate_lot_size(symbol, final_price, sl, risk_pct=final_risk_pct)

        if magic_number == 777777:
            volume = min(float(volume), 0.04)  # Hard cap for Telegram Signals (avoids oversized drawdown)
        else:
            volume = min(float(volume), 1.00)  # ABSOLUTE HARD GOVERNOR SAFETY CAP

        # Clean, human-readable channel punch on MT5 Comment (max 31 chars)
        raw_comment = swarm_payload.get("comment", "")
        raw_chan = swarm_payload.get("source_channel", "")
        if raw_comment and raw_comment.startswith("[") and raw_comment.endswith("]"):
            order_comment = raw_comment[:31]
        elif raw_chan:
            clean_chan_str = raw_chan.encode('ascii', 'ignore').decode('ascii').strip()
            order_comment = f"[{clean_chan_str[:27]}]"[:31]
        else:
            order_comment = (raw_comment or "AI_SWARM")[:31]

        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(final_price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": magic_number,
            "comment": order_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC if action_type == mt5.TRADE_ACTION_DEAL else mt5.ORDER_FILLING_RETURN,
        }
        
        log.info(f"Sending Order to Broker: {action} {volume} {symbol} @ {final_price} | SL: {sl} | TP: {tp}")
        
        result = mt5.order_send(request)
        
        if result is None:
            log.error(f"mt5.order_send returned None. Last error: {mt5.last_error()} | Request: {request}")
            return False
            
        # ── Retry on 10018 Market Closed: wait 5 seconds then re-try once as MARKET order
        if result.retcode == 10018:
            log.warning("Retcode 10018 (Market Closed) — waiting 5s and retrying as MARKET order...")
            import time; time.sleep(5)
            tick2 = mt5.symbol_info_tick(symbol)
            if tick2:
                request["action"] = mt5.TRADE_ACTION_DEAL
                request["type"] = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
                request["price"] = tick2.ask if action == "BUY" else tick2.bid
                request["type_filling"] = mt5.ORDER_FILLING_IOC
                log.info(f"[MT5] Retry MARKET order @ {request['price']}")
                result = mt5.order_send(request)
                if result is None:
                    log.error(f"mt5.order_send returned None on retry. Last error: {mt5.last_error()} | Request: {request}")
                    return False
                    
        if result.retcode == 10016:
            log.warning("Retcode 10016 (Invalid Stops) detected! Recalculating dynamic SL/TP and retrying...")
            
            # Dynamic proxy: 0.5% of asset price
            fallback_dist = final_price * 0.005
            
            # Recalculate strictly based on current Market Price to guarantee validity
            current_ask = mt5.symbol_info_tick(symbol).ask
            current_bid = mt5.symbol_info_tick(symbol).bid
            
            if action == "BUY":
                request["price"] = current_ask
                request["sl"] = current_ask - fallback_dist
                request["tp"] = current_ask + fallback_dist
            else:
                request["price"] = current_bid
                request["sl"] = current_bid + fallback_dist
                request["tp"] = current_bid - fallback_dist
                
            request["action"] = mt5.TRADE_ACTION_DEAL # Force market deal on retry
            request["type_filling"] = mt5.ORDER_FILLING_IOC
            
            log.info(f"Retry Order: {action} {volume} {symbol} @ {request['price']} | SL: {request['sl']} | TP: {request['tp']}")
            result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed definitively! Retcode: {result.retcode} | Comment: {result.comment} | Symbol: {symbol} | Price: {final_price} | SL: {sl} | TP: {tp} | Type: {order_type}")
            # Write to alerts
            try:
                alert_path = BASE_DIR / "alerts.json"
                import json, datetime
                alerts = []
                if alert_path.exists():
                    with open(alert_path, "r", encoding="utf-8") as af:
                        try: alerts = json.load(af)
                        except: pass
                alerts.append({
                    "source": f"MT5 Execution ({symbol})",
                    "message": f"Order Failed: {result.comment} (Code {result.retcode}). Price: {final_price} | SL: {sl} | TP: {tp}",
                    "level": "CRITICAL",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                with open(alert_path, "w", encoding="utf-8") as af:
                    json.dump(alerts, af, indent=2)
            except: pass
            return False
            
        log.info(f"SUCCESS! Trade {result.order} opened by Swarm AI.")
        swarm_payload["ticket"] = result.order
        return True

    def move_sl_to_breakeven(self, symbol: str, magic_number: int = 888888, buffer_points: float = 0.0) -> bool:
        """Moves Stop Loss to Entry Price (Cost-to-Cost) with optional breathing buffer for open positions."""
        if not self.connected:
            if not self.connect(): return False
            
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            # Try finding by magic number across all symbols
            all_pos = mt5.positions_get()
            positions = [p for p in (all_pos or []) if p.magic == magic_number and (symbol is None or p.symbol == symbol)]
            
        if not positions:
            log.warning(f"[BREAKEVEN] No open position found for symbol {symbol} (magic {magic_number}).")
            return False
            
        success = True
        for p in positions:
            if magic_number and p.magic != magic_number:
                continue
            entry_price = p.price_open
            # Apply breathing buffer: for BUY, leave SL below entry by buffer_points to absorb spread; for SELL, above
            if buffer_points > 0:
                adjusted_sl = (entry_price - buffer_points) if p.type == mt5.ORDER_TYPE_BUY else (entry_price + buffer_points)
                if p.type == mt5.ORDER_TYPE_BUY and adjusted_sl <= p.sl:
                    continue
                elif p.type == mt5.ORDER_TYPE_SELL and p.sl > 0 and adjusted_sl >= p.sl:
                    continue
            else:
                adjusted_sl = entry_price
                
            info = mt5.symbol_info(p.symbol)
            digits = info.digits if info else 2
            adjusted_sl = round(adjusted_sl, digits)
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": p.ticket,
                "symbol": p.symbol,
                "sl": float(adjusted_sl),
                "tp": float(p.tp),
                "magic": p.magic
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"[BREAKEVEN SUCCESS] Moved SL to {adjusted_sl} (buffer={buffer_points}) for ticket {p.ticket} ({p.symbol}).")
            else:
                err = res.comment if res else mt5.last_error()
                log.error(f"[BREAKEVEN FAILED] Ticket {p.ticket}: {err}")
                success = False
        return success

    def close_partial_position(self, symbol: str, close_pct: int = 50, magic_number: int = 888888) -> bool:
        """Closes a percentage (e.g. 50%, 60%, 80%) of open volume to bank profits."""
        if not self.connected:
            if not self.connect(): return False
            
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            all_pos = mt5.positions_get()
            positions = [p for p in (all_pos or []) if p.magic == magic_number and (symbol is None or p.symbol == symbol)]
            
        if not positions:
            log.warning(f"[PARTIAL CLOSE] No open position for {symbol}.")
            return False
            
        for p in positions:
            if magic_number and p.magic != magic_number:
                continue
            info = mt5.symbol_info(p.symbol)
            if not info: continue
            
            raw_close_vol = p.volume * (close_pct / 100.0)
            step = info.volume_step if info.volume_step > 0 else 0.01
            close_vol = round(raw_close_vol / step) * step
            close_vol = max(info.volume_min, min(close_vol, p.volume))
            
            tick = mt5.symbol_info_tick(p.symbol)
            price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
            close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": p.ticket,
                "symbol": p.symbol,
                "volume": float(close_vol),
                "type": close_type,
                "price": float(price),
                "deviation": 20,
                "magic": p.magic,
                "comment": f"PARTIAL_{close_pct}%"[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"[PARTIAL CLOSE SUCCESS] Closed {close_vol} of {p.volume} lots for ticket {p.ticket}.")
            else:
                log.error(f"[PARTIAL CLOSE FAILED] Ticket {p.ticket}: {res.comment if res else mt5.last_error()}")
        return True

    def close_position(self, symbol: str, magic_number: int = 888888) -> bool:
        """Closes 100% of open positions for the symbol."""
        return self.close_partial_position(symbol, close_pct=100, magic_number=magic_number)

