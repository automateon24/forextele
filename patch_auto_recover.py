import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace run_live_engine function
run_live_engine_str = """def run_live_engine():
    if not init_mt5():
        return
        
    logging.info("Starting Multi-Threaded AI Strategy Executor...")
    dna_db = get_optimized_dna()
    symbols_to_trade = ["GOLD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY", "SILVER", "AUDUSD"]
    
    # Start ThreadPoolExecutor (Adding +1 for the Trailing Manager)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 1) as executor:
        # Submit the Trailing Engine Thread
        futures = {executor.submit(trailing_stop_manager, dna_db): "TRAILING_ENGINE"}
        
        # Submit the Strategy Polling Threads
        for sym in symbols_to_trade:
            futures[executor.submit(process_symbol, sym, dna_db)] = sym
            
        try:
            for future in concurrent.futures.as_completed(futures):
                sym_or_engine = futures[future]
                logging.info(f"[{sym_or_engine}] Thread Terminated.")
        except KeyboardInterrupt:
            logging.info("Shutting down live engine threads...")
            mt5.shutdown()"""

new_run_live_engine_str = """def run_live_engine():
    if not init_mt5():
        return
        
    logging.info("Starting Multi-Threaded AI Strategy Executor (CRASH RESISTANT)...")
    dna_db = get_optimized_dna()
    symbols_to_trade = ["GOLD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY", "SILVER", "AUDUSD"]
    
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_to_trade) + 1)
    
    # Initial Submission
    futures = {}
    futures[executor.submit(trailing_stop_manager, dna_db)] = "TRAILING_ENGINE"
    for sym in symbols_to_trade:
        futures[executor.submit(process_symbol, sym, dna_db)] = sym
        
    try:
        while True:
            done, not_done = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                sym_or_engine = futures.pop(future)
                try:
                    # Retrieve exception if any
                    exc = future.exception()
                    if exc:
                        logging.error(f"[{sym_or_engine}] Thread CRASHED: {exc}. Restarting...")
                    else:
                        logging.warning(f"[{sym_or_engine}] Thread Exited. Restarting...")
                except Exception as e:
                    logging.error(f"[{sym_or_engine}] Could not retrieve thread exception: {e}")
                
                # Auto-Recover / Restart the thread
                time.sleep(2) # Brief cooldown before restart
                if sym_or_engine == "TRAILING_ENGINE":
                    new_future = executor.submit(trailing_stop_manager, dna_db)
                else:
                    new_future = executor.submit(process_symbol, sym_or_engine, dna_db)
                futures[new_future] = sym_or_engine
                
    except KeyboardInterrupt:
        logging.info("Shutting down live engine threads (KeyboardInterrupt)...")
        executor.shutdown(wait=False)
        mt5.shutdown()"""

code = code.replace(run_live_engine_str, new_run_live_engine_str)

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched live_strategy_executor.py for Auto Recovery!")
