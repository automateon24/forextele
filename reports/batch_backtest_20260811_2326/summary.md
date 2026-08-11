# Batch Backtest Report - 20260811_2326

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP     |           949.96 |      63.33 |            16.99 |      193 |        50.26 |            1.52 |             4.92 |
| FVG_RETEST               |           506.29 |      33.75 |            20.63 |      232 |        40.52 |            1.24 |             2.18 |
| ASIAN_RANGE_SCALP        |           387.7  |      25.85 |            11.84 |      306 |        29.41 |            1.36 |             1.27 |
| BOLLINGER_MEAN_REVERSION |           158.79 |      10.59 |            37.26 |      750 |        33.2  |            1.04 |             0.21 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.14 |        -0.03 |                  -0.01 |
| BOLLINGER_MEAN_REVERSION |                0.14 |                       1    |        -0.08 |                  -0.08 |
| FVG_RETEST               |               -0.03 |                      -0.08 |         1    |                   0.01 |
| LONDON_SESSION_SCALP     |               -0.01 |                      -0.08 |         0.01 |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
