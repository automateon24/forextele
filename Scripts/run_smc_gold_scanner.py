import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import MetaTrader5 as mt5
from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import CostModel
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.fvg_retest import FVGRetestStrategy
def get_base_params(sym: str):
    from src.backtest.cost_model import CostModel
    if "GOLD" in sym or "XAU" in sym:
        return CostModel(spread_points=0.10, commission_per_lot=0.0), 0.02
    elif "SILVER" in sym or "XAG" in sym:
        return CostModel(spread_points=0.01, commission_per_lot=0.0), 0.005
    elif "JPY" in sym:
        return CostModel(spread_points=0.002, commission_per_lot=0.0), 0.05
    else:
        return CostModel(spread_points=0.00002, commission_per_lot=0.0), 0.05

def fetch_bars(symbol: str, timeframe: int, count: int):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df
def scan_smc():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return
    
    symbols = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY"]
    results = []
    
    for sym in symbols:
        df_h1 = fetch_bars(sym, mt5.TIMEFRAME_M15, 3000)
        if df_h1.empty or len(df_h1) < 200:
            continue
            
        cost_m, vol = get_base_params(sym)
        
        from src.strategy.chart_pattern_swing import ChartPatternSwingStrategy
        strategies = [
            ("SMC_ORDER_BLOCK", SMCOrderBlockStrategy(sym)),
            ("FVG_RETEST", FVGRetestStrategy(sym)),
            ("CHART_PATTERN_SWING", ChartPatternSwingStrategy(sym)),
        ]
        
        for s_name, strat in strategies:
            try:
                engine = BacktestEngine(
                    df=df_h1,
                    strategies=[strat],
                    cost_model=cost_m,
                    capital=1500.0,
                    volume=vol
                )
                res = engine.run()
                valid_trades = [t for t in engine.trades if t.get("exit_price") is not None]
                if not valid_trades:
                    continue
                    
                n_trades = len(valid_trades)
                wins = [t for t in valid_trades if t["pnl"] > 0]
                losses = [t for t in valid_trades if t["pnl"] <= 0]
                wr = (len(wins) / n_trades) * 100 if n_trades > 0 else 0
                net_pnl = sum(t["pnl"] for t in valid_trades)
                
                gross_win = sum(t["pnl"] for t in wins)
                gross_loss = abs(sum(t["pnl"] for t in losses))
                pf = gross_win / gross_loss if gross_loss > 0 else 99.0
                
                avg_win = gross_win / len(wins) if wins else 0
                avg_loss = gross_loss / len(losses) if losses else 0
                rr = avg_win / avg_loss if avg_loss > 0 else 99.0
                
                roi = (net_pnl / 1500.0) * 100
                
                peak = 1500.0
                running = 1500.0
                max_dd = 0.0
                for t in valid_trades:
                    running += t["pnl"]
                    if running > peak:
                        peak = running
                    dd = (peak - running) / peak * 100
                    if dd > max_dd:
                        max_dd = dd
                        
                results.append({
                    "symbol": sym,
                    "strategy": s_name,
                    "trades": n_trades,
                    "win_rate": round(wr, 1),
                    "net_pnl": round(net_pnl, 2),
                    "roi": round(roi, 1),
                    "rr": round(rr, 2),
                    "dd": round(max_dd, 1),
                    "profit_factor": round(pf, 2),
                    "is_profitable": net_pnl > 0
                })
            except Exception as e:
                import traceback
                print(f"Exception for {s_name} on {sym}: {e}")
                traceback.print_exc()
                continue
                
    mt5.shutdown()
    
    res_df = pd.DataFrame(results)
    if res_df.empty:
        print("No valid trades generated for any strategy.")
        return

    print("\n" + "="*120)
    print("  SUMMARY OF DISCOVERED SMC OPPORTUNITIES (Capital: $1500.0)")
    print("="*120)
    print(f"  {'Symbol':<10} {'Strategy':<30} {'Trades':<8} {'Win %':<8} {'Net PnL':<12} {'ROI %':<8} {'PF':<8} {'RR':<8} {'Max DD %':<10} {'Status'}")
    print("  " + "-"*115)

    for _, r in res_df.iterrows():
        status_str = "[PROFITABLE]" if r["net_pnl"] > 0 else "[LOSS]"
        print(f"  {r['symbol']:<10} {r['strategy']:<30} {r['trades']:<8} {r['win_rate']:>5.1f}%   ${r['net_pnl']:>9.2f}  {r['roi']:>6.1f}%  {r['profit_factor']:>5.2f}   {r['rr']:>4.2f}   {r['dd']:>6.1f}%    {status_str}")

    print("="*120)

if __name__ == "__main__":
    scan_smc()
