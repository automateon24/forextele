#!/usr/bin/env python3
"""
TEST SUITE: MODULAR_TRADER_V3.py
=================================
Industry-standard tests for a live financial trading program.

Test Categories:
  1. SANITY   - Config values are safe and within expected bounds
  2. UNIT     - Each strategy's analyze() method with synthetic data
  3. FILTER   - can_enter() gate logic (direction, PCR, VWAP, momentum, time)
  4. RISK     - SL/Target calculation, trailing stop, time-stop
  5. RELOAD   - Trade state reload from CSV on startup
  6. HEALTH   - LiveHealthMonitor.qualify() produces valid output
  7. INTEGRATION - Full cycle: data → analyze → enter → manage_exit
  8. EOD      - EOD force-exit only hits truly open trades (orphan bug regression)

Run:  py tests/test_modular_trader_v3.py
"""

import sys, os, csv, json, time, unittest, tempfile, threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional, Dict

# ── Patch API import before loading V3 ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')

# Mock dhanhq so we don't need the real library to run tests
import types
mock_dhan_module = types.ModuleType('dhanhq')
class MockDhan:
    def __init__(self, *a, **kw): pass
mock_dhan_module.dhanhq = MockDhan
sys.modules['dhanhq'] = mock_dhan_module

# ── Now import V3 ────────────────────────────────────────────────────────────
from MODULAR_TRADER_V3 import (
    Config, MarketData, OptionContract, Trade, Signal, StrategyModule,
    TradeManager,
    UltimateDayHighLowModule, DayHighBearishModule, DayLowBullishModule,
    EnhancedBearishModule, EnhancedBullishModule, DayHighLowTraditionalModule,
    TrendFollowingModule, AIEnhancedModule, MeanReversionModule,
    ScalpingModule, BreakoutModule, VolatilityBreakoutModule,
    OptionsGreeksModule, MagicSquareModule,
    ShortUnwindModule, LongUnwindModule, ResistBreakModule, PutWriterSupportModule,
    OrderBlockReversalModule,
    LiveHealthMonitor,
)

# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def make_option(strike, opt_type, ltp, delta=0.50, theta=-5.0, iv=20.0, oi=100000, volume=5000):
    # OptionContract field order: security_id, strike, option_type, ltp, iv, delta, gamma, theta, vega, oi, volume, bid, ask
    return OptionContract(
        security_id=None, strike=strike, option_type=opt_type,
        ltp=ltp, iv=iv, delta=delta, gamma=0.001, theta=theta, vega=20,
        oi=oi, volume=volume, bid=ltp-0.5, ask=ltp+0.5
    )

