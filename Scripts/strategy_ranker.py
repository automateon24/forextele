import os
import pandas as pd
import numpy as np

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
RESULTS_FILE = os.path.join(LOGS_DIR, "backtest_results.csv")

def run_ranker():
    if not os.path.exists(RESULTS_FILE):
        print(f"No backtest results found at {RESULTS_FILE}")
        return

    df = pd.read_csv(RESULTS_FILE)
    if df.empty:
        print("Backtest results file is empty.")
        return
        
    print("\n--- Strategy Performance Ranker ---")
    
    strategies = df['strategy_id'].unique()
    metrics = []
    
    # Base strategy returns (for correlation)
    # Pivot table: rows=time, cols=strategy_id, values=pnl
    # If multiple trades happen at the exact same time, we'll sum them for the correlation matrix
    try:
        pnl_series = df.groupby(['time', 'strategy_id'])['pnl'].sum().unstack(fill_value=0)
        correlation_matrix = pnl_series.corr()
    except Exception:
        correlation_matrix = pd.DataFrame()
        
    for strat in strategies:
        strat_df = df[df['strategy_id'] == strat]
        trade_count = len(strat_df)
        wins = strat_df[strat_df['pnl'] > 0]
        losses = strat_df[strat_df['pnl'] < 0]
        
        win_rate = len(wins) / trade_count if trade_count > 0 else 0
        loss_rate = len(losses) / trade_count if trade_count > 0 else 0
        
        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0
        
        expectancy = (avg_win * win_rate) + (avg_loss * loss_rate)
        
        # Max Drawdown estimation (simplified, assuming linear execution)
        cumulative_pnl = strat_df['pnl'].cumsum()
        peak = cumulative_pnl.expanding(min_periods=1).max()
        drawdown = (cumulative_pnl - peak).min()
        
        metrics.append({
            "Strategy": strat,
            "Trades": trade_count,
            "Win %": round(win_rate * 100, 2),
            "Expectancy (pts)": round(expectancy, 2),
            "Max Drawdown (pts)": round(drawdown, 2),
            "Total PnL (pts)": round(cumulative_pnl.iloc[-1] if not cumulative_pnl.empty else 0, 2)
        })
        
    metrics_df = pd.DataFrame(metrics)
    
    # Sort by Expectancy (descending) then Drawdown (ascending)
    metrics_df = metrics_df.sort_values(by=["Expectancy (pts)", "Max Drawdown (pts)"], ascending=[False, False])
    
    print("\nRanking by Expectancy:")
    print(metrics_df.to_string(index=False))
    
    if not correlation_matrix.empty:
        print("\nStrategy Correlation Matrix (PnL):")
        # Find high correlation pairs (> 0.7)
        high_corr = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                corr = correlation_matrix.iloc[i, j]
                if abs(corr) > 0.7:
                    high_corr.append((correlation_matrix.columns[i], correlation_matrix.columns[j], corr))
                    
        print(correlation_matrix.round(2))
        if high_corr:
            print("\nWARNING: High correlations detected! Consider disabling one to diversify risk:")
            for s1, s2, c in high_corr:
                print(f"  - {s1} & {s2} (r = {c:.2f})")
        else:
            print("\nExcellent! No highly correlated strategies detected.")

if __name__ == "__main__":
    run_ranker()
