# Batch Backtest Report - 20260811_2233

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| VWAP_MEAN_REVERSION        |             2.55 |       0.17 |             0    |        1 |       100    |     2.55127e+09 |             2.55 |
| ASIAN_RANGE_SCALP          |           150.15 |      10.01 |             4.57 |      324 |        25.62 |     1.36        |             0.46 |
| SMC_ORDER_BLOCK            |           140.25 |       9.35 |             7.62 |      600 |        28.83 |     1.13        |             0.23 |
| LONDON_BREAKOUT            |           -22.74 |      -1.52 |            35.99 |      423 |        39.01 |     0.99        |            -0.05 |
| ORB_OPENING_RANGE_BREAKOUT |            -3.72 |      -0.25 |             1.86 |       28 |        32.14 |     0.93        |            -0.13 |
| LONDON_BREAKOUT_V2         |           -82.99 |      -5.53 |             7.38 |      143 |        37.76 |     0.71        |            -0.58 |
| LONDON_SESSION_SCALP       |          -125.43 |      -8.36 |            13.48 |      186 |        34.95 |     0.79        |            -0.67 |
| FVG_RETEST                 |          -160.15 |     -10.68 |            10.23 |      232 |        29.74 |     0.72        |            -0.69 |
| NY_OPEN_BREAKOUT           |          -135.15 |      -9.01 |            14.06 |       66 |        31.82 |     0.55        |            -2.05 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   VWAP_MEAN_REVERSION |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|----------------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0    |             -0.12 |                -0.02 |                  -0.02 |               0    |                         0    |              0.01 |                    -0 |
| FVG_RETEST                 |               -0    |         1    |              0.01 |                -0    |                   0.01 |               0.07 |                         0    |              0    |                     0 |
| LONDON_BREAKOUT            |               -0.12 |         0.01 |              1    |                 0.18 |                   0.22 |               0.22 |                         0.06 |              0.01 |                     0 |
| LONDON_BREAKOUT_V2         |               -0.02 |        -0    |              0.18 |                 1    |                   0.64 |              -0    |                        -0    |              0    |                     0 |
| LONDON_SESSION_SCALP       |               -0.02 |         0.01 |              0.22 |                 0.64 |                   1    |              -0    |                        -0    |              0.01 |                     0 |
| NY_OPEN_BREAKOUT           |                0    |         0.07 |              0.22 |                -0    |                  -0    |               1    |                         0.27 |             -0    |                     0 |
| ORB_OPENING_RANGE_BREAKOUT |                0    |         0    |              0.06 |                -0    |                  -0    |               0.27 |                         1    |              0.02 |                     0 |
| SMC_ORDER_BLOCK            |                0.01 |         0    |              0.01 |                 0    |                   0.01 |              -0    |                         0.02 |              1    |                    -0 |
| VWAP_MEAN_REVERSION        |               -0    |         0    |              0    |                 0    |                   0    |               0    |                         0    |             -0    |                     1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