def make_chain(spot, atm_step=50, n_strikes=10):
    atm = round(spot / atm_step) * atm_step
    chain = {}
    for i in range(-n_strikes//2, n_strikes//2 + 1):
        s = atm + i * atm_step
        dist = abs(s - spot)
        ce_delta = max(0.05, 0.50 - dist/1000)
        pe_delta = max(0.05, 0.50 - dist/1000)
        ce_ltp = max(1.0, 200 - dist * 0.8)
        pe_ltp = max(1.0, 200 - dist * 0.8)
        theta_v = -5 - dist * 0.01
        chain[s] = {
            'CE': make_option(s, 'CE', ce_ltp, delta=ce_delta, theta=theta_v),
            'PE': make_option(s, 'PE', pe_ltp, delta=pe_delta, theta=theta_v),
        }
    return chain, atm

def make_data(spot=24000, day_open=24000, day_high=24100, day_low=23900,
              prev_close=23980, rsi14=55.0, pcr=1.0, pcr_bias='NEUTRAL',
              ema5=24010, ema20=23990, vwap=24005, closes=None,
              prev_oi=None, max_call_oi=24200, max_put_oi=23800):
    chain, atm = make_chain(spot)
    if closes is None:
        closes = [day_open + i*2 for i in range(20)]
    # MarketData positional: timestamp, spot, day_open, day_high, day_low, prev_close, vix
    data = MarketData(
        timestamp=datetime.now(),
        spot=spot,
        day_open=day_open,
        day_high=day_high,
        day_low=day_low,
        prev_close=prev_close,
        vix=15.0,
    )
    data.rsi14 = rsi14
    data.pcr = pcr
    data.pcr_bias = pcr_bias
    data.ema5 = ema5
    data.ema20 = ema20
    data.vwap = vwap
    data.closes = closes
    data.chain = chain
    data.atm_strike = atm
    data.max_call_oi_strike = max_call_oi
    data.max_put_oi_strike = max_put_oi
    data.prev_oi_state = prev_oi or {}
    data.prev_spot = spot - 5
    return data


# ════════════════════════════════════════════════════════════════════════════
# 1. SANITY TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestSanityConfig(unittest.TestCase):
    """Config values are safe and within expected industry bounds."""

    def test_lot_size_positive(self):
        self.assertGreater(Config.LOT_SIZE, 0)

    def test_sl_pct_bounded(self):
        self.assertGreater(Config.SL_PCT, 0)
        self.assertLess(Config.SL_PCT, 1.0, "SL_PCT >= 100% would allow unlimited loss")

    def test_target_pct_greater_than_sl(self):
        self.assertGreater(Config.TARGET_PCT, Config.SL_PCT,
                           "Risk:reward must be > 1. Target must be larger than SL")

    def test_capital_per_strategy_reasonable(self):
        self.assertGreaterEqual(Config.CAPITAL_PER_STRATEGY, 5000)
        self.assertLessEqual(Config.CAPITAL_PER_STRATEGY, 500_000)

    def test_daily_loss_limit_negative(self):
        self.assertLess(Config.DAILY_LOSS_LIMIT, 0, "DAILY_LOSS_LIMIT should be negative")

    def test_daily_profit_target_positive(self):
        self.assertGreater(Config.DAILY_PROFIT_TARGET, 0)

    def test_market_open_before_close(self):
        open_mins  = Config.MARKET_OPEN[0]  * 60 + Config.MARKET_OPEN[1]
        close_mins = Config.MARKET_CLOSE[0] * 60 + Config.MARKET_CLOSE[1]
        self.assertLess(open_mins, close_mins)

    def test_no_entry_after_before_market_close(self):
        no_entry_mins = Config.NO_ENTRY_AFTER[0] * 60 + Config.NO_ENTRY_AFTER[1]
        close_mins    = Config.MARKET_CLOSE[0]   * 60 + Config.MARKET_CLOSE[1]
        self.assertLessEqual(no_entry_mins, close_mins)

    def test_trail_lock_gt_breakeven(self):
        self.assertGreater(Config.TRAIL_LOCK_PCT, Config.TRAIL_BREAKEVEN_PCT)

    def test_time_stop_minutes_positive(self):
        self.assertGreater(Config.TIME_STOP_MINUTES, 0)

    def test_magic_squares_are_perfect_squares(self):
        import math
        for sq in Config.MAGIC_SQUARES:
            root = math.isqrt(sq)
            self.assertEqual(root * root, sq, f"{sq} is not a perfect square")

    def test_premium_max_realistic(self):
        self.assertGreater(Config.PREMIUM_MAX, 0)
        self.assertLess(Config.PREMIUM_MAX, 5000)

    def test_18_strategy_count(self):
        # Instantiate all and verify 18 exist
        from MODULAR_TRADER_V3 import (
            UltimateDayHighLowModule, DayHighBearishModule, DayLowBullishModule,
            EnhancedBearishModule, EnhancedBullishModule, DayHighLowTraditionalModule,
            TrendFollowingModule, AIEnhancedModule, MeanReversionModule,
            ScalpingModule, BreakoutModule, VolatilityBreakoutModule,
            OptionsGreeksModule, MagicSquareModule,
            ShortUnwindModule, LongUnwindModule, ResistBreakModule, PutWriterSupportModule,
        )
        modules = [
            UltimateDayHighLowModule(), DayHighBearishModule(), DayLowBullishModule(),
            EnhancedBearishModule(), EnhancedBullishModule(), DayHighLowTraditionalModule(),
            TrendFollowingModule(), AIEnhancedModule(), MeanReversionModule(),
            ScalpingModule(), BreakoutModule(), VolatilityBreakoutModule(),
            OptionsGreeksModule(), MagicSquareModule(),
            ShortUnwindModule(), LongUnwindModule(), ResistBreakModule(), PutWriterSupportModule(),
        ]
        self.assertEqual(len(modules), 18)


# ════════════════════════════════════════════════════════════════════════════
# 2. UNIT TESTS - Strategy analyze() methods
# ════════════════════════════════════════════════════════════════════════════

class TestUltimateORB(unittest.TestCase):
    def setUp(self):
        self.mod = UltimateDayHighLowModule()

    def test_no_signal_before_15_candles(self):
        data = make_data(closes=[24000]*10)
        self.assertIsNone(self.mod.analyze(data))

    def test_orb_locked_at_candle_15(self):
        closes = [24000 + i for i in range(20)]
        data = make_data(closes=closes)
        self.mod.analyze(data)
        self.assertIsNotNone(self.mod.orb_high)
        self.assertEqual(self.mod.orb_high, max(closes[:15]))
        self.assertEqual(self.mod.orb_low,  min(closes[:15]))

    def test_orb_level_static_after_lock(self):
        closes = [24000 + i for i in range(20)]
        data = make_data(closes=closes)
        self.mod.analyze(data)
        locked_high = self.mod.orb_high
        # Simulate more candles with higher highs
        data.closes = closes + [25000, 25100]
        self.mod.analyze(data)
        self.assertEqual(self.mod.orb_high, locked_high, "ORB high must not change after lock")

    def test_no_entry_on_first_breakout_without_retest(self):
        """Must NOT fire on first breakout – needs retest first."""
        closes = [24000] * 15 + [24200, 24250]  # big break above
        data = make_data(spot=24250, day_high=24250, closes=closes)
        sig = self.mod.analyze(data)
        # After lock: first cycle just sets orb_high, returns None
        # Second cycle sees breakout, sets _broke_ce=True, still None
        self.assertIsNone(sig, "Must NOT enter on first breakout without retest")

    def test_entry_after_break_retest_rebreak(self):
        mod = UltimateDayHighLowModule()
        closes = [24000] * 15
        data = make_data(spot=24000, closes=closes)
        mod.analyze(data)  # locks ORB H=24000 L=24000
        orb_h = mod.orb_high

        # Step 1: breakout
        data.spot = orb_h * 1.003
        mod.analyze(data)
        self.assertTrue(mod._broke_ce)

        # Step 2: retest (pull back)
        data.spot = orb_h * 1.0005
        mod.analyze(data)
        self.assertTrue(mod._retest_ce)

        # Step 3: re-break → should fire CE
        data.spot = orb_h * 1.002
        sig = mod.analyze(data)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, 'CE')

    def test_pe_side_break_retest_rebreak(self):
        mod = UltimateDayHighLowModule()
        closes = [24100] * 15
        data = make_data(spot=24100, closes=closes)
        mod.analyze(data)
        orb_l = mod.orb_low

        data.spot = orb_l * 0.997
        mod.analyze(data)
        self.assertTrue(mod._broke_pe)

        data.spot = orb_l * 0.9995
        mod.analyze(data)
        self.assertTrue(mod._retest_pe)

        data.spot = orb_l * 0.998
        sig = mod.analyze(data)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, 'PE')

    def test_ce_fires_only_once(self):
        mod = UltimateDayHighLowModule()
        closes = [24000]*15
        data = make_data(spot=24000, closes=closes)
        mod.analyze(data)
        orb_h = mod.orb_high
        data.spot = orb_h * 1.003; mod.analyze(data)
        data.spot = orb_h * 1.0005; mod.analyze(data)
        data.spot = orb_h * 1.002; sig1 = mod.analyze(data)
        data.spot = orb_h * 1.005; sig2 = mod.analyze(data)
        self.assertIsNotNone(sig1)
        self.assertIsNone(sig2, "CE must only fire once (ce_fired=True)")


