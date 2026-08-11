# Batch Backtest Report - 20260811_2350

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| ASIAN_RANGE_SCALP        |           438.58 |      29.24 |             4.06 |      176 |        37.5  |            1.91 |             2.49 |
| LONDON_SESSION_SCALP     |             8.93 |       0.6  |             4    |       16 |        43.75 |            1.05 |             0.56 |
| BOLLINGER_MEAN_REVERSION |          -321.18 |     -21.41 |            28.59 |      219 |        21.46 |            0.76 |            -1.47 |
| FVG_RETEST               |           -32.42 |      -2.16 |            11.09 |       19 |        31.58 |            0.87 |            -1.71 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.01 |            0 |                     -0 |
| BOLLINGER_MEAN_REVERSION |                0.01 |                       1    |           -0 |                      0 |
| FVG_RETEST               |                0    |                      -0    |            1 |                      0 |
| LONDON_SESSION_SCALP     |               -0    |                       0    |            0 |                      1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
