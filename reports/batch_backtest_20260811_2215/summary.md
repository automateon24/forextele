# Batch Backtest Report - 20260811_2215

## Strategy Ranking
| Strategy             |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:---------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| LONDON_SESSION_SCALP |           701.87 |      46.79 |            10.34 |       34 |        55.88 |            2.34 |            20.64 |
| ASIAN_RANGE_SCALP    |            93.21 |       6.21 |             5.93 |       61 |        40.98 |            1.44 |             1.53 |
| TREND_MOMENTUM       |            -0.07 |      -0    |             0    |        1 |         0    |            0    |            -0.07 |
| SMC_ORDER_BLOCK      |           -16.55 |      -1.1  |            12.39 |       29 |        24.14 |            0.95 |            -0.57 |
| LONDON_BREAKOUT_V2   |           -96.6  |      -6.44 |             9.85 |       26 |        38.46 |            0.75 |            -3.72 |
| NY_OPEN_BREAKOUT     |           -84.81 |      -5.65 |            34.28 |       19 |        42.11 |            0.88 |            -4.46 |
| FVG_RETEST           |          -222.65 |     -14.84 |            17.13 |       45 |        31.11 |            0.76 |            -4.95 |
| LONDON_BREAKOUT      |          -749.18 |     -49.95 |           160.51 |       77 |        29.87 |            0.78 |            -9.73 |

## Correlation Matrix
| strategy_id          |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   LONDON_SESSION_SCALP |   NY_OPEN_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |
|:---------------------|--------------------:|-------------:|------------------:|---------------------:|-----------------------:|-------------------:|------------------:|-----------------:|
| ASIAN_RANGE_SCALP    |                1    |        -0.01 |             -0.01 |                 0.06 |                   0.07 |               0    |             -0.03 |             0    |
| FVG_RETEST           |               -0.01 |         1    |              0.06 |                -0    |                   0.01 |              -0    |              0    |            -0    |
| LONDON_BREAKOUT      |               -0.01 |         0.06 |              1    |                 0.04 |                   0.3  |               0.43 |             -0    |            -0.18 |
| LONDON_BREAKOUT_V2   |                0.06 |        -0    |              0.04 |                 1    |                   0.48 |              -0    |             -0    |            -0    |
| LONDON_SESSION_SCALP |                0.07 |         0.01 |              0.3  |                 0.48 |                   1    |               0    |              0    |             0.01 |
| NY_OPEN_BREAKOUT     |                0    |        -0    |              0.43 |                -0    |                   0    |               1    |             -0    |            -0.3  |
| SMC_ORDER_BLOCK      |               -0.03 |         0    |             -0    |                -0    |                   0    |              -0    |              1    |            -0    |
| TREND_MOMENTUM       |                0    |        -0    |             -0.18 |                -0    |                   0.01 |              -0.3  |             -0    |             1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
