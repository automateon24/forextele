import unittest
import pandas as pd
import sys
import os

sys.path.insert(0, r'c:\cursor\options\niftyopt')
sys.path.insert(0, r'C:\25stragy')

from regime_detector import RegimeDetector, RegimeSnapshot, DayContext, label_days, regime_summary

class TestRegimeDetector(unittest.TestCase):
    def setUp(self):
        self.detector = RegimeDetector()
        
    def test_new_day(self):
        self.detector.new_day(24000.0)
        self.assertEqual(self.detector._ctx.day_open, 24000.0)
        self.assertEqual(self.detector._ctx.day_high, 24000.0)
        self.assertEqual(self.detector._ctx.day_low, 24000.0)
        self.assertEqual(self.detector._candle_count, 0)
        
    def test_update_normal_regime(self):
        self.detector.new_day(24000.0)
        snap = self.detector.update(24010.0, iv=15.0, hhmm=915)
        self.assertEqual(snap.regime, "NORMAL")
        self.assertEqual(snap.spot_vs_open, 10.0)
        self.assertEqual(snap.daily_range, 10.0)
        
    def test_update_high_volatility(self):
        self.detector.new_day(24000.0)
        snap = self.detector.update(24400.0, iv=25.0, hhmm=930) # iv > 20
        self.assertEqual(snap.regime, "HIGH_VOLATILITY")
        self.assertEqual(snap.size_multiplier, 0.5)
        
    def test_update_trending_bull(self):
        self.detector.new_day(24000.0)
        snap = self.detector.update(24200.0, iv=15.0, hhmm=930) # move = 200, > 24000 * 0.0065 = 156
        self.assertEqual(snap.regime, "TRENDING_BULL")
        
    def test_update_trending_bear(self):
        self.detector.new_day(24000.0)
        snap = self.detector.update(23800.0, iv=15.0, hhmm=930) # move = -200
        self.assertEqual(snap.regime, "TRENDING_BEAR")
        
    def test_update_range_bound(self):
        self.detector.new_day(24000.0)
        # small move from open, narrow range
        snap = self.detector.update(24010.0, iv=15.0, hhmm=930)
        self.assertEqual(snap.regime, "RANGE_BOUND")
        
    def test_udhl_block(self):
        self.detector.new_day(24000.0)
        # spot moved > udhl_threshold (24000 * 0.0043 = 103.2)
        snap = self.detector.update(24105.0, iv=15.0, hhmm=930)
        self.assertTrue(snap.udhl_blocked)
        self.assertFalse(snap.strategy_flags.get("ULTIMATE_DAY_HIGH_LOW", True))
        
    def test_udhl_block_time(self):
        self.detector.new_day(24000.0)
        snap = self.detector.update(24010.0, iv=15.0, hhmm=1401)
        self.assertTrue(snap.udhl_blocked)
        self.assertFalse(snap.strategy_flags.get("ULTIMATE_DAY_HIGH_LOW", True))

    def test_classify_day_batch(self):
        df = pd.DataFrame({
            "hhmm": [915, 930, 1000],
            "spot": [24000.0, 24200.0, 24250.0],
            "iv": [15.0, 15.0, 15.0]
        })
        regime = RegimeDetector.classify_day(df)
        self.assertEqual(regime, "TRENDING_BULL")

    def test_label_days(self):
        df = pd.DataFrame({
            "date": ["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02"],
            "hhmm": [915, 1000, 915, 1000],
            "spot": [24000.0, 24250.0, 24000.0, 23800.0],
            "iv": [15.0, 15.0, 15.0, 15.0]
        })
        labels = label_days(df)
        self.assertEqual(labels["2026-06-01"], "TRENDING_BULL")
        self.assertEqual(labels["2026-06-02"], "TRENDING_BEAR")

    def test_regime_summary(self):
        df = pd.DataFrame({
            "date": ["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02"],
            "hhmm": [915, 1000, 915, 1000],
            "spot": [24000.0, 24250.0, 24000.0, 23800.0],
            "iv": [15.0, 15.0, 15.0, 15.0]
        })
        summary = regime_summary(df)
        self.assertEqual(summary.loc[2026, "TRENDING_BULL"], 1)
        self.assertEqual(summary.loc[2026, "TRENDING_BEAR"], 1)

if __name__ == '__main__':
    unittest.main()
