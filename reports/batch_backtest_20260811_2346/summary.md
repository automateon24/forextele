# Batch Backtest Report - 20260811_2346

## Strategy Ranking
| Strategy             |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP |          2121.72 |     141.45 |            28.14 |       49 |        55.1  |            2.12 |            43.3  |
| ASIAN_RANGE_SCALP    |          3031.27 |     202.08 |            14.38 |      115 |        45.22 |            3.29 |            26.36 |

## Correlation Matrix
| strategy_id          |   ASIAN_RANGE_SCALP |   LONDON_SESSION_SCALP |
|:---------------------|--------------------:|-----------------------:|
| ASIAN_RANGE_SCALP    |                1    |                  -0.04 |
| LONDON_SESSION_SCALP |               -0.04 |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
