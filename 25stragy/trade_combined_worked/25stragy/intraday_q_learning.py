import math
from typing import Dict, List, Any

class IntradayQBrain:
    """
    On-The-Fly (Intraday) Q-Learning & Adaptive Micro-Tuner.
    Tracks live performance within the exact same day to dynamically
    adjust risk allocation, block failing strategies, and boost hot strategies.
    """
    def __init__(self):
        self.strat_stats: Dict[str, Dict[str, float]] = {}
        self.index_stats: Dict[str, Dict[str, float]] = {}
        # strategy -> { 'wins': 0, 'losses': 0, 'consecutive_losses': 0, 'block_until': 0 }
        # index -> { 'wins': 0, 'losses': 0, 'consecutive_losses': 0 }
        
    def register_closed_trade(self, strategy: str, index: str, pnl: float, current_hhmm: int):
        if strategy not in self.strat_stats:
            self.strat_stats[strategy] = {'wins': 0, 'losses': 0, 'consecutive_losses': 0, 'block_until': 0}
        if index not in self.index_stats:
            self.index_stats[index] = {'wins': 0, 'losses': 0, 'consecutive_losses': 0}
            
        s_stat = self.strat_stats[strategy]
        i_stat = self.index_stats[index]
        
        if pnl > 0:
            s_stat['wins'] += 1
            s_stat['consecutive_losses'] = 0
            i_stat['wins'] += 1
            i_stat['consecutive_losses'] = 0
        else:
            s_stat['losses'] += 1
            s_stat['consecutive_losses'] += 1
            i_stat['losses'] += 1
            i_stat['consecutive_losses'] += 1
            
            # If strategy fails 2 times in a row, block it for 2 hours
            if s_stat['consecutive_losses'] >= 2:
                # Add 200 (2 hours) to HHMM, handle hour overflow
                h = current_hhmm // 100
                m = current_hhmm % 100
                h += 2
                self.strat_stats[strategy]['block_until'] = h * 100 + m

    def get_strategy_multiplier(self, strategy: str, current_hhmm: int) -> float:
        """
        Returns a size multiplier between 0.0 (blocked) and 1.5 (hot).
        """
        if strategy not in self.strat_stats:
            return 1.0
            
        s_stat = self.strat_stats[strategy]
        
        # 1. Block check
        if s_stat['block_until'] > current_hhmm:
            return 0.0
            
        # 2. Hot Hand (100% win rate with at least 2 wins)
        if s_stat['wins'] >= 2 and s_stat['losses'] == 0:
            return 1.5
            
        # 3. Cooling off (1 win, 1 loss)
        if s_stat['losses'] > s_stat['wins']:
            return 0.5
            
        return 1.0

    def get_index_multiplier(self, index: str) -> float:
        """
        Dampen entire index capital if the index is persistently choppy/losing.
        """
        if index not in self.index_stats:
            return 1.0
            
        i_stat = self.index_stats[index]
        
        if i_stat['consecutive_losses'] >= 3:
            return 0.25  # Severe penalty
        elif i_stat['consecutive_losses'] == 2:
            return 0.50  # Caution
            
        total = i_stat['wins'] + i_stat['losses']
        if total >= 3:
            win_rate = i_stat['wins'] / total
            if win_rate > 0.7:
                return 1.25 # Boost
            if win_rate < 0.3:
                return 0.5 # Penalty
                
        return 1.0
