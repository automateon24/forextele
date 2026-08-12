"""
ML Signal Filter Engine
=======================
Evaluates trading signals deterministically using trained classical ML models (RandomForest/XGBoost).
Provides evaluate() used in backtests, paper trading, and live execution.
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from src.ml.registry import ModelRegistry
from src.ml.features import FEATURE_COLS

logger = logging.getLogger(__name__)


class MLSignalFilter:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent.parent / "config" / "ml_config.json"

        self.config = {}
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                self.config = json.load(f)

        self.enabled      = self.config.get("enabled", True)
        self.threshold    = self.config.get("threshold", 0.58)
        self.prod_dir     = Path(__file__).resolve().parent.parent.parent / self.config.get("models_dir", "models/production")
        self.registry     = ModelRegistry(self.prod_dir)

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        strategy_id: str,
        features: Dict[str, float]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Evaluates signal features against production ML model.
        Returns: (allow_trade: bool, prob_win: float, event_payload: Dict)
        """
        if not self.enabled:
            return True, 1.0, {"decision": "ALLOW", "reason": "ML_DISABLED", "prob_win": 1.0}

        model = self.registry.load_model(symbol, strategy_id, timeframe)
        if model is None:
            # If no trained model exists yet, default ALLOW with neutral probability
            return True, 0.50, {"decision": "ALLOW", "reason": "NO_MODEL_FALLBACK", "prob_win": 0.50}

        X_pred = np.array([[features.get(col, 0.0) for col in FEATURE_COLS]])
        try:
            prob_win = float(model.predict_proba(X_pred)[0][1])
        except Exception as e:
            logger.error(f"Error predicting with ML model for {symbol} {strategy_id}: {e}")
            return True, 0.50, {"decision": "ALLOW", "reason": "PREDICT_ERROR", "prob_win": 0.50}

        decision = "ALLOW" if prob_win >= self.threshold else "BLOCK"
        allow    = (decision == "ALLOW")

        payload = {
            "decision":  decision,
            "prob_win":  round(prob_win, 4),
            "threshold": self.threshold,
            "model_id":  f"ml_{symbol}_{strategy_id}_{timeframe}"
        }

        return allow, prob_win, payload
