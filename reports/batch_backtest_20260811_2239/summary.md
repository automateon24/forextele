# Batch Backtest Report - 20260811_2239

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| NY_OPEN_BREAKOUT           |           718.03 |      47.87 |            33.04 |       98 |        48.98 |            1.45 |             7.33 |
| LONDON_BREAKOUT            |          2907.85 |     193.86 |           117.85 |      453 |        39.96 |            1.27 |             6.42 |
| LONDON_SESSION_SCALP       |           932.12 |      62.14 |            16.99 |      193 |        50.26 |            1.51 |             4.83 |
| FVG_RETEST                 |           436.4  |      29.09 |            20.63 |      228 |        39.47 |            1.21 |             1.91 |
| ASIAN_RANGE_SCALP          |           411.2  |      27.41 |            11.84 |      298 |        29.87 |            1.39 |             1.38 |
| SMC_ORDER_BLOCK            |            11.65 |       0.78 |            16.37 |      329 |        27.05 |            1.01 |             0.04 |
| LONDON_BREAKOUT_V2         |            -5.89 |      -0.39 |             8.89 |      151 |        44.37 |            0.99 |            -0.04 |
| VWAP_MEAN_REVERSION        |            -0.14 |      -0.01 |             0    |        1 |         0    |            0    |            -0.14 |
| ORB_OPENING_RANGE_BREAKOUT |           -58.1  |      -3.87 |            14.78 |       33 |        36.36 |            0.83 |            -1.76 |
| TREND_MOMENTUM             |            -5.62 |      -0.37 |             0    |        1 |         0    |            0    |            -5.62 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |   VWAP_MEAN_REVERSION |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|-----------------:|----------------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0.02 |             -0.05 |                -0.02 |                  -0.01 |              -0    |                         0    |              0.05 |             0    |                  0    |
| FVG_RETEST                 |               -0.02 |         1    |              0.03 |                 0.01 |                   0.01 |               0.03 |                         0.03 |             -0.09 |             0    |                  0    |
| LONDON_BREAKOUT            |               -0.05 |         0.03 |              1    |                 0.06 |                   0.2  |               0.37 |                         0.04 |             -0    |            -0.06 |                 -0.06 |
| LONDON_BREAKOUT_V2         |               -0.02 |         0.01 |              0.06 |                 1    |                   0.46 |               0    |                        -0    |              0.01 |            -0    |                 -0    |
| LONDON_SESSION_SCALP       |               -0.01 |         0.01 |              0.2  |                 0.46 |                   1    |              -0    |                         0    |              0.01 |             0    |                  0    |
| NY_OPEN_BREAKOUT           |               -0    |         0.03 |              0.37 |                 0    |                  -0    |               1    |                         0.18 |              0.01 |             0    |                  0    |
| ORB_OPENING_RANGE_BREAKOUT |                0    |         0.03 |              0.04 |                -0    |                   0    |               0.18 |                         1    |              0    |            -0    |                 -0    |
| SMC_ORDER_BLOCK            |                0.05 |        -0.09 |             -0    |                 0.01 |                   0.01 |               0.01 |                         0    |              1    |             0    |                  0    |
| TREND_MOMENTUM             |                0    |         0    |             -0.06 |                -0    |                   0    |               0    |                        -0    |              0    |             1    |                  1    |
| VWAP_MEAN_REVERSION        |                0    |         0    |             -0.06 |                -0    |                   0    |               0    |                        -0    |              0    |             1    |                  1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
