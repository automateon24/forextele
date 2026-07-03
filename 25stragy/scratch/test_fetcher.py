import sys
import os
import time

sys.path.insert(0, r"C:\cursor\options\niftyopt")
sys.path.insert(0, r"C:\cursor\options\niftyopt\united_Indian_market1.0")

from global_data_fetcher import get_global_data_fetcher

def test_fetcher():
    print("Initializing GlobalDataFetcher...")
    fetcher = get_global_data_fetcher()
    print("Performing warmup (seeding all 5 indices)...")
    fetcher.perform_data_warmup()
    
    print("Warmup complete. Starting background fetcher threads...")
    fetcher.start()
    
    # Wait and check
    for _ in range(5):
        time.sleep(2)
        print("\n--- Current Index States ---")
        for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
            data = fetcher.get_market_data(idx)
            print(f"{idx}: Spot={data.spot}, PCR={data.pcr:.2f}, Regime={data.regime}, ATM={data.atm_strike}, ClosesCount={len(data.closes)}")
            
    print("Stopping fetcher...")
    fetcher.stop()
    print("Test complete.")

if __name__ == "__main__":
    test_fetcher()