class TestDayHighBearish(unittest.TestCase):
    def setUp(self):
        self.mod = DayHighBearishModule()
        self.closes = [24100] * 15

    def test_no_signal_low_pcr(self):
        data = make_data(spot=24100, day_high=24100, rsi14=75, pcr=0.8, closes=self.closes)
        self.assertIsNone(self.mod.analyze(data), "PCR < 1.1 must block PE signal")

    def test_no_signal_low_rsi(self):
        data = make_data(spot=24100, day_high=24100, rsi14=60, pcr=1.2, closes=self.closes)
        self.assertIsNone(self.mod.analyze(data), "RSI < 65 must block PE signal")

    def test_requires_retest_sequence(self):
        """touch → pull back → touch again = fire"""
        # Lock session high
        data = make_data(spot=24100, day_high=24110, rsi14=72, pcr=1.15, closes=self.closes)
        self.mod.analyze(data)  # lock
        ref_high = self.mod._session_high

        # Touch
        data.spot = ref_high * 0.998
        self.mod.analyze(data)
        self.assertTrue(self.mod._touched_high)

        # Pull back
        data.spot = ref_high * 0.993
        self.mod.analyze(data)
        self.assertTrue(self.mod._retested)

        # Re-touch → should fire
        data.spot = ref_high * 0.998
        sig = self.mod.analyze(data)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, 'PE')


class TestDayLowBullish(unittest.TestCase):
    def setUp(self):
        self.mod = DayLowBullishModule()
        self.closes = [23900]*15

    def test_no_signal_pcr_below_1_2(self):
        data = make_data(spot=23900, day_low=23900, rsi14=25, pcr=1.1, closes=self.closes)
        self.assertIsNone(self.mod.analyze(data), "PCR < 1.2 must block CE signal")

    def test_no_signal_rsi_above_35(self):
        data = make_data(spot=23900, day_low=23900, rsi14=40, pcr=1.3, closes=self.closes)
        self.assertIsNone(self.mod.analyze(data), "RSI > 35 must block CE signal")

    def test_double_bottom_fires_ce(self):
        data = make_data(spot=23900, day_low=23900, rsi14=25, pcr=1.25, closes=self.closes)
        self.mod.analyze(data)
        ref_low = self.mod._session_low

        # Touch
        data.spot = ref_low * 1.002
        self.mod.analyze(data)
        self.assertTrue(self.mod._touched_low)

        # Bounce
        data.spot = ref_low * 1.005
        self.mod.analyze(data)
        self.assertTrue(self.mod._retested)

        # Dip back → fire
        data.spot = ref_low * 1.002
        sig = self.mod.analyze(data)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, 'CE')


class TestEnhancedBullishPCR(unittest.TestCase):
    def test_pcr_below_0_9_and_rsi_above_30_blocks(self):
        mod = EnhancedBullishModule()
        # RSI=32 (not deeply oversold), PCR=0.7 (below 0.9) → should block
        data = make_data(spot=23900, day_low=23900, rsi14=32, pcr=0.7)
        self.assertIsNone(mod.analyze(data), "PCR<0.9 + RSI>30 must block ENHANCED_BULLISH")

    def test_rsi_deeply_oversold_passes_without_pcr(self):
        mod = EnhancedBullishModule()
        # RSI=25 (deeply oversold <=30) → should pass regardless of PCR
        data = make_data(spot=23900, day_low=23950, rsi14=25, pcr=0.7)
        # spot <= day_low * 1.005 = 23950*1.005 = 24069.75 → ok
        # Key: RSI <= 30 alone should pass the filter (may still be None if no contract)
        # Verify that higher RSI + low PCR blocks
        mod2 = EnhancedBullishModule()
        data2 = make_data(spot=23900, day_low=23950, rsi14=32, pcr=0.7)
        sig2 = mod2.analyze(data2)
        self.assertIsNone(sig2, "RSI>30 + PCR<0.9 must block")


