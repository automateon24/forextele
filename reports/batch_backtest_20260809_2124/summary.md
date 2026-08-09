# Batch Backtest Report - 20260809_2124

## Strategy Ranking
| Strategy        |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:----------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| SMC_ORDER_BLOCK |             1.97 |       0.13 |             3.27 |      108 |        27.78 |            1.01 |             0.02 |
| LONDON_BREAKOUT |          -130.71 |      -8.71 |            12.31 |      121 |        28.93 |            0.63 |            -1.08 |

## Correlation Matrix
| strategy_id     |   LONDON_BREAKOUT |   SMC_ORDER_BLOCK |
|:----------------|------------------:|------------------:|
| LONDON_BREAKOUT |                 1 |                 0 |
| SMC_ORDER_BLOCK |                 0 |                 1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
