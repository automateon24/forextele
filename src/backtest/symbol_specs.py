from dataclasses import dataclass

@dataclass
class SymbolSpec:
    point: float
    trade_tick_size: float
    trade_tick_value: float
    trade_contract_size: float
    volume_step: float

# Hardcoded repository of known broker specs.
# In a live system, this should be queried via mt5.symbol_info(symbol).
KNOWN_SPECS = {
    "EURUSD": SymbolSpec(
        point=0.00001,
        trade_tick_size=0.00001,
        trade_tick_value=1.00,       # 1 tick = $1 for 1 standard lot
        trade_contract_size=100000,
        volume_step=0.01
    ),
    "GBPUSD": SymbolSpec(
        point=0.00001,
        trade_tick_size=0.00001,
        trade_tick_value=1.00,       # 1 tick = $1 for 1 standard lot
        trade_contract_size=100000,
        volume_step=0.01
    ),
    "GOLD": SymbolSpec(
        point=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.00,       # 1 tick ($0.01 move) = $1 for 1 standard lot (100 oz)
        trade_contract_size=100,
        volume_step=0.01
    ),
    "XAUUSD": SymbolSpec(
        point=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.00,
        trade_contract_size=100,
        volume_step=0.01
    )
}

def get_symbol_spec(symbol: str) -> SymbolSpec:
    if symbol not in KNOWN_SPECS:
        raise ValueError(f"Symbol {symbol} is missing from symbol specifications. Cannot compute PnL safely.")
    return KNOWN_SPECS[symbol]

def calculate_pnl(symbol: str, side: str, entry_price: float, exit_price: float, volume: float, spec: SymbolSpec) -> float:
    """
    Centralized PnL calculation using strict MT5 tick math.
    PnL = (price_diff / tick_size) * tick_value * (volume / volume_step)
    
    Wait, in MT5:
    For 1 lot of EURUSD (100,000):
    1 pip (0.0001) = $10.
    1 tick/point (0.00001) = $1.
    If we buy 0.01 lots, 1 tick = $0.01.
    Math:
    ticks = (0.00001) / 0.00001 = 1 tick.
    volume_ratio = 0.01 / 0.01 = 1 volume step.
    Wait! MT5 tick_value is usually defined *per 1 standard lot*.
    If tick_value is $1 for 1 lot:
    Then for 0.01 lot, tick_value is $0.01? No, MT5 tick_value is per standard lot? Let's check MT5 docs.
    Actually, MT5 symbol_info.trade_tick_value is the value of one tick *for one standard lot*.
    So PnL = (price_diff / tick_size) * tick_value * volume
    Let's verify:
    EURUSD: price_diff = 0.00010 (10 points). tick_size = 0.00001. ticks = 10.
    tick_value = $1.00.
    volume = 0.01.
    PnL = 10 * 1.00 * 0.01 = $0.10. Correct. (10 micro-lot points = $0.10).
    
    GOLD: price_diff = 1.00 ($1 move). tick_size = 0.01. ticks = 100.
    tick_value = $1.00 (for 1 lot = 100 oz, a 1 cent move is $1).
    volume = 0.01.
    PnL = 100 * 1.00 * 0.01 = $1.00. Correct. (0.01 lot = 1 oz. $1 move on 1 oz = $1).
    """
    if side == "BUY":
        price_diff = exit_price - entry_price
    else:
        price_diff = entry_price - exit_price
        
    ticks = price_diff / spec.trade_tick_size
    pnl = ticks * spec.trade_tick_value * volume
    
    return pnl
