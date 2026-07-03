#!/usr/bin/env python3
"""
TEST SUITE: engine_v15.py
=========================
Industry-standard unit tests for C:\\25stragy\\engine_v15.py.

Run: python tests/test_engine_v15.py
"""

import sys
import os
import csv
import json
import time
import unittest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

# ── Patch API import before loading V15 ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')

# Mock dhanhq so we don't need the real library or API connection
import types
mock_dhan_module = types.ModuleType('dhanhq')
class MockDhan:
    def __init__(self, *a, **kw):
        self.client = MagicMock()
mock_dhan_module.dhanhq = MockDhan
sys.modules['dhanhq'] = mock_dhan_module

# ── Now import engine_v15 ────────────────────────────────────────────────────
import engine_v15
from engine_v15 import (
    IndexConfig, IndexStrategyDNA, StrategyDef, Trade,
    get_tier_deploy_pct, get_numerical_strike, resolve_target_strike,
    get_dynamic_hard_exit, calc_rsi, calc_vwap,
    volume_spike_filter, adx_filter, pcr_stability_filter,
    ema_alignment_filter, entry_time_filter, regime_gate_filter,
    bb_position_filter, signal_check, signal_check_idx,
    get_shared_active_margin, get_today_realized_pnl
)

class TestV15Configuration(unittest.TestCase):
    """Verify system constants are loaded correctly from config DB."""

    def test_capital_base_valid(self):
        self.assertGreaterEqual(engine_v15.CAPITAL_BASE, 100000)

    def test_spot_sl_pct_reasonable(self):
        self.assertGreater(engine_v15.SPOT_SL_PCT, 0)
        self.assertLess(engine_v15.SPOT_SL_PCT, 0.05)

    def test_tier_deployment_percentages(self):
        self.assertGreaterEqual(engine_v15.TIER1_DEPLOY_PCT, 0.05)
        self.assertGreaterEqual(engine_v15.TIER2_DEPLOY_PCT, 0.05)
        self.assertGreaterEqual(engine_v15.TIER3_DEPLOY_PCT, 0.05)
        self.assertGreaterEqual(engine_v15.TIER4_DEPLOY_PCT, 0.05)

    def test_tier_mapping_resolves(self):
        # Tier 1 strat
        t1_strat = list(engine_v15.TIER1_STRATEGIES)[0] if engine_v15.TIER1_STRATEGIES else 'ULTIMATE_DAY_HIGH_LOW'
        self.assertEqual(get_tier_deploy_pct(t1_strat), engine_v15.TIER1_DEPLOY_PCT)
        
        # Non-existent strategy defaults to Tier 4
        self.assertEqual(get_tier_deploy_pct('UNKNOWN_STRAT_XYZ'), engine_v15.TIER4_DEPLOY_PCT)


