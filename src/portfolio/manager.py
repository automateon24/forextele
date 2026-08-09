import zmq
import time
import json
import logging
import MetaTrader5 as mt5
import os
from datetime import datetime, timezone
from src.common.messages import PortfolioSnapshotMessage, OpenPosition, MessageHeader

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "mt5_config.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [PORTFOLIO] - %(levelname)s - %(message)s')

def init_mt5():
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))
    return mt5.terminal_info() is not None

def get_daily_realised_pnl():
    now_utc = datetime.utcnow()
    start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day)
    deals = mt5.history_deals_get(start_of_day, now_utc)
    if not deals:
        return 0.0
    
    # Sum profit of closed deals
    pnl = sum(d.profit for d in deals if d.entry == mt5.DEAL_ENTRY_OUT)
    return pnl

def load_high_water_mark(current_equity):
    hwm_path = os.path.join(BASE_DIR, "config", "high_water_mark.json")
    hwm = current_equity
    if os.path.exists(hwm_path):
        try:
            with open(hwm_path, "r") as f:
                data = json.load(f)
                hwm = data.get("high_water_mark", current_equity)
        except Exception:
            pass
            
    if current_equity > hwm:
        hwm = current_equity
        try:
            with open(hwm_path, "w") as f:
                json.dump({"high_water_mark": hwm, "timestamp": datetime.utcnow().isoformat()}, f)
        except Exception:
            pass
            
    return hwm

def main():
    if not init_mt5():
        logging.error("Failed to connect to MT5. Portfolio Manager halting.")
        return

    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://127.0.0.1:5559")
    
    logging.info("Portfolio Manager connected to MT5 and bound to tcp://127.0.0.1:5559 for PortfolioSnapshots")

    while True:
        try:
            account = mt5.account_info()
            if account is None:
                logging.warning("Failed to retrieve account info.")
                time.sleep(5)
                continue
                
            daily_realised = get_daily_realised_pnl()
            hwm = load_high_water_mark(account.equity)
            
            mt5_positions = mt5.positions_get()
            open_positions = []
            daily_unrealised = 0.0
            
            if mt5_positions:
                for p in mt5_positions:
                    side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    
                    # Estimate risk amount based on SL if it exists
                    risk_amt = 0.0
                    if p.sl > 0.0:
                        tick_val = mt5.symbol_info(p.symbol).trade_tick_value if mt5.symbol_info(p.symbol) else 1.0
                        pts = abs(p.price_open - p.sl) / (mt5.symbol_info(p.symbol).point if mt5.symbol_info(p.symbol) else 0.0001)
                        risk_amt = pts * p.volume * tick_val
                        
                    daily_unrealised += p.profit
                        
                    open_pos = OpenPosition(
                        symbol=p.symbol,
                        side=side,
                        volume=p.volume,
                        entry_price=p.price_open,
                        current_price=p.price_current,
                        sl=p.sl,
                        unrealised_pnl=p.profit,
                        risk_amount=risk_amt
                    )
                    open_positions.append(open_pos)
            
            snapshot = PortfolioSnapshotMessage(
                header=MessageHeader(message_type="PortfolioSnapshot", source_component="svc_portfolio_manager"),
                equity=account.equity,
                balance=account.balance,
                margin_used=account.margin,
                margin_free=account.margin_free,
                open_positions=open_positions,
                daily_realised_pnl=daily_realised,
                daily_unrealised_pnl=daily_unrealised,
                high_water_mark_equity=hwm
            )
            
            pub_socket.send_string(f"PORTFOLIO {snapshot.model_dump_json()}")
            
            time.sleep(5) # Poll every 5 seconds
            
        except KeyboardInterrupt:
            logging.info("Shutting down Portfolio Manager.")
            break
        except Exception as e:
            logging.error(f"Error in Portfolio Manager loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
