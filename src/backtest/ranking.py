import pandas as pd

def calculate_metrics_and_rank(trades_df: pd.DataFrame, initial_capital: float = 1500.0):
    if trades_df.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    strategies = trades_df['strategy_id'].unique()
    metrics = []
    
    # Correlation Matrix calculation
    try:
        pnl_series = trades_df.groupby(['time', 'strategy_id'])['pnl'].sum().unstack(fill_value=0)
        correlation_matrix = pnl_series.corr()
    except Exception:
        correlation_matrix = pd.DataFrame()
        
    for strat in strategies:
        strat_df = trades_df[trades_df['strategy_id'] == strat]
        trade_count = len(strat_df)
        wins = strat_df[strat_df['pnl'] > 0]
        losses = strat_df[strat_df['pnl'] < 0]
        
        win_rate = len(wins) / trade_count if trade_count > 0 else 0
        loss_rate = len(losses) / trade_count if trade_count > 0 else 0
        
        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0
        
        net_profit = strat_df['pnl'].sum()
        return_pct = (net_profit / initial_capital) * 100
        
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1e-9 # avoid div zero
        profit_factor = gross_profit / gross_loss
        
        expectancy = (avg_win * win_rate) + (avg_loss * loss_rate)
        
        # Max Drawdown
        cumulative_pnl = strat_df['pnl'].cumsum()
        peak = cumulative_pnl.expanding(min_periods=1).max()
        drawdown_usd = (cumulative_pnl - peak).min()
        max_drawdown_pct = (abs(drawdown_usd) / initial_capital) * 100
        
        metrics.append({
            "Strategy": strat,
            "Net Profit ($)": round(net_profit, 2),
            "Return %": round(return_pct, 2),
            "Max Drawdown %": round(max_drawdown_pct, 2),
            "Trades": trade_count,
            "Win Rate %": round(win_rate * 100, 2),
            "Profit Factor": round(profit_factor, 2),
            "Expectancy ($)": round(expectancy, 2)
        })
        
    metrics_df = pd.DataFrame(metrics)
    
    # Ranking logic: Primary sort by Expectancy, secondary by Drawdown
    metrics_df = metrics_df.sort_values(by=["Expectancy ($)", "Max Drawdown %"], ascending=[False, True])
    
    return metrics_df, correlation_matrix
