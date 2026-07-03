# ADAPTIVE V4 - Adaptive Trading Layer
## Phase A: Ready for Live Trading

---

## Quick Start

### Step 1: Start V4 as Usual
```batch
RUN_MODULAR_V4.bat
```

### Step 2: Start Adaptive Engine (In a NEW terminal)
```batch
START_ADAPTIVE_V4.bat
```

Both run in parallel with matching V4 version numbers.

---

## What You Will See

### Terminal 1 (V4): Normal trading output
```
[RUN] Starting main loop - V4 ENHANCED + ADAPTIVE V4
[SESSION START] V4.0 - Learning from April 29 executed
[ADAPTIVE] V4 Engine integration: Check adaptive_data/adaptive_config.json every 60s
```

### Terminal 2 (Adaptive): Dashboard output
```
================================================================================
ADAPTIVE V4 DASHBOARD | 10:15:30 | Cycle #42
================================================================================

[MARKET REGIME] TRENDING_BULL
  Spot: 19500.00 | VIX: 16.50 | VWAP: 19480.00

[CURRENT THRESHOLDS]
  VWAP_BAND_PCT: 0.003
  MOMENTUM_THRESHOLD: 50
  CONFIDENCE_BYPASS: 0.9
  POSITION_SIZE_PCT: 1.0
  COOLDOWN_MINUTES: 30

[STRATEGY PERFORMANCE - Last 4 Hours]
  MAGIC_SQUARE        : 5/8 taken, W/L: 3/2, P&L: ₹4,200
  AI_ENHANCED         : 3/5 taken, W/L: 2/1, P&L: ₹2,800

[SYSTEM STATUS]
  Auto-correction: ACTIVE (every 15 min)
  Safety limits: ENFORCED
  Config file: adaptive_data/adaptive_config.json
```

---

## How It Works

```
┌────────────────────────────────────────────────────────────┐
│  ADAPTIVE_V4.py (Terminal 2)                               │
│  ├─ Reads V4 logs every 30 seconds                       │
│  ├─ Detects market regime (Trending/Range/Volatile/Quiet)│
│  ├─ Tracks which signals trigger vs get blocked          │
│  ├─ Adjusts thresholds every 15 minutes if needed        │
│  └─ Writes to adaptive_config.json                       │
└────────────────────────────────────────────────────────────┘
                            ↓
                    adaptive_config.json
                            ↓
┌────────────────────────────────────────────────────────────┐
│  MODULAR_TRADER_V4.py (Terminal 1)                       │
│  ├─ Checks adaptive_config.json every 60 seconds          │
│  ├─ Loads new thresholds automatically                   │
│  ├─ Applies them WITHOUT restart                         │
│  └─ Continues trading with updated parameters            │
└────────────────────────────────────────────────────────────┘
```

---

## Safety Limits (Hardcoded)

- **Max daily adjustment:** 30% per parameter
- **Min position size:** 50% (never goes lower)
- **Max SL widening:** 20%
- **Min confidence:** 75%
- **Correction interval:** 15 minutes minimum
- **Auto-rollback:** If P&L worsens after adjustment

---

## Files

| File | Purpose |
|------|---------|
| `ADAPTIVE_V4.py` | Main adaptive engine |
| `START_ADAPTIVE_V4.bat` | Launcher script |
| `adaptive_data/adaptive_config.json` | Shared config (V4 reads this) |
| `adaptive_data/performance.db` | SQLite database of all signals |
| `adaptive_data/corrections.log` | Audit trail of auto-corrections |
| `adaptive_data/adaptive_engine.log` | Engine debug log |

---

## What Gets Auto-Corrected

### 1. Regime-Based Thresholds
- **Trending Market:** Tighter VWAP band (0.1%), higher momentum threshold
- **Ranging Market:** Standard VWAP (0.3%), standard momentum
- **Volatile Market:** Wider VWAP (0.5%), much higher momentum (100)
- **Quiet Market:** Relaxed VWAP (0.2%), lower momentum (30)

### 2. Performance-Based Corrections
- **Consecutive Losses:** Increase confidence requirement by 5%
- **Filter Over-Blocking (>70%):** Relax filter threshold by 20%
- **Afternoon Session:** Reduce position size to 50%

---

## Emergency Stop

If Adaptive Engine causes problems:

1. **Press Ctrl+C** in the Adaptive Engine terminal
2. **Delete** `adaptive_data/adaptive_config.json` (resets to defaults)
3. **V4 continues running** with original thresholds

---

## Integration Test

To verify everything works before market opens:

```batch
cd c:\cursor\options\niftyopt
.\venv\Scripts\python.exe ADAPTIVE_V4.py --test
```

This runs 5 test cycles without V4 integration.

---

## 5 Layers Implemented

| Layer | Name | Status | Description |
|-------|------|--------|-------------|
| L2 | Performance Monitor | Active | Tracks all signals from V4 logs |
| L3 | Regime Detector | Active | Classifies market conditions |
| L4 | Auto-Correction | Active | Rule-based threshold adjustment |
| L5 | Meta-Learning | Active | Parses FIXES.md patterns |

---

## Version Alignment

Both systems now use V4 versioning:
- **MODULAR_TRADER_V4.py** - Core trading engine
- **ADAPTIVE_V4.py** - Adaptive layer that monitors and adjusts V4

This makes upgrades easier to track - both advance together.

---

## Support

If issues occur:
1. Check `adaptive_data/adaptive_engine.log`
2. Check `adaptive_data/corrections.log`
3. Ensure `adaptive_config.json` is valid JSON
4. Restart only the Adaptive Engine (V4 keeps running)
