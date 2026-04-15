"""LGA Flight Delay Prediction Dashboard — FastAPI Backend.

Run with: uvicorn main:app --reload --port 8000

Set PRODUCTION_MODE=true to skip raw-data pipeline and load pre-computed
parquet files from data/production/ (fast ~3s startup, no ML models needed).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
BACKEND_DIR = Path(__file__).resolve().parent
PRODUCTION_DATA_DIR = BACKEND_DIR / "data" / "production"

# Columns the API actually reads from flight_cache — everything else is skipped
# in production to keep memory well under Render's 512 MB free-tier limit.
PRODUCTION_CACHE_COLUMNS = [
    "flight_id", "Flight", "Direction", "Airline", "Remote_Airport",
    "Gate", "Terminal", "Date", "Scheduled_Time", "Actual_Time", "Hour",
    "Registration", "Body_Type", "Runway",
    "risk_tier", "delay_probability",
    "pred_delay_q50", "pred_delay_q10", "pred_delay_q90",
    "confidence", "delay_cause",
    "Delay_Minutes", "Is_Delayed",
    "mock_origin_weather", "mock_origin_severity",
    "mock_prev_aircraft_delay", "mock_turnaround", "mock_route_delay_rate",
]

from data.faa_live import fetch_faa_live_status

if not PRODUCTION_MODE:
    # Heavy ML imports — only loaded in development mode
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

FAA_REFRESH_INTERVAL = 120  # seconds between live FAA API polls

# Global app state
app_state: dict = {
    "flight_cache": pd.DataFrame(),
    "ground_stops": pd.DataFrame(),
    "ground_delays": pd.DataFrame(),
    "hourly_weather": pd.DataFrame(),
    "faa_live": None,       # live FAA data dict or None (→ fallback to CSV)
    "predictor": None,      # Predictor instance (for on-demand SHAP)
    "mode": "balanced",
    "models_loaded": False,
    "mock_mode": True,
}


async def _faa_refresh_loop():
    """Background task: refresh FAA live data every FAA_REFRESH_INTERVAL seconds."""
    while True:
        await asyncio.sleep(FAA_REFRESH_INTERVAL)
        try:
            data = fetch_faa_live_status()
            if data is not None:
                app_state["faa_live"] = data
                logger.info(
                    f"FAA live refreshed: "
                    f"{len(data['ground_stops'])} ground stop(s), "
                    f"{len(data['ground_delays'])} delay program(s)"
                )
        except Exception as exc:
            logger.warning(f"FAA live refresh error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load models and prepare flight data cache."""
    logger.info("Starting LGA Dashboard backend...")

    if PRODUCTION_MODE:
        # ── Production mode: load pre-computed parquet files (fast, ~3s) ──────
        logger.info("PRODUCTION MODE: loading pre-computed parquet files...")
        import pyarrow.parquet as pq
        cache_path = PRODUCTION_DATA_DIR / "production_cache.parquet"
        # Only read columns the API actually uses — skips 20+ ML feature columns
        # and shap_factors, keeping memory well under Render's 512 MB free-tier limit.
        existing_cols = set(pq.read_schema(cache_path).names)
        cols_to_load = [c for c in PRODUCTION_CACHE_COLUMNS if c in existing_cols]
        app_state["flight_cache"] = pd.read_parquet(cache_path, columns=cols_to_load)
        app_state["hourly_weather"] = pd.read_parquet(
            PRODUCTION_DATA_DIR / "production_weather.parquet"
        )
        app_state["ground_stops"] = pd.read_parquet(
            PRODUCTION_DATA_DIR / "production_ground_stops.parquet"
        )
        app_state["ground_delays"] = pd.read_parquet(
            PRODUCTION_DATA_DIR / "production_ground_delays.parquet"
        )
        app_state["models_loaded"] = True
        app_state["mock_mode"] = False
        logger.info(
            f"Production data loaded: {len(app_state['flight_cache'])} flights cached."
        )
    else:
        # ── Development mode: full pipeline ──────────────────────────────────
        # 1. Try loading ML models
        model_store.load_all()
        app_state["models_loaded"] = not model_store.mock_mode
        app_state["mock_mode"] = model_store.mock_mode

        # 2. Load raw flight data
        logger.info("Loading raw flight data...")
        arr_raw, dep_raw = load_raw_flights()

        # 3. Clean data
        logger.info("Cleaning flight data...")
        arr_clean = clean_flight_data(arr_raw, "arrival")
        dep_clean = clean_flight_data(dep_raw, "departure")
        logger.info(f"Cleaned: {len(arr_clean)} arrivals, {len(dep_clean)} departures")

        # 3b. Enrich with real per-flight feature values from model training context
        logger.info("Loading feature lookup tables (real per-flight features)...")
        arr_lookup, dep_lookup = load_feature_lookups()
        if not arr_lookup.empty:
            arr_clean = enrich_with_lookup(arr_clean, arr_lookup)
        if not dep_lookup.empty:
            dep_clean = enrich_with_lookup(dep_clean, dep_lookup)

        # 4. Generate predictions
        if model_store.mock_mode:
            logger.info("MOCK MODE: Generating synthetic predictions...")
            arr_pred = generate_mock_predictions(arr_clean, "arrival")
            dep_pred = generate_mock_predictions(dep_clean, "departure")
        else:
            logger.info("REAL MODE: Running V9 inference...")
            try:
                predictor = Predictor(model_store)
                arr_pred = predictor.predict_arrivals(arr_clean)
                dep_pred = predictor.predict_departures(dep_clean)
                app_state["predictor"] = predictor   # store for on-demand SHAP
            except Exception as exc:
                logger.exception(f"Real inference failed, falling back to mock: {exc}")
                arr_pred = generate_mock_predictions(arr_clean, "arrival")
                dep_pred = generate_mock_predictions(dep_clean, "departure")

        # 5. Build unified cache
        app_state["flight_cache"] = build_flight_cache(arr_pred, dep_pred)

        # 6. Load FAA Ground Stops + Ground Delays + hourly weather (historical CSV)
        app_state["ground_stops"] = load_ground_stops()
        app_state["ground_delays"] = load_ground_delays()
        app_state["hourly_weather"] = load_hourly_weather()

        logger.info(
            f"Dashboard ready! {len(app_state['flight_cache'])} flights cached. "
            f"Mode: {'MOCK' if app_state['mock_mode'] else 'REAL'}"
        )

    # 7. Fetch initial FAA live data
    logger.info("Fetching FAA live operational data...")
    faa_live = fetch_faa_live_status()
    app_state["faa_live"] = faa_live
    if faa_live is not None:
        logger.info(
            f"FAA live: {len(faa_live['ground_stops'])} ground stop(s), "
            f"{len(faa_live['ground_delays'])} delay program(s) "
            f"(fetched at {faa_live['fetched_at']})"
        )
    else:
        logger.info("FAA live API unavailable — overview will use historical CSV data")

    # 8. Start background FAA refresh loop
    refresh_task = asyncio.create_task(_faa_refresh_loop())

    yield

    # Shutdown: cancel background task
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down dashboard backend.")


