from src.backtest.symbol_specs import get_symbol_spec, calculate_pnl

def run_verification():
    print("--- MANUAL PNL VERIFICATION ---")
    spec = get_symbol_spec("GOLD")
    print(f"Loaded Spec for GOLD: {spec}")
    
    # Trade 1: BUY 0.01 lots at 2300.00, exit at 2310.00 ($10 move)
    # Expected: $10 move on 1 oz (0.01 lot of 100 oz contract) = $10.00 profit.
    pnl_buy = calculate_pnl("GOLD", "BUY", 2300.00, 2310.00, 0.01, spec)
    print(f"Trade 1 (BUY 0.01, 2300 -> 2310): Calculated PnL = ${pnl_buy:.2f}")
    assert pnl_buy == 10.00, f"Expected $10.00, got {pnl_buy}"
    
    # Trade 2: SELL 0.01 lots at 2350.50, exit at 2345.25 ($5.25 move down)
    # Expected: $5.25 move on 1 oz = $5.25 profit.
    pnl_sell = calculate_pnl("GOLD", "SELL", 2350.50, 2345.25, 0.01, spec)
    print(f"Trade 2 (SELL 0.01, 2350.50 -> 2345.25): Calculated PnL = ${pnl_sell:.2f}")
    assert pnl_sell == 5.25, f"Expected $5.25, got {pnl_sell}"
    
    print("Verification Passed: Engine output exactly matches manual broker math.")

if __name__ == "__main__":
    run_verification()
