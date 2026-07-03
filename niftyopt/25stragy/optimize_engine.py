import json
import os

def main():
    config_path = "C:\\25stragy\\config.json"
    dna_path = "C:\\25stragy\\strategy_dna.json"
    
    with open(config_path, 'r') as f:
        config = json.load(f)
        
    with open(dna_path, 'r') as f:
        dna = json.load(f)
        
    # 1. Update strategy_tuning in config.json to include max_trade_duration_mins
    if "strategy_tuning" not in config:
        config["strategy_tuning"] = {}
    config["strategy_tuning"]["max_trade_duration_mins"] = 60
    
    # Enable all 36 strategies
    all_strategies = list(dna['strategies'].keys())
    for idx_name, profile in config['index_profiles'].items():
        profile['active_strategies'] = all_strategies
        
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print("Updated config.json successfully.")
    
    # 2. Modify BACKTEST_V8_AI.py
    engine_path = "C:\\25stragy\\BACKTEST_V8_AI.py"
    with open(engine_path, 'r') as f:
        content = f.read()
        
    # Add MAX_TRADE_DURATION_MINS loader right after STRATEGY_TUNING
    old_strategy_tuning_block = """STRATEGY_TUNING = config_db.get("strategy_tuning", {})
ORB_CANDLES = STRATEGY_TUNING.get("orb_candles", 4)"""
    
    new_strategy_tuning_block = """STRATEGY_TUNING = config_db.get("strategy_tuning", {})
MAX_TRADE_DURATION_MINS = STRATEGY_TUNING.get("max_trade_duration_mins", 60)
ORB_CANDLES = STRATEGY_TUNING.get("orb_candles", 4)"""
    
    if old_strategy_tuning_block in content:
        content = content.replace(old_strategy_tuning_block, new_strategy_tuning_block)
        print("Added MAX_TRADE_DURATION_MINS loader to global variables.")
        
    # Replace execute_fixed_target_idx to support duration-based exits
    old_fixed_target_loop = """    for _, bar in remaining.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = bar['ts_ist']; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = bar['ts_ist']; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = bar['ts_ist']; break"""
            
    new_fixed_target_loop = """    mins_in_trade = 0
    for _, bar in remaining.iterrows():
        ts   = bar['ts_ist'] if hasattr(bar['ts_ist'], 'hour') else pd.Timestamp(bar['ts_ist'])
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        mins_in_trade += 1

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = bar['ts_ist']; break
        if mins_in_trade >= MAX_TRADE_DURATION_MINS:
            xp = float(bar['close']); xr = 'DURATION'; xt = bar['ts_ist']; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = bar['ts_ist']; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = bar['ts_ist']; break"""
            
    content = content.replace(old_fixed_target_loop, new_fixed_target_loop)
    print("Updated execute_fixed_target_idx with duration-based exit.")
    
    # Replace execute_tsl_idx to support duration-based exits
    old_tsl_loop = """    for _, bar in remaining.iterrows():
        ts   = _get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        thi  = max(thi, hi)

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = ts; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = ts; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = ts; break
        if thi >= ep * (1 + tsl_activate):
            floor = thi * (1 - tsl_trail)
            if lo <= floor and floor > sl:
                xp = max(floor, sl); xr = 'TSL'; xt = ts; break"""
                
    new_tsl_loop = """    mins_in_trade = 0
    for _, bar in remaining.iterrows():
        ts   = _get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        thi  = max(thi, hi)
        mins_in_trade += 1

        if hhmm >= hard_exit:
            xp = float(bar['close']); xr = 'TIME'; xt = ts; break
        if mins_in_trade >= MAX_TRADE_DURATION_MINS:
            xp = float(bar['close']); xr = 'DURATION'; xt = ts; break
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = ts; break
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = ts; break
        if thi >= ep * (1 + tsl_activate):
            floor = thi * (1 - tsl_trail)
            if lo <= floor and floor > sl:
                xp = max(floor, sl); xr = 'TSL'; xt = ts; break"""
                
    content = content.replace(old_tsl_loop, new_tsl_loop)
    print("Updated execute_tsl_idx with duration-based exit.")
    
    with open(engine_path, 'w') as f:
        f.write(content)
    print("BACKTEST_V8_AI.py updated successfully.")

if __name__ == "__main__":
    main()
