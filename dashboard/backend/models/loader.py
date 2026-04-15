"""Model loader: loads .joblib model files or falls back to mock mode."""

import logging
from pathlib import Path
from typing import Any

import joblib

from config import MODELS_DIR, ARRIVAL_MODELS, DEPARTURE_MODELS

logger = logging.getLogger(__name__)


class ModelStore:
    """Holds all loaded models (arrival + departure) in memory."""

    def __init__(self):
        self.arrival: dict[str, Any] = {}
        self.departure: dict[str, Any] = {}
        self.mock_mode: bool = False

    def load_all(self) -> None:
        """Load all model files.

        Only the 'classifier' key is required for real-mode inference.
        Missing calibrator / regression files are logged as warnings but do NOT
        trigger mock_mode — the Predictor handles absent optional models gracefully.
        """
        required_keys = {"classifier"}
        missing_required = []

        # Try loading arrival models
        for key, filename in ARRIVAL_MODELS.items():
            path = MODELS_DIR / filename
            if path.exists():
                self.arrival[key] = joblib.load(path)
                logger.info(f"Loaded arrival/{key}: {filename}")
            elif key in required_keys:
                missing_required.append(f"arrival/{filename}")
            else:
                logger.warning(f"Optional model not found (skipping): arrival/{filename}")

        # Try loading departure models
        for key, filename in DEPARTURE_MODELS.items():
            path = MODELS_DIR / filename
            if path.exists():
                self.departure[key] = joblib.load(path)
                logger.info(f"Loaded departure/{key}: {filename}")
            elif key in required_keys:
                missing_required.append(f"departure/{filename}")
            else:
                logger.warning(f"Optional model not found (skipping): departure/{filename}")

        if missing_required:
            self.mock_mode = True
            logger.warning(
                f"Missing {len(missing_required)} required model file(s) — running in MOCK mode. "
                f"Missing: {missing_required}"
            )
        else:
            logger.info("All required models loaded successfully.")

    def get_arrival_classifier(self) -> Any | None:
        """Get production arrival classifier (dict with 'model' key)."""
        return self.arrival.get("classifier")

    def get_departure_classifier(self) -> Any | None:
        """Get production departure classifier."""
        return self.departure.get("classifier")

    def get_arrival_calibrator(self) -> Any | None:
        return self.arrival.get("calibrator")

    def get_departure_calibrator(self) -> Any | None:
        return self.departure.get("calibrator")

    def get_arrival_quantile(self, quantile: str) -> Any | None:
        """Get arrival quantile regression model. quantile: 'q05','q10','q50','q90','q95'."""
        return self.arrival.get(f"regression_{quantile}")

    def get_departure_quantile(self, quantile: str) -> Any | None:
        return self.departure.get(f"regression_{quantile}")


# Singleton
model_store = ModelStore()