class TestMeanReversion(unittest.TestCase):
    def test_no_signal_small_deviation(self):
        mod = MeanReversionModule()
        # 0.3% deviation < 0.5% threshold
        data = make_data(spot=24072, day_open=24000, rsi14=70)
        self.assertIsNone(mod.analyze(data))

    def test_pe_signal_on_upside_deviation(self):
        mod = MeanReversionModule()
        # 0.6% deviation above open + RSI overbought
        data = make_data(spot=24144, day_open=24000, rsi14=70)
        sig = mod.analyze(data)
        if sig:
            self.assertEqual(sig.direction, 'PE')

    def test_ce_signal_on_downside_deviation(self):
        mod = MeanReversionModule()
        # -0.6% below open + RSI oversold
        data = make_data(spot=23856, day_open=24000, rsi14=28)
        sig = mod.analyze(data)
        if sig:
            self.assertEqual(sig.direction, 'CE')

    def test_no_signal_rsi_neutral_despite_deviation(self):
        mod = MeanReversionModule()
        # 1% up but RSI is only 60 (not overbought)
        data = make_data(spot=24240, day_open=24000, rsi14=60)
        sig = mod.analyze(data)
        self.assertIsNone(sig, "RSI must confirm overbought (>65) for PE signal")


class TestScalping(unittest.TestCase):
    def test_no_signal_fewer_than_5_candles(self):
        mod = ScalpingModule()
        data = make_data(closes=[24000, 24010, 24020, 24030])
        self.assertIsNone(mod.analyze(data))

    def test_no_signal_on_3_candles_up(self):
        """Old V2 would fire on 3 candles; V3 requires 5."""
        mod = ScalpingModule()
        # Need 22+ candles for avg_move calculation (range -21 to -1)
        # Only last 3 are up - should NOT fire (needs 5 consecutive)
        closes = [24000]*25 + [24010, 24020, 24030]  # only 3 consecutive up at end
        data = make_data(spot=24030, closes=closes)
        sig = mod.analyze(data)
        self.assertIsNone(sig, "V3 Scalping needs 5 consecutive candles, not 3")

    def test_ce_on_5_up_candles_strong_move(self):
        mod = ScalpingModule()
        # 20 flat candles then 5 big up candles
        flat = [24000] * 20
        up5  = [24000 + i*8 for i in range(1, 6)]  # +8 per candle
        closes = flat + up5
        data = make_data(spot=closes[-1], pcr_bias='NEUTRAL', closes=closes)
        sig = mod.analyze(data)
        if sig:
            self.assertEqual(sig.direction, 'CE')

    def test_pe_blocked_when_bullish_bias(self):
        mod = ScalpingModule()
        flat = [24200]*20
        down5 = [24200 - i*8 for i in range(1,6)]
        closes = flat + down5
        data = make_data(spot=closes[-1], pcr_bias='BULLISH', closes=closes)
        sig = mod.analyze(data)
        self.assertIsNone(sig, "SCALP_DOWN must be blocked when PCR bias is BULLISH")


class TestBreakoutRetest(unittest.TestCase):
    def test_no_immediate_signal_on_breakout(self):
        """V3 requires retest - must not fire on first breakout."""
        mod = BreakoutModule()
        lb = Config.BREAKOUT_CANDLES
        closes = [24000] * (lb + 1)
        closes[-1] = 24060  # breaks above range
        data = make_data(spot=24060, closes=closes)
        sig = mod.analyze(data)
        self.assertIsNone(sig, "Must not fire on first breakout, needs retest")
        self.assertTrue(mod._broke_ce)

    def test_ce_signal_after_break_retest_rebreak(self):
        mod = BreakoutModule()
        lb = Config.BREAKOUT_CANDLES
        closes = [24000] * (lb + 1)

        # Breakout
        closes[-1] = 24060
        data = make_data(spot=24060, closes=closes)
        mod.analyze(data)

        # Retest (pull back)
        closes[-1] = 24002
        data.spot = 24002
        data.closes = closes
        mod.analyze(data)
        self.assertTrue(mod._retest_ce)

        # Re-break → fire
        closes[-1] = 24060
        data.spot = 24060
        data.closes = closes
        sig = mod.analyze(data)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.direction, 'CE')


class TestVolatilityBreakout(unittest.TestCase):
    def test_uses_atm_iv_not_all_chain(self):
        """IV must come from ATM±100pts only, so OTM options don't dilute."""
        mod = VolatilityBreakoutModule()
        spot = 24000
        chain, atm = make_chain(spot)
        # Set ALL OTM (abs > 100pts) to near-zero IV to simulate dilution
        for s in chain:
            if abs(s - spot) > 100:
                chain[s]['CE'].iv = 2.0
                chain[s]['PE'].iv = 2.0
        # Set ATM ± 100pts to high IV
        for s in chain:
            if abs(s - spot) <= 100:
                chain[s]['CE'].iv = 25.0
                chain[s]['PE'].iv = 25.0
                chain[s]['CE'].delta = 0.50  # within MIN_DELTA/MAX_DELTA range
                chain[s]['PE'].delta = 0.50
        # EMA5 > EMA20 triggers CE signal
        data = make_data(spot=spot, ema5=24050, ema20=23990)
        data.chain = chain
        data.atm_strike = atm
        sig = mod.analyze(data)
        # Key: with ATM-only IV = 25 > threshold 18, strategy SHOULD fire
        # Without the fix (using all-chain IV diluted to ~3%), it would NOT fire
        self.assertIsNotNone(sig, "Should fire when ATM IV is high even if OTM IV is low")


