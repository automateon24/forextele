import MetaTrader5 as mt5
import json
import logging
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"

log = logging.getLogger(__name__)

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
        
        return max(info.volume_min, min(scaled_lot, info.volume_max))

    def execute_trade(self, swarm_payload: dict, magic_number: int = 999999) -> bool:
        """
        Executes the exact parameters determined by the AI Swarm Governor.
        """
        if not self.connected:
            if not self.connect():
                return False
                
        symbol = swarm_payload.get("symbol")
        action = swarm_payload.get("action", "BUY").upper()
        
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
        sl = round(swarm_payload.get("final_sl", 0.0), info.digits)
        tp = round(swarm_payload.get("final_tp1", 0.0), info.digits)
        
        # Extract sentiment modifier
        risk_modifier = float(swarm_payload.get("risk_modifier", 1.0))
        final_risk_pct = 0.01 * risk_modifier

        # Calculate Lot Size (Governor approved the trade, we scale it accurately)
        volume = self.calculate_lot_size(symbol, price, sl, risk_pct=final_risk_pct)
        
        # Prepare Order
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        
        sl = round(swarm_payload.get("final_sl", 0.0), info.digits)
        tp = round(swarm_payload.get("final_tp1", 0.0), info.digits)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": magic_number,
            "comment": "AI_SWARM",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        log.info(f"Sending Order to Broker: {action} {volume} {symbol} @ {price} | SL: {sl} | TP: {tp}")
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed! Retcode: {result.retcode} Comment: {result.comment}")
            return False
            
        log.info(f"SUCCESS! Trade {result.order} opened by Swarm AI.")
        return True
