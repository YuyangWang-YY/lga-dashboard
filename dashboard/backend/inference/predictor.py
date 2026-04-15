"""Real V9.0 inference orchestration.

Phase 1: arrival classifier only.
- Builds 25-column feature matrix via ArrivalFeatureBuilder.
- Calls production_model.predict_proba → IsotonicRegression calibrator → risk_tier.
- Fills the rest of the dashboard's expected columns with mock values
  (will be replaced in Phases 2-5).

Track A: Real SHAP — lazy per-flight explanation, cached in memory.
Track B: Real operational context — extracted from feature matrix.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from data.processor import generate_mock_predictions, assign_risk_tier
from config import (
    ARRIVAL_RISK_TIERS,
    DEPARTURE_RISK_TIERS,
    SHAP_LABELS,
    SHAP_LEVEL_THRESHOLDS,
)

from .feature_builder import ArrivalFeatureBuilder, DepartureFeatureBuilder

logger = logging.getLogger(__name__)


# ── Delay cause helpers ─────────────────────────────────────────────────────

def _compute_delay_cause(X: pd.DataFrame) -> np.ndarray:
    """Assign a primary delay cause category per flight from real feature values.

    Priority order (highest wins):
      1. weather  — significant weather impact at origin/dest or LGA (wx_impact >= 2.0)
      2. aircraft — inbound/prev-aircraft delay > 20 min (chain effect)
      3. cascade  — recent LGA delay rate > 30 % (airport-wide backlog)
      4. route    — everything else (airline/route/schedule risk)
    """
    # Weather: max of origin, dest, and LGA wx_impact (0-10 scale)
    wx_cols = ["origin_wx_impact", "dest_wx_impact", "lga_wx_impact"]
    wx = pd.Series(0.0, index=X.index)
    for col in wx_cols:
        if col in X.columns:
            wx = wx.combine(X[col].fillna(0.0), max)

    # Aircraft chain: prev_aircraft_delay (arrivals) or prev_inbound_delay (departures)
    prev_col = "prev_inbound_delay" if "prev_inbound_delay" in X.columns else "prev_aircraft_delay"
    prev = X[prev_col].fillna(-10.0) if prev_col in X.columns else pd.Series(-10.0, index=X.index)

    # Cascade: recent LGA delay rate
    cascade = X["delay_rate_1h"].fillna(0.0) if "delay_rate_1h" in X.columns else pd.Series(0.0, index=X.index)

    causes = np.where(
        wx >= 2.0, "weather",
        np.where(
            prev > 20.0, "aircraft",
            np.where(
                cascade > 0.30, "cascade",
                "route"
            )
        )
    )
    return causes


# ── Weather helpers (Track B) ───────────────────────────────────────────────

def _build_weather_strings(X: pd.DataFrame, prefix: str) -> tuple[list[str], list[str]]:
    """Build (weather_description, severity) lists from feature matrix columns.

    Uses {prefix}_wx_impact (0-10 scale) and {prefix}_dewpoint (°F) if available.
    Falls back to generic strings when columns are absent.
    """
    # wx_impact: 0 = no weather, 10 = severe (from WeatherImpactScores)
    wx_col = f"{prefix}_wx_impact"
    wx = X[wx_col].fillna(0.0) if wx_col in X.columns else pd.Series(0.0, index=X.index)

    # dewpoint in °F
    dp_col = f"{prefix}_dewpoint"
    dp = X[dp_col].fillna(65.0) if dp_col in X.columns else pd.Series(65.0, index=X.index)

    descs, sevs = [], []
    for i in range(len(X)):
        w = float(wx.iloc[i])
        d = float(dp.iloc[i])

        # Condition from wx_impact (0-10 scale)
        if w >= 7.0:
            cond, sev = "Significant weather impact", "severe"
        elif w >= 3.5:
            cond, sev = "Moderate weather activity", "moderate"
        elif w >= 1.0:
            cond, sev = "Minor weather activity", "moderate"
        else:
            cond, sev = "Clear conditions", "clear"

        # Humidity from dewpoint (°F): >=70 humid, 55-70 moderate, <55 dry
        if d >= 70:
            hum = "Humid"
        elif d >= 55:
            hum = "Moderate humidity"
        else:
            hum = "Dry"

        descs.append(f"{cond}, {hum} (DP {d:.0f}°F)")
        sevs.append(sev)

    return descs, sevs


# ── Main Predictor class ─────────────────────────────────────────────────────

class Predictor:
    """Holds loaded models + feature builders. One instance per backend lifespan."""

    def __init__(self, model_store):
        self.model_store = model_store

        arr_dict = model_store.arrival.get("classifier")
        if arr_dict is None:
            raise RuntimeError("Arrival classifier not loaded — cannot init Predictor")

        self.arr_model_dict = arr_dict
        self.arr_model = arr_dict["model"]            # CatBoostClassifier
        self.arr_calibrator = model_store.arrival.get("calibrator")  # IsotonicRegression
        self.arr_feature_builder = ArrivalFeatureBuilder(arr_dict)

        # Phase 2: load arrival quantile regressors.
        self.arr_quantile_models: dict[str, object] = {}
        for q in ("q05", "q10", "q50", "q90", "q95"):
            entry = model_store.arrival.get(f"regression_{q}")
            if entry is not None:
                self.arr_quantile_models[q] = entry["model"] if isinstance(entry, dict) else entry

        # Phase 3: departure classifier + calibrator + quantile regressors.
        dep_dict = model_store.departure.get("classifier")
        if dep_dict is None:
            self.dep_model_dict = None
            self.dep_model = None
            self.dep_calibrator = None
            self.dep_feature_builder = None
            self.dep_quantile_models: dict[str, object] = {}
            logger.warning("Departure classifier not loaded — dep predictions will fall back to mock")
        else:
            self.dep_model_dict = dep_dict
            self.dep_model = dep_dict["model"]
            self.dep_calibrator = model_store.departure.get("calibrator")
            self.dep_feature_builder = DepartureFeatureBuilder(dep_dict)
            self.dep_quantile_models = {}
            for q in ("q05", "q10", "q50", "q90", "q95"):
                entry = model_store.departure.get(f"regression_{q}")
                if entry is not None:
                    self.dep_quantile_models[q] = entry["model"] if isinstance(entry, dict) else entry

        # ── Track A: SHAP state ────────────────────────────────────────────
        # Explainers are initialised lazily on first explain_flight() call.
        self._shap_arr_explainer = None
        self._shap_dep_explainer = None
        self._shap_cache: dict[str, list] = {}

        # Feature matrices stored at predict time, keyed by flight_id position.
        self._arr_feature_matrix: pd.DataFrame | None = None
        self._arr_fid_to_pos: dict[str, int] = {}
        self._dep_feature_matrix: pd.DataFrame | None = None
        self._dep_fid_to_pos: dict[str, int] = {}

        logger.info(
            f"Predictor initialized: arrival v9 ready "
            f"(features={len(self.arr_feature_builder.feature_columns)}, "
            f"AUC={arr_dict.get('auc', 0):.4f}, "
            f"threshold={arr_dict.get('optimal_threshold', 0.42):.3f}, "
            f"quantile_models={list(self.arr_quantile_models.keys())})"
        )
        if self.dep_model_dict is not None:
            logger.info(
                f"Predictor initialized: departure v9 ready "
                f"(features={len(self.dep_feature_builder.feature_columns)}, "
                f"AUC={dep_dict.get('auc', 0):.4f}, "
                f"threshold={dep_dict.get('optimal_threshold', 0.59):.3f}, "
                f"quantile_models={list(self.dep_quantile_models.keys())} [v8])"
            )

    # ── Track A: SHAP explanation ────────────────────────────────────────────

    def explain_flight(self, flight_id: str, direction: str) -> list[dict]:
        """Compute (or return cached) real SHAP values for a single flight.

        Returns a list of ShapFactor-compatible dicts sorted by |value| desc.
        Returns [] on any failure (caller falls back to stored mock factors).
        """
        if flight_id in self._shap_cache:
            return self._shap_cache[flight_id]

        is_arr    = direction.upper() == "ARR"
        fm        = self._arr_feature_matrix if is_arr else self._dep_feature_matrix
        fid_map   = self._arr_fid_to_pos    if is_arr else self._dep_fid_to_pos
        model     = self.arr_model          if is_arr else self.dep_model
        feat_cols = (
            self.arr_feature_builder.feature_columns if is_arr
            else (self.dep_feature_builder.feature_columns if self.dep_feature_builder else [])
        )

        if fm is None or model is None or flight_id not in fid_map:
            return []

        pos   = fid_map[flight_id]
        X_row = fm.iloc[[pos]]

        try:
            import shap as _shap

            if is_arr:
                if self._shap_arr_explainer is None:
                    logger.info("Initialising arrival SHAP TreeExplainer (first call)...")
                    self._shap_arr_explainer = _shap.TreeExplainer(model)
                explainer = self._shap_arr_explainer
            else:
                if self._shap_dep_explainer is None:
                    logger.info("Initialising departure SHAP TreeExplainer (first call)...")
                    self._shap_dep_explainer = _shap.TreeExplainer(model)
                explainer = self._shap_dep_explainer

            raw  = explainer.shap_values(X_row)
            # CatBoost binary classifier: shap_values returns (1, n_features) array
            vals = np.asarray(raw).flatten()[:len(feat_cols)]

        except Exception as exc:
            logger.warning(f"SHAP computation failed for {flight_id}: {exc}")
            return []

        # Build sorted factor list (top-8; frontend shows top-5)
        pairs         = sorted(zip(feat_cols, vals), key=lambda x: abs(x[1]), reverse=True)
        major_t       = SHAP_LEVEL_THRESHOLDS.get("major", 0.05)
        contributing_t = SHAP_LEVEL_THRESHOLDS.get("contributing", 0.02)

        factors = []
        for feat, val in pairs[:8]:
            abs_v = abs(val)
            level = (
                "major"        if abs_v >= major_t else
                "contributing" if abs_v >= contributing_t else
                "minor"
            )
            factors.append({
                "feature": feat,
                "label":   SHAP_LABELS.get(feat, feat),
                "value":   round(float(val), 4),
                "level":   level,
            })

        self._shap_cache[flight_id] = factors
        return factors

    # ── Arrivals ─────────────────────────────────────────────────────────────

    def predict_arrivals(self, arr_df: pd.DataFrame) -> pd.DataFrame:
        """Run real V9 inference on the cleaned arrival flight cache."""
        if arr_df.empty:
            return arr_df

        logger.info(f"Running V9 arrival inference on {len(arr_df)} flights...")

        # Step 1: feature matrix
        X = self.arr_feature_builder.build(arr_df)

        # Track A: store feature matrix for on-demand SHAP
        if "flight_id" in arr_df.columns:
            self._arr_feature_matrix = X.reset_index(drop=True)
            self._arr_fid_to_pos = {
                fid: i for i, fid in enumerate(arr_df["flight_id"].values)
            }

        # Step 2: classifier predict_proba → calibrator
        raw_proba = self.arr_model.predict_proba(X)[:, 1]
        if self.arr_calibrator is not None:
            calibrated = self.arr_calibrator.predict(raw_proba)
            calibrated = np.clip(calibrated, 0.0, 1.0)
        else:
            calibrated = raw_proba

        # Step 3: assign risk tier
        risk_tiers = [
            assign_risk_tier(float(p), ARRIVAL_RISK_TIERS) for p in calibrated
        ]

        logger.info(
            f"Arrival inference done. mean_proba={calibrated.mean():.3f}, "
            f"CRITICAL={risk_tiers.count('CRITICAL')}, "
            f"HIGH={risk_tiers.count('HIGH')}, "
            f"MEDIUM={risk_tiers.count('MEDIUM')}, "
            f"LOW={risk_tiers.count('LOW')}"
        )

        # Step 4: quantile regressors
        quantile_predictions: dict[str, np.ndarray] = {}
        for q, m in self.arr_quantile_models.items():
            try:
                preds = m.predict(X)
                quantile_predictions[q] = np.clip(preds, 0, None)
            except Exception as exc:
                logger.warning(f"Arrival regression {q} failed: {exc}")

        if "q50" in quantile_predictions:
            logger.info(
                f"Arrival quantiles done. "
                f"q10_mean={quantile_predictions.get('q10', np.zeros(1)).mean():.1f}, "
                f"q50_mean={quantile_predictions['q50'].mean():.1f}, "
                f"q90_mean={quantile_predictions.get('q90', np.zeros(1)).mean():.1f}"
            )

        # Step 5: stitch real predictions into the dashboard column shape.
        result = generate_mock_predictions(arr_df, "arrival")
        result["delay_probability"] = calibrated.astype(float)
        result["risk_tier"] = risk_tiers

        if "q50" in quantile_predictions:
            result["pred_delay_q50"] = quantile_predictions["q50"].round().astype(int)
        if "q10" in quantile_predictions:
            result["pred_delay_q10"] = quantile_predictions["q10"].round().astype(int)
        if "q90" in quantile_predictions:
            result["pred_delay_q90"] = quantile_predictions["q90"].round().astype(int)

        result["confidence"] = "MODERATE"

        # Track B: overwrite mock operational context with real feature values
        try:
            result["mock_prev_aircraft_delay"] = (
                X["prev_aircraft_delay"].fillna(0).round().astype(int).values
            )
            result["mock_turnaround"] = X["turnaround_hours"].fillna(
                self.arr_feature_builder.train_medians.get("turnaround_hours", 2.5)
            ).values
            result["mock_route_delay_rate"] = (
                (X["airline_delay_rate"].fillna(0) * 100).round(1).values
            )
            descs, sevs = _build_weather_strings(X, "origin")
            result["mock_origin_weather"]  = descs
            result["mock_origin_severity"] = sevs
            # Real delay cause from feature thresholds
            result["delay_cause"] = _compute_delay_cause(X)
        except Exception as exc:
            logger.warning(f"Track B arrival operational context extraction failed: {exc}")

        return result

    # ── Departures ────────────────────────────────────────────────────────────

    def predict_departures(self, dep_df: pd.DataFrame) -> pd.DataFrame:
        """Run real V9 inference on the cleaned departure flight cache."""
        if dep_df.empty:
            return dep_df

        if self.dep_model is None or self.dep_feature_builder is None:
            logger.warning("Departure model not loaded — falling back to mock")
            return generate_mock_predictions(dep_df, "departure")

        logger.info(f"Running V9 departure inference on {len(dep_df)} flights...")

        # Step 1: feature matrix
        X = self.dep_feature_builder.build(dep_df)

        # Track A: store feature matrix for on-demand SHAP
        if "flight_id" in dep_df.columns:
            self._dep_feature_matrix = X.reset_index(drop=True)
            self._dep_fid_to_pos = {
                fid: i for i, fid in enumerate(dep_df["flight_id"].values)
            }

        # Step 2: classifier predict_proba → calibrator
        raw_proba = self.dep_model.predict_proba(X)[:, 1]
        if self.dep_calibrator is not None:
            calibrated = self.dep_calibrator.predict(raw_proba)
            calibrated = np.clip(calibrated, 0.0, 1.0)
        else:
            calibrated = raw_proba

        # Step 3: assign risk tier
        risk_tiers = [
            assign_risk_tier(float(p), DEPARTURE_RISK_TIERS) for p in calibrated
        ]

        logger.info(
            f"Departure inference done. mean_proba={calibrated.mean():.3f}, "
            f"CRITICAL={risk_tiers.count('CRITICAL')}, "
            f"HIGH={risk_tiers.count('HIGH')}, "
            f"MEDIUM={risk_tiers.count('MEDIUM')}, "
            f"LOW={risk_tiers.count('LOW')}"
        )

        # Step 4: quantile regressors
        quantile_predictions: dict[str, np.ndarray] = {}
        for q, m in self.dep_quantile_models.items():
            try:
                preds = m.predict(X)
                quantile_predictions[q] = np.clip(preds, 0, None)
            except Exception as exc:
                logger.warning(f"Departure regression {q} failed: {exc}")

        if "q50" in quantile_predictions:
            logger.info(
                f"Departure quantiles done. "
                f"q50_mean={quantile_predictions['q50'].mean():.1f}"
            )

        # Step 5: stitch real predictions over mock baseline
        result = generate_mock_predictions(dep_df, "departure")
        result["delay_probability"] = calibrated.astype(float)
        result["risk_tier"] = risk_tiers

        if "q50" in quantile_predictions:
            result["pred_delay_q50"] = quantile_predictions["q50"].round().astype(int)
        if "q10" in quantile_predictions:
            result["pred_delay_q10"] = quantile_predictions["q10"].round().astype(int)
        if "q90" in quantile_predictions:
            result["pred_delay_q90"] = quantile_predictions["q90"].round().astype(int)

        result["confidence"] = "MODERATE"

        # Track B: overwrite mock operational context with real feature values
        try:
            prev_col = (
                "prev_inbound_delay" if "prev_inbound_delay" in X.columns
                else "prev_aircraft_delay"
            )
            if prev_col in X.columns:
                result["mock_prev_aircraft_delay"] = (
                    X[prev_col].fillna(0).round().astype(int).values
                )
            if "turnaround_hours" in X.columns:
                result["mock_turnaround"] = X["turnaround_hours"].fillna(
                    self.dep_feature_builder.train_medians.get("turnaround_hours", 2.5)
                ).values
            dep_rate_col = (
                "dep_airline_delay_rate" if "dep_airline_delay_rate" in X.columns
                else "airline_delay_rate"
            )
            if dep_rate_col in X.columns:
                result["mock_route_delay_rate"] = (
                    (X[dep_rate_col].fillna(0) * 100).round(1).values
                )
            descs, sevs = _build_weather_strings(X, "dest")
            result["mock_origin_weather"]  = descs   # schema reuses origin_ name for both
            result["mock_origin_severity"] = sevs
            # Real delay cause from feature thresholds
            result["delay_cause"] = _compute_delay_cause(X)
        except Exception as exc:
            logger.warning(f"Track B departure operational context extraction failed: {exc}")

        return result
