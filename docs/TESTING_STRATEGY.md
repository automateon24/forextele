# Testing Strategy v1.0

## Test Pyramid
1. **Unit Tests (Mandatory)**: Pure functions, every risk check, message schemas.
2. **Integration Tests**: Signal → Risk → Gateway mock flows.
3. **Simulation / Replay**: Closed-candle strategy backtesting with realistic spreads/costs/latency.
4. **Stress / Scenario**: Gaps, connection loss, heat exhaustion, kill-switch.
5. **Regression**: Must stay green on every material change.

## Material Change Definition
Any change to signal logic, risk limits, sizing, SL/TP construction, candle handling, or kill-switch behaviour requires full re-validation + audit record.

## Risk Engine Cases (RE-01 to RE-17)
- **RE-01/02:** Kill switch (global + symbol) -> BLOCK
- **RE-03:** Stale portfolio data -> BLOCK
- **RE-04:** Spread too wide -> BLOCK
- **RE-05/06:** Missing / too-close SL -> BLOCK
- **RE-10:** Portfolio heat limit -> BLOCK / REDUCE
- **RE-11/12:** Max positions (total + per symbol) -> BLOCK
- **RE-13:** Daily loss limit -> BLOCK
- **RE-14:** Drawdown from HWM -> BLOCK
- **RE-16:** Happy-path -> ALLOW
- **RE-17:** Invalid tick value -> BLOCK

## Strategy Families Test Cases
- Common rules (closed-candle only, schema, strength bounds)
- LONDON_BREAKOUT (session window, range break, debounce)
- MEAN_REVERSION / RSI (ADX regime filter)
- SMC (confluence on closed bars only, structural SL)

## Migration Rule for Legacy Strategies
Extract pure closed-candle function → write unit tests first → run simulation under production risk limits → wire into the orchestrator.
