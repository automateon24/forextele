import asyncio
import httpx
import json
import logging
import time
import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TRAIL_BOSS] - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

class SwarmPositionManager:
    def __init__(self):
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.model = "llama3.2"
        with open(PROMPTS_FILE, "r") as f:
            self.prompts = json.load(f)
        self.connect_mt5()

    def connect_mt5(self):
        if not mt5.initialize():
            try:
                with open(MT5_CFG_PATH, "r") as f:
                    cfg = json.load(f)
                mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
            except Exception as e:
                log.error(f"Failed to connect to MT5: {e}")

    def calculate_atr(self, symbol, timeframe=mt5.TIMEFRAME_M5, period=14):
        """Calculate live Average True Range for the symbol"""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)
        if rates is None or len(rates) < period:
            return 0.0
        
        df = pd.DataFrame(rates)
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        atr = df['tr'].rolling(window=period).mean().iloc[-1]
        return float(atr)

    async def _ask_ollama(self, system_prompt: str, payload_str: str) -> str:
        full_prompt = f"{system_prompt}\n\nTRADE STATE:\n{payload_str}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(self.ollama_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
            except Exception as e:
                log.error(f"Ollama API Error: {e}")
                return ""

    def modify_sl(self, ticket, symbol, new_sl, pos_type):
        """Execute the SL modification on MT5 with broker distance validation."""
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick:
            log.error(f"Cannot validate SL for {symbol}: symbol info unavailable.")
            return

        point = info.point
        min_stop_dist = info.trade_stops_level * point
        current_price = tick.bid if pos_type == "BUY" else tick.ask

        # Validate SL is outside the freeze zone
        sl_distance = abs(current_price - new_sl)
        if sl_distance < min_stop_dist:
            log.warning(f"[TRAIL_BOSS] SL {new_sl} is inside broker min-stop distance ({min_stop_dist:.5f}) for {symbol}. Skipping move.")
            return

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": float(new_sl)
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to trail SL for {ticket}: {result.retcode} | {result.comment}")
        else:
            log.info(f"✅ Successfully trailed SL for {ticket} to {new_sl}")

    def close_position(self, ticket, symbol, pos_type, volume, current_price):
        """Close a position immediately (used for Dead Trade Ejector)."""
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL if pos_type == "BUY" else mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": current_price,
            "type_filling": mt5.ORDER_FILLING_IOC
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to close position {ticket}: {result.retcode} | {result.comment}")
        else:
            log.info(f"🚨 DEAD TRADE EJECTOR: Force-closed position {ticket} ({symbol})")

    def partial_scale_out_and_breakeven(self, pos):
        """Execute 50% partial volume scale-out at TP1 and move SL to Entry (Breakeven)."""
        symbol = pos.symbol
        pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return

        current_price = tick.bid if pos_type == "BUY" else tick.ask
        pnl_points = (current_price - pos.price_open) if pos_type == "BUY" else (pos.price_open - current_price)
        
        info = mt5.symbol_info(symbol)
        point = info.point if info else 0.0001
        atr = self.calculate_atr(symbol)
        atr_target_dist = atr * 1.5 if atr > 0 else (100 * point)

        # Trigger partial close if profit >= 1.5x ATR distance and SL is not yet at breakeven
        is_sl_at_be = abs(pos.sl - pos.price_open) < (5 * point) if pos.sl > 0 else False

        if pnl_points >= atr_target_dist and not is_sl_at_be:
            if pos.volume >= 0.02:
                step = info.volume_step if info.volume_step > 0 else 0.01
                close_vol = round((pos.volume / 2.0) / step) * step
                close_vol = max(info.volume_min, min(close_vol, pos.volume))

                log.info(f"🚀 PARTIAL PROFIT SCALING: Closing 50% lot ({close_vol}) for {symbol} at TP1 & Moving SL to Entry ({pos.price_open})")
                self.close_position(pos.ticket, symbol, pos_type, close_vol, current_price)

            # Move SL to Entry (Breakeven)
            self.modify_sl(pos.ticket, symbol, pos.price_open, pos_type)

    async def run_loop(self):
        log.info("Trail Boss Engine Online. Monitoring active positions...")
        while True:
            positions = mt5.positions_get()
            if positions:
                current_time = time.time()
                for pos in positions:
                    if pos.magic in (777777, 888888, 999999): # Telegram & Strategy Swarm Trades
                        tick = mt5.symbol_info_tick(pos.symbol)
                        if tick is None or (current_time - tick.time > 300):
                            continue
                            
                        pos_type_str = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                        
                        # --- PARTIAL PROFIT SCALING AT TP1 ---
                        self.partial_scale_out_and_breakeven(pos)
                        
                        # --- DEAD TRADE EJECTOR LOGIC ---
                        trade_duration_mins = (current_time - pos.time) / 60
                        if trade_duration_mins > 45 and pos.profit < 0:
                            log.warning(f"[DEAD_TRADE_EJECTOR] {pos.symbol} {pos_type_str} open for {trade_duration_mins:.1f}m in loss. EJECTING!")
                            current_price = mt5.symbol_info_tick(pos.symbol).bid if pos_type_str == "BUY" else mt5.symbol_info_tick(pos.symbol).ask
                            self.close_position(pos.ticket, pos.symbol, pos_type_str, pos.volume, current_price)
                            continue
                        
                        atr = self.calculate_atr(pos.symbol)
                        state_payload = {
                            "symbol": pos.symbol,
                            "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                            "entry_price": pos.price_open,
                            "current_price": pos.price_current,
                            "current_sl": pos.sl,
                            "live_atr": atr
                        }
                        
                        log.info(f"Analyzing volatility for {pos.symbol} (ATR: {atr:.5f})")
                        ai_response = await self._ask_ollama(self.prompts["TRAIL_BOSS_PROMPT"], json.dumps(state_payload))
                        
                        try:
                            clean_resp = ai_response.replace("```json", "").replace("```", "").strip()
                            decision = json.loads(clean_resp)
                            if decision.get("modify_sl", False):
                                new_sl = decision.get("new_sl")
                                # Basic safety check to prevent looping if SL is identical
                                if new_sl and round(new_sl, 5) != round(pos.sl, 5):
                                    info = mt5.symbol_info(pos.symbol)
                                    rounded_sl = round(new_sl, info.digits)
                                    log.warning(f"🚨 TRAIL BOSS EXECUTING SL MOVE to {rounded_sl}!")
                                    pos_type_str = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                                    self.modify_sl(pos.ticket, pos.symbol, rounded_sl, pos_type_str)
                        except json.JSONDecodeError:
                            pass
            
            await asyncio.sleep(15) # Check every 15 seconds

if __name__ == "__main__":
    manager = SwarmPositionManager()
    asyncio.run(manager.run_loop())