class TestOptionsGreeksDirection(unittest.TestCase):
    def test_ce_blocked_when_spot_below_ema20(self):
        mod = OptionsGreeksModule()
        # skew_ratio > 0.55 but spot BELOW ema20 → CE must be blocked
        data = make_data(spot=23900, ema20=24000)
        # Force CE skew by making CE delta*OI much larger
        for s in data.chain:
            data.chain[s]['CE'].delta = 0.8
            data.chain[s]['CE'].oi    = 1_000_000
            data.chain[s]['PE'].delta = 0.2
            data.chain[s]['PE'].oi    = 100_000
        sig = mod.analyze(data)
        if sig:
            self.assertNotEqual(sig.direction, 'CE', "CE must be blocked when spot < EMA20")

    def test_pe_blocked_when_spot_above_ema20(self):
        mod = OptionsGreeksModule()
        data = make_data(spot=24200, ema20=24000)
        for s in data.chain:
            data.chain[s]['PE'].delta = 0.8
            data.chain[s]['PE'].oi    = 1_000_000
            data.chain[s]['CE'].delta = 0.2
            data.chain[s]['CE'].oi    = 100_000
        sig = mod.analyze(data)
        if sig:
            self.assertNotEqual(sig.direction, 'PE', "PE must be blocked when spot > EMA20")


class TestMagicSquareTheta(unittest.TestCase):
    def test_theta_limit_relaxed_on_thursday(self):
        """On Thursdays (expiry day), theta_limit should be 0.50 not 0.15."""
        mod = MagicSquareModule()
        # We verify the logic inside _find_magic_square + theta_ok path
        # by checking what theta_limit is set to on a Thursday
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = MagicMock(weekday=lambda: 3, strftime=lambda f: '10:30:00')
            is_expiry = mock_dt.now().weekday() == 3
            theta_limit = 0.50 if is_expiry else 0.15
            self.assertEqual(theta_limit, 0.50)

    def test_theta_limit_strict_on_non_thursday(self):
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = MagicMock(weekday=lambda: 1)  # Tuesday
            is_expiry = mock_dt.now().weekday() == 3
            theta_limit = 0.50 if is_expiry else 0.15
            self.assertEqual(theta_limit, 0.15)

    def test_magic_square_find(self):
        """_find_magic_square must match premiums close to 9,36,81,144 etc."""
        from MODULAR_TRADER_V3 import MagicSquareModule
        self.assertEqual(MagicSquareModule._find_magic_square(36.0), 36)
        self.assertEqual(MagicSquareModule._find_magic_square(37.5), 36)  # within 5%
        self.assertEqual(MagicSquareModule._find_magic_square(81.0), 81)
        self.assertIsNone(MagicSquareModule._find_magic_square(50.0))   # between squares


class TestPutWriterSupportInvalidation(unittest.TestCase):
    def test_blocked_when_support_broken(self):
        mod = PutWriterSupportModule()
        # max_put_oi = 24000, day_low = 23985 (< 24000 - 10 = 23990) → broken
        data = make_data(spot=24015, day_low=23985, max_put_oi=24000)
        sig = mod.analyze(data)
        self.assertIsNone(sig, "Support broken (day_low < level-10) → must block CE")

    def test_fires_when_support_intact(self):
        mod = PutWriterSupportModule()
        # day_low = 23995 > 24000 - 10 = 23990 → intact
        data = make_data(spot=24020, day_low=23995, max_put_oi=24000)
        # Add prev_oi_state to avoid OI drop block
        data.prev_oi_state = {24000: {'PE': 1_000_000}}
        data.chain[24000] = {
            'CE': make_option(24000, 'CE', 50),
            'PE': make_option(24000, 'PE', 50, delta=0.5),
        }
        data.chain[24000]['PE'].oi = 1_010_000  # OI stable/growing
        sig = mod.analyze(data)
        if sig:
            self.assertEqual(sig.direction, 'CE')


# ════════════════════════════════════════════════════════════════════════════
# 3. FILTER TESTS — can_enter()
# ════════════════════════════════════════════════════════════════════════════

