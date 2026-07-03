"""
Regime Detector — classifies each trading day's market regime and
returns strategy enable/disable flags + position-size multipliers.

Regimes
-------
TRENDING_BULL   : strong uptrend from open, spot >> open, RSI high
TRENDING_BEAR   : strong downtrend, spot << open, RSI low
RANGE_BOUND     : low daily range, multiple direction reversals
HIGH_VOLATILITY : wide range (>300 pts), large candles, IV spike
NORMAL          : default / unclassified

Strategy compatibility matrix (based on 2025-vs-2026 backtest analysis)
-------------------------------------------------------------------------
                         TREND_BULL  TREND_BEAR  RANGE  HIGH_VOL  NORMAL
TREND_FOLLOWING             ✓           ✓         ✗       ✗        ✓
DAY_LOW_BULLISH             ✓           ✗         ✓       ✗        ✓
DAY_HIGH_BEARISH            ✗           ✓         ✓       ✗        ✓
SCALPING                    ✗           ✗         ✓       ✗        ✓
MEAN_REVERSION              ✗           ✗         ✓       ✗        ✓
ULTIMATE_DAY_HIGH_LOW       ✗           ✗         ✓       ✗        ✓
MAGIC_SQUARE                ✓           ✓         ✓       ✗        ✓
SHORT_UNWIND                ✗           ✓         ✓       ✗        ✓
LONG_UNWIND                 ✓           ✗         ✓       ✗        ✓
AI_ENHANCED                 ✓           ✓         ✗       ✗        ✓
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os

# ─────────────────────────────────────────────────────────────────────────────
# Thresholds & Matrix — Loaded from configuration database (JSON)
# ─────────────────────────────────────────────────────────────────────────────

# Default percentage-based coefficients if JSON load fails
TREND_STRONG_MOVE_PCT = 0.0065
HIGH_VOL_RANGE_PCT    = 0.0174
RANGE_MAX_TREND_PCT   = 0.0022
RANGE_MAX_RANGE_PCT   = 0.0078
UDHL_BLOCK_MOVE_PCT   = 0.0043
HIGH_IV_THRESHOLD     = 20.0

config_path = r"C:\25stragy\config.json"
if not os.path.exists(config_path):
    config_path = "config.json"

if os.path.exists(config_path):
    try:
        with open(config_path, "r") as f:
            cfg_data = json.load(f)
            coeffs = cfg_data.get("regime_detection_pct_coefficients", {})
            TREND_STRONG_MOVE_PCT = coeffs.get("trend_strong_move", TREND_STRONG_MOVE_PCT)
            HIGH_VOL_RANGE_PCT = coeffs.get("high_vol_range", HIGH_VOL_RANGE_PCT)
            RANGE_MAX_TREND_PCT = coeffs.get("range_max_trend", RANGE_MAX_TREND_PCT)
            RANGE_MAX_RANGE_PCT = coeffs.get("range_max_range", RANGE_MAX_RANGE_PCT)
            UDHL_BLOCK_MOVE_PCT = coeffs.get("udhl_block_move", UDHL_BLOCK_MOVE_PCT)
            HIGH_IV_THRESHOLD = coeffs.get("high_iv_threshold", HIGH_IV_THRESHOLD)
    except Exception as e:
        pass

# Position-size multipliers per regime
SIZE_MULTIPLIERS: Dict[str, float] = {
    "TRENDING_BULL":   1.0,
    "TRENDING_BEAR":   1.0,
    "RANGE_BOUND":     1.0,
    "HIGH_VOLATILITY": 0.5,   # half size on chaotic days
    "NORMAL":          1.0,
}

# Default Strategy Regime Compatibility Matrix
STRATEGY_REGIME_MATRIX: Dict[str, Dict[str, bool]] = {
    "TREND_FOLLOWING": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "DAY_LOW_BULLISH": {
        "TRENDING_BULL": True, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "DAY_HIGH_BEARISH": {
        "TRENDING_BULL": False, "TRENDING_BEAR": True,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "SCALPING": {
        "TRENDING_BULL": False, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "MEAN_REVERSION": {
        "TRENDING_BULL": False, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "ULTIMATE_DAY_HIGH_LOW": {
        "TRENDING_BULL": False, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "MAGIC_SQUARE": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "SHORT_UNWIND": {
        "TRENDING_BULL": False, "TRENDING_BEAR": True,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "LONG_UNWIND": {
        "TRENDING_BULL": True, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "AI_ENHANCED": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "DAY_HIGH_LOW_TRADITIONAL": {
        "TRENDING_BULL": False, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "BREAKOUT": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "VOLATILITY_BREAKOUT": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": True, "NORMAL": True,
    },
    "GAMMA_BLAST": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": True, "NORMAL": True,
    },
    "OPTIONS_GREEKS": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": True, "NORMAL": True,
    },
    "ENHANCED_BULLISH": {
        "TRENDING_BULL": True, "TRENDING_BEAR": False,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "ENHANCED_BEARISH": {
        "TRENDING_BULL": False, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "PUT_WRITER_SUPPORT": {
        "TRENDING_BULL": True, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "RESIST_BREAK": {
        "TRENDING_BULL": True, "TRENDING_BEAR": False,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "ORDER_BLOCK_REVERSAL": {
        "TRENDING_BULL": False, "TRENDING_BEAR": False,
        "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True,
    },
    "ZERO_HERO": {
        "TRENDING_BULL": True, "TRENDING_BEAR": True,
        "RANGE_BOUND": False, "HIGH_VOLATILITY": True, "NORMAL": True,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RegimeSnapshot:
    """Live snapshot of current regime — updated every candle."""
    regime: str = "NORMAL"
    spot_vs_open: float = 0.0        # pts above/below day open
    daily_range: float = 0.0         # high - low so far
    trend_strength: float = 0.0      # 0-1
    avg_iv: float = 0.0
    size_multiplier: float = 1.0
    strategy_flags: Dict[str, bool] = field(default_factory=dict)
    # Extra UDHL-specific flag
    udhl_blocked: bool = False
    udhl_block_reason: str = ""

    def is_enabled(self, strategy: str) -> bool:
        return self.strategy_flags.get(strategy, True)


@dataclass
class DayContext:
    """Accumulated intraday context for regime detection."""
    day_open: float = 0.0
    day_high: float = 0.0
    day_low: float = float("inf")
    candle_closes: List[float] = field(default_factory=list)
    avg_iv: float = 0.0
    first_30min_move: float = 0.0   # close of 9:45 candle - open


# ─────────────────────────────────────────────────────────────────────────────
# Core detector
# ─────────────────────────────────────────────────────────────────────────────
class RegimeDetector:
    """
    Call update() on each new 1-min candle with current spot data.
    Call snapshot() to get the current RegimeSnapshot for signal gating.
    """

    def __init__(self):
        self._ctx = DayContext()
        self._snapshot = RegimeSnapshot()
        self._candle_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def new_day(self, open_price: float):
        """Reset at the start of each trading day."""
        self._ctx = DayContext(day_open=open_price, day_high=open_price,
                               day_low=open_price)
        self._snapshot = RegimeSnapshot()
        self._candle_count = 0

    def update(self, spot: float, iv: float = 0.0, hhmm: int = 0) -> RegimeSnapshot:
        """
        Feed a new candle's spot price and optional IV.
        Returns updated RegimeSnapshot.
        """
        ctx = self._ctx
        if ctx.day_open == 0.0:
            ctx.day_open = spot

        # Update running high/low
        ctx.day_high = max(ctx.day_high, spot)
        ctx.day_low  = min(ctx.day_low,  spot)
        ctx.candle_closes.append(spot)
        self._candle_count += 1

        # Capture first-30-min directional move (9:15→9:45 = 30 candles)
        if self._candle_count == 30:
            ctx.first_30min_move = spot - ctx.day_open

        # Rolling IV average
        if iv > 0:
            n = self._candle_count
            ctx.avg_iv = (ctx.avg_iv * (n - 1) + iv) / n

        self._snapshot = self._classify(ctx, spot, hhmm)
        return self._snapshot

    def snapshot(self) -> RegimeSnapshot:
        return self._snapshot

    # ------------------------------------------------------------------
    # Batch mode: classify a full day's DataFrame at once
    # (used in backtest to pre-label each day)
    # ------------------------------------------------------------------
    @staticmethod
    def classify_day(day_df: pd.DataFrame) -> str:
        """
        day_df must have columns: spot, iv (optional), hhmm.
        Returns the day's primary regime label.
        NOTE: IV is stored as raw percentage (e.g. 13.8 = 13.8%).
        """
        if day_df is None or len(day_df) == 0:
            return "NORMAL"

        # Use spot column (not option close price)
        if "spot" not in day_df.columns:
            return "NORMAL"

        # Deduplicate to spot-level (one spot value per timestamp)
        spot = day_df.drop_duplicates(subset=["hhmm"])["spot"]
        if len(spot) == 0:
            spot = day_df["spot"]

        day_open  = spot.iloc[0]
        day_high  = spot.max()
        day_low   = spot.min()
        day_close = spot.iloc[-1]
        daily_range = day_high - day_low

        spot_vs_open_final = day_close - day_open
        spot_vs_open_max   = (spot - day_open).abs().max()

        avg_iv = day_df["iv"].mean() if "iv" in day_df.columns else 0.0

        return RegimeDetector._classify_from_stats(
            spot_vs_open=spot_vs_open_final,
            spot_vs_open_max=spot_vs_open_max,
            daily_range=daily_range,
            avg_iv=avg_iv,
            day_open=day_open,
        )
 
    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _classify(self, ctx: DayContext, spot: float, hhmm: int) -> RegimeSnapshot:
        spot_vs_open = spot - ctx.day_open
        daily_range  = ctx.day_high - ctx.day_low
        spot_vs_open_max = max(abs(spot_vs_open),
                               abs(ctx.day_high - ctx.day_open),
                               abs(ctx.day_low  - ctx.day_open))
 
        regime = self._classify_from_stats(
            spot_vs_open=spot_vs_open,
            spot_vs_open_max=spot_vs_open_max,
            daily_range=daily_range,
            avg_iv=ctx.avg_iv,
            day_open=ctx.day_open,
        )
 
        size_mult = SIZE_MULTIPLIERS.get(regime, 1.0)
        flags = self._build_flags(regime)
 
        # UDHL-specific block: if spot already moved beyond the configured threshold
        udhl_blocked = False
        udhl_reason  = ""
        udhl_threshold = ctx.day_open * UDHL_BLOCK_MOVE_PCT
        if abs(spot_vs_open) >= udhl_threshold:
            udhl_blocked = True
            udhl_reason  = f"spot moved {spot_vs_open:+.0f}pts from open (>{udhl_threshold:.1f})"
            flags["ULTIMATE_DAY_HIGH_LOW"] = False
        # Also block UDHL after 14:00
        if hhmm >= 1400:
            udhl_blocked = True
            udhl_reason  = udhl_reason or "after 14:00 cutoff"
            flags["ULTIMATE_DAY_HIGH_LOW"] = False
 
        # Trend-following direction hint
        trend_strength = min(abs(spot_vs_open) / max(daily_range, 1), 1.0)
 
        return RegimeSnapshot(
            regime=regime,
            spot_vs_open=spot_vs_open,
            daily_range=daily_range,
            trend_strength=trend_strength,
            avg_iv=ctx.avg_iv,
            size_multiplier=size_mult,
            strategy_flags=flags,
            udhl_blocked=udhl_blocked,
            udhl_block_reason=udhl_reason,
        )
 
    @staticmethod
    def _classify_from_stats(
        spot_vs_open: float,
        spot_vs_open_max: float,
        daily_range: float,
        avg_iv: float,
        day_open: float = 23000.0,
    ) -> str:
        # Scale thresholds dynamically as a percentage of the index open price
        trend_strong_move = day_open * TREND_STRONG_MOVE_PCT
        high_vol_range    = day_open * HIGH_VOL_RANGE_PCT
        range_max_trend   = day_open * RANGE_MAX_TREND_PCT
        range_max_range   = day_open * RANGE_MAX_RANGE_PCT

        # HIGH_VOLATILITY: very wide range or IV spike
        if daily_range >= high_vol_range or avg_iv >= HIGH_IV_THRESHOLD:
            return "HIGH_VOLATILITY"
 
        # TRENDING: strong directional move from open
        if spot_vs_open_max >= trend_strong_move:
            if spot_vs_open > 0:
                return "TRENDING_BULL"
            else:
                return "TRENDING_BEAR"
 
        # RANGE_BOUND: small move from open AND narrow range
        if abs(spot_vs_open) <= range_max_trend and daily_range <= range_max_range:
            return "RANGE_BOUND"
 
        return "NORMAL"

    @staticmethod
    def _build_flags(regime: str) -> Dict[str, bool]:
        flags: Dict[str, bool] = {}
        for strat, compat in STRATEGY_REGIME_MATRIX.items():
            flags[strat] = compat.get(regime, True)
        return flags


# ─────────────────────────────────────────────────────────────────────────────
# Batch utility — label every trading day in opt_data
# ─────────────────────────────────────────────────────────────────────────────
def label_days(opt_data: pd.DataFrame) -> pd.Series:
    """
    Given the full opt_data DataFrame (with 'date', 'spot', 'iv', 'hhmm' cols),
    returns a Series indexed by date with regime labels.
    """
    regimes = {}
    for d, grp in opt_data.groupby("date"):
        regimes[d] = RegimeDetector.classify_day(grp)
    return pd.Series(regimes, name="regime")


def regime_summary(opt_data: pd.DataFrame) -> pd.DataFrame:
    """Print a summary table of regime distribution per year."""
    s = label_days(opt_data)
    df = s.reset_index()
    df.columns = ["date", "regime"]
    df["year"] = pd.to_datetime(df["date"]).dt.year
    return df.groupby(["year", "regime"]).size().unstack(fill_value=0)


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "c:/cursor/options/niftyopt")
    from BACKTEST_V3_TUNED import load_option_data

    print("Loading option data...")
    opt_data = load_option_data()

    print("\n=== REGIME DISTRIBUTION BY YEAR ===")
    summary = regime_summary(opt_data)
    print(summary.to_string())

    # Per-regime count and percentage
    s = label_days(opt_data)
    total = len(s)
    print(f"\nTotal trading days: {total}")
    print("\nBreakdown:")
    for regime, cnt in s.value_counts().items():
        print(f"  {regime:<20}: {cnt:3d} days  ({100*cnt/total:.0f}%)")

    # Show how many trades each strategy would gain/lose from filtering
    print("\n=== STRATEGY ENABLE RATE BY REGIME ===")
    day_regimes = label_days(opt_data)
    print(f"\n{'Strategy':<30} {'Enabled %':>10}")
    print("-" * 42)
    for strat in sorted(STRATEGY_REGIME_MATRIX.keys()):
        enabled = sum(
            1 for r in day_regimes
            if STRATEGY_REGIME_MATRIX[strat].get(r, True)
        )
        pct = 100 * enabled / total
        print(f"{strat:<30} {pct:>9.0f}%")
