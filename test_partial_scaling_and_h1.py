from smc_confluence_engine import SMCConfluenceEngine
from swarm_position_manager import SwarmPositionManager

def test_h1_trend_confluence():
    print("=" * 75)
    print("TEST 1: H1 TREND CONFLUENCE ENGINE")
    print("=" * 75)

    smc = SMCConfluenceEngine()
    symbols = ["USDCHF", "GBPJPY", "GOLD", "EURUSD", "GBPUSD"]

    for sym in symbols:
        h1_trend = smc.get_h1_trend_structure(sym)
        smc_buy = smc.get_smc_analysis(sym, "BUY")
        smc_sell = smc.get_smc_analysis(sym, "SELL")

        print(f"[{sym}] H1 Trend: {h1_trend:<8} | BUY SMC Score: {smc_buy['smc_confluence_score']} (H1 Aligned: {smc_buy['h1_aligned']}) | SELL SMC Score: {smc_sell['smc_confluence_score']} (H1 Aligned: {smc_sell['h1_aligned']})")

def test_partial_scale_out_math():
    print("\n" + "=" * 75)
    print("TEST 2: PARTIAL SCALING LOT MATH")
    print("=" * 75)

    sample_lots = [0.05, 0.03, 0.02, 0.01]
    step = 0.01

    for vol in sample_lots:
        if vol >= 0.02:
            close_vol = round((vol / 2.0) / step) * step
            remain_vol = round((vol - close_vol), 2)
            print(f"Original Volume: {vol:.2f} lots -> Scale-Out Close at TP1: {close_vol:.2f} lots | Remaining Volume with Breakeven SL: {remain_vol:.2f} lots")
        else:
            print(f"Original Volume: {vol:.2f} lots -> Single micro-lot (no scale-out possible, SL moved to Breakeven)")

if __name__ == "__main__":
    test_h1_trend_confluence()
    test_partial_scale_out_math()