class TestV15Helpers(unittest.TestCase):
    """Verify core arithmetic and strike resolution logic."""

    def test_get_numerical_strike_atm(self):
        self.assertAlmostEqual(get_numerical_strike(24020, 'ATM', 50), 24000)
        self.assertAlmostEqual(get_numerical_strike(24026, 'ATM', 50), 24050)

    def test_get_numerical_strike_offsets(self):
        self.assertAlmostEqual(get_numerical_strike(24000, 'ATM+1', 50), 24050)
        self.assertAlmostEqual(get_numerical_strike(24000, 'ATM-2', 50), 23900)

    def test_get_numerical_strike_hardcoded(self):
        # Verified fix: parses numeric strings
        self.assertAlmostEqual(get_numerical_strike(24000, '24150', 50), 24150)
        self.assertAlmostEqual(get_numerical_strike(24000, '23850.5', 50), 23850.5)

    def test_resolve_target_strike_expiry(self):
        self.assertEqual(resolve_target_strike('CE', 'ATM', True, 'ZERO_HERO'), 'ATM+3')
        self.assertEqual(resolve_target_strike('CE', 'ATM', True, 'GAMMA_BLAST'), 'ATM+2')

    def test_resolve_target_strike_pe_direction_flip(self):
        # ATM remains ATM
        self.assertEqual(resolve_target_strike('PE', 'ATM', False, 'BREAKOUT'), 'ATM')
        # ATM+1 turns to ATM-1 for PE
        self.assertEqual(resolve_target_strike('PE', 'ATM+1', False, 'BREAKOUT'), 'ATM-1')
        # ATM-2 turns to ATM+2 for PE
        self.assertEqual(resolve_target_strike('PE', 'ATM-2', False, 'BREAKOUT'), 'ATM+2')

    def test_get_dynamic_hard_exit(self):
        # Expiry Reversal
        self.assertEqual(get_dynamic_hard_exit('NIFTY', 'MEAN_REVERSION', 'NORMAL', True), 1245)
        # Expiry Trend
        self.assertEqual(get_dynamic_hard_exit('NIFTY', 'TREND_FOLLOWING', 'NORMAL', True), 1330)
        # Trending Reversal
        self.assertEqual(get_dynamic_hard_exit('NIFTY', 'MEAN_REVERSION', 'TRENDING_BULL', False), 1330)
        # Trending Trend
        self.assertEqual(get_dynamic_hard_exit('NIFTY', 'TREND_FOLLOWING', 'TRENDING_BULL', False), 1430)
        # Normal Reversal
        self.assertEqual(get_dynamic_hard_exit('NIFTY', 'MEAN_REVERSION', 'NORMAL', False), 1300)


class TestV15IndicatorCalculations(unittest.TestCase):
    """Test indicators like RSI and VWAP with synthetic data."""

    def test_calc_rsi_flat(self):
        closes = pd.Series([100.0] * 20)
        self.assertAlmostEqual(calc_rsi(closes), 50.0)

    def test_calc_rsi_rising(self):
        # Create an oscillating series with an upward trend to test normal RSI behavior
        closes = pd.Series([100.0 + (i % 3) * 5 + i * 2 for i in range(25)])
        self.assertGreater(calc_rsi(closes), 50.0)

    def test_calc_rsi_falling(self):
        # Create an oscillating series with a downward trend
        closes = pd.Series([200.0 - (i % 3) * 5 - i * 2 for i in range(25)])
        self.assertLess(calc_rsi(closes), 50.0)

    def test_calc_vwap(self):
        now = datetime.now()
        candles = pd.DataFrame({
            'timestamp': [now - timedelta(minutes=i) for i in range(5)],
            'high': [102.0, 102.0, 102.0, 102.0, 102.0],
            'low': [98.0, 98.0, 98.0, 98.0, 98.0],
            'close': [100.0, 100.0, 100.0, 100.0, 100.0],
            'volume': [10, 20, 30, 40, 50]
        })
        self.assertAlmostEqual(calc_vwap(candles), 100.0)


