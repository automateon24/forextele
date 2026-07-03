import sys
import os
import unittest
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')

# Mock dhanhq
import types
from unittest.mock import MagicMock
mock_dhan_module = types.ModuleType('dhanhq')
class MockDhan:
    def __init__(self, *a, **kw):
        self.client = MagicMock()
mock_dhan_module.dhanhq = MockDhan
sys.modules['dhanhq'] = mock_dhan_module

import engine_v15
from engine_v15 import StrategyDef, IndexConfig, signal_check

class TestV15ExtendedSignalChecks(unittest.TestCase):
    def setUp(self):
        now = datetime.now()
        # Ensure we have enough data for all indicators (min 25 rows for ema20, etc.)
        self.candles = pd.DataFrame({
            'timestamp': [now - timedelta(minutes=i) for i in range(25, 0, -1)],
            'open': [24000.0] * 25,
            'high': [24010.0] * 25,
            'low': [23990.0] * 25,
            'close': [24000.0] * 25,
            'volume': [100] * 25
        })
        self.day_ohlc = {'open': 24000.0, 'high': 24050.0, 'low': 23950.0}
        self.cfg = IndexConfig(name='NIFTY', lot_size=75, atm_step=50.0, expiry_dow=3, security_id='13')

    def _create_strat(self, name, direction='CE', require_vwap=False, require_volume=False):
        return StrategyDef(
            name=name, direction=direction, strike='ATM',
            entry_start=930, entry_end=1430, sl_pct=0.2, target_pct=0.4,
            tsl_pts=2.0, min_premium=10, max_premium=500,
            require_vwap=require_vwap, require_volume=require_volume, direction_bias=''
        )

    def test_ultimate_day_high_low_ce(self):
        # CE logic: near_low, prev_green, strong_candle, rsi > 35
        self.candles.loc[23, 'low'] = 23950.0 # near run_low
        self.candles.loc[23, 'open'] = 23950.0
        self.candles.loc[23, 'close'] = 23980.0 # prev_green, strong_candle
        
        strat = self._create_strat('ULTIMATE_DAY_HIGH_LOW', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_ultimate_day_high_low_pe(self):
        # PE logic: near_high, prev_red, strong_candle, rsi < 45
        self.candles.loc[23, 'high'] = 24050.0 # near run_high
        self.candles.loc[23, 'open'] = 24050.0
        self.candles.loc[23, 'close'] = 24020.0 # prev_red, strong_candle
        # Mock rsi < 45
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 - i # Downward trend for RSI < 45
        self.candles.loc[23, 'high'] = 24050.0
        self.candles.loc[23, 'open'] = 24050.0
        self.candles.loc[23, 'close'] = 24020.0 
        
        strat = self._create_strat('ULTIMATE_DAY_HIGH_LOW', 'PE')
        res = signal_check(strat, 'PE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_day_high_bearish(self):
        self.candles.loc[24, 'close'] = 24049.0 # spot near day_high
        # Mock rsi > 58
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 + i
        self.candles.loc[24, 'close'] = 24049.0
        strat = self._create_strat('DAY_HIGH_BEARISH', 'PE')
        res = signal_check(strat, 'PE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_day_low_bullish(self):
        self.candles.loc[24, 'close'] = 23951.0 # spot near day_low
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 - i # Mock rsi < 47
        self.candles.loc[24, 'close'] = 23951.0
        strat = self._create_strat('DAY_LOW_BULLISH', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_day_high_low_traditional_ce(self):
        # breakout = spot > orb_high * 1.003
        self.candles.loc[0, 'high'] = 24000.0 # orb_high
        self.candles.loc[24, 'close'] = 24075.0 # spot > orb_high * 1.003
        self.candles.loc[24, 'open'] = 24050.0 # c['close'] > c['open']
        self.candles.loc[24, 'volume'] = 500 # vol_spike
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 + i*4 # strong uptrend for rsi > 55, ema5 > ema20
        self.candles.loc[24, 'close'] = 24075.0 
        self.candles.loc[24, 'open'] = 24050.0
        self.candles.loc[24, 'volume'] = 500
        
        strat = self._create_strat('DAY_HIGH_LOW_TRADITIONAL', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)
        
    def test_ai_enhanced(self):
        # CE bullish: ema5 > ema20, pcr > 1.3, rsi < 55, close > open
        self.candles.loc[24, 'open'] = 24000.0
        self.candles.loc[24, 'close'] = 24010.0
        # Need ema5 > ema20 but rsi < 55, achieved via sideways then small bounce
        strat = self._create_strat('AI_ENHANCED', 'CE')
        # We manually inject the conditions inside engine_v15 by mocking if it's too complex to synthesize exactly
        # But let's try direct synthesis:
        for i in range(24):
            self.candles.loc[i, 'close'] = 24000.0
        self.candles.loc[24, 'close'] = 24010.0
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.5, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_mean_reversion(self):
        # CE: spot < bb_dn and rsi < 40 and close > open
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 - i*10
        self.candles.loc[24, 'close'] = 23700.0 # big drop
        self.candles.loc[24, 'open'] = 23650.0  # close > open
        strat = self._create_strat('MEAN_REVERSION', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_volatility_breakout(self):
        # CE: candle_rng >= avg5_rng * 1.3, close > open, close > p['high'], rsi > 52
        for i in range(25):
            self.candles.loc[i, 'high'] = 24010.0
            self.candles.loc[i, 'low'] = 24000.0
            self.candles.loc[i, 'close'] = 24005.0 + i
        self.candles.loc[24, 'high'] = 24050.0
        self.candles.loc[24, 'low'] = 24000.0
        self.candles.loc[24, 'open'] = 24000.0
        self.candles.loc[24, 'close'] = 24040.0
        strat = self._create_strat('VOLATILITY_BREAKOUT', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)
        
    def test_options_greeks(self):
        # CE: rsi < 42, close > open, candle_rng > avg5_rng
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 - i
        self.candles.loc[24, 'high'] = 23990.0
        self.candles.loc[24, 'low'] = 23960.0
        self.candles.loc[24, 'open'] = 23960.0
        self.candles.loc[24, 'close'] = 23985.0
        strat = self._create_strat('OPTIONS_GREEKS', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_magic_square(self):
        # PE: near_618, rsi > 55, ema5 < ema20
        # day_range = 100, day_low=23950, 618 = 23950 + 61.8 = 24011.8
        for i in range(25):
            self.candles.loc[i, 'close'] = 24020.0 - i # downtrend for ema5 < ema20
        self.candles.loc[24, 'close'] = 24011.8 # spot
        # Need rsi > 55, so let's make it an uptrend that recently turned down
        for i in range(20):
            self.candles.loc[i, 'close'] = 23950.0 + i*5
        self.candles.loc[20:24, 'close'] = 24011.8
        
        strat = self._create_strat('MAGIC_SQUARE', 'PE')
        res = signal_check(strat, 'PE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_zero_hero(self):
        # is_expiry=True, CE: close > open, ema5 > ema20, rsi > 48
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 + i
        self.candles.loc[24, 'open'] = 24000.0
        self.candles.loc[24, 'close'] = 24050.0
        strat = self._create_strat('ZERO_HERO', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, True, 100.0, self.cfg)
        self.assertTrue(res)

    def test_momentum_burst(self):
        # CE: close > p_close, rsi > 60, ema5 > ema20, vol_spike
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 + i*2
        self.candles.loc[24, 'volume'] = 500
        strat = self._create_strat('MOMENTUM_BURST', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

    def test_vwap_bounce(self):
        # CE: near_vwap, close > open, rsi > 50, ema5 > ema20
        for i in range(25):
            self.candles.loc[i, 'close'] = 24000.0 + i
        self.candles.loc[24, 'open'] = 24000.0
        self.candles.loc[24, 'close'] = 24024.0
        strat = self._create_strat('VWAP_BOUNCE', 'CE')
        res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
        self.assertTrue(res)

if __name__ == '__main__':
    unittest.main()
