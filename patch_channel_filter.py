import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the load_channel_map function
load_map_find = """def load_channel_map() -> dict:
    mapping = {}
    def _read(p: Path):
        if not p.exists(): return
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        mapping[parts[0].strip()] = parts[1].strip()
    _read(CHANNELS_FILE_1)
    _read(CHANNELS_FILE_2)
    return mapping"""

load_map_replace = """def load_channel_map() -> dict:
    import unicodedata
    mapping = {}
    
    # Target keywords from telegram_signal_engine.py
    FOREX_GOLD_VIPS = [
        "scalping gold", "goldsnipers11", "sureshot fx", "sureshot gold", 
        "gold trade signals", "easy forex", "gold trader", "global gold insight",
        "global profit club", "gold_mast78", "forexero", "forexking1132",
        "xauusd signal 99%", "josefina trader", "forex trading master",
        "gold sniper pips", "messy forex", "forex trading tips", "rasrasanforex",
        "riaogoldforex", "gold snipers", "michael gold trader", "grade profit forex",
        "forex market", "gold dreams trader", "xau profit zone", "saviour gold ea",
        "culersforex", "global profit culb", "gold scalper", "victory forex", 
        "source fx hub", "mr.david, xau/usd club", "gold fx network",
        "dubai capital fx group 3", "onyx alpha trades", "xauusd accurate signals",
        "mrgoldenway trader", "vip-mrgoldencircle", "max leverage"
    ]

    CRYPTO_VIPS = [
        "market trader crypto", "coin chief", "binance killers", "crypto world updates",
        "binance 360", "dil se trader crypto", "cryptosimplicity", "crypto radar",
        "king crypto scalp", "earlypumpdetector"
    ]
    
    all_vips = set([v.lower() for v in FOREX_GOLD_VIPS + CRYPTO_VIPS])

    def _read(p: Path):
        if not p.exists(): return
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        cid = parts[0].strip()
                        name = parts[1].strip()
                        
                        normalized_name = unicodedata.normalize('NFKC', name).lower()
                        for vip in all_vips:
                            if vip in normalized_name:
                                mapping[cid] = name
                                break
    _read(CHANNELS_FILE_1)
    _read(CHANNELS_FILE_2)
    return mapping"""
code = code.replace(load_map_find, load_map_replace)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Dashboard UI customized to filter ONLY the 50 VIP channels!")
