"""One-time script: wrap model1_arrival_catboost.cbm into the joblib dict format
that the dashboard backend expects, and save as models/production_model_v9_0.joblib.

Run from the LGA/ project root:
    python scripts/wrap_arrival_model.py
"""

import pickle
from pathlib import Path

import catboost
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

CBM_PATH = MODELS_DIR / "model1_arrival_catboost.cbm"
CTX_PATH = PROCESSED_DIR / "arrival_model_context.pkl"
OUT_PATH = MODELS_DIR / "arrival_delay_classifier_v9.joblib"

# ── 1. Load the CatBoost classifier from .cbm ──────────────────────────────
print(f"Loading {CBM_PATH.name} ...")
model = catboost.CatBoostClassifier()
model.load_model(str(CBM_PATH))
feature_columns = list(model.feature_names_)
print(f"  tree_count  : {model.tree_count_}")
print(f"  features ({len(feature_columns)}): {feature_columns}")

# ── 2. Base train_medians from arrival_model_context.pkl (21 base features) ─
print(f"\nLoading {CTX_PATH.name} ...")
with open(CTX_PATH, "rb") as f:
    ctx = pickle.load(f)

base_medians: dict = dict(ctx["train_medians"])   # Series → dict
train_delay_rate: float = float(ctx["y_train"].mean())
print(f"  base features : {len(base_medians)}")
print(f"  train_delay_rate : {train_delay_rate:.4f}")

# ── 3. Compute medians for the 4 engineered features ───────────────────────
# These features are interaction terms; we use the product of their component
# medians as a sensible fallback when the raw values aren't available.

dewpoint_median = base_medians.get("origin_dewpoint", 68.0)
delay_rate_median = base_medians.get("delay_rate_1h", 0.16)
gate_rate_median = base_medians.get("gate_delay_rate", 0.242)
prev_ac_median = base_medians.get("prev_aircraft_delay", -10.0)
turnaround_median = base_medians.get("turnaround_hours", 5.52)
rolling3h_median = base_medians.get("delay_rolling_3h", 1.64)

engineered_medians = {
    # Binary flag: was origin_dewpoint originally missing?
    # Default = 0 (data present), because most rows have weather data.
    "origin_dewpoint_missing": 0.0,

    # congestion × gate interaction: delay_rate_1h * gate_delay_rate
    "congestion_x_gate": delay_rate_median * gate_rate_median,

    # chain × turnaround: max(0, prev_aircraft_delay) * turnaround_hours
    # prev_aircraft_delay median is negative (early aircraft); clamp to 0.
    "chain_x_turnaround": max(0.0, prev_ac_median) * turnaround_median,

    # congestion acceleration: delay_rate_1h - delay_rolling_3h / 3
    # Approximates the rate of change in congestion over the past hour.
    "congestion_accel": delay_rate_median - rolling3h_median / 3.0,
}
print(f"\nEngineered feature medians:")
for k, v in engineered_medians.items():
    print(f"  {k}: {v:.6f}")

train_medians = {**base_medians, **engineered_medians}

# Sanity-check: every feature the model expects has a median entry
missing_medians = [f for f in feature_columns if f not in train_medians]
if missing_medians:
    print(f"\nWARNING: no median for features {missing_medians} — defaulting to 0.0")
    for f in missing_medians:
        train_medians[f] = 0.0

# ── 4. Pack into the dict format the backend expects ───────────────────────
wrapped = {
    "model": model,
    "model_type": "CatBoost",
    "auc": 0.8083,              # from model1_config.json
    "optimal_threshold": 0.46,  # from model1_config.json
    "feature_columns": feature_columns,
    "train_medians": train_medians,
    "train_delay_rate": train_delay_rate,
    "version": "v9_0",
}

# ── 5. Save ─────────────────────────────────────────────────────────────────
print(f"\nSaving → {OUT_PATH} ...")
joblib.dump(wrapped, OUT_PATH)
print("Done.")

# ── 6. Quick round-trip check ───────────────────────────────────────────────
loaded = joblib.load(OUT_PATH)
assert loaded["model_type"] == "CatBoost"
assert loaded["feature_columns"] == feature_columns
assert len(loaded["train_medians"]) == len(feature_columns)
print(f"Round-trip OK. Packed {len(loaded['train_medians'])} medians, "
      f"{len(loaded['feature_columns'])} feature columns.")
