# Batch Backtest Report - 20260811_2352

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP     |          3295.66 |     219.71 |            88.42 |      163 |        48.47 |            1.4  |            20.22 |
| ASIAN_RANGE_SCALP        |          3145.52 |     209.7  |            35.46 |      235 |        37.45 |            1.89 |            13.39 |
| BOLLINGER_MEAN_REVERSION |          3263.9  |     217.59 |           140.32 |      743 |        29.21 |            1.23 |             4.39 |
| FVG_RETEST               |           373.38 |      24.89 |           100.97 |      181 |        37.02 |            1.04 |             2.06 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.12 |        -0    |                  -0.03 |
| BOLLINGER_MEAN_REVERSION |                0.12 |                       1    |        -0.06 |                  -0.11 |
| FVG_RETEST               |               -0    |                      -0.06 |         1    |                   0    |
| LONDON_SESSION_SCALP     |               -0.03 |                      -0.11 |         0    |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
