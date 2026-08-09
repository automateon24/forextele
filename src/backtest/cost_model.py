from dataclasses import dataclass

@dataclass
class CostModel:
    spread_points: float = 0.00010
    commission_per_lot: float = 7.0
    slippage_points: float = 0.0

    def apply_entry_cost(self, price: float, side: str) -> float:
        """
        Adjusts entry price based on spread and slippage.
        BUY pays spread on entry (ASK price). SELL enters at BID (no spread added to bid, spread is paid on cover).
        However, for simplicity, we can apply half spread on entry, half on exit, or full spread on entry for BUYs.
        Standard MT5 logic: 
        BUY opens at ASK (price + spread).
        SELL opens at BID (price).
        """
        total_cost_points = self.spread_points + self.slippage_points
        if side == "BUY":
            return price + total_cost_points
        else:
            return price - self.slippage_points

    def apply_exit_cost(self, price: float, side: str) -> float:
        """
        Adjusts exit price based on spread and slippage.
        BUY closes at BID (price).
        SELL closes at ASK (price + spread).
        """
        total_cost_points = self.spread_points + self.slippage_points
        if side == "BUY":
            return price - self.slippage_points
        else:
            return price + total_cost_points
            
    def get_commission_cost(self, volume: float = 0.01) -> float:
        """
        Returns absolute monetary cost of commission.
        """
        return self.commission_per_lot * volume
