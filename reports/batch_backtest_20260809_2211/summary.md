# Batch Backtest Report - 20260809_2211

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| ASIAN_RANGE_SCALP          |           106.31 |       7.09 |             4.71 |      254 |        36.61 |            1.29 |             0.42 |
| SMC_ORDER_BLOCK            |            26.3  |       1.75 |             4.26 |      302 |        27.15 |            1.06 |             0.09 |
| LONDON_SESSION_SCALP       |            -3.93 |      -0.26 |             5.49 |      198 |        39.39 |            0.99 |            -0.02 |
| LONDON_BREAKOUT_V2         |           -38.7  |      -2.58 |             3.29 |      155 |        38.71 |            0.76 |            -0.25 |
| ORB_OPENING_RANGE_BREAKOUT |           -13.24 |      -0.88 |             2.54 |       28 |        35.71 |            0.76 |            -0.47 |
| FVG_RETEST                 |           -50.66 |      -3.38 |             5.1  |       81 |        29.63 |            0.76 |            -0.63 |
| LONDON_BREAKOUT            |          -299.06 |     -19.94 |            29.2  |      384 |        30.21 |            0.79 |            -0.78 |
| NY_OPEN_BREAKOUT           |           -81.65 |      -5.44 |             8.76 |      101 |        34.65 |            0.73 |            -0.81 |
| TREND_MOMENTUM             |            -5.02 |      -0.33 |             0.16 |        2 |         0    |            0    |            -2.51 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|-----------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0.03 |             -0.08 |                -0.03 |                  -0.02 |               0    |                         0    |              0.09 |                0 |
| FVG_RETEST                 |               -0.03 |         1    |              0.02 |                -0    |                   0    |              -0    |                        -0    |             -0.04 |               -0 |
| LONDON_BREAKOUT            |               -0.08 |         0.02 |              1    |                 0.07 |                   0.25 |               0.31 |                         0.15 |              0.03 |               -0 |
| LONDON_BREAKOUT_V2         |               -0.03 |        -0    |              0.07 |                 1    |                   0.46 |              -0    |                        -0    |              0    |               -0 |
| LONDON_SESSION_SCALP       |               -0.02 |         0    |              0.25 |                 0.46 |                   1    |              -0    |                        -0    |              0    |               -0 |
| NY_OPEN_BREAKOUT           |                0    |        -0    |              0.31 |                -0    |                  -0    |               1    |                         0.3  |              0.05 |               -0 |
| ORB_OPENING_RANGE_BREAKOUT |                0    |        -0    |              0.15 |                -0    |                  -0    |               0.3  |                         1    |              0    |               -0 |
| SMC_ORDER_BLOCK            |                0.09 |        -0.04 |              0.03 |                 0    |                   0    |               0.05 |                         0    |              1    |                0 |
| TREND_MOMENTUM             |                0    |        -0    |             -0    |                -0    |                  -0    |              -0    |                        -0    |              0    |                1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
