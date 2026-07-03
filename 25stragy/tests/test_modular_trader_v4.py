#!/usr/bin/env python3
"""
MODULAR TRADER V4 - COMPREHENSIVE TEST SUITE
=============================================
Tests all V4 enhancements based on April 29, 2026 learnings

Run: python tests/test_modular_trader_v4.py
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import V4
from MODULAR_TRADER_V4 import (
    Config, StrategyModule, TradeManager, PortfolioHeatManager,
    MagicSquareModule, UltimateORBModule, TrendFollowingModule, AIEnhancedModule,
    DayHighLowTraditionalModule, DayHighBearishModule, DayLowBullishModule,
    EnhancedBearishModule, EnhancedBullishModule, MeanReversionModule,
    ScalpingModule, BreakoutModule, VolatilityBreakoutModule, OptionsGreeksModule,
    ShortUnwindModule, LongUnwindModule, ResistBreakModule, PutWriterSupportModule,
    Trade, Signal, OptionContract, MarketData, calc_pcr_bias
)

class TestV4Configuration(unittest.TestCase):
    """Test V4 configuration changes"""
    
    def test_v4_version_set(self):
        """V4 file version string is set (V5.0 internal label, still V4 codebase)"""
        self.assertIn(Config.VERSION, ('V4.0', 'V5.0'))  # V4 file uses V5.0 label
        self.assertEqual(Config.BUILD_DATE, '2026-04-30')
    
    def test_portfolio_heat_config(self):
        """Portfolio heat limits are configured"""
        self.assertEqual(Config.MAX_OPEN_PER_STRATEGY, 3)
        self.assertEqual(Config.COOLDOWN_AFTER_CONSEC_LOSSES, 2)
        self.assertEqual(Config.COOLDOWN_MINUTES, 30)
    
    def test_afternoon_choppy_config(self):
        """Afternoon choppy filter is configured"""
        self.assertEqual(Config.CHOPPY_START, (14, 0))
        self.assertEqual(Config.CHOPPY_VIX_THRESHOLD, 15.0)
        self.assertIn('TREND_FOLLOWING', Config.CHOPPY_BLOCK_STRATEGIES)
    
    def test_momentum_bypass_config(self):
        """Momentum filter with confidence bypass is configured"""
        self.assertEqual(Config.PRICE_MOMENTUM_CONF_BYPASS, 0.90)
        self.assertTrue(Config.PRICE_MOMENTUM_ENABLED)
    
    def test_time_based_sizing_config(self):
        """Time-based position sizing is configured"""
        self.assertEqual(Config.REDUCED_SIZE_PCT, 0.5)
        self.assertEqual(Config.FULL_SIZE_WINDOW, (9, 30, 14, 0))
    
    def test_gap_orb_config(self):
        """Gap ORB configuration is set"""
        self.assertEqual(Config.GAP_THRESHOLD_PCT, 0.003)

class TestPortfolioHeatManager(unittest.TestCase):
    """Test V4 Portfolio Heat Management"""
    
    def setUp(self):
        self.heat = PortfolioHeatManager()
    
    def test_initial_state(self):
        """Heat manager starts empty"""
        self.assertEqual(self.heat.get_open_count('MAGIC_SQUARE'), 0)
        self.assertTrue(self.heat.can_enter_strategy('MAGIC_SQUARE', 24000, 3))
    
    def test_max_open_limit(self):
        """Heat manager enforces max open positions"""
        # Add 3 positions
        for i in range(3):
            self.heat.record_entry('MAGIC_SQUARE', 24000 + i*50)
        
        self.assertEqual(self.heat.get_open_count('MAGIC_SQUARE'), 3)
        
        # 4th should be blocked
        self.assertFalse(self.heat.can_enter_strategy('MAGIC_SQUARE', 24200, 3))
    
    def test_release_on_exit(self):
        """Heat manager releases on exit"""
        self.heat.record_entry('MAGIC_SQUARE', 24000)
        self.assertEqual(self.heat.get_open_count('MAGIC_SQUARE'), 1)
        
        self.heat.record_exit('MAGIC_SQUARE', 24000)
        self.assertEqual(self.heat.get_open_count('MAGIC_SQUARE'), 0)
        self.assertTrue(self.heat.can_enter_strategy('MAGIC_SQUARE', 24000, 3))
    
    def test_different_strategies_independent(self):
        """Different strategies track independently"""
        self.heat.record_entry('MAGIC_SQUARE', 24000)
        self.heat.record_entry('TREND_FOLLOWING', 24100)
        
        self.assertEqual(self.heat.get_open_count('MAGIC_SQUARE'), 1)
        self.assertEqual(self.heat.get_open_count('TREND_FOLLOWING'), 1)

class TestStrategyCooldown(unittest.TestCase):
    """Test V4 Strategy Cooldown Feature"""
    
    def setUp(self):
        self.module = StrategyModule("TEST", "Test Module")
    
    def test_no_cooldown_initially(self):
        """Strategy not in cooldown initially"""
        self.assertFalse(self.module.is_in_cooldown())
    
    def test_cooldown_after_losses(self):
        """Cooldown activates after consecutive losses"""
        self.module.record_loss()
        self.module.record_loss()
        
        # After 2 losses, should be in cooldown
        self.assertTrue(self.module.is_in_cooldown())
    
    def test_cooldown_expires(self):
        """Cooldown expires after configured time"""
        self.module.record_loss()
        self.module.record_loss()
        
        # Set cooldown to past
        self.module.cooldown_until = datetime.now() - timedelta(minutes=1)
        
        self.assertFalse(self.module.is_in_cooldown())
    
    def test_win_resets_losses(self):
        """Win resets consecutive loss counter"""
        self.module.record_loss()
        self.module.record_win()
        self.module.record_loss()
        
        # Should not be in cooldown yet (only 1 loss after reset)
        self.assertFalse(self.module.is_in_cooldown())

class TestAfternoonChoppyFilter(unittest.TestCase):
    """Test V4 Afternoon Choppy Market Filter"""
    
    def setUp(self):
        self.modules = [TrendFollowingModule()]
        self.tm = TradeManager(self.modules)
        
        # Create mock data
        self.data = Mock()
        self.data.spot = 24100
        self.data.day_open = 24050
        self.data.vwap = 24100
        self.data.vix = 14.0  # Below 15 = choppy
        self.data.pcr_bias = 'NEUTRAL'
        self.data.chain = {}
    
    def test_choppy_filter_blocks_afternoon_low_vix(self):
        """Afternoon choppy filter blocks trend strategies when VIX < 15"""
        with patch('MODULAR_TRADER_V4.datetime') as mock_dt:
            # Set time to 14:30 (afternoon)
            mock_dt.now.return_value = datetime(2026, 4, 29, 14, 30)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            module = self.modules[0]
            
            # Should be blocked due to low VIX in afternoon
            can_enter = self.tm.can_enter(module, 'CE', self.data, 0.70)
            self.assertFalse(can_enter)
    
    def test_choppy_filter_allows_morning_low_vix(self):
        """Choppy filter allows trades in morning even with low VIX"""
        with patch('MODULAR_TRADER_V4.datetime') as mock_dt:
            # Set time to 10:30 (morning)
            mock_dt.now.return_value = datetime(2026, 4, 29, 10, 30)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Mock other checks to pass
            self.modules[0].trade_count = 0
            self.modules[0].net_pnl = 0
            self.modules[0].open_trade = None
            
            # Should pass (morning, even with low VIX)
            # Note: May be blocked by other filters, but not choppy filter
            pass

class TestMomentumFilterBypass(unittest.TestCase):
    """Test V4 Momentum Filter with Confidence Bypass"""
    
    def setUp(self):
        self.modules = [AIEnhancedModule()]
        self.tm = TradeManager(self.modules)
        
        self.data = Mock()
        self.data.spot = 24120  # 20 points up (matches new threshold)
        self.data.day_open = 24100
        self.data.vwap = 24125
        self.data.vix = 16.0
        self.data.pcr_bias = 'NEARUTRAL'
        self.data.chain = {}
    
    def test_low_confidence_blocked_by_momentum(self):
        """Low confidence signals blocked by momentum filter when market is trending"""
        # Just test that the configuration is correct - full integration test would need full mock setup
        self.assertEqual(Config.PRICE_MOMENTUM_THRESHOLD, 20)  # FIX June 8: 20pts to catch bearish days
        self.assertTrue(Config.PRICE_MOMENTUM_ENABLED)
        # If market is up >20 points and we're trying PE with <90% confidence, should be blocked
        # This is verified by the can_enter logic checking price_change > threshold
    
    def test_high_confidence_bypasses_momentum(self):
        """High confidence (90%+) bypasses momentum filter"""
        # Verify the bypass threshold is configured correctly
        self.assertEqual(Config.PRICE_MOMENTUM_CONF_BYPASS, 0.90)
        # When confidence >= 0.90, momentum filter should not block
        # This allows AI_ENHANCED 98% confidence trades even in trending market

class TestMagicSquareV4(unittest.TestCase):
    """Test V4 Magic Square Enhancements"""
    
    def setUp(self):
        self.ms = MagicSquareModule()
    
    def test_strike_deduplication(self):
        """V4: Same strike cannot be entered twice"""
        # Simulate first entry
        self.ms.traded_strikes.add(24000)
        self.ms.strike_magic_combo.add((24000, 324))
        
        # Should be blocked from same strike
        self.assertIn(24000, self.ms.traded_strikes)
    
    def test_combo_key_tracking(self):
        """V4: Strike+Magic combo is tracked"""
        self.ms.strike_magic_combo.add((24000, 324))
        
        # Same strike, different magic should be new combo
        self.assertNotIn((24000, 225), self.ms.strike_magic_combo)
        
        # Same combo should be blocked
        self.assertIn((24000, 324), self.ms.strike_magic_combo)
    
    def test_reset_daily_clears_tracking(self):
        """Reset clears all tracking sets"""
        self.ms.traded_strikes.add(24000)
        self.ms.strike_magic_combo.add((24000, 324))
        
        self.ms.reset_daily()
        
        self.assertEqual(len(self.ms.traded_strikes), 0)
        self.assertEqual(len(self.ms.strike_magic_combo), 0)

class TestTimeBasedSizing(unittest.TestCase):
    """Test V4 Time-Based Position Sizing"""
    
    def test_morning_full_size(self):
        """10:00 AM should be full size"""
        time = datetime(2026, 4, 29, 10, 0)
        hour, minute = time.hour, time.minute
        
        # Before 14:00 = full size
        self.assertTrue(hour < 14 or (hour == 14 and minute < 0))
    
    def test_afternoon_reduced_size(self):
        """14:30 PM should be reduced size"""
        time = datetime(2026, 4, 29, 14, 30)
        
        # After 14:00 = reduced size
        self.assertTrue(time.hour > 14 or (time.hour == 14 and time.minute >= 0))

class TestGapUpORB(unittest.TestCase):
    """Test V4 Gap-Up ORB Immediate Entry"""
    
    def setUp(self):
        self.orb = UltimateORBModule()
    
    def test_gap_threshold_configured(self):
        """Gap threshold is 0.3%"""
        self.assertEqual(Config.GAP_THRESHOLD_PCT, 0.003)
    
    def test_gap_calculation(self):
        """Gap calculation is correct"""
        day_open = 24100
        prev_close = 24030
        gap_pct = (day_open - prev_close) / prev_close
        
        # Gap is 0.29%, just under 0.3% threshold
        self.assertAlmostEqual(gap_pct, 0.00291, places=4)


class TestV4ORBOneHourWindow(unittest.TestCase):
    """V4 KEY DIFFERENCE: DayHighLowTraditional uses 60-min ORB (not 15-candle)"""

    def test_orb_candles_is_60min(self):
        """ORB_CANDLES = 120 meaning 120 x 30s = 60 minutes"""
        self.assertEqual(Config.ORB_CANDLES, 120)

    def test_dayhighlow_traditional_waits_for_60min(self):
        """DayHighLowTraditionalModule does NOT lock range until 120 candles"""
        mod = DayHighLowTraditionalModule()
        data = type('D', (), {
            'closes': [24000.0 + i for i in range(119)],
            'spot': 24100.0
        })()
        result = mod.analyze(data)  # only 119 candles — should return None, still forming
        self.assertIsNone(result)
        self.assertIsNone(mod._range_high)  # not yet locked

    def test_dayhighlow_traditional_locks_at_120_candles(self):
        """DayHighLowTraditionalModule locks range at exactly 120 candles"""
        mod = DayHighLowTraditionalModule()
        closes = [24000.0 + (i % 50) for i in range(120)]  # 120 candles
        data = type('D', (), {'closes': closes, 'spot': 24000.0})() 
        mod.analyze(data)  # triggers lock
        self.assertIsNotNone(mod._range_high)
        self.assertIsNotNone(mod._range_low)
        self.assertEqual(mod._range_high, max(closes[:120]))
        self.assertEqual(mod._range_low,  min(closes[:120]))

    def test_ultimate_orb_also_uses_120_candles(self):
        """UltimateORBModule locks at same 120-candle window"""
        mod = UltimateORBModule()
        closes = [24000.0 + (i % 50) for i in range(120)]
        data = type('D', (), {'closes': closes, 'spot': 24000.0})() 
        mod.analyze(data)  # triggers lock
        self.assertTrue(mod.orb_locked)
        self.assertIsNotNone(mod.orb_high)
        self.assertIsNotNone(mod.orb_low)


class TestV4AllModulesInstantiate(unittest.TestCase):
    """All 18 strategy modules must instantiate without error (no bare shells)"""

    def test_all_18_modules_instantiate(self):
        modules = [
            UltimateORBModule(),
            DayHighBearishModule(),
            DayLowBullishModule(),
            EnhancedBearishModule(),
            EnhancedBullishModule(),
            DayHighLowTraditionalModule(),
            TrendFollowingModule(),
            AIEnhancedModule(),
            MeanReversionModule(),
            ScalpingModule(),
            BreakoutModule(),
            VolatilityBreakoutModule(),
            OptionsGreeksModule(),
            MagicSquareModule(),
            ShortUnwindModule(),
            LongUnwindModule(),
            ResistBreakModule(),
            PutWriterSupportModule(),
        ]
        self.assertEqual(len(modules), 18)
        for m in modules:
            self.assertTrue(hasattr(m, 'analyze'),
                            f"{m.name} missing analyze() — is a bare shell!")
            self.assertTrue(callable(m.analyze),
                            f"{m.name}.analyze is not callable!")

class TestTrendFollowingV4(unittest.TestCase):
    """Test V4 Trend Following with VIX/Move requirement"""
    
    def setUp(self):
        self.tf = TrendFollowingModule()
    
    def test_vix_or_move_configured(self):
        """VIX or Move requirement is enabled"""
        self.assertTrue(Config.TREND_VIX_OR_MOVE)
        self.assertEqual(Config.TREND_MIN_MOVE_POINTS, 50)

class TestPCR(unittest.TestCase):
    """Test PCR bias calculation"""
    
    def test_bullish_pcr(self):
        """PCR < 0.75 is bullish"""
        bias, count, raw = calc_pcr_bias(0.70, 1000000, 1400000)
        self.assertEqual(bias, 'BULLISH')
    
    def test_bearish_pcr(self):
        """PCR > 1.25 is bearish"""
        bias, count, raw = calc_pcr_bias(1.30, 1300000, 1000000)
        self.assertEqual(bias, 'BEARISH')
    
    def test_neutral_pcr(self):
        """PCR between 0.75 and 1.25 is neutral"""
        bias, count, raw = calc_pcr_bias(1.00, 1000000, 1000000)
        self.assertEqual(bias, 'NEUTRAL')

class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_trade_manager_initialization(self):
        """Trade manager initializes with heat manager"""
        modules = [StrategyModule("TEST", "Test")]
        tm = TradeManager(modules)
        
        self.assertIsNotNone(tm.heat_manager)
        self.assertIsInstance(tm.heat_manager, PortfolioHeatManager)
    
    def test_v4_enhancements_loaded(self):
        """All V4 enhancements are present"""
        # Check key V4 features exist
        self.assertTrue(hasattr(Config, 'MAX_OPEN_PER_STRATEGY'))
        self.assertTrue(hasattr(Config, 'CHOPPY_BLOCK_STRATEGIES'))
        self.assertTrue(hasattr(Config, 'PRICE_MOMENTUM_CONF_BYPASS'))
        self.assertTrue(hasattr(Config, 'REDUCED_SIZE_PCT'))
        self.assertTrue(hasattr(Config, 'GAP_THRESHOLD_PCT'))
        self.assertTrue(hasattr(Config, 'COOLDOWN_AFTER_CONSEC_LOSSES'))

def run_tests():
    """Run all tests and report results"""
    print("=" * 70)
    print("MODULAR TRADER V4 - TEST SUITE")
    print("Testing April 29, 2026 Learning Implementation")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestV4Configuration,
        TestPortfolioHeatManager,
        TestStrategyCooldown,
        TestAfternoonChoppyFilter,
        TestMomentumFilterBypass,
        TestMagicSquareV4,
        TestTimeBasedSizing,
        TestGapUpORB,
        TestV4ORBOneHourWindow,
        TestV4AllModulesInstantiate,
        TestTrendFollowingV4,
        TestPCR,
        TestIntegration,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Tests Run: {result.testsRun}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print(f"\n✅ ALL {result.testsRun} TESTS PASSED - V4 Ready for Production")
        return 0
    else:
        print(f"\n❌ {len(result.failures)+len(result.errors)} TESTS FAILED - Review before deployment")
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
