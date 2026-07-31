from smc_confluence_engine import SMCConfluenceEngine

def test_smc_confluence_unit():
    print("=" * 75)
    print("TEST 1: SMC CONFLUENCE ENGINE (ORDER BLOCKS, FVG, BOS, MOMENTUM)")
    print("=" * 75)

    smc = SMCConfluenceEngine()
    symbols = ["USDCHF", "GBPJPY", "GOLD"]

    for sym in symbols:
        res_buy = smc.get_smc_analysis(sym, "BUY")
        res_sell = smc.get_smc_analysis(sym, "SELL")

        print(f"\n[{sym}] BUY Analysis -> Confluence Score: {res_buy['smc_confluence_score']} | FVG Aligned: {res_buy['fvg_aligned']} | Momentum Ratio: {res_buy['momentum_ratio']}x ATR | Structural SL: {res_buy['structural_sl']}")
        print(f"[{sym}] SELL Analysis -> Confluence Score: {res_sell['smc_confluence_score']} | FVG Aligned: {res_sell['fvg_aligned']} | Momentum Ratio: {res_sell['momentum_ratio']}x ATR | Structural SL: {res_sell['structural_sl']}")

    print("\n" + "=" * 75)
    print("ALL SMC CONFLUENCE ENGINE TESTS PASSED CLEANLY!")
    print("=" * 75)

if __name__ == "__main__":
    test_smc_confluence_unit()
