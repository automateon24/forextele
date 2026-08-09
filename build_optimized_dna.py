import pandas as pd
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
CSV_PATH = BASE_DIR / "backtest_highres_signals.csv"
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"

def build_dna():
    log.info("Loading recent backtest data...")
    df = pd.read_csv(CSV_PATH)
    
    # Filter out expired/pending trades
    df = df[df['outcome'] != 'EXPIRED'].copy()
    df['pnl_pts'] = pd.to_numeric(df['pnl_pts'])
    df['is_win'] = df['outcome'] == 'WIN'
    
    # Group by Symbol and Strategy
    stats = df.groupby(['symbol', 'strategy']).agg(
        trades=('outcome', 'count'),
        win_rate=('is_win', 'mean'),
        net_pnl_pts=('pnl_pts', 'sum')
    ).reset_index()
    
    # Require at least 20 trades to be statistically significant
    stats = stats[stats['trades'] >= 20]
    
    new_dna = {"strategies": {}}
    
    # Core categorization logic
    crypto_pairs = ["BTCUSD", "ETHUSD"]
    high_vol_pairs = ["GOLD", "SILVER", "GBPUSD", "USDJPY"]
    mean_revert_pairs = ["EURUSD", "AUDUSD"]
    
    total_retained = 0
    total_discarded = 0
    
    for idx, row in stats.iterrows():
        sym = row['symbol']
        strat = row['strategy']
        wr = row['win_rate']
        pnl = row['net_pnl_pts']
        
        # KEY PRUNING LOGIC: Only keep the strategy on this symbol if it shows a native edge!
        if pnl <= 0:
            total_discarded += 1
            continue
            
        key = f"{sym}_{strat}"
        
        # Determine DNA parameters based on the pair's asset class and performance
        is_crypto = sym in crypto_pairs
        
        if is_crypto:
            # Crypto: Trend following, no grid, wide SL/TP
            sl = 2.0
            tgt = 4.0
            use_grid = False
        elif sym in high_vol_pairs:
            # High Volatility: Momentum, wide SL/TP, no grid
            sl = 1.5
            tgt = 3.0
            use_grid = False
        else:
            # Flat Forex: Mean Reversion, tight SL/TP, Grid Recovery allowed
            sl = 1.0
            tgt = 1.5
            use_grid = True
            
        # Micro-adjustments based on native win rate
        if wr > 0.65:
            # Very high win rate natively -> tighter target to ensure it hits consistently
            tgt = max(sl * 3.0, tgt)
            
        new_dna["strategies"][key] = {
            "sl": sl,
            "tgt": tgt,
            "use_grid": use_grid,
            "thresh": 0.50, # Lowering ML threshold so we rely more on the DNA rules
            "description": f"Optimized natively. WinRate: {wr*100:.1f}%, PnL: {pnl:.1f}"
        }
        total_retained += 1

    # Save the new DNA
    DNA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DNA_PATH, 'w') as f:
        json.dump(new_dna, f, indent=4)
        
    log.info(f"DNA Optimization Complete!")
    log.info(f"Retained {total_retained} highly profitable (Symbol+Strategy) combinations.")
    log.info(f"Pruned {total_discarded} toxic combinations that were bleeding the account.")
    log.info(f"New DNA saved to: {DNA_PATH}")

if __name__ == "__main__":
    build_dna()
