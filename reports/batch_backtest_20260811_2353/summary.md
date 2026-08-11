# Batch Backtest Report - 20260811_2353

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP     |           967.08 |      64.47 |            16.99 |      193 |        50.26 |            1.53 |             5.01 |
| ASIAN_RANGE_SCALP        |           394.26 |      26.28 |            11.84 |      304 |        29.61 |            1.37 |             1.3  |
| FVG_RETEST               |           164.96 |      11    |            20.89 |      155 |        36.13 |            1.08 |             1.06 |
| BOLLINGER_MEAN_REVERSION |           178.73 |      11.92 |            37.26 |      749 |        33.38 |            1.05 |             0.24 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.14 |        -0.03 |                  -0.01 |
| BOLLINGER_MEAN_REVERSION |                0.14 |                       1    |        -0.06 |                  -0.08 |
| FVG_RETEST               |               -0.03 |                      -0.06 |         1    |                   0.01 |
| LONDON_SESSION_SCALP     |               -0.01 |                      -0.08 |         0.01 |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
