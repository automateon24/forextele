import importlib
import pkgutil
from pathlib import Path

# Dynamically discover all Bollinger strategy classes in src.strategy
def load_bollinger_strategies(pairs_config):
    """Return a list of tuples (symbol, timeframe, strategy_instance, tier_label).

    pairs_config: list of dicts, each with keys:
        - symbol (str)
        - timeframe (mt5 constant, e.g. mt5.TIMEFRAME_M15)
        - tf_name (str)
        - tier (str)
    The function will import every class in src.strategy whose name contains
    'Bollinger' and instantiate it with the symbol.
    """
    import src.strategy  # ensure the package is loaded
    loader = pkgutil.iter_modules(src.strategy.__path__)
    bollinger_classes = []
    for _, module_name, _ in loader:
        module = importlib.import_module(f"src.strategy.{module_name}")
        for attr_name in dir(module):
            if "Bollinger" in attr_name:
                cls = getattr(module, attr_name)
                if isinstance(cls, type):
                    bollinger_classes.append(cls)
    # Build whitelist
    whitelist = []
    for cfg in pairs_config:
        symbol = cfg["symbol"]
        tf_code = cfg["timeframe"]
        tf_name = cfg["tf_name"]
        tier = cfg["tier"]
        for strat_cls in bollinger_classes:
            try:
                instance = strat_cls(symbol)
                whitelist.append((symbol, tf_code, tf_name, instance, tier))
            except Exception:
                # Some strategies may require extra args; skip them
                continue
    return whitelist

if __name__ == "__main__":
    # Example usage – prints the discovered strategies for demo purposes
    example_pairs = [
        {"symbol": "GOLD", "timeframe": 15, "tf_name": "M15", "tier": "ST4"},
    ]
    wl = load_bollinger_strategies(example_pairs)
    for entry in wl:
        print(entry[3].strategy_id, entry[0], entry[2])
