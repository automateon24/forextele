import json
from pathlib import Path

def adapt_to_forex():
    base_dir = Path(r"c:\anlyzeforex\forextele\25stragy")
    in_file = base_dir / "strategy_dna.json"
    out_file = base_dir / "forex_strategy_dna.json"
    
    with open(in_file, "r") as f:
        data = json.load(f)
        
    forex_strats = {}
    
    for name, params in data["strategies"].items():
        new_params = params.copy()
        
        # Convert Options direction to Spot
        if new_params.get("direction") == "CE":
            new_params["direction"] = "BUY"
        elif new_params.get("direction") == "PE":
            new_params["direction"] = "SELL"
            
        if new_params.get("direction_bias") == "CE":
            new_params["direction_bias"] = "BUY"
        elif new_params.get("direction_bias") == "PE":
            new_params["direction_bias"] = "SELL"
            
        # Strike prices are irrelevant in spot Forex
        if "strike" in new_params:
            del new_params["strike"]
            
        # Timeings: Indian market is 9:15 to 15:30. 
        # For Forex, let's just make most of them 24/5 (0000 to 2359), 
        # unless they are explicitly time-based breakouts.
        # We will keep time-based ones but expand their window to cover major sessions (800 to 2200 UTC)
        if new_params["entry_start"] > 0:
            new_params["entry_start"] = 800 # London Open UTC
        if new_params["entry_end"] < 2359:
            new_params["entry_end"] = 2200 # NY Close UTC
            
        # Rename options-specific strategies
        forex_name = name
        if name == "OPTIONS_GREEKS":
            forex_name = "SWAP_ARBITRAGE"
        elif name == "GAMMA_BLAST":
            forex_name = "PIP_BLAST"
        elif name == "PREMIUM_CRUSH":
            forex_name = "RANGE_CONTRACTION"
        elif name == "PUT_WRITER_SUPPORT":
            forex_name = "INSTITUTIONAL_SUPPORT"
        elif name == "SHORT_UNWIND":
            forex_name = "SHORT_SQUEEZE"
        elif name == "LONG_UNWIND":
            forex_name = "LONG_LIQUIDATION"
            
        forex_strats[forex_name] = new_params
        
    # Add new MUST-HAVE Forex specific strategies
    forex_strats["LONDON_BREAKOUT"] = {
        "direction": "BOTH",
        "entry_start": 800,  # London Open
        "entry_end": 1000,
        "require_vwap": True,
        "require_volume": True,
        "direction_bias": "",
        "tsl_a": 0.08,
        "tsl_t": 0.05,
        "tgt": 1.0,
        "sl": 0.3,
        "thresh": 0.85,
        "max_d": 3,
        "min_p": 50,
        "max_p": 400,
        "boost": 0.06
    }
    
    forex_strats["NY_OPEN_REVERSAL"] = {
        "direction": "BOTH",
        "entry_start": 1300, # NY Open
        "entry_end": 1500,
        "require_vwap": False,
        "require_volume": True,
        "direction_bias": "",
        "tsl_a": 0.1,
        "tsl_t": 0.08,
        "tgt": 0.8,
        "sl": 0.35,
        "thresh": 0.9,
        "max_d": 2,
        "min_p": 40,
        "max_p": 350,
        "boost": 0.08
    }
    
    forex_strats["ASIAN_RANGE_SCALP"] = {
        "direction": "BOTH",
        "entry_start": 2300, # Tokyo Open
        "entry_end": 600,
        "require_vwap": False,
        "require_volume": False,
        "direction_bias": "",
        "tsl_a": 0.04,
        "tsl_t": 0.02,
        "tgt": 0.3,
        "sl": 0.2,
        "thresh": 0.82,
        "max_d": 4,
        "min_p": 30,
        "max_p": 200,
        "boost": 0.03
    }

    data["strategies"] = forex_strats
    
    # Adapt Regime Matrix
    new_regime = {}
    for name, regimes in data["strategy_regime_matrix"].items():
        forex_name = name
        if name == "OPTIONS_GREEKS": forex_name = "SWAP_ARBITRAGE"
        elif name == "GAMMA_BLAST": forex_name = "PIP_BLAST"
        elif name == "PREMIUM_CRUSH": forex_name = "RANGE_CONTRACTION"
        elif name == "PUT_WRITER_SUPPORT": forex_name = "INSTITUTIONAL_SUPPORT"
        elif name == "SHORT_UNWIND": forex_name = "SHORT_SQUEEZE"
        elif name == "LONG_UNWIND": forex_name = "LONG_LIQUIDATION"
        new_regime[forex_name] = regimes
        
    new_regime["LONDON_BREAKOUT"] = {"TRENDING_BULL": True, "TRENDING_BEAR": True, "RANGE_BOUND": False, "HIGH_VOLATILITY": True, "NORMAL": True}
    new_regime["NY_OPEN_REVERSAL"] = {"TRENDING_BULL": False, "TRENDING_BEAR": False, "RANGE_BOUND": True, "HIGH_VOLATILITY": True, "NORMAL": True}
    new_regime["ASIAN_RANGE_SCALP"] = {"TRENDING_BULL": False, "TRENDING_BEAR": False, "RANGE_BOUND": True, "HIGH_VOLATILITY": False, "NORMAL": True}
    
    data["strategy_regime_matrix"] = new_regime
    
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully converted {len(forex_strats)} strategies to Forex and saved to {out_file}")

if __name__ == "__main__":
    adapt_to_forex()
