# Batch Backtest Report - 20260809_2131

## Strategy Ranking
| Strategy          |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| ASIAN_RANGE_SCALP |           106.31 |       7.09 |             4.71 |      254 |        36.61 |            1.29 |             0.42 |
| SMC_ORDER_BLOCK   |            26.3  |       1.75 |             4.26 |      302 |        27.15 |            1.06 |             0.09 |
| LONDON_BREAKOUT   |          -299.06 |     -19.94 |            29.2  |      384 |        30.21 |            0.79 |            -0.78 |
| NY_OPEN_BREAKOUT  |           -81.65 |      -5.44 |             8.76 |      101 |        34.65 |            0.73 |            -0.81 |
| TREND_MOMENTUM    |            -5.02 |      -0.33 |             0.16 |        2 |         0    |            0    |            -2.51 |

## Correlation Matrix
| strategy_id       |   ASIAN_RANGE_SCALP |   LONDON_BREAKOUT |   NY_OPEN_BREAKOUT |   SMC_ORDER_BLOCK |   TREND_MOMENTUM |
|:------------------|--------------------:|------------------:|-------------------:|------------------:|-----------------:|
| ASIAN_RANGE_SCALP |                1    |             -0.08 |               0    |              0.09 |                0 |
| LONDON_BREAKOUT   |               -0.08 |              1    |               0.31 |              0.03 |               -0 |
| NY_OPEN_BREAKOUT  |                0    |              0.31 |               1    |              0.05 |               -0 |
| SMC_ORDER_BLOCK   |                0.09 |              0.03 |               0.05 |              1    |                0 |
| TREND_MOMENTUM    |                0    |             -0    |              -0    |              0    |                1 |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
