@echo off
cd /d c:\cursor\options\niftyopt
echo [%DATE% %TIME%] Starting 5-10%% Target Backtest with Looser TSL... > detailed_backtest.log 2>&1
echo TSL: 3%% activate, 8%% trail, 60%% target, 2 lots >> detailed_backtest.log 2>&1
c:\cursor\options\niftyopt\venv\Scripts\python.exe -u BACKTEST_V7_AGGRESSIVE.py >> detailed_backtest.log 2>&1
echo [%DATE% %TIME%] Backtest Exit: %ERRORLEVEL% >> detailed_backtest.log 2>&1
echo [%DATE% %TIME%] Running detailed analysis... >> detailed_backtest.log 2>&1
c:\cursor\options\niftyopt\venv\Scripts\python.exe detailed_analysis.py >> detailed_backtest.log 2>&1
echo [%DATE% %TIME%] Complete >> detailed_backtest.log 2>&1
