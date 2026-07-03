#!/usr/bin/env python3
"""Deep audit of MODULAR_TRADER_V4 and ADAPTIVE_V4 for runtime bugs."""
import ast, sys, re

issues = []

def check(label, condition, detail=""):
    if not condition:
        issues.append((label, detail))

# ─────────────────────────────────────────────
# Load source
# ─────────────────────────────────────────────
with open('MODULAR_TRADER_V4.py', encoding='utf-8', errors='ignore') as f:
    v4_src = f.read()
with open('ADAPTIVE_V4.py', encoding='utf-8', errors='ignore') as f:
    adp_src = f.read()

v4_lines  = v4_src.splitlines()
adp_lines = adp_src.splitlines()

# ─────────────────────────────────────────────
# 1. OptionContract attribute .get() calls (the killer bug)
# ─────────────────────────────────────────────
for i, line in enumerate(v4_lines, 1):
    if 'data.chain[' in line and '.get(' in line and 'isinstance' not in line:
        issues.append(("CRITICAL", f"V4 line {i}: OptionContract.get() call - {line.strip()}"))

# ─────────────────────────────────────────────
# 2. cooldown_minutes attribute - does StrategyModule have it?
# ─────────────────────────────────────────────
has_cooldown_minutes = 'cooldown_minutes' in v4_src
has_cooldown_attr_set = re.search(r'self\.cooldown_minutes\s*=', v4_src)
# It's used in aggressive mode:
uses_cooldown_minutes = 'module.cooldown_minutes' in v4_src
if uses_cooldown_minutes and not has_cooldown_attr_set:
    issues.append(("CRITICAL", "V4: module.cooldown_minutes used but never defined on StrategyModule"))

# ─────────────────────────name ───────────────
# 3. timedelta import check (used in aggressive cooldown logic)
# ─────────────────────────────────────────────
uses_timedelta = 'timedelta' in v4_src
imports_timedelta = 'from datetime import' in v4_src and 'timedelta' in v4_src
if uses_timedelta and not imports_timedelta:
    issues.append(("CRITICAL", "V4: timedelta used but not imported"))

# ─────────────────────────────────────────────
# 4. Aggressive mode - module.cooldown_until exists?
# ─────────────────────────────────────────────
has_cooldown_until = re.search(r'self\.cooldown_until\s*=', v4_src)
uses_cooldown_until = 'module.cooldown_until' in v4_src
if uses_cooldown_until and not has_cooldown_until:
    issues.append(("CRITICAL", "V4: module.cooldown_until used but never set on StrategyModule"))

# ─────────────────────────────────────────────
# 5. is_in_cooldown() method exists?
# ─────────────────────────────────────────────
has_is_in_cooldown = 'def is_in_cooldown' in v4_src
if not has_is_in_cooldown:
    issues.append(("CRITICAL", "V4: is_in_cooldown() called but never defined"))

# ─────────────────────────────────────────────
# 6. Trade dataclass fields - target/stop_loss named correctly?
# ─────────────────────────────────────────────
trade_dataclass = re.search(r'@dataclass\nclass Trade.*?(?=@dataclass|\nclass )', v4_src, re.DOTALL)
if trade_dataclass:
    td = trade_dataclass.group()
    has_target = 'target' in td
    has_stop_loss = 'stop_loss' in td
    if not has_target:
        issues.append(("CRITICAL", "V4: Trade dataclass missing 'target' field"))
    if not has_stop_loss:
        issues.append(("CRITICAL", "V4: Trade dataclass missing 'stop_loss' field"))

# ─────────────────────────────────────────────
# 7. Config attrs used but not defined
# ─────────────────────────────────────────────
new_config_attrs = [
    'VWAP_VOLUME_CONFIRM',
    'DOWN_DRIFT_ENABLED',
    'DOWN_DRIFT_THRESHOLD_PCT',
    'DOWN_DRIFT_TIME_MINUTES',
    'AGGRESSIVE_MODE_ENABLED',
    'MIN_CONFIDENCE_RELAXED',
    'STRATEGY_COOLDOWN_REDUCTION',
    'MULTI_SIGNAL_CONFLUENCE',
    'MICRO_PROFIT_TARGETS',
]
config_block = re.search(r'class Config.*?(?=\nclass )', v4_src, re.DOTALL)
config_text = config_block.group() if config_block else ''
for attr in new_config_attrs:
    if attr not in config_text:
        issues.append(("CRITICAL", f"V4: Config.{attr} used but not defined in Config class"))

