"""
Model Registry & Version Manager
================================
Loads production models from models/production and maintains version metadata.
"""

import json
import pickle
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ModelRegistry:
    def __init__(self, production_dir: Optional[Path] = None):
        if production_dir is None:
            production_dir = Path(__file__).resolve().parent.parent.parent / "models" / "production"
        self.production_dir = Path(production_dir)
        self.production_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_models: Dict[str, Any] = {}

    def get_model_key(self, symbol: str, strategy_id: str, timeframe: str) -> str:
        return f"ml_{symbol}_{strategy_id}_{timeframe}"

    def load_model(self, symbol: str, strategy_id: str, timeframe: str) -> Optional[Any]:
        key = self.get_model_key(symbol, strategy_id, timeframe)
        if key in self._loaded_models:
            return self._loaded_models[key]

        model_file = self.production_dir / f"{key}.pkl"
        if not model_file.exists():
            # Check root models/ folder fallback
            fallback = self.production_dir.parent / f"{key}.pkl"
            if fallback.exists():
                model_file = fallback
            else:
                return None

        try:
            with open(model_file, "rb") as f:
                model = pickle.load(f)
            self._loaded_models[key] = model
            logger.info(f"Loaded production ML model: {model_file.name}")
            return model
        except Exception as e:
            logger.error(f"Failed to load model {model_file}: {e}")
            return None

    def list_production_models(self) -> Dict[str, str]:
        models = {}
        for pkl in self.production_dir.glob("*.pkl"):
            models[pkl.stem] = str(pkl)
        return models
