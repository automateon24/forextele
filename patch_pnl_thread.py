import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add strategy_pnl_tracker thread function
thread_str = """def strategy_pnl_tracker():
    \"\"\"
    QA Requirement: Tracking of all orders and calculating profit by strategy for the Dashboard.
    Runs periodically to query MT5 history for today and aggregate PnL by Strategy (Comment).
    \"\"\"
    logging.info("[SYSTEM] Strategy PnL Tracker Engine Online.")
    THREAD_STATUS["PNL_TRACKER"] = "Active"
    
    from datetime import datetime
    
    while True:
        try:
            account = mt5.account_info()
            if not account:
                time.sleep(5)
                continue
                
            now_utc = datetime.utcnow()
            start_of_day = datetime(now_utc.year, now_utc.month, now_utc.day)
            
            deals = mt5.history_deals_get(start_of_day, now_utc)
            if deals:
                closed_deals = [d for d in deals if d.magic == 888888 and d.entry == mt5.DEAL_ENTRY_OUT]
                
                strategy_stats = {}
                for d in closed_deals:
                    strat = d.comment
                    if not strat: strat = "UNKNOWN"
                    
                    if strat not in strategy_stats:
                        strategy_stats[strat] = {"trades": 0, "wins": 0, "pnl": 0.0}
                        
                    strategy_stats[strat]["trades"] += 1
                    strategy_stats[strat]["pnl"] += float(d.profit)
                    if d.profit > 0:
                        strategy_stats[strat]["wins"] += 1
                
                # Format for dashboard
                dashboard_data = {}
                for strat, stats in strategy_stats.items():
                    win_rate = f"{(stats['wins'] / stats['trades']):.1%}" if stats['trades'] > 0 else "0.0%"
                    dashboard_data[strat] = {
                        "trades": stats["trades"],
                        "win_rate": win_rate,
                        "pnl": stats["pnl"]
                    }
                
                try:
                    with open(BASE_DIR / "strategy_pnl_today.json", "w") as f:
                        json.dump(dashboard_data, f)
                except Exception as e:
                    pass
            
            time.sleep(10) # Update every 10 seconds
        except Exception as e:
            THREAD_STATUS["PNL_TRACKER"] = f"Error: {e}"
            time.sleep(5)
"""

# Insert right before run_live_engine
run_live_idx = code.find("def run_live_engine():")
code = code[:run_live_idx] + thread_str + "\n" + code[run_live_idx:]

# Update run_live_engine to launch it
run_live_replace = """    futures = {}
    futures[executor.submit(trailing_stop_manager, dna_db)] = "TRAILING_ENGINE"
    futures[executor.submit(strategy_pnl_tracker)] = "PNL_TRACKER\""""

code = code.replace("    futures = {}\n    futures[executor.submit(trailing_stop_manager, dna_db)] = \"TRAILING_ENGINE\"", run_live_replace)

# Update run_live_engine inside auto-recover to restart it
recover_replace = """                if sym_or_engine == "TRAILING_ENGINE":
                    new_future = executor.submit(trailing_stop_manager, dna_db)
                elif sym_or_engine == "PNL_TRACKER":
                    new_future = executor.submit(strategy_pnl_tracker)
                else:
                    new_future = executor.submit(process_symbol, sym_or_engine, dna_db)"""
code = code.replace("""                if sym_or_engine == "TRAILING_ENGINE":
                    new_future = executor.submit(trailing_stop_manager, dna_db)
                else:
                    new_future = executor.submit(process_symbol, sym_or_engine, dna_db)""", recover_replace)
                    
# Update ThreadPoolExecutor size
code = code.replace("executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 1)", "executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 2)")

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched live_strategy_executor.py for Strategy PnL tracking!")
