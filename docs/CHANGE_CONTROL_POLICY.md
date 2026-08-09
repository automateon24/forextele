# Change Control & Audit Policy v1.0

## 1. Immutable Audit Trail
The system strictly enforces an append-only JSON Lines format (`audit.jsonl`) for all Risk Engine decisions. 
- Every `ALLOW`, `ALLOW_REDUCED`, and `BLOCK` decision must be recorded instantly.
- The record must include the exact timestamp, the original signal correlation ID, and the exact portfolio snapshot evaluated at that millisecond.
- **Rule:** Log tampering or deletion is strictly prohibited. `audit.jsonl` is the sole source of truth for execution forensics.

## 2. Material Change Protocol
A "Material Change" is defined as any modification to:
- Signal generation logic (indicators, lookbacks).
- Risk limits (Daily loss, portfolio heat, margin buffer).
- Kill Switch conditions.
- Message schemas.

### 2.1 Testing Prerequisite
No Material Change may be deployed to the `master_swarm_runner` without first:
1. Passing the full `pytest` suite locally (`pytest tests/`).
2. Completing a closed-candle historical simulation (Backtest) that mirrors production risk limits.

### 2.2 Deployment
- Changes to `config/risk_config.json` can be made live; the Risk Engine will pick them up if designed to poll, but a system restart is recommended for safety.
- Changes to Python logic (`src/`) require a complete halt of the Swarm runner and a cold reboot.

## 3. Emergency Procedures (Kill Switch)
- In the event of extreme market volatility, broker API failure, or unexpected strategy behavior, the Global Kill Switch (`config/kill_switch.json -> "global": true`) must be triggered.
- The Risk Engine will immediately block all incoming signals.
- The Kill Switch state must remain active until a formal post-mortem is conducted using the `audit.jsonl` forensics.