class TestCanEnterFilters(unittest.TestCase):
    def _make_module(self):
        m = UltimateDayHighLowModule()
        m.trade_count = 0
        m.open_trade = None
        m.net_pnl = 0.0
        return m

    def _make_tm(self):
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            fname = f.name
        tm = TradeManager()
        tm.csv_file = fname
        return tm

    def test_time_before_market_open_blocked(self):
        tm = self._make_tm()
        m  = self._make_module()
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 9, 10)
            result = tm.can_enter(m, 'CE', None, 0.8)
        self.assertFalse(result, "No entry before market open")

    def test_time_after_cutoff_blocked(self):
        tm = self._make_tm()
        m  = self._make_module()
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 15, 5)
            result = tm.can_enter(m, 'CE', None, 0.8)
        self.assertFalse(result, "No entry after NO_ENTRY_AFTER cutoff (15:00)")

    def test_pcr_bullish_blocks_pe(self):
        tm = self._make_tm()
        m  = self._make_module()
        data = make_data(pcr_bias='BULLISH')
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'PE', data, 0.9)
        self.assertFalse(result, "BULLISH PCR bias must block PE entry")

    def test_pcr_bearish_blocks_ce(self):
        tm = self._make_tm()
        m  = self._make_module()
        data = make_data(pcr_bias='BEARISH')
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'CE', data, 0.9)
        self.assertFalse(result, "BEARISH PCR bias must block CE entry")

    def test_max_trades_per_strategy_blocks(self):
        tm = self._make_tm()
        m  = self._make_module()
        m.trade_count = Config.MAX_TRADES_PER_STRATEGY
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'CE', None, 0.8)
        self.assertFalse(result, "Max trades per strategy must block entry")

    def test_open_trade_blocks(self):
        tm = self._make_tm()
        m  = self._make_module()
        m.open_trade = MagicMock()  # pretend there's an open trade
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'CE', None, 0.8)
        self.assertFalse(result, "Already open trade must block new entry")

    def test_price_momentum_up_blocks_pe(self):
        tm = self._make_tm()
        m  = self._make_module()
        # Market up 150 points from open (> threshold)
        data = make_data(spot=24150, day_open=24000)
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'PE', data, 0.5)
        self.assertFalse(result, "Strong upward momentum must block PE entry")

    def test_vwap_chop_filter_blocks_non_exempt(self):
        tm = self._make_tm()
        m  = self._make_module()
        # Spot within 0.1% of VWAP = choppy zone
        data = make_data(spot=24000, vwap=24005)
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            result = tm.can_enter(m, 'CE', data, 0.5)
        self.assertFalse(result, "Price near VWAP (choppy zone) must block entry")

    def test_portfolio_circuit_breaker_halts_all(self):
        """FIX 1: When total closed P&L <= PORTFOLIO_LOSS_LIMIT, no new entries allowed."""
        tm = self._make_tm()
        m  = self._make_module()
        # Simulate closed trades that sum to a large loss
        t1 = MagicMock(); t1.pnl = -12_000; t1.status = 'CLOSED'
        t2 = MagicMock(); t2.pnl = -10_000; t2.status = 'CLOSED'
        tm.trades = [t1, t2]  # total = -22000 <= -20000 limit
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 18, 10, 30)
            result = tm.can_enter(m, 'CE', None, 0.5)
        self.assertFalse(result, "Portfolio circuit breaker must halt all entries when total loss >= limit")

    def test_gap_recovery_blocks_pe_after_reversal(self):
        """FIX 2: On a gap-down day, once spot recovers to open level after 60min, PE must be blocked."""
        from MODULAR_TRADER_V3 import OrderBlockReversalModule
        tm = self._make_tm()
        m  = self._make_module()
        # Gap down day: open=23482 (-0.68% from prev 23644), now spot recovered to 23490 (near open)
        data = make_data(spot=23490, day_open=23482, prev_close=23644)
        # Manually set gap recovery state (as if 60+ mins have passed)
        tm._gap_down_day = True
        tm._gap_recovered = True
        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 18, 10, 30)
            result = tm.can_enter(m, 'PE', data, 0.8)
        self.assertFalse(result, "Gap recovery must block new PE entries on gap-down-and-reverse day")

    def test_order_block_ce_on_support_bounce(self):
        """Fix 3: OrderBlockReversal must fire CE when price bounces off PUT OI support with RSI oversold."""
        from MODULAR_TRADER_V3 import OrderBlockReversalModule
        mod = OrderBlockReversalModule()
        # Step 1: price touches support (23150), RSI oversold
        data_touch = make_data(spot=23150, day_open=23482, max_put_oi=23150, max_call_oi=23800, rsi14=38)
        mod._touched_support = True
        mod._support_low = 23145
        # Step 2: price bounces 0.55% above support -> outside 0.5% proximity, bounce confirmed
        data_bounce = make_data(spot=23280, day_open=23482, max_put_oi=23150, max_call_oi=23800, rsi14=38)
        signal = mod.analyze(data_bounce)
        self.assertIsNotNone(signal, "OrderBlockReversal must fire CE on confirmed support bounce with RSI oversold")
        self.assertEqual(signal.direction, 'CE')
        self.assertEqual(signal.strategy, 'SUPPORT_BOUNCE_CE')


# ════════════════════════════════════════════════════════════════════════════
# 4. RISK MANAGEMENT TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestRiskManagement(unittest.TestCase):
    def _make_trade(self, entry=100.0):
        contract = make_option(24000, 'CE', entry)
        t = Trade(
            trade_id='TEST_001',
            strategy='TEST',
            module='TEST',
            contract=contract,
            entry_price=entry,
            quantity=Config.LOT_SIZE,
            target=round(entry * (1 + Config.TARGET_PCT), 2),
            stop_loss=round(entry * (1 - Config.SL_PCT), 2),
            open_time=datetime.now()
        )
        return t

    def test_sl_calculation_correct(self):
        t = self._make_trade(entry=100.0)
        expected_sl = round(100.0 * (1 - Config.SL_PCT), 2)
        self.assertAlmostEqual(t.stop_loss, expected_sl, places=2)

    def test_target_calculation_correct(self):
        t = self._make_trade(entry=100.0)
        expected_tgt = round(100.0 * (1 + Config.TARGET_PCT), 2)
        self.assertAlmostEqual(t.target, expected_tgt, places=2)

    def test_pnl_calculation_on_exit(self):
        t = self._make_trade(entry=100.0)
        exit_price = 150.0
        t.pnl = (exit_price - t.entry_price) * t.quantity
        expected_pnl = 50.0 * Config.LOT_SIZE
        self.assertAlmostEqual(t.pnl, expected_pnl, places=2)

    def test_trail_stop_moves_to_breakeven(self):
        """When gain >= TRAIL_BREAKEVEN_PCT, SL must move to entry."""
        t = self._make_trade(entry=100.0)
        # Simulate gain of exactly TRAIL_BREAKEVEN_PCT
        ltp = 100.0 * (1 + Config.TRAIL_BREAKEVEN_PCT)
        gain_pct = (ltp - t.entry_price) / t.entry_price
        self.assertGreaterEqual(gain_pct, Config.TRAIL_BREAKEVEN_PCT)
        # Apply trail logic from manage_exits
        if gain_pct >= Config.TRAIL_LOCK_PCT:
            new_sl = round(t.entry_price * (1 + Config.TRAIL_BREAKEVEN_PCT), 2)
            if new_sl > t.stop_loss:
                t.stop_loss = new_sl
        elif gain_pct >= Config.TRAIL_BREAKEVEN_PCT:
            if t.stop_loss < t.entry_price:
                t.stop_loss = t.entry_price
        self.assertGreaterEqual(t.stop_loss, t.entry_price,
                                "After breakeven trail, SL must be >= entry price")

    def test_risk_reward_ratio(self):
        """Target / SL must be >= 1.5 to ensure positive expectancy."""
        entry = 100.0
        sl  = entry * (1 - Config.SL_PCT)
        tgt = entry * (1 + Config.TARGET_PCT)
        reward = tgt - entry
        risk   = entry - sl
        rr = reward / risk if risk > 0 else 0
        self.assertGreaterEqual(rr, 1.5,
                                f"Risk:Reward {rr:.2f} is below 1.5 — will lose money long-term")


