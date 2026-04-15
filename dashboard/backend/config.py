"""Dashboard configuration: model paths, thresholds, SHAP label translations."""

from pathlib import Path

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # analyze/
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "LGA_Dataset"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# === Model File Names ===
ARRIVAL_MODELS = {
    "classifier":     "arrival_delay_classifier_v9.joblib",
    "regression_q50": "arrival_delay_regressor_q50_v9.joblib",
}

DEPARTURE_MODELS = {
    "classifier":     "departure_delay_classifier_v9.joblib",
    "calibrator":     "departure_prob_calibrator_v9.joblib",
    "regression_q50": "departure_delay_regressor_q50_v8.joblib",
}

# === Arrival Feature Columns (V7.0: 20 features) ===
ARRIVAL_FEATURES = [
    "delay_rate_1h",
    "terminal_delay_1h",
    "severe_delay_count_prev",
    "delay_rolling_3h",
    "lga_dep_delay_1h",
    "prev_aircraft_delay",
    "gate_delay_rate",
    "faa_delay_reason",
    "runway_delay_rate",
    "airline_delay_rate",
    "Hour",
    "Month",
    "faa_delay_severity",
    "runway_config_change",
    "origin_dewpoint",
    "origin_storm_flag",
    "origin_cloud_cover",
    "origin_historical_delay",
    "route_risk_score",
    "turnaround_hours",
]

# === Departure Feature Columns (V7.0: 21 features) ===
DEPARTURE_FEATURES = [
    "delay_rate_1h",
    "terminal_delay_1h",
    "severe_delay_count_prev",
    "delay_rolling_3h",
    "lga_arr_delay_1h",
    "prev_inbound_delay",
    "gate_delay_rate",
    "faa_delay_reason",
    "runway_delay_rate",
    "airline_delay_rate",
    "Hour",
    "Month",
    "faa_delay_severity",
    "runway_config_change",
    "dest_dewpoint",
    "dest_storm_flag",
    "dest_cloud_cover",
    "dest_historical_delay",
    "route_risk_score",
    "turnaround_hours",
    "lga_dep_delay_1h",
]

# === Operating Mode Thresholds ===
ARRIVAL_THRESHOLDS = {
    "balanced": 0.39,
    "high_precision": 0.46,
    "high_recall": 0.29,
}

DEPARTURE_THRESHOLDS = {
    "balanced": 0.53,
    "high_precision": 0.64,
    "high_recall": 0.23,
}

# === 4-Tier Risk Boundaries ===
ARRIVAL_RISK_TIERS = {
    "CRITICAL": 0.75,
    "HIGH": 0.30,
    "MEDIUM": 0.15,
    "LOW": 0.0,
}

DEPARTURE_RISK_TIERS = {
    "CRITICAL": 0.80,
    "HIGH": 0.25,
    "MEDIUM": 0.10,
    "LOW": 0.0,
}

# === SHAP Feature → Human-Readable Labels ===
SHAP_LABELS = {
    # Core Lag
    "delay_rate_1h": "Recent LGA delay rate (past 1h)",
    "terminal_delay_1h": "Terminal recent delays",
    "severe_delay_count_prev": "Severe delays in past 3h",
    "delay_rolling_3h": "Rolling average delay (3h)",
    "lga_dep_delay_1h": "LGA departure delays (past 1h)",
    "lga_arr_delay_1h": "LGA arrival delays (past 1h)",
    # Aircraft Continuity
    "prev_aircraft_delay": "Same aircraft previous arrival delay",
    "prev_inbound_delay": "Inbound aircraft delay",
    # Target Encoding
    "gate_delay_rate": "Gate historical delay rate",
    "faa_delay_reason": "FAA delay reason category",
    "runway_delay_rate": "Runway historical delay rate",
    "airline_delay_rate": "Airline delay tendency",
    # Time
    "Hour": "Time of day",
    "Month": "Month/seasonal effect",
    # Operational
    "faa_delay_severity": "FAA delay program severity",
    "runway_config_change": "Recent runway configuration change",
    # Origin/Dest Weather
    "origin_dewpoint": "Origin airport humidity",
    "origin_storm_flag": "Origin storm activity",
    "origin_cloud_cover": "Origin cloud cover",
    "origin_historical_delay": "Origin historical delay pattern",
    "dest_dewpoint": "Destination humidity",
    "dest_storm_flag": "Destination storm activity",
    "dest_cloud_cover": "Destination cloud cover",
    "dest_historical_delay": "Destination historical delay pattern",
    # Network
    "route_risk_score": "Route historical risk score",
    # Aircraft
    "turnaround_hours": "Aircraft turnaround time",
    # Engineered interaction features (V9 arrival model)
    "origin_dewpoint_missing": "Origin weather data missing",
    "congestion_x_gate": "Congestion × gate pressure",
    "chain_x_turnaround": "Aircraft chain × turnaround pressure",
    "congestion_accel": "Congestion acceleration (1h vs 3h)",
    # V9 weather impact scores
    "origin_wx_impact": "Origin weather impact score",
    "lga_wx_impact": "LGA weather impact score",
    "faa_event_duration_hours": "FAA event duration",
    "faa_active_event_count": "Active FAA events",
}