app = FastAPI(
    title="LGA Flight Delay Prediction Dashboard",
    version="1.0.0",
    description="Predictive intelligence layer for LGA airport operations",
    lifespan=lifespan,
)

# CORS for React frontend
_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://lga-dashboard.vercel.app",
]
if _frontend_url := os.getenv("FRONTEND_URL"):
    _cors_origins.append(_frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from api.overview import router as overview_router
from api.flights import router as flights_router
from api.config_api import router as config_router

app.include_router(overview_router, prefix="/api", tags=["Overview"])
app.include_router(flights_router, prefix="/api", tags=["Flights"])
app.include_router(config_router, prefix="/api", tags=["Config"])


@app.get("/api/health")
async def health():
    """System health check."""
    cache = app_state["flight_cache"]
    faa_live = app_state.get("faa_live")
    return {
        "status": "ok",
        "mock_mode": app_state["mock_mode"],
        "models_loaded": app_state["models_loaded"],
        "total_flights": len(cache),
        "arrivals": int((cache["Direction"] == "ARR").sum()) if not cache.empty else 0,
        "departures": int((cache["Direction"] == "DEP").sum()) if not cache.empty else 0,
        "mode": app_state["mode"],
        "available_dates": len(cache["Date"].unique()) if not cache.empty else 0,
        "faa_live_active": faa_live is not None,
        "faa_live_fetched_at": faa_live["fetched_at"] if faa_live else None,
    }