class TestV15Filters(unittest.TestCase):
    """Test indicator alignment and signal gates."""

    def test_volume_spike_filter(self):
        # 10 flat volumes, then spike
        volumes = [100] * 9 + [300]
        df = pd.DataFrame({'volume': volumes})
        self.assertTrue(volume_spike_filter(df, min_spike=1.3))

        # flat volumes without spike
        volumes = [100] * 10
        df = pd.DataFrame({'volume': volumes})
        self.assertFalse(volume_spike_filter(df, min_spike=1.3))

    def test_adx_filter(self):
        # Trending high-adx synthetic candles
        df = pd.DataFrame({
            'high': [100 + i*2 for i in range(20)],
            'low': [98 + i*2 for i in range(20)],
            'close': [99 + i*2 for i in range(20)]
        })
        # adx > 28 will block
        self.assertFalse(adx_filter(df, max_adx=15.0))
        # high adx threshold of 105.0 will pass (since linear trend max ADX is ~100)
        self.assertTrue(adx_filter(df, max_adx=105.0))

    def test_pcr_stability_filter(self):
        # Clear/reset history first
        engine_v15.pcr_histories = {}
        # Stable
        self.assertTrue(pcr_stability_filter('NIFTY', 1.0))
        self.assertTrue(pcr_stability_filter('NIFTY', 1.02))
        
        # At 3 items: [1.0, 1.02, 0.99] -> variance = 0.03, avg = 1.003 -> variance/avg = 0.0298 < 0.15 (Stable)
        self.assertTrue(pcr_stability_filter('NIFTY', 0.99))
        
        # At 4 items: [1.02, 0.99, 1.5] -> variance = 0.51, avg = 1.17 -> variance/avg = 0.435 >= 0.15 (Unstable)
        self.assertFalse(pcr_stability_filter('NIFTY', 1.5))

    def test_ema_alignment_filter_ce(self):
        # EMA9 > EMA21 > EMA50 (Bullish)
        df = pd.DataFrame({
            'close': [100 + i*5 for i in range(60)]
        })
        self.assertTrue(ema_alignment_filter(df, 'CE'))
        self.assertFalse(ema_alignment_filter(df, 'PE'))

    def test_ema_alignment_filter_pe(self):
        # EMA9 < EMA21 < EMA50 (Bearish)
        df = pd.DataFrame({
            'close': [500 - i*5 for i in range(60)]
        })
        self.assertTrue(ema_alignment_filter(df, 'PE'))
        self.assertFalse(ema_alignment_filter(df, 'CE'))

    def test_entry_time_filter(self):
        self.assertTrue(entry_time_filter(1030, cutoff=1300))
        self.assertFalse(entry_time_filter(1315, cutoff=1300))

    def test_regime_gate_filter(self):
        self.assertTrue(regime_gate_filter('NORMAL', blocked_regimes={'TRENDING_BEAR'}))
        self.assertFalse(regime_gate_filter('TRENDING_BEAR', blocked_regimes={'TRENDING_BEAR'}))

    def test_bb_position_filter_outside(self):
        # Prices jumping outside Bollinger standard bands
        closes = [100.0] * 19 + [150.0]
        df = pd.DataFrame({'close': closes})
        self.assertTrue(bb_position_filter(df, threshold=1.0))


class TestV15SignalChecks(unittest.TestCase):
    """Test strategy entry trigger verification under normal conditions."""

    def setUp(self):
        now = datetime.now()
        # Create standard 25-bar synthetic data
        self.candles = pd.DataFrame({
            'timestamp': [now - timedelta(minutes=i) for i in range(25)],
            'open': [24000.0] * 25,
            'high': [24010.0] * 25,
            'low': [23990.0] * 25,
            'close': [24000.0] * 25,
            'volume': [100] * 25
        })
        self.day_ohlc = {'open': 24000.0, 'high': 24050.0, 'low': 23950.0}
        self.cfg = IndexConfig(name='NIFTY', lot_size=75, atm_step=50.0, expiry_dow=3, security_id='13')

    def test_signal_check_rsi_reversal_ce(self):
        # Force low RSI and green candle
        self.candles.loc[24, 'close'] = 24010.0
        self.candles.loc[24, 'open'] = 24000.0
        # Strat definition
        strat = StrategyDef(
            name='RSI_REVERSAL', direction='BOTH', strike='ATM',
            entry_start=930, entry_end=1430, sl_pct=0.2, target_pct=0.4,
            tsl_pts=2.0, min_premium=10, max_premium=500,
            require_vwap=False, require_volume=False, direction_bias=''
        )
        # Mock calc_rsi to oversold (e.g. 20)
        with patch('engine_v15.calc_rsi', return_value=20.0):
            res = signal_check(strat, 'CE', self.candles, self.day_ohlc, 1.0, 1030, False, 100.0, self.cfg)
            self.assertTrue(res)

    def test_signal_check_idx_adaptive_bear_blocks_low_bullish(self):
        strat = StrategyDef(
            name='DAY_LOW_BULLISH', direction='CE', strike='ATM',
            entry_start=1200, entry_end=1350, sl_pct=0.35, target_pct=0.6,
            tsl_pts=8.0, min_premium=50, max_premium=500,
            require_vwap=False, require_volume=False, direction_bias=''
        )
        with patch('engine_v15.get_adaptive_engine_regime', return_value='TRENDING_BEAR'):
            res = signal_check_idx(
                strat, 'CE', self.candles, self.day_ohlc, 1.0, 1230, False, 100.0, self.cfg
            )
            # Under TRENDING_BEAR regime, DAY_LOW_BULLISH should be filtered out
            self.assertFalse(res)


