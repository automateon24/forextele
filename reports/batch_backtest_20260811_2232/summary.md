# Batch Backtest Report - 20260811_2232

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_BREAKOUT            |          2566.41 |     171.09 |            89.81 |      400 |        38.75 |            1.33 |             6.42 |
| ASIAN_RANGE_SCALP          |           488.54 |      32.57 |            10.7  |      292 |        32.19 |            1.65 |             1.67 |
| ORB_OPENING_RANGE_BREAKOUT |            37    |       2.47 |             7.14 |       26 |        42.31 |            1.17 |             1.42 |
| FVG_RETEST                 |           126.33 |       8.42 |            22.89 |      197 |        34.01 |            1.08 |             0.64 |
| LONDON_SESSION_SCALP       |            68.46 |       4.56 |            43.01 |      168 |        40.48 |            1.04 |             0.41 |
| LONDON_BREAKOUT_V2         |            37.12 |       2.47 |            13.95 |      126 |        41.27 |            1.05 |             0.29 |
| SMC_ORDER_BLOCK            |            41.54 |       2.77 |            10.32 |      189 |        26.98 |            1.04 |             0.22 |
| VWAP_MEAN_REVERSION        |            -0.07 |      -0    |             0    |        1 |         0    |            0    |            -0.07 |
| NY_OPEN_BREAKOUT           |          -261.6  |     -17.44 |            58.79 |       90 |        40    |            0.84 |            -2.91 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   VWAP_MEAN_REVERSION |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|----------------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0.01 |             -0.03 |                 0.01 |                   0.01 |               0    |                        -0    |              0.01 |                     0 |
| FVG_RETEST                 |               -0.01 |         1    |              0.05 |                 0.02 |                   0.02 |              -0    |                        -0    |             -0.02 |                     0 |
| LONDON_BREAKOUT            |               -0.03 |         0.05 |              1    |                 0.15 |                   0.21 |               0.34 |                         0.09 |             -0    |                     0 |
| LONDON_BREAKOUT_V2         |                0.01 |         0.02 |              0.15 |                 1    |                   0.44 |               0    |                        -0    |             -0    |                     0 |
| LONDON_SESSION_SCALP       |                0.01 |         0.02 |              0.21 |                 0.44 |                   1    |               0    |                        -0    |             -0    |                     0 |
| NY_OPEN_BREAKOUT           |                0    |        -0    |              0.34 |                 0    |                   0    |               1    |                         0.29 |              0    |                    -0 |
| ORB_OPENING_RANGE_BREAKOUT |               -0    |        -0    |              0.09 |                -0    |                  -0    |               0.29 |                         1    |             -0    |                     0 |
| SMC_ORDER_BLOCK            |                0.01 |        -0.02 |             -0    |                -0    |                  -0    |               0    |                        -0    |              1    |                     0 |
| VWAP_MEAN_REVERSION        |                0    |         0    |              0    |                 0    |                   0    |              -0    |                         0    |              0    |                     1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
