"""
Institutional Session & Rollover Failure Gate
===============================================
Filters out high-loss time windows based on empirical failure analysis:
- BLOCKS 21:00 - 22:59 UTC (NY Liquidity Drain & Broker Rollover Spread Spike)
- BLOCKS 11:00 - 11:59 UTC (Pre-US Economic News Trap)
- ALLOWS Prime Windows: Asian Range (23:00-07:00), London (07:00-11:00), NY (12:30-18:00)
"""

from datetime import datetime

def is_prime_trading_hour(dt: datetime) -> bool:
    """
    Returns True if UTC time is within high-probability trading windows.
    Returns False if UTC time falls in known failure dead zones.
    """
    hour = dt.hour
    
    # 1. Block Market Rollover & NY Drain (21:00 to 22:59 UTC) -> 0% Win Rate Zone
    if 21 <= hour <= 22:
        return False
        
    # 2. Block Pre-US News Trap (11:00 to 11:59 UTC) -> 3.3% Win Rate Zone
    if hour == 11:
        return False
        
    return True
