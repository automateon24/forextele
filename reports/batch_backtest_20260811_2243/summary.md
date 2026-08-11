# Batch Backtest Report - 20260811_2243

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| NY_OPEN_BREAKOUT           |           732.67 |      48.84 |            33.04 |       98 |        48.98 |            1.46 |             7.48 |
| LONDON_BREAKOUT            |          2808.39 |     187.23 |           117.85 |      452 |        39.6  |            1.26 |             6.21 |
| LONDON_SESSION_SCALP       |           927.24 |      61.82 |            16.99 |      193 |        49.74 |            1.51 |             4.8  |
| FVG_RETEST                 |           431.52 |      28.77 |            20.63 |      228 |        39.47 |            1.21 |             1.89 |
| ASIAN_RANGE_SCALP          |           411.04 |      27.4  |            11.84 |      297 |        29.63 |            1.39 |             1.38 |
| SMC_ORDER_BLOCK            |            16.53 |       1.1  |            16.37 |      329 |        27.05 |            1.01 |             0.05 |
| LONDON_BREAKOUT_V2         |            -5.89 |      -0.39 |             8.89 |      151 |        44.37 |            0.99 |            -0.04 |
| TREND_MOMENTUM             |            -0.13 |      -0.01 |             0    |        1 |         0    |            0    |            -0.13 |
| VWAP_MEAN_REVERSION        |            -0.14 |      -0.01 |             0    |        1 |         0    |            0    |            -0.14 |
| ORB_OPENING_RANGE_BREAKOUT |           -58.1  |      -3.87 |            14.78 |       33 |        36.36 |            0.83 |            -1.76 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |   VWAP_MEAN_REVERSION |
|:---------------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|-----------------------------:|------------------:|-----------------:|----------------------:|
| ASIAN_RANGE_SCALP          |                1    |        -0.02 |             -0.05 |                -0.02 |                  -0.01 |              -0    |                         0    |              0.05 |             0.01 |                  0.01 |
| FVG_RETEST                 |               -0.02 |         1    |              0.03 |                 0.01 |                   0.01 |               0.03 |                         0.03 |             -0.09 |            -0.14 |                 -0.14 |
| LONDON_BREAKOUT            |               -0.05 |         0.03 |              1    |                 0.06 |                   0.2  |               0.37 |                         0.05 |             -0    |            -0.06 |                 -0.06 |
| LONDON_BREAKOUT_V2         |               -0.02 |         0.01 |              0.06 |                 1    |                   0.46 |               0    |                        -0    |              0.01 |            -0    |                 -0    |
| LONDON_SESSION_SCALP       |               -0.01 |         0.01 |              0.2  |                 0.46 |                   1    |              -0    |                         0    |              0.01 |             0    |                  0    |
| NY_OPEN_BREAKOUT           |               -0    |         0.03 |              0.37 |                 0    |                  -0    |               1    |                         0.18 |              0.01 |             0    |                  0    |
| ORB_OPENING_RANGE_BREAKOUT |                0    |         0.03 |              0.05 |                -0    |                   0    |               0.18 |                         1    |              0    |            -0    |                 -0    |
| SMC_ORDER_BLOCK            |                0.05 |        -0.09 |             -0    |                 0.01 |                   0.01 |               0.01 |                         0    |              1    |             0    |                  0    |
| TREND_MOMENTUM             |                0.01 |        -0.14 |             -0.06 |                -0    |                   0    |               0    |                        -0    |              0    |             1    |                  1    |
| VWAP_MEAN_REVERSION        |                0.01 |        -0.14 |             -0.06 |                -0    |                   0    |               0    |                        -0    |              0    |             1    |                  1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
