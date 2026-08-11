# Batch Backtest Report - 20260811_2257

## Strategy Ranking
| Strategy                   |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| NY_OPEN_BREAKOUT           |           713.35 |      47.56 |            33.04 |       98 |        48.98 |            1.45 |             7.28 |
| LONDON_BREAKOUT            |          2752.57 |     183.5  |           117.85 |      451 |        39.69 |            1.26 |             6.1  |
| LONDON_SESSION_SCALP       |           933.68 |      62.25 |            16.99 |      193 |        50.26 |            1.51 |             4.84 |
| FVG_RETEST                 |           385.54 |      25.7  |            20.63 |      227 |        39.21 |            1.19 |             1.7  |
| ASIAN_RANGE_SCALP          |           413.3  |      27.55 |            11.84 |      296 |        29.73 |            1.39 |             1.4  |
| BOLLINGER_MEAN_REVERSION   |           295.4  |      19.69 |            37.26 |      736 |        33.97 |            1.08 |             0.4  |
| SMC_ORDER_BLOCK            |            10.09 |       0.67 |            16.37 |      329 |        27.05 |            1.01 |             0.03 |
| RSI_REVERSAL               |           -19.4  |      -1.29 |            43.05 |      747 |        47.12 |            0.99 |            -0.03 |
| LONDON_BREAKOUT_V2         |            -5.89 |      -0.39 |             8.89 |      151 |        44.37 |            0.99 |            -0.04 |
| VWAP_MEAN_REVERSION        |            -0.14 |      -0.01 |             0    |        1 |         0    |            0    |            -0.14 |
| ORB_OPENING_RANGE_BREAKOUT |           -58.1  |      -3.87 |            14.78 |       33 |        36.36 |            0.83 |            -1.76 |
| MEAN_REVERSION             |            -2.52 |      -0.17 |             0    |        1 |         0    |            0    |            -2.52 |

## Correlation Matrix
| strategy_id                |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   MEAN_REVERSION |   NY_OPEN_BREAKOUT |   ORB_OPENING_RANGE_BREAKOUT |   RSI_REVERSAL |   SMC_ORDER_BLOCK |   VWAP_MEAN_REVERSION |
|:---------------------------|--------------------:|---------------------------:|-------------:|------------------:|---------------------:|-----------------------:|-----------------:|-------------------:|-----------------------------:|---------------:|------------------:|----------------------:|
| ASIAN_RANGE_SCALP          |                1    |                       0.14 |        -0.02 |             -0.05 |                -0.02 |                  -0.01 |             0.03 |              -0    |                         0    |           0.11 |              0.05 |                  0.03 |
| BOLLINGER_MEAN_REVERSION   |                0.14 |                       1    |        -0.07 |             -0.17 |                -0.07 |                  -0.07 |             0    |              -0.05 |                        -0.02 |           0.26 |              0.21 |                  0    |
| FVG_RETEST                 |               -0.02 |                      -0.07 |         1    |              0.02 |                 0.01 |                   0.01 |             0    |               0.03 |                         0.03 |          -0.1  |             -0.09 |                  0    |
| LONDON_BREAKOUT            |               -0.05 |                      -0.17 |         0.02 |              1    |                 0.06 |                   0.2  |             0    |               0.37 |                         0.04 |          -0.1  |             -0    |                  0    |
| LONDON_BREAKOUT_V2         |               -0.02 |                      -0.07 |         0.01 |              0.06 |                 1    |                   0.46 |            -0    |               0    |                        -0    |          -0.08 |              0.01 |                 -0    |
| LONDON_SESSION_SCALP       |               -0.01 |                      -0.07 |         0.01 |              0.2  |                 0.46 |                   1    |             0    |              -0    |                         0    |          -0.07 |              0.01 |                  0    |
| MEAN_REVERSION             |                0.03 |                       0    |         0    |              0    |                -0    |                   0    |             1    |               0    |                        -0    |           0.03 |              0    |                  1    |
| NY_OPEN_BREAKOUT           |               -0    |                      -0.05 |         0.03 |              0.37 |                 0    |                  -0    |             0    |               1    |                         0.18 |          -0.09 |              0.01 |                  0    |
| ORB_OPENING_RANGE_BREAKOUT |                0    |                      -0.02 |         0.03 |              0.04 |                -0    |                   0    |            -0    |               0.18 |                         1    |          -0.02 |              0    |                 -0    |
| RSI_REVERSAL               |                0.11 |                       0.26 |        -0.1  |             -0.1  |                -0.08 |                  -0.07 |             0.03 |              -0.09 |                        -0.02 |           1    |              0.15 |                  0.03 |
| SMC_ORDER_BLOCK            |                0.05 |                       0.21 |        -0.09 |             -0    |                 0.01 |                   0.01 |             0    |               0.01 |                         0    |           0.15 |              1    |                  0    |
| VWAP_MEAN_REVERSION        |                0.03 |                       0    |         0    |              0    |                -0    |                   0    |             1    |               0    |                        -0    |           0.03 |              0    |                  1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
