import pandas as pd
import numpy as np

def analyze():
    df = pd.read_csv(r'C:\25stragy\scratch\expiry_jumps.csv')
    if df.empty:
        print("No jump data to analyze.")
        return
        
    print("="*80)
    print(f"ANALYZING OPTION SPIKES ON EXPIRY DAYS (Total Jumps Found: {len(df)})")
    print("="*80)
    
    # Categorize jumps
    df['category'] = '2x - 3x (Double)'
    df.loc[df['multiplier'] >= 3.0, 'category'] = '3x - 10x (Triple+)'
    df.loc[df['multiplier'] >= 10.0, 'category'] = '10x - 20x (Ten-bagger)'
    df.loc[df['multiplier'] >= 20.0, 'category'] = '20x - 25x (Super-bagger)'
    df.loc[df['multiplier'] >= 25.0, 'category'] = '25x+ (Monster-bagger)'
    
    cats = df['category'].value_counts()
    print("Jump Distribution:")
    for k, v in cats.items():
        print(f"  {k:<30}: {v:>3} ({100*v/len(df):.1f}%)")
        
    print("\n" + "="*80)
    print("TOP 10 LARGEST JUMPS IN THE DATASET:")
    print("="*80)
    top10 = df.sort_values('multiplier', ascending=False).head(10)
    cols = ['index', 'expiry_date', 'option_type', 'strike', 'low_price', 'high_price', 'low_time', 'high_time', 'multiplier', 'spot_change_pct', 'oi_change_pct']
    print(top10[cols].to_string(index=False))
    
    print("\n" + "="*80)
    print("AVERAGE METRICS BY JUMP CATEGORY:")
    print("="*80)
    metrics = df.groupby('category').agg({
        'low_price': 'mean',
        'high_price': 'mean',
        'spot_change_pct': 'mean',
        'oi_change_pct': 'mean',
        'iv_low': 'mean',
        'iv_high': 'mean'
    }).reindex(['2x - 3x (Double)', '3x - 10x (Triple+)', '10x - 20x (Ten-bagger)', '20x - 25x (Super-bagger)', '25x+ (Monster-bagger)'])
    print(metrics.to_string())

    print("\n" + "="*80)
    print("TIMING ANALYSIS (When do these jumps occur?):")
    print("="*80)
    # Convert time strings to hour floats
    df['low_hour'] = df['low_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60)
    df['high_hour'] = df['high_time'].apply(lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60)
    
    print("Low/Entry Time Distribution:")
    df['low_time_group'] = 'Morning (9:15 - 11:30)'
    df.loc[df['low_hour'] >= 11.5, 'low_time_group'] = 'Midday (11:30 - 13:30)'
    df.loc[df['low_hour'] >= 13.5, 'low_time_group'] = 'Afternoon (13:30 - 15:30)'
    low_times = df['low_time_group'].value_counts()
    for k, v in low_times.items():
        print(f"  {k:<30}: {v:>3} ({100*v/len(df):.1f}%)")

    print("\nPeak/Exit Time Distribution:")
    df['high_time_group'] = 'Morning (9:15 - 11:30)'
    df.loc[df['high_hour'] >= 11.5, 'high_time_group'] = 'Midday (11:30 - 13:30)'
    df.loc[df['high_hour'] >= 13.5, 'high_time_group'] = 'Afternoon (13:30 - 15:30)'
    high_times = df['high_time_group'].value_counts()
    for k, v in high_times.items():
        print(f"  {k:<30}: {v:>3} ({100*v/len(df):.1f}%)")

    print("\n" + "="*80)
    print("INDEX DISTRIBUTION:")
    print("="*80)
    idx_dist = df['index'].value_counts()
    for k, v in idx_dist.items():
        print(f"  {k:<12}: {v:>3} ({100*v/len(df):.1f}%)")

    print("\n" + "="*80)
    print("OPTION TYPE DISTRIBUTION:")
    print("="*80)
    opt_dist = df['option_type'].value_counts()
    for k, v in opt_dist.items():
        print(f"  {k:<12}: {v:>3} ({100*v/len(df):.1f}%)")

if __name__ == '__main__':
    analyze()
