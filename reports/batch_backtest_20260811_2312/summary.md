# Batch Backtest Report - 20260811_2312

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP     |          1454.24 |      96.95 |            16.95 |       27 |        59.26 |            3.29 |            53.86 |
| BOLLINGER_MEAN_REVERSION |           946.54 |      63.1  |            34.29 |      115 |        33.91 |            1.68 |             8.23 |
| ASIAN_RANGE_SCALP        |          -106.88 |      -7.13 |            15.76 |       47 |        36.17 |            0.82 |            -2.27 |
| FVG_RETEST               |           -91.74 |      -6.12 |            18.1  |       32 |        34.38 |            0.92 |            -2.87 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.25 |        -0    |                   0.07 |
| BOLLINGER_MEAN_REVERSION |                0.25 |                       1    |        -0.12 |                  -0.1  |
| FVG_RETEST               |               -0    |                      -0.12 |         1    |                   0    |
| LONDON_SESSION_SCALP     |                0.07 |                      -0.1  |         0    |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
