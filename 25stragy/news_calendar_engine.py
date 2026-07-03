import MetaTrader5 as mt5
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")

class NewsStraddleEngine:
    """
    Engine to handle high-impact news events (e.g. CPI, NFP, FOMC).
    It places a Buy Stop and a Sell Stop order simultaneously (a Straddle)
    shortly before the news drops. 
    """
    def __init__(self, gap_pips: int = 10, sl_pips: int = 15, tgt_pips: int = 50):
        self.gap_pips = gap_pips
        self.sl_pips = sl_pips
        self.tgt_pips = tgt_pips
        
    def _calculate_price_levels(self, symbol: str):
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        
        if not tick or not info:
            return None
            
        pip_size = info.point * (10 if info.digits in [3, 5] else 1)
        
        buy_stop_price = tick.ask + (self.gap_pips * pip_size)
        buy_sl = buy_stop_price - (self.sl_pips * pip_size)
        buy_tp = buy_stop_price + (self.tgt_pips * pip_size)
        
        sell_stop_price = tick.bid - (self.gap_pips * pip_size)
        sell_sl = sell_stop_price + (self.sl_pips * pip_size)
        sell_tp = sell_stop_price - (self.tgt_pips * pip_size)
        
        return {
            "buy": (buy_stop_price, buy_sl, buy_tp),
            "sell": (sell_stop_price, sell_sl, sell_tp)
        }

    def place_news_straddle(self, symbol: str, volume: float = 0.01):
        """
        Executes the straddle logic. To be called ~1 minute prior to 
        a high-impact economic release.
        """
        levels = self._calculate_price_levels(symbol)
        if not levels:
            logging.error(f"Could not calculate levels for {symbol}")
            return False
            
        # Place Buy Stop
        buy_req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY_STOP,
            "price": levels["buy"][0],
            "sl": levels["buy"][1],
            "tp": levels["buy"][2],
            "deviation": 20,
            "magic": 999999,
            "comment": "News_Straddle_Buy",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Place Sell Stop
        sell_req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL_STOP,
            "price": levels["sell"][0],
            "sl": levels["sell"][1],
            "tp": levels["sell"][2],
            "deviation": 20,
            "magic": 999999,
            "comment": "News_Straddle_Sell",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send both
        res_buy = mt5.order_send(buy_req)
        res_sell = mt5.order_send(sell_req)
        
        if res_buy.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"✅ Placed Buy Stop on {symbol} @ {levels['buy'][0]} (SL: {levels['buy'][1]})")
        else:
            logging.error(f"❌ Failed Buy Stop on {symbol}: {res_buy.comment}")
            
        if res_sell.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"✅ Placed Sell Stop on {symbol} @ {levels['sell'][0]} (SL: {levels['sell'][1]})")
        else:
            logging.error(f"❌ Failed Sell Stop on {symbol}: {res_sell.comment}")
            
        return res_buy.retcode == mt5.TRADE_RETCODE_DONE and res_sell.retcode == mt5.TRADE_RETCODE_DONE

# Example Usage
if __name__ == "__main__":
    # Ensure MT5 is initialized before calling this
    engine = NewsStraddleEngine(gap_pips=10, sl_pips=15, tgt_pips=80)
    # This would typically be triggered by an Economic Calendar API 1 minute before NFP / CPI
    # engine.place_news_straddle("GOLD", volume=0.01)
    # engine.place_news_straddle("EURUSD", volume=0.01)
