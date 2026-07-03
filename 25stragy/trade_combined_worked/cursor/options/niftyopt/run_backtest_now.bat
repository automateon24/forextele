@echo off
cd /d c:\cursor\options\niftyopt
echo [%DATE% %TIME%] Starting... > backtest_run.log 2>&1
c:\cursor\options\niftyopt\venv\Scripts\python.exe -u BACKTEST_V7_AGGRESSIVE.py >> backtest_run.log 2>&1
echo [%DATE% %TIME%] Exit: %ERRORLEVEL% >> backtest_run.log 2>&1
echo [%DATE% %TIME%] Done >> backtest_run.log 2>&1
