# Batch Backtest Report - 20260811_2329

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP     |           284.71 |      18.98 |            26.96 |      540 |        42.59 |            1.1  |             0.53 |
| NY_OPEN_BREAKOUT         |           110.59 |       7.37 |            45.26 |      256 |        43.36 |            1.05 |             0.43 |
| ASIAN_RANGE_SCALP        |           321.53 |      21.44 |            17.76 |      883 |        23.78 |            1.14 |             0.36 |
| LONDON_BREAKOUT_V2       |           -54.94 |      -3.66 |            15.01 |      429 |        44.76 |            0.96 |            -0.13 |
| FVG_RETEST               |          -215.7  |     -14.38 |            22.76 |      607 |        32.45 |            0.92 |            -0.36 |
| BOLLINGER_MEAN_REVERSION |          -739.51 |     -49.3  |            64.37 |     1858 |        37.94 |            0.87 |            -0.4  |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |
|:-------------------------|--------------------:|---------------------------:|-------------:|---------------------:|-----------------------:|-------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.19 |        -0.04 |                -0.02 |                  -0.03 |              -0    |
| BOLLINGER_MEAN_REVERSION |                0.19 |                       1    |        -0.09 |                -0.07 |                  -0.08 |              -0.07 |
| FVG_RETEST               |               -0.04 |                      -0.09 |         1    |                 0.01 |                   0.06 |               0.03 |
| LONDON_BREAKOUT_V2       |               -0.02 |                      -0.07 |         0.01 |                 1    |                   0.54 |               0    |
| LONDON_SESSION_SCALP     |               -0.03 |                      -0.08 |         0.06 |                 0.54 |                   1    |              -0    |
| NY_OPEN_BREAKOUT         |               -0    |                      -0.07 |         0.03 |                 0    |                  -0    |               1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
