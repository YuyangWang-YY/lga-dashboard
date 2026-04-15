"""Feature builder for V9.0 production inference.

This module builds the exact 21-column feature matrix that
production_model_v9_0.joblib expects, in the exact order specified by
its `feature_columns` field.

PHASE 1 (current): real lag features (5) + real time feature (1) + train_medians fallback
for the remaining 15 features. This validates the end-to-end wiring with real
predictions for the most influential features (lag accounts for >50% of model AUC
per V9 SHAP analysis).

PHASE 2-5 (future): replace medians with real computations for aircraft continuity,
target encodings, network/route features, weather features, and FAA event features.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .column_adapter import to_notebook_schema

logger = logging.getLogger(__name__)


# Make the project's src/ importable so we can reuse src/features modules.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def _import_lag_features():
    """Import the notebook's lag feature builder lazily so missing src/ doesn't crash boot."""
    try:
        from features.lag_features import add_lag_features  # type: ignore
        return add_lag_features
    except ImportError as exc:
        logger.warning(f"Could not import features.lag_features: {exc}")
        return None


class _BaseFeatureBuilder:
    """Shared logic for arrival/departure feature builders."""

    direction: str = "arrival"  # overridden by subclass
    cascade_alias: str = "lga_dep_delay_1h"  # overridden for departure

    def __init__(self, model_dict: dict):
        self.feature_columns: list[str] = model_dict["feature_columns"]
        self.train_medians: dict[str, float] = model_dict["train_medians"]
        self.train_delay_rate: float = model_dict.get("train_delay_rate", 0.20)

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a (len(df), len(feature_columns)) feature matrix in order."""
        if df.empty:
            return pd.DataFrame(columns=self.feature_columns)

        nb = to_notebook_schema(df, self.direction)
        nb = self._add_lag_features(nb)

        feature_matrix = pd.DataFrame(index=df.index)

        for col in self.feature_columns:
            if col in nb.columns:
                series = nb[col]
                series = series.fillna(self.train_medians.get(col, 0.0))
                feature_matrix[col] = series.astype(float).values
            else:
                feature_matrix[col] = float(self.train_medians.get(col, 0.0))

        feature_matrix = feature_matrix.fillna(0.0)

        assert list(feature_matrix.columns) == self.feature_columns, (
            f"Feature column order mismatch! "
            f"got={list(feature_matrix.columns)} expected={self.feature_columns}"
        )
        return feature_matrix

    def _add_lag_features(self, nb: pd.DataFrame) -> pd.DataFrame:
        """Compute the 5 V9 lag features via src/features/lag_features.

        Aliases delay_rolling_1h → cascade_alias (lga_dep_delay_1h for arrivals,
        lga_arr_delay_1h for departures) as a Phase-1 approximation.
        Phase 5 will replace with real cross-direction queue joins.
        """
        add_lag_features = _import_lag_features()
        if add_lag_features is None:
            logger.warning(f"[{self.direction}] lag features unavailable — using train medians")
            return nb

        try:
            nb = add_lag_features(
                nb,
                delay_col="Total_Calculated_Delay",
                datetime_col="Scheduled_Arrival_Datetime",
                date_col="Date",
                terminal_col="Terminal_Clean",
                airline_col="Marketing Airline Desc",
                origin_col="Non-PA Airport",
                verbose=False,
            )
        except Exception as exc:
            logger.warning(f"[{self.direction}] add_lag_features failed: {exc}")
            return nb

        if "delay_rolling_1h" in nb.columns and self.cascade_alias not in nb.columns:
            nb[self.cascade_alias] = nb["delay_rolling_1h"]

        return nb


class ArrivalFeatureBuilder(_BaseFeatureBuilder):
    """V9 arrival feature builder (25 cols, including 4 engineered interaction features)."""
    direction = "arrival"
    cascade_alias = "lga_dep_delay_1h"

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extend base build() with the 4 engineered features before matrix construction."""
        if df.empty:
            return pd.DataFrame(columns=self.feature_columns)

        nb = self._to_notebook_with_lags(df)
        nb = self._add_engineered_features(nb)

        feature_matrix = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in nb.columns:
                series = nb[col]
                series = series.fillna(self.train_medians.get(col, 0.0))
                feature_matrix[col] = series.astype(float).values
            else:
                feature_matrix[col] = float(self.train_medians.get(col, 0.0))

        feature_matrix = feature_matrix.fillna(0.0)

        assert list(feature_matrix.columns) == self.feature_columns, (
            f"Feature column order mismatch! "
            f"got={list(feature_matrix.columns)} expected={self.feature_columns}"
        )
        return feature_matrix

    def _to_notebook_with_lags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Schema translate + lag features (reuses base class helpers)."""
        nb = to_notebook_schema(df, self.direction)
        nb = self._add_lag_features(nb)
        return nb

    def _add_engineered_features(self, nb: pd.DataFrame) -> pd.DataFrame:
        """Compute the 4 interaction/derived features the arrival classifier was trained on."""

        # 1. origin_dewpoint_missing: 1 if origin_dewpoint was NaN before fill, else 0.
        #    We detect it by checking whether the value equals the train median (proxy for fill).
        if "origin_dewpoint" in nb.columns:
            dewpoint_median = self.train_medians.get("origin_dewpoint", 68.0)
            nb["origin_dewpoint_missing"] = (
                nb["origin_dewpoint"].isna() |
                (nb["origin_dewpoint"] == dewpoint_median)
            ).astype(float)
        else:
            nb["origin_dewpoint_missing"] = self.train_medians.get("origin_dewpoint_missing", 0.0)

        # 2. congestion_x_gate: delay_rate_1h × gate_delay_rate
        dr = nb.get("delay_rate_1h", pd.Series(
            self.train_medians.get("delay_rate_1h", 0.16), index=nb.index))
        gr = nb.get("gate_delay_rate", pd.Series(
            self.train_medians.get("gate_delay_rate", 0.242), index=nb.index))
        nb["congestion_x_gate"] = (
            dr.fillna(self.train_medians.get("delay_rate_1h", 0.16)) *
            gr.fillna(self.train_medians.get("gate_delay_rate", 0.242))
        )

        # 3. chain_x_turnaround: max(0, prev_aircraft_delay) × turnaround_hours
        pa = nb.get("prev_aircraft_delay", pd.Series(
            self.train_medians.get("prev_aircraft_delay", -10.0), index=nb.index))
        th = nb.get("turnaround_hours", pd.Series(
            self.train_medians.get("turnaround_hours", 5.52), index=nb.index))
        nb["chain_x_turnaround"] = (
            pa.fillna(self.train_medians.get("prev_aircraft_delay", -10.0)).clip(lower=0.0) *
            th.fillna(self.train_medians.get("turnaround_hours", 5.52))
        )

        # 4. congestion_accel: delay_rate_1h − delay_rolling_3h / 3
        #    Approximates how congestion is accelerating vs. its 3-hour baseline.
        r3h = nb.get("delay_rolling_3h", pd.Series(
            self.train_medians.get("delay_rolling_3h", 1.64), index=nb.index))
        nb["congestion_accel"] = (
            dr.fillna(self.train_medians.get("delay_rate_1h", 0.16)) -
            r3h.fillna(self.train_medians.get("delay_rolling_3h", 1.64)) / 3.0
        )

        return nb


class DepartureFeatureBuilder(_BaseFeatureBuilder):
    """V9 departure feature builder (23 cols)."""
    direction = "departure"
    cascade_alias = "lga_arr_delay_1h"
