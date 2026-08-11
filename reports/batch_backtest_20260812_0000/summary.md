# Batch Backtest Report - 20260812_0000

## Strategy Ranking
| Strategy                 |   Net Profit ($) |   Return % |   Max Drawdown % |   Trades |   Win Rate % |   Profit Factor |   Expectancy ($) |
|:-------------------------|-----------------:|-----------:|-----------------:|---------:|-------------:|----------------:|-----------------:|
| ASIAN_RANGE_SCALP        |           519.92 |      34.66 |             4.76 |      304 |        50.99 |            1.77 |             1.71 |
| LONDON_SESSION_SCALP     |           219.4  |      14.63 |            11.4  |      193 |        71.5  |            1.24 |             1.14 |
| BOLLINGER_MEAN_REVERSION |           198.17 |      13.21 |            21.66 |      748 |        46.39 |            1.07 |             0.26 |
| FVG_RETEST               |          -176.3  |     -11.75 |            26.38 |      155 |        60    |            0.84 |            -1.14 |

## Correlation Matrix
| strategy_id              |   ASIAN_RANGE_SCALP |   BOLLINGER_MEAN_REVERSION |   FVG_RETEST |   LONDON_SESSION_SCALP |
|:-------------------------|--------------------:|---------------------------:|-------------:|-----------------------:|
| ASIAN_RANGE_SCALP        |                1    |                       0.28 |        -0.03 |                  -0.02 |
| BOLLINGER_MEAN_REVERSION |                0.28 |                       1    |        -0.04 |                  -0.08 |
| FVG_RETEST               |               -0.03 |                      -0.04 |         1    |                   0.01 |
| LONDON_SESSION_SCALP     |               -0.02 |                      -0.08 |         0.01 |                   1    |

## Recommendations
Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.
