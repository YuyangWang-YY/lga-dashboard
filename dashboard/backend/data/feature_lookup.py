"""Feature lookup: loads model training context to provide real per-flight feature values.

The arrival_model_context.pkl and dep_deployment_context.pkl files contain the full
feature matrices (X_train + X_test) produced by the NB03 feature-engineering notebooks.
These have real per-flight values for features that the live feature_builder cannot
recompute (e.g. prev_aircraft_delay from fleet tracking, target encodings, etc.).

Usage:
    arr_lookup, dep_lookup = load_feature_lookups()
    # Returns DataFrames indexed by flight_id with all feature columns as floats.
    # Merge into arr_clean / dep_clean before calling Predictor.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import pandas as pd

from config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

ARR_CONTEXT_FILE = PROCESSED_DATA_DIR / "arrival_model_context.pkl"
DEP_CONTEXT_FILE = PROCESSED_DATA_DIR / "dep_deployment_context.pkl"


def _make_flight_id(call_sign: pd.Series, scheduled_dt: pd.Series) -> pd.Series:
    """Replicate the dashboard's flight_id logic: CallSign_YYYYMMDDHHmm."""
    return (
        call_sign.astype(str) + "_" +
        pd.to_datetime(scheduled_dt).dt.strftime("%Y%m%d%H%M").fillna("unknown")
    )


def _load_context(path: Path, dt_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a context pkl → (feature_df indexed by flight_id, full_train_df).

    Returns (empty, empty) on any failure so the rest of the pipeline degrades
    gracefully to train_median fallback.
    """
    if not path.exists():
        logger.warning(f"Feature context file not found: {path}")
        return pd.DataFrame(), pd.DataFrame()

    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
    except Exception as exc:
        logger.warning(f"Failed to load {path.name}: {exc}")
        return pd.DataFrame(), pd.DataFrame()

    X_train = data.get("X_train")
    X_test  = data.get("X_test")
    train   = data.get("train")
    test    = data.get("test")

    if X_train is None or train is None:
        logger.warning(f"{path.name}: missing X_train or train key")
        return pd.DataFrame(), pd.DataFrame()

    # Combine train + test
    parts_x = [X_train]
    parts_id = [train]
    if X_test is not None and test is not None:
        parts_x.append(X_test)
        parts_id.append(test)

    X_all  = pd.concat(parts_x, ignore_index=True)
    id_all = pd.concat(parts_id, ignore_index=True)

    # Build flight_id join key
    if "Call Sign" not in id_all.columns or dt_col not in id_all.columns:
        logger.warning(f"{path.name}: missing 'Call Sign' or '{dt_col}' in context")
        return pd.DataFrame(), id_all

    X_all = X_all.copy()
    X_all["flight_id"] = _make_flight_id(id_all["Call Sign"], id_all[dt_col])

    # Drop duplicates on flight_id (keep first — same as dedup in load_raw_flights)
    before = len(X_all)
    X_all = X_all.drop_duplicates(subset=["flight_id"], keep="first")
    if len(X_all) < before:
        logger.info(f"{path.name}: deduped {before - len(X_all)} duplicate flight_ids")

    X_all = X_all.set_index("flight_id")

    # Ensure all feature columns are float (avoids dtype issues when merging)
    for col in X_all.columns:
        try:
            X_all[col] = X_all[col].astype(float)
        except (ValueError, TypeError):
            X_all = X_all.drop(columns=[col])

    logger.info(
        f"Loaded {path.name}: {len(X_all):,} flights × {len(X_all.columns)} features"
    )
    return X_all, id_all


def load_feature_lookups() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (arr_lookup, dep_lookup) feature DataFrames indexed by flight_id.

    Each row contains all pre-computed feature values for that flight.
    Enrich arr_clean / dep_clean by joining these before calling the Predictor.
    """
    arr_lookup, _ = _load_context(ARR_CONTEXT_FILE, "Scheduled_Arrival_Datetime")
    dep_lookup, _ = _load_context(DEP_CONTEXT_FILE, "Scheduled_Departure_Datetime")
    return arr_lookup, dep_lookup


def enrich_with_lookup(
    df: pd.DataFrame,
    lookup: pd.DataFrame,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Left-join real feature values from the lookup into df.

    Only enriches columns that are present in the lookup AND either absent from df
    or explicitly listed in feature_cols (which causes overwrite).

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned flight DataFrame (must have a 'flight_id' column).
    lookup : pd.DataFrame
        Feature lookup indexed by flight_id (from load_feature_lookups()).
    feature_cols : list[str] | None
        Columns to import from lookup. If None, imports all lookup columns
        that are not already in df (conservative; preserves computed lag features).

    Returns
    -------
    pd.DataFrame
        A copy of df with real feature columns merged in.
    """
    if lookup.empty or "flight_id" not in df.columns:
        return df

    if feature_cols is None:
        # Import all lookup columns that are currently absent from df
        feature_cols = [c for c in lookup.columns if c not in df.columns]

    if not feature_cols:
        return df

    # Only keep requested columns that actually exist in the lookup
    available = [c for c in feature_cols if c in lookup.columns]
    if not available:
        return df

    subset = lookup[available]
    df = df.copy()
    df = df.join(subset, on="flight_id", how="left", rsuffix="_lkp")

    # Resolve any _lkp suffix conflicts (prefer lookup values)
    for col in available:
        lkp_col = col + "_lkp"
        if lkp_col in df.columns:
            # Use lookup value where available, else keep original
            df[col] = df[lkp_col].combine_first(df[col])
            df = df.drop(columns=[lkp_col])

    n_matched = df[available[0]].notna().sum() if available else 0
    logger.info(
        f"Feature lookup enriched {n_matched}/{len(df)} flights "
        f"with {len(available)} real feature columns"
    )
    return df
