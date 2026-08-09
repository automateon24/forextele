import os
import pandas as pd
from datetime import datetime

def generate_reports(trades_df: pd.DataFrame, metrics_df: pd.DataFrame, correlation_df: pd.DataFrame, base_dir: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_dir = os.path.join(base_dir, f"batch_backtest_{timestamp}")
    os.makedirs(report_dir, exist_ok=True)
    
    # CSV Outputs
    ranking_csv = os.path.join(report_dir, "ranking.csv")
    metrics_df.to_csv(ranking_csv, index=False)
    
    corr_csv = os.path.join(report_dir, "correlation.csv")
    correlation_df.to_csv(corr_csv)
    
    trades_csv = os.path.join(report_dir, "all_trades.csv")
    trades_df.to_csv(trades_csv, index=False)
    
    # Markdown Summary
    md_path = os.path.join(report_dir, "summary.md")
    with open(md_path, "w") as f:
        f.write(f"# Batch Backtest Report - {timestamp}\n\n")
        f.write("## Strategy Ranking\n")
        f.write(metrics_df.to_markdown(index=False))
        f.write("\n\n## Correlation Matrix\n")
        f.write(correlation_df.round(2).to_markdown())
        
        f.write("\n\n## Recommendations\n")
        f.write("Keep strategies with Expectancy > 0, Max Drawdown < 15%, and correlation < 0.70.\n")
        
    return md_path