class TestV15StateAndMargin(unittest.TestCase):
    """Verify thread-safe trade loading and state tracking limits."""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
        self.temp_file.close()
        engine_v15.TRADE_LOG_FILE = self.temp_file.name

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_load_save_state_cycle(self):
        t = Trade(
            index='NIFTY', strategy='SCALPING', direction='CE', strike=24000.0,
            option_name='NIFTY-24000-CE', lots=2, entry_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            entry_price=85.0, entry_spot=24010.0, highest_premium=85.0, spot_sl_level=23950.0
        )
        engine_v15.active_trades = [t]
        engine_v15.completed_trades = []
        
        # Save
        engine_v15.save_trade_state_to_csv()
        
        # Clear
        engine_v15.active_trades = []
        
        # Load
        engine_v15.load_trade_state_from_csv()
        self.assertEqual(len(engine_v15.active_trades), 1)
        self.assertEqual(engine_v15.active_trades[0].strategy, 'SCALPING')

    def test_get_shared_active_margin_calculation(self):
        t1 = Trade(
            index='NIFTY', strategy='SCALPING', direction='CE', strike=24000.0,
            option_name='NIFTY-24000-CE', lots=2, entry_time='2026-06-25 10:00:00',
            entry_price=80.0, entry_spot=24000.0, highest_premium=80.0, spot_sl_level=23950.0,
            status='OPEN'
        )
        t2 = Trade(
            index='BANKNIFTY', strategy='MAGIC_SQUARE', direction='PE', strike=48000.0,
            option_name='BANKNIFTY-48000-PE', lots=1, entry_time='2026-06-25 10:05:00',
            entry_price=120.0, entry_spot=48000.0, highest_premium=120.0, spot_sl_level=48100.0,
            status='CLOSED'  # should not count
        )
        engine_v15.active_trades = [t1]
        engine_v15.completed_trades = [t2]
        
        # Margin: quantity * entry_price. t1 lot size = 75. 2 lots * 75 = 150 options. 150 * 80.0 = Rs. 12,000.
        self.assertAlmostEqual(get_shared_active_margin(), 12000.0)

    def test_get_today_realized_pnl(self):
        t1 = Trade(
            index='NIFTY', strategy='SCALPING', direction='CE', strike=24000.0,
            option_name='NIFTY-24000-CE', lots=2, entry_time='2026-06-25 10:00:00',
            entry_price=80.0, entry_spot=24000.0, highest_premium=80.0, spot_sl_level=23950.0,
            status='CLOSED', pnl_rs=2500.0
        )
        t2 = Trade(
            index='NIFTY', strategy='MEAN_REVERSION', direction='PE', strike=24100.0,
            option_name='NIFTY-24100-PE', lots=2, entry_time='2026-06-25 10:00:00',
            entry_price=80.0, entry_spot=24000.0, highest_premium=80.0, spot_sl_level=23950.0,
            status='CLOSED', pnl_rs=-1200.0
        )
        engine_v15.completed_trades = [t1, t2]
        self.assertAlmostEqual(get_today_realized_pnl('NIFTY'), 1300.0)


if __name__ == '__main__':
    unittest.main()
