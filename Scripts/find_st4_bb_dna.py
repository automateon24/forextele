import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from src.backtest.cost_model import CostModel
from src.common.indicators import calculate_bollinger_bands, calculate_atr

def get_base_params(sym: str):
    if "GOLD" in sym or "XAU" in sym:
        return CostModel(spread_points=0.10, commission_per_lot=0.0), 0.02, 1.00
    elif "SILVER" in sym or "XAG" in sym:
        return CostModel(spread_points=0.01, commission_per_lot=0.0), 0.005, 0.10
    elif "JPY" in sym:
        return CostModel(spread_points=0.002, commission_per_lot=0.0), 0.05, 0.05
    else:
        return CostModel(spread_points=0.00002, commission_per_lot=0.0), 0.05, 0.0005

def fetch_bars(symbol: str, timeframe: int, count: int):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def simulate_trades(df, cost_model, volume, signal_col, tp_col, sl_col):
    trades = []
    in_trade = False
    entry_price = 0
    trade_side = ""
    tp = 0
    sl = 0
    
    for i in range(1, len(df)):
        if not in_trade:
            if df[signal_col].iloc[i-1] == 1:
                in_trade = True
                trade_side = "BUY"
                entry_price = df['open'].iloc[i] + cost_model.spread_points
                tp = df[tp_col].iloc[i-1]
                sl = df[sl_col].iloc[i-1]
            elif df[signal_col].iloc[i-1] == -1:
                in_trade = True
                trade_side = "SELL"
                entry_price = df['open'].iloc[i] - cost_model.spread_points
                tp = df[tp_col].iloc[i-1]
                sl = df[sl_col].iloc[i-1]
        else:
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            close = df['close'].iloc[i]
            
            pnl = 0
            exit_price = 0
            closed = False
            
            if trade_side == "BUY":
                if low <= sl:
                    exit_price = sl
                    closed = True
                elif high >= tp:
                    exit_price = tp
                    closed = True
                
                if closed:
                    pnl = (exit_price - entry_price) * volume * 100000
            elif trade_side == "SELL":
                if high >= sl:
                    exit_price = sl
                    closed = True
                elif low <= tp:
                    exit_price = tp
                    closed = True
                
                if closed:
                    pnl = (entry_price - exit_price) * volume * 100000
                    
            if closed:
                trades.append(pnl)
                in_trade = False
                
    return trades