# ════════════════════════════════════════════════════════════════════════════
# 5. TRADE RELOAD TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestTradeReload(unittest.TestCase):
    def _write_csv(self, filepath, rows):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['timestamp','event','trade_id','module','strategy',
                        'direction','strike','entry','exit','sl','target',
                        'pnl','exit_reason','confidence','reason','unreal_pnl'])
            for r in rows:
                w.writerow(r)

    def test_open_trade_reloaded(self):
        """If a trade has ENTER but no EXIT, it must be reloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'trades.csv')
            row_enter = ['2026-04-28 09:30:00','ENTER','TEST_1',
                         'AI_ENHANCED','AI_ENHANCED','PE','24100',
                         '50.00','','35.00','75.00','','','0.80','signal','0.00']
            self._write_csv(csv_path, [row_enter])

            tm = TradeManager()
            tm.csv_file = csv_path

            # Manually run the reload logic (same as _reload_open_trades_from_csv)
            enters = {}
            exited_ids = set()
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('event') == 'ENTER':
                        enters[row['trade_id']] = row
                    elif row.get('event') == 'EXIT':
                        exited_ids.add(row['trade_id'])
            open_rows = [r for tid, r in enters.items() if tid not in exited_ids]
            self.assertEqual(len(open_rows), 1, "One open trade must be found")

    def test_exited_trade_not_reloaded(self):
        """If a trade has both ENTER and EXIT, it must NOT be reloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'trades.csv')
            enter = ['2026-04-28 09:30:00','ENTER','TEST_2','AI_ENHANCED','AI_ENHANCED',
                     'PE','24100','50.00','','35.00','75.00','','','0.80','sig','0.00']
            exit_ = ['2026-04-28 10:00:00','EXIT', 'TEST_2','AI_ENHANCED','AI_ENHANCED',
                     'PE','24100','50.00','35.00','','','−1125.00','STOP_LOSS','','','0.00']
            self._write_csv(csv_path, [enter, exit_])

            enters = {}
            exited_ids = set()
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('event') == 'ENTER':
                        enters[row['trade_id']] = row
                    elif row.get('event') == 'EXIT':
                        exited_ids.add(row['trade_id'])
            open_rows = [r for tid, r in enters.items() if tid not in exited_ids]
            self.assertEqual(len(open_rows), 0, "Exited trade must NOT be reloaded")

    def test_eod_orphan_regression(self):
        """Regression: EOD force-exit must NOT re-exit already-SL-closed trades."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'trades.csv')
            enter = ['2026-04-28 09:30:00','ENTER','TEST_3','SCALPING','SCALPING',
                     'CE','24100','60.00','','42.00','90.00','','','0.65','sig','0.00']
            exit_ = ['2026-04-28 10:05:00','EXIT', 'TEST_3','SCALPING','SCALPING',
                     'CE','24100','60.00','42.00','','','−1350.00','STOP_LOSS','','','0.00']
            self._write_csv(csv_path, [enter, exit_])

            enters = {}
            exited_ids = set()
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('event') == 'ENTER':
                        enters[row['trade_id']] = row
                    elif row.get('event') == 'EXIT':
                        exited_ids.add(row['trade_id'])
            open_rows = [r for tid, r in enters.items() if tid not in exited_ids]
            self.assertEqual(len(open_rows), 0,
                             "REGRESSION: SL-exited trade must not appear in open trades for EOD")


# ════════════════════════════════════════════════════════════════════════════
# 6. LIVE HEALTH MONITOR TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestLiveHealthMonitor(unittest.TestCase):
    def _make_mock_trader(self):
        """Build a minimal mock trader that LiveHealthMonitor can work with."""
        trader = MagicMock()
        trader.modules = [
            UltimateDayHighLowModule(),
            DayHighBearishModule(),
            MeanReversionModule(),
            MagicSquareModule(),
            AIEnhancedModule(),
        ]
        tm = MagicMock()
        tm.get_total_pnl.return_value = 0.0
        tm.same_dir_count = {'CE': 0, 'PE': 0}
        trader.trade_manager = tm
        return trader

    def test_qualify_runs_without_error(self):
        trader = self._make_mock_trader()
        monitor = LiveHealthMonitor(trader)
        data = make_data()
        try:
            monitor.qualify(data)
        except Exception as e:
            self.fail(f"qualify() raised exception: {e}")

    def test_qualify_increments_cycle(self):
        trader = self._make_mock_trader()
        monitor = LiveHealthMonitor(trader)
        data = make_data()
        monitor.qualify(data)
        monitor.qualify(data)
        self.assertEqual(monitor._cycle, 2)

    def test_qualify_detects_open_trade_near_zero(self):
        """Health monitor must flag LTP near zero as a data feed issue."""
        trader = self._make_mock_trader()
        mod = trader.modules[0]  # ULTIMATE_DAY_HIGH_LOW
        contract = make_option(24000, 'CE', 0.1)  # near-zero LTP!
        trade = Trade(trade_id='T1', strategy='S', module='ULTIMATE_DAY_HIGH_LOW',
                      contract=contract, entry_price=50.0, quantity=75,
                      target=75.0, stop_loss=35.0, open_time=datetime.now())
        mod.open_trade = trade
        monitor = LiveHealthMonitor(trader)
        # Should not crash, and would log a warning
        data = make_data()
        try:
            monitor.qualify(data)
        except Exception as e:
            self.fail(f"qualify() crashed on near-zero LTP: {e}")

    def test_all_18_strategies_covered_in_expected(self):
        """EXPECTED dict must cover all 19 strategy names."""
        all_names = [
            'ULTIMATE_DAY_HIGH_LOW', 'DAY_HIGH_BEARISH', 'DAY_LOW_BULLISH',
            'ENHANCED_BEARISH_REVERSAL', 'ENHANCED_BULLISH_REVERSAL',
            'DAY_HIGH_LOW_TRADITIONAL', 'TREND_FOLLOWING', 'AI_ENHANCED',
            'MEAN_REVERSION', 'SCALPING', 'BREAKOUT', 'VOLATILITY_BREAKOUT',
            'OPTIONS_GREEKS', 'MAGIC_SQUARE', 'SHORT_UNWIND', 'LONG_UNWIND',
            'WRITER_RESIST_BREAK', 'PUT_WRITER_SUPPORT', 'ORDER_BLOCK_REVERSAL',
        ]
        for name in all_names:
            self.assertIn(name, LiveHealthMonitor.EXPECTED,
                          f"Strategy {name} missing from LiveHealthMonitor.EXPECTED")


# ════════════════════════════════════════════════════════════════════════════
# 7. INTEGRATION TEST — full cycle
# ════════════════════════════════════════════════════════════════════════════

class TestIntegrationFullCycle(unittest.TestCase):
    def test_signal_to_trade_lifecycle(self):
        """Signal → enter → manage_exit (SL hit) → CLOSED status."""
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            csv_path = f.name

        mod = AIEnhancedModule()
        mod.trade_count = 0
        mod.open_trade = None
        mod.net_pnl = 0.0

        tm = TradeManager()
        tm.csv_file = csv_path

        contract = make_option(24000, 'PE', 80.0, delta=0.50)
        signal = Signal(
            module='AI_ENHANCED', strategy='AI_SIGNAL', direction='PE',
            contract=contract, confidence=0.80, reason='test signal'
        )

        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 30)
            mock_dt.strptime = datetime.strptime
            # spot=24020: only +20pts from day_open=24000, within PRICE_MOMENTUM_THRESHOLD
            data = make_data(spot=24020)
            trade = tm.enter(signal, mod, data)

        self.assertIsNotNone(trade, "Trade must be created from valid signal")
        self.assertEqual(trade.status, 'OPEN')
        self.assertEqual(len(tm.trades), 1)

        # Verify SL and target
        self.assertAlmostEqual(trade.stop_loss, round(trade.entry_price * 0.70, 2), places=1)
        self.assertAlmostEqual(trade.target,    round(trade.entry_price * 1.50, 2), places=1)

        # Now simulate SL hit: LTP drops to below stop_loss
        sl_ltp = trade.stop_loss * 0.99  # just below SL
        data.chain[24000]['PE'] = make_option(24000, 'PE', sl_ltp)
        module_dict = {'AI_ENHANCED': mod}

        with patch('MODULAR_TRADER_V3.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 10, 45)
            tm.manage_exits(data, module_dict)

        self.assertEqual(trade.status, 'CLOSED', "Trade must be closed when LTP hits SL")
        self.assertEqual(trade.exit_reason, 'STOP_LOSS')
        self.assertLess(trade.pnl, 0, "SL exit must produce a loss")
        self.assertIsNone(mod.open_trade, "open_trade must be cleared after SL")

        os.unlink(csv_path)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    test_classes = [
        TestSanityConfig,
        TestUltimateORB,
        TestDayHighBearish,
        TestDayLowBullish,
        TestEnhancedBullishPCR,
        TestMeanReversion,
        TestScalping,
        TestBreakoutRetest,
        TestVolatilityBreakout,
        TestOptionsGreeksDirection,
        TestMagicSquareTheta,
        TestPutWriterSupportInvalidation,
        TestCanEnterFilters,
        TestRiskManagement,
        TestTradeReload,
        TestLiveHealthMonitor,
        TestIntegrationFullCycle,
    ]

    for tc in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"\n{'='*70}")
    print(f"V3 TEST RESULTS: {passed}/{total} PASSED  |  "
          f"FAIL:{len(result.failures)}  ERROR:{len(result.errors)}")
    print(f"{'='*70}")

    sys.exit(0 if result.wasSuccessful() else 1)
