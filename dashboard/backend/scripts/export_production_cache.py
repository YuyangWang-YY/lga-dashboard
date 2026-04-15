"""Export pre-computed flight cache and auxiliary data to parquet.

Run once locally while the full dataset is available:
    cd dashboard/backend
    python scripts/export_production_cache.py

Outputs (written to dashboard/backend/data/production/):
    production_cache.parquet     – full flight_cache with ML predictions
    production_weather.parquet   – processed hourly LGA weather
    production_ground_stops.parquet
    production_ground_delays.parquet
"""

import sys
import logging
from pathlib import Path

# Ensure backend root is on sys.path so we can import backend modules
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd

from models.loader import model_store
from data.processor import (
    load_raw_flights,
    load_ground_stops,
    load_ground_delays,
    load_hourly_weather,
    clean_flight_data,
    generate_mock_predictions,
    build_flight_cache,
)
from data.feature_lookup import load_feature_lookups, enrich_with_lookup
from inference.predictor import Predictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUT_DIR = BACKEND_DIR / "data" / "production"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {OUT_DIR}")

    # 1. Load ML models
    logger.info("Loading ML models...")
    model_store.load_all()
    if model_store.mock_mode:
        logger.warning("ML models not found — will export with MOCK predictions.")

    # 2. Load raw flight CSVs
    logger.info("Loading raw flight data...")
    arr_raw, dep_raw = load_raw_flights()

    # 3. Clean
    logger.info("Cleaning flight data...")
    arr_clean = clean_flight_data(arr_raw, "arrival")
    dep_clean = clean_flight_data(dep_raw, "departure")
    logger.info(f"Cleaned: {len(arr_clean)} arrivals, {len(dep_clean)} departures")

    # 4. Enrich with feature lookups
    logger.info("Loading feature lookup tables...")
    arr_lookup, dep_lookup = load_feature_lookups()
    if not arr_lookup.empty:
        arr_clean = enrich_with_lookup(arr_clean, arr_lookup)
    if not dep_lookup.empty:
        dep_clean = enrich_with_lookup(dep_clean, dep_lookup)

    # 5. Run inference (or mock)
    if model_store.mock_mode:
        logger.info("Generating mock predictions...")
        arr_pred = generate_mock_predictions(arr_clean, "arrival")
        dep_pred = generate_mock_predictions(dep_clean, "departure")
    else:
        logger.info("Running real ML inference...")
        predictor = Predictor(model_store)
        arr_pred = predictor.predict_arrivals(arr_clean)
        dep_pred = predictor.predict_departures(dep_clean)

    # 6. Build unified cache and export
    logger.info("Building flight cache...")
    flight_cache = build_flight_cache(arr_pred, dep_pred)

    # Normalize mixed-type object columns so pyarrow can serialize them.
    # Any column with object dtype that contains non-uniform types (e.g. int + str)
    # gets cast to plain string.
    for col in flight_cache.select_dtypes(include="object").columns:
        try:
            flight_cache[col] = flight_cache[col].astype(str)
        except Exception:
            pass  # leave column as-is if cast fails

    out_path = OUT_DIR / "production_cache.parquet"
    flight_cache.to_parquet(out_path, index=False, compression="snappy")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info(f"✓ Exported flight cache: {len(flight_cache)} rows → {out_path.name} ({size_mb:.1f} MB)")

    # 7. Load and export hourly weather
    logger.info("Loading hourly weather...")
    hourly_weather = load_hourly_weather()
    out_path = OUT_DIR / "production_weather.parquet"
    hourly_weather.to_parquet(out_path, index=False, compression="snappy")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info(f"✓ Exported weather: {len(hourly_weather)} rows → {out_path.name} ({size_mb:.1f} MB)")

    # 8. Load and export FAA ground stops
    logger.info("Loading FAA ground stops...")
    ground_stops = load_ground_stops()
    out_path = OUT_DIR / "production_ground_stops.parquet"
    ground_stops.to_parquet(out_path, index=False, compression="snappy")
    logger.info(f"✓ Exported ground stops: {len(ground_stops)} rows → {out_path.name}")

    # 9. Load and export FAA ground delays
    logger.info("Loading FAA ground delays...")
    ground_delays = load_ground_delays()
    out_path = OUT_DIR / "production_ground_delays.parquet"
    ground_delays.to_parquet(out_path, index=False, compression="snappy")
    logger.info(f"✓ Exported ground delays: {len(ground_delays)} rows → {out_path.name}")

    logger.info("Export complete. Files are ready in dashboard/backend/data/production/")
    logger.info("Next: check file sizes, then commit to git (or use Git LFS if > 100 MB).")


if __name__ == "__main__":
    main()