# ─────────────────────────────────────────────
# 8. _update_down_drift called before defined?
# ─────────────────────────────────────────────
call_line   = next((i for i,l in enumerate(v4_lines,1) if '_update_down_drift' in l and 'def ' not in l), None)
define_line = next((i for i,l in enumerate(v4_lines,1) if 'def _update_down_drift' in l), None)
if call_line and define_line and call_line < define_line:
    issues.append(("WARNING", f"V4: _update_down_drift called at line {call_line} before defined at line {define_line}"))

# ─────────────────────────────────────────────
# 9. ADAPTIVE_V4: regime_history - deque maxlen set?
# ─────────────────────────────────────────────
has_deque = 'deque' in adp_src
regime_history_init = re.search(r'regime_history\s*=\s*deque\(.*?maxlen\s*=\s*(\d+)', adp_src)
if has_deque and not regime_history_init:
    issues.append(("WARNING", "ADAPTIVE: regime_history deque has no maxlen - memory leak risk"))

# ─────────────────────────────────────────────
# 10. ADAPTIVE_V4: hysteresis - all() on empty list?
# ─────────────────────────────────────────────
if 'all(r == regime for r in list(self.regime_history)[-5:])' in adp_src:
    # If history has < 5 items, [-5:] returns partial list - all() on partial = true too soon
    # Check if len guard is correct
    if 'len(self.regime_history) >= 5' not in adp_src:
        issues.append(("WARNING", "ADAPTIVE: hysteresis all() check missing len >= 5 guard"))

# ─────────────────────────────────────────────
# 11. V4: open_trades vs open_trade - MAGIC_SQUARE uses list, others use single
# ─────────────────────────────────────────────
if 'module.open_trades' in v4_src and 'open_trades' not in v4_src.split('class StrategyModule')[1].split('class ')[0]:
    issues.append(("WARNING", "V4: module.open_trades used but may not be defined on base StrategyModule"))

# ─────────────────────────────────────────────
# 12. data.chain volume - oi attribute access in OPTIONS_GREEKS secondary filter
# ─────────────────────────────────────────────
for i, line in enumerate(v4_lines, 1):
    if "data.chain[s]['CE'].oi" in line or "data.chain[s]['PE'].oi" in line:
        # check if chain[s] is accessed with string keys
        if "data.chain[s]['CE']" in line:
            issues.append(("CRITICAL", f"V4 line {i}: chain accessed with string key ['CE'] - should use .get('CE') - {line.strip()}"))
            break

# ─────────────────────────────────────────────
# 13. ADAPTIVE: corrections applied to V4 config - does it write correct keys?
# ─────────────────────────────────────────────
written_keys = re.findall(r"corrections\[.([A-Z_]+).\]", adp_src)
v4_config_keys = re.findall(r"^\s+([A-Z_]+)\s*=", config_text, re.MULTILINE)
for k in written_keys:
    if k not in v4_config_keys and k not in ['VWAP_BAND_PCT','CONFIDENCE_BYPASS','MAGIC_MAX_TRADES','MAGIC_VWAP_THRESHOLD']:
        issues.append(("WARNING", f"ADAPTIVE writes key '{k}' to config but V4 may not read it"))

# ─────────────────────────────────────────────
print("=" * 65)
print("V4 + ADAPTIVE DEEP AUDIT RESULTS")
print("=" * 65)
if not issues:
    print("✅ No issues found!")
else:
    criticals = [(l,d) for l,d in issues if l == "CRITICAL"]
    warnings  = [(l,d) for l,d in issues if l == "WARNING"]
    print(f"\n🔴 CRITICAL ({len(criticals)}):")
    for _, d in criticals:
        print(f"   ❌ {d}")
    print(f"\n🟡 WARNINGS ({len(warnings)}):")
    for _, d in warnings:
        print(f"   ⚠️  {d}")
print(f"\nTotal issues: {len(issues)}")
