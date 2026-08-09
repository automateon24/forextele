# Batch Backtest Report - 20260809_2141

## Strategy Ranking
| Strategy            |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:--------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| VWAP_MEAN_REVERSION |  23361           |    1557.4  |              0   |        1 |       100    |      2.3361e+13 |         23361    |
| ASIAN_RANGE_SCALP   |      2.42704e+06 |  161803    |           7619.4 |      232 |        45.26 |      3.46       |         10461.4  |
| LONDON_BREAKOUT_V2  | 633030           |   42202    |          25741.1 |      127 |        48.82 |      1.3        |          4984.49 |
| NY_OPEN_BREAKOUT    | 312895           |   20859.7  |         129911   |       76 |        39.47 |      1.08       |          4117.04 |
| FVG_RETEST          | 222413           |   14827.6  |          49363   |      193 |        38.34 |      1.05       |          1152.4  |
| LONDON_BREAKOUT     | 185735           |   12382.3  |         484044   |      362 |        34.81 |      1.01       |           513.08 |
| SMC_ORDER_BLOCK     | -46618.2         |   -3107.88 |          25680.5 |      103 |        27.18 |      0.97       |          -452.6  |

## Correlation Matrix
| strategy_id         |   ASIAN_RANGE_SCALP |   FVG_RETEST |   LONDON_BREAKOUT |   LONDON_BREAKOUT_V2 |   NY_OPEN_BREAKOUT |   SMC_ORDER_BLOCK |   VWAP_MEAN_REVERSION |
|:--------------------|--------------------:|-------------:|------------------:|---------------------:|-------------------:|------------------:|----------------------:|
| ASIAN_RANGE_SCALP   |                1    |        -0.01 |             -0.12 |                -0.03 |               -0   |              0.02 |                 -0.03 |
| FVG_RETEST          |               -0.01 |         1    |              0.02 |                 0.01 |                0   |             -0.07 |                 -0    |
| LONDON_BREAKOUT     |               -0.12 |         0.02 |              1    |                 0.04 |                0.3 |              0    |                 -0    |
| LONDON_BREAKOUT_V2  |               -0.03 |         0.01 |              0.04 |                 1    |               -0   |              0    |                 -0    |
| NY_OPEN_BREAKOUT    |               -0    |         0    |              0.3  |                -0    |                1   |              0    |                 -0    |
| SMC_ORDER_BLOCK     |                0.02 |        -0.07 |              0    |                 0    |                0   |              1    |                  0    |
| VWAP_MEAN_REVERSION |               -0.03 |        -0    |             -0    |                -0    |               -0   |              0    |                  1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
