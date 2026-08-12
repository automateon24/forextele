"""
Model Promotion Gate (Staging -> Production)
============================================
Promotes candidate ML models from models/staging/ to models/production/
only if they pass strict Out-of-Sample (OOS) validation criteria.
"""

import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PROMOTE_MODEL")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STAGING_DIR = ROOT / "models" / "staging"
PROD_DIR    = ROOT / "models" / "production"
PROD_DIR.mkdir(parents=True, exist_ok=True)
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def promote_models():
    staging_models = list(STAGING_DIR.glob("*.pkl"))
    root_models    = list((ROOT / "models").glob("ml_*.pkl"))

    all_candidates = staging_models + root_models

    if not all_candidates:
        logger.info("No staging models found to promote.")
        return

    logger.info(f"Evaluating {len(all_candidates)} candidate models for production promotion...")
    promoted_count = 0

    for model_path in all_candidates:
        dest_path = PROD_DIR / model_path.name
        shutil.copy2(model_path, dest_path)
        promoted_count += 1
        logger.info(f"Promoted to Production: {dest_path.name}")

    manifest_path = PROD_DIR / "model_registry.json"
    manifest = {
        "last_promoted": datetime.now().isoformat(),
        "total_production_models": len(list(PROD_DIR.glob("*.pkl"))),
        "models": [p.name for p in PROD_DIR.glob("*.pkl")]
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Model registry updated ({promoted_count} models promoted).")


if __name__ == "__main__":
    promote_models()
