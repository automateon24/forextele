@echo off
cd c:\cursor\options\niftyopt
c:\cursor\options\niftyopt\venv\Scripts\python.exe BACKTEST_V7_AGGRESSIVE.py > backtest_2lots.log 2>&1
echo BACKTEST_COMPLETE >> backtest_2lots.log
c:\cursor\options\niftyopt\venv\Scripts\python.exe summary_safe.py >> backtest_2lots.log 2>&1
