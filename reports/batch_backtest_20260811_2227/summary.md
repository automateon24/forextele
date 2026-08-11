# Batch Backtest Report - 20260811_2227

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP       |           709.25 |      47.28 |            10.34 |       34 |        55.88 |            2.37 |            20.86 |
| ASIAN_RANGE_SCALP          |            22.33 |       1.49 |            14.31 |       61 |        31.15 |            1.06 |             0.37 |
| TREND_MOMENTUM             |            -0.07 |      -0    |             0    |        1 |         0    |            0    |            -0.07 |
| SMC_ORDER_BLOCK            |           -14.09 |      -0.94 |            12.39 |       29 |        24.14 |            0.95 |            -0.49 |
| LONDON_BREAKOUT_V2         |           -94.14 |      -6.28 |             9.68 |       26 |        38.46 |            0.76 |            -3.62 |
| NY_OPEN_BREAKOUT           |           -89.73 |      -5.98 |            34.28 |       19 |        42.11 |            0.88 |            -4.72 |
| FVG_RETEST                 |          -222.65 |     -14.84 |            17.13 |       45 |        31.11 |            0.76 |            -4.95 |
| LONDON_BREAKOUT            |          -783.62 |     -52.24 |           160.51 |       77 |        29.87 |            0.77 |           -10.18 |
| ORB_OPENING_RANGE_BREAKOUT |           -78.32 |      -5.22 |             3.68 |        3 |         0    |            0    |           -26.11 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|-----------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0.01 |             -0.01 |                 0.03 |                   0.04 |               0    |                         0    |             -0.03 |             0    |
| FVG_RETEST                 |               -0.01 |         1    |              0.06 |                -0    |                   0.01 |              -0    |                        -0.01 |              0    |            -0    |
| LONDON_BREAKOUT            |               -0.01 |         0.06 |              1    |                 0.04 |                   0.3  |               0.43 |                        -0.03 |             -0    |            -0.18 |
| LONDON_BREAKOUT_V2         |                0.03 |        -0    |              0.04 |                 1    |                   0.47 |              -0    |                        -0.01 |             -0    |            -0    |
| LONDON_SESSION_SCALP       |                0.04 |         0.01 |              0.3  |                 0.47 |                   1    |               0    |                         0.02 |              0    |             0.01 |
| NY_OPEN_BREAKOUT           |                0    |        -0    |              0.43 |                -0    |                   0    |               1    |                        -0.01 |             -0    |            -0.3  |
| ORB_OPENING_RANGE_BREAKOUT |                0    |        -0.01 |             -0.03 |                -0.01 |                   0.02 |              -0.01 |                         1    |             -0    |            -0.01 |
| SMC_ORDER_BLOCK            |               -0.03 |         0    |             -0    |                -0    |                   0    |              -0    |                        -0    |              1    |            -0    |
| TREND_MOMENTUM             |                0    |        -0    |             -0.18 |                -0    |                   0.01 |              -0.3  |                        -0.01 |             -0    |             1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
