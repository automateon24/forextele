@echo off
cd c:\cursor\options\niftyopt
echo Starting backtest... > backtest_15pct.log 2>&1
c:\cursor\options\niftyopt\venv\Scripts\python.exe BACKTEST_V7_AGGRESSIVE.py >> backtest_15pct.log 2>&1
echo Exit code: %ERRORLEVEL% >> backtest_15pct.log 2>&1
echo BACKTEST_COMPLETE >> backtest_15pct.log 2>&1