# === SHAP Feature → Delay Cause Category ===
SHAP_CATEGORIES: dict[str, str] = {
    # Weather (origin/dest)
    "origin_dewpoint": "weather",
    "origin_storm_flag": "weather",
    "origin_cloud_cover": "weather",
    "origin_historical_delay": "weather",
    "dest_dewpoint": "weather",
    "dest_storm_flag": "weather",
    "dest_cloud_cover": "weather",
    "dest_historical_delay": "weather",
    # Aircraft Continuity
    "prev_aircraft_delay": "aircraft",
    "prev_inbound_delay": "aircraft",
    "turnaround_hours": "aircraft",
    # LGA Cascade (lag features)
    "delay_rate_1h": "cascade",
    "terminal_delay_1h": "cascade",
    "severe_delay_count_prev": "cascade",
    "delay_rolling_3h": "cascade",
    "lga_dep_delay_1h": "cascade",
    "lga_arr_delay_1h": "cascade",
    # Route & Operational
    "route_risk_score": "route",
    "gate_delay_rate": "route",
    "runway_delay_rate": "route",
    "airline_delay_rate": "route",
    "faa_delay_reason": "route",
    "faa_delay_severity": "route",
    "runway_config_change": "route",
    "Hour": "route",
    "Month": "route",
}

# === SHAP Factor Level Thresholds ===
SHAP_LEVEL_THRESHOLDS = {
    "major": 0.05,       # |SHAP value| >= 0.05 → "major factor"
    "contributing": 0.02, # >= 0.02 → "contributing"
    # < 0.02 → "minor factor"
}

# === Simulation Settings ===
SIMULATION_SPEED_OPTIONS = {
    "1x": 1.0,      # 1 second = 1 minute real time
    "5x": 5.0,      # 1 second = 5 minutes
    "15x": 15.0,    # 1 second = 15 minutes (default)
    "60x": 60.0,    # 1 second = 1 hour
}
DEFAULT_SIMULATION_SPEED = "15x"

# === Raw Data Files ===
# Source: notebooks/delay/arrival/01_data_preparation.ipynb (V9.0, Jan-Oct 2025)
# Files have schema variations (v2 schema for Jan-May & Sept-Oct, old schema for May-Sept).
# Boundary overlaps at end of May (Jan-May ↔ May-June) and start of Sept (Aug-Sept ↔ Sept-Oct)
# are deduplicated downstream in load_raw_flights().
ARRIVAL_FILES = [
    "LGA_Jan-May2025_Arrivals.csv",      # v2 schema, Jan 1 – May 22
    "LGA_May-June2025_Arrivals.csv",     # old schema, May 22 – Jun 30
    "LGA_July2025_Arrivals.csv",         # old schema, Jul 1 – Jul 31
    "LGA_Aug-Sept2025_Arrivals.csv",     # old schema, Aug 1 – Sep 1
    "LGA_Sept-Oct2025_Arrivals.csv",     # v2 schema, Sep 2 – Oct 31
]

DEPARTURE_FILES = [
    "LGA_Jan-May2025_Departures.csv",
    "LGA_May-June2025_Departures.csv",
    "LGA_July2025_Departures.csv",
    "LGA_Aug-Sept2025_Departures.csv",
    "LGA_Sept-Oct2025_Departures.csv",
]

LGA_WEATHER_FILE = "LGA_Summer2025_Weather.csv"

# Hourly weather: full Jan-Oct METAR coverage from multiple sources.
# WeatherFull files are LGA-only; NonPAAirportWeather files cover all US airports
# (we filter to KLGA rows). The Summer aggregated file is kept as a low-fidelity
# fallback for any timestamp the METAR sources don't cover.
LGA_HOURLY_WEATHER_FILES = [
    # Real METAR observations (temp + wind direction + wind speed + gust + vis)
    "LGA_Jan-May2025_WeatherFull.csv",
    "LGA_Sept-Oct2025_WeatherFull.csv",
    "LGA_NonPAAirportWeather_Jan-May2025.csv",
    "LGA_NonPAAirportWeather_May-June2025.csv",
    "LGA_NonPAAirportWeather_July-Sept2025.csv",
    "LGA_NonPAAirportWeather_Sept-Oct2025.csv",
    # Legacy aggregated fallback (gust + vis + weather desc only — no temp/wdir/wspd)
    "LGA_Summer2025_Weather.csv",
]

FAA_ARR_DELAYS_FILE = "LGA_FAA_ArrivalDelays2025.csv"
FAA_DEP_DELAYS_FILE = "LGA_FAA_DepartureDelays2025.csv"
FAA_DELAYS_FILE = FAA_ARR_DELAYS_FILE  # legacy alias
FAA_GROUND_STOPS_FILE = "LGA_FAA_GroundStops2025.csv"
