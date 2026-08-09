# Batch Backtest Report - 20260809_2155

## Strategy Ranking
| Strategy            |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:--------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| VWAP_MEAN_REVERSION |            23.29 |       1.55 |             0    |        1 |       100    |      2.3291e+10 |            23.29 |
| ASIAN_RANGE_SCALP   |          2410.82 |     160.72 |             7.69 |      232 |        45.26 |      3.42       |            10.39 |
| LONDON_BREAKOUT_V2  |           624.15 |      41.61 |            25.85 |      127 |        48.82 |      1.3        |             4.91 |
| NY_OPEN_BREAKOUT    |           307.58 |      20.51 |           130.16 |       76 |        39.47 |      1.08       |             4.05 |
| FVG_RETEST          |           208.92 |      13.93 |            49.47 |      193 |        38.34 |      1.05       |             1.08 |
| LONDON_BREAKOUT     |           160.42 |      10.69 |           485.35 |      362 |        34.81 |      1.01       |             0.44 |
| SMC_ORDER_BLOCK     |           -53.82 |      -3.59 |            25.83 |      103 |        27.18 |      0.96       |            -0.52 |

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