def scan_bb():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return

    symbols = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]
    timeframes = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    results = []

    for sym in symbols:
        cost_m, vol, buffer = get_base_params(sym)
        
        for tf_name, tf_code in timeframes.items():
            df = fetch_bars(sym, tf_code, 3000)
            if df.empty or len(df) < 200: continue
            
            df['upper'], df['middle'], df['lower'] = calculate_bollinger_bands(df['close'], 20, 2.0)
            df['atr'] = calculate_atr(df['high'], df['low'], df['close'], 14)
            df['bb_width'] = df['upper'] - df['lower']
            df['width_thresh'] = df['bb_width'].rolling(20).quantile(0.20)
            df['is_squeeze'] = df['bb_width'] <= df['width_thresh']
            df['was_squeezed'] = df['is_squeeze'].rolling(5).max() > 0
            
            # --- BB BASIC MR ---
            df['sig_mr'] = 0
            df['tp_mr'] = 0.0
            df['sl_mr'] = 0.0
            buy_mr_idx = (df['low'] <= df['lower'])
            sell_mr_idx = (df['high'] >= df['upper'])
            df.loc[buy_mr_idx, 'sig_mr'] = 1
            df.loc[buy_mr_idx, 'sl_mr'] = np.minimum(df['low'], df['lower']) - buffer
            df.loc[buy_mr_idx, 'tp_mr'] = df['close'] + np.abs(df['close'] - df['sl_mr']) * 1.5
            df.loc[sell_mr_idx, 'sig_mr'] = -1
            df.loc[sell_mr_idx, 'sl_mr'] = np.maximum(df['high'], df['upper']) + buffer
            df.loc[sell_mr_idx, 'tp_mr'] = df['close'] - np.abs(df['sl_mr'] - df['close']) * 1.5
            
            # --- BB SQUEEZE BREAKOUT ---
            df['sig_sq'] = 0
            df['tp_sq'] = 0.0
            df['sl_sq'] = 0.0
            buy_sq_idx = df['was_squeezed'].shift(1) & (df['close'].shift(1) <= df['upper'].shift(1)) & (df['close'] > df['upper'])
            sell_sq_idx = df['was_squeezed'].shift(1) & (df['close'].shift(1) >= df['lower'].shift(1)) & (df['close'] < df['lower'])
            df.loc[buy_sq_idx, 'sig_sq'] = 1
            df.loc[buy_sq_idx, 'sl_sq'] = df['middle'] - buffer
            df.loc[buy_sq_idx, 'tp_sq'] = df['close'] + np.abs(df['close'] - df['sl_sq']) * 2.0
            df.loc[sell_sq_idx, 'sig_sq'] = -1
            df.loc[sell_sq_idx, 'sl_sq'] = df['middle'] + buffer
            df.loc[sell_sq_idx, 'tp_sq'] = df['close'] - np.abs(df['sl_sq'] - df['close']) * 2.0
            
            # --- BB REJECTION PINBAR ---
            df['sig_rj'] = 0
            df['tp_rj'] = 0.0
            df['sl_rj'] = 0.0
            body = np.abs(df['open'] - df['close'])
            upper_w = df['high'] - np.maximum(df['open'], df['close'])
            lower_w = np.minimum(df['open'], df['close']) - df['low']
            buy_rj_idx = (df['low'] <= df['lower']) & (df['close'] > df['lower']) & (lower_w >= body * 1.5)
            sell_rj_idx = (df['high'] >= df['upper']) & (df['close'] < df['upper']) & (upper_w >= body * 1.5)
            df.loc[buy_rj_idx, 'sig_rj'] = 1
            df.loc[buy_rj_idx, 'sl_rj'] = df['low'] - buffer
            df.loc[buy_rj_idx, 'tp_rj'] = df['close'] + np.abs(df['close'] - df['sl_rj']) * 1.5
            df.loc[sell_rj_idx, 'sig_rj'] = -1
            df.loc[sell_rj_idx, 'sl_rj'] = df['high'] + buffer
            df.loc[sell_rj_idx, 'tp_rj'] = df['close'] - np.abs(df['sl_rj'] - df['close']) * 1.5
            
            strats = [
                ("BB_BASIC_MR", "sig_mr", "tp_mr", "sl_mr"),
                ("BB_SQUEEZE_BREAKOUT", "sig_sq", "tp_sq", "sl_sq"),
                ("BB_REJECTION_PINBAR", "sig_rj", "tp_rj", "sl_rj"),
            ]
            
            for s_name, sig_col, tp_col, sl_col in strats:
                trades = simulate_trades(df, cost_m, vol, sig_col, tp_col, sl_col)
                if not trades: continue
                n_trades = len(trades)
                wins = [t for t in trades if t > 0]
                losses = [t for t in trades if t <= 0]
                wr = len(wins) / n_trades * 100
                net_pnl = sum(trades)
                gross_win = sum(wins)
                gross_loss = abs(sum(losses))
                pf = gross_win / gross_loss if gross_loss > 0 else 99.0
                roi = (net_pnl / 1500.0) * 100
                
                peak = 1500.0; running = 1500.0; max_dd = 0.0
                for t in trades:
                    running += t
                    if running > peak: peak = running
                    dd = (peak - running) / peak * 100
                    if dd > max_dd: max_dd = dd
                
                results.append({
                    "symbol": sym, "tf": tf_name, "strategy": s_name,
                    "trades": n_trades, "win_rate": round(wr, 1),
                    "net_pnl": round(net_pnl, 2), "roi": round(roi, 1),
                    "pf": round(pf, 2), "dd": round(max_dd, 1),
                    "status": "[PROFITABLE]" if net_pnl > 0 else "[LOSS]"
                })

    mt5.shutdown()
    res_df = pd.DataFrame(results)
    if res_df.empty:
        print("No valid trades generated.")
        return
    res_df = res_df.sort_values(by=["symbol", "net_pnl"], ascending=[True, False])

    print("\n" + "="*120)
    print("  ST4 (PURE BOLLINGER BANDS) DNA DISCOVERY MATRIX (Capital: $1500.0)")
    print("="*120)
    print(f"  {'Symbol':<10} {'TF':<5} {'Strategy':<25} {'Trades':<8} {'Win %':<8} {'Net PnL':<12} {'ROI %':<8} {'PF':<6} {'Max DD %':<10} {'Status'}")
    print("  " + "-"*115)
    for _, r in res_df.iterrows():
        print(f"  {r['symbol']:<10} {r['tf']:<5} {r['strategy']:<25} {r['trades']:<8} {r['win_rate']:>5.1f}%   ${r['net_pnl']:>9.2f}  {r['roi']:>6.1f}%  {r['pf']:>5.2f}  {r['dd']:>6.1f}%    {r['status']}")
    print("="*120)

if __name__ == "__main__":
    scan_bb()
