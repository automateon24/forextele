import pandas as pd
import json

print("Decoding Symbol-Specific Time DNA...")

try:
    df = pd.read_csv('backtest_highres_signals.csv')
    df['win'] = (df['outcome'] == 'WIN').astype(int)
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit()

# Load existing DNA
with open('25stragy/ai_optimized_forex_dna.json', 'r') as f:
    dna_db = json.load(f)

strategies = dna_db.get("strategies", {})

for symbol in df['symbol'].unique():
    sym_df = df[df['symbol'] == symbol]
    
    # Analyze by hour
    hourly = sym_df.groupby('hour')['win'].agg(['count', 'mean']).reset_index()
    
    # We define a "Golden Hour" as one where win rate is >= 50% and has at least 5 trades
    golden_hours = []
    for _, r in hourly.iterrows():
        if r['mean'] >= 0.50 and r['count'] >= 5:
            golden_hours.append(int(r['hour']))
            
    # If no golden hours found due to strict filter, just take the top 4 hours
    if not golden_hours:
        top_hours = hourly.sort_values('mean', ascending=False).head(4)
        golden_hours = [int(h) for h in top_hours['hour'].tolist()]
        
    print(f"{symbol} Golden Hours: {golden_hours}")
    
    # Inject into DNA
    for key, dna in strategies.items():
        if key.startswith(f"{symbol}_"):
            dna['golden_hours'] = golden_hours
            dna['golden_rr'] = 3.0 # Golden zone gets 1:3 RR
            dna['fallback_rr'] = 2.0 # Non-golden zone gets 1:2 RR

# Save updated DNA
dna_db['strategies'] = strategies
with open('25stragy/ai_optimized_forex_dna.json', 'w') as f:
    json.dump(dna_db, f, indent=4)
    
print("Successfully injected Time DNA into ai_optimized_forex_dna.json!")
