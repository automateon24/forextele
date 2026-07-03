@echo off
cd /d c:\cursor\options\niftyopt
echo [%TIME%] Starting backtest... > run.log 2>&1
c:\cursor\options\niftyopt\venv\Scripts\python.exe BACKTEST_V7_AGGRESSIVE.py >> run.log 2>&1
echo [%TIME%] Exit code: %ERRORLEVEL% >> run.log 2>&1
echo [%TIME%] Done >> run.log 2>&1
