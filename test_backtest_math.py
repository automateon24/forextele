import unittest
import sys
from datetime import datetime, timedelta
import pandas as pd

# Mocking the math from report_1year_results.py
CONTRACT_SIZE = {
    "EURUSD": 100000, "GBPUSD": 100000, "AUDUSD": 100000, "USDJPY": 100000,
    "GOLD": 100, "SILVER": 5000, "BTCUSD": 1, "ETHUSD": 10
}
POINT = {
    "EURUSD": 0.00001, "GBPUSD": 0.00001, "USDJPY": 0.001, "AUDUSD": 0.00001,
    "GOLD": 0.01, "SILVER": 0.001, "BTCUSD": 0.01, "ETHUSD": 0.001
}

def compute_pnl(symbol, pts, lot_size):
    pt = POINT.get(symbol, 0.00001)
    cs = CONTRACT_SIZE.get(symbol, 100000)
    raw_pnl = pts * pt * cs * lot_size
    if symbol == "USDJPY":
        return raw_pnl / 150.0
    return raw_pnl

def calculate_dynamic_lot(symbol, risk_usd, sl_pts):
    pt = POINT.get(symbol, 0.00001)
    cs = CONTRACT_SIZE.get(symbol, 100000)
    usd_val = sl_pts * pt * cs
    if symbol == 'USDJPY':
        usd_val /= 150.0
    return risk_usd / usd_val if usd_val > 0 else 0.01

class TestBacktestEngineMath(unittest.TestCase):
    def test_pnl_calculation_forex(self):
        # 100 points (10 pips) on 1 Lot EURUSD = $100
        self.assertAlmostEqual(compute_pnl("EURUSD", 100.0, 1.0), 100.0, places=2)
        # 50 points (5 pips) on 0.5 Lot GBPUSD = $25
        self.assertAlmostEqual(compute_pnl("GBPUSD", 50.0, 0.5), 25.0, places=2)
        
    def test_pnl_calculation_jpy(self):
        # 100 points (10 pips) on 1 Lot USDJPY. 10 pips = 10,000 JPY / 150 = $66.67
        self.assertAlmostEqual(compute_pnl("USDJPY", 100.0, 1.0), 66.666, places=2)
        
    def test_pnl_calculation_crypto_gold(self):
        # 100 points ($1.00 move) on 1 Lot GOLD (100 oz) = $100
        self.assertAlmostEqual(compute_pnl("GOLD", 100.0, 1.0), 100.0, places=2)
        # 10000 points ($100 move) on 1 Lot BTCUSD (1 btc) = $100
        self.assertAlmostEqual(compute_pnl("BTCUSD", 10000.0, 1.0), 100.0, places=2)
        
    def test_lot_sizing(self):
        # $100 risk on 100 points SL EURUSD = 1.0 Lot
        self.assertAlmostEqual(calculate_dynamic_lot("EURUSD", 100.0, 100.0), 1.0, places=2)
        # $100 risk on 100 points SL USDJPY. 1 lot sl = $66.67. 100/66.67 = 1.5 Lots
        self.assertAlmostEqual(calculate_dynamic_lot("USDJPY", 100.0, 100.0), 1.5, places=2)
        # $100 risk on 100 points ($1) SL GOLD = 1.0 Lot
        self.assertAlmostEqual(calculate_dynamic_lot("GOLD", 100.0, 100.0), 1.0, places=2)

if __name__ == '__main__':
    unittest.main()
