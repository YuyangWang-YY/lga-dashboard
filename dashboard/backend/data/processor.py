"""Data processor: loads raw flight CSVs and generates predictions.

In MOCK mode (no .joblib models available), generates realistic synthetic
predictions based on actual delay patterns in the historical data.
In REAL mode, runs the full inference pipeline with trained models.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import (
    RAW_DATA_DIR,
    ARRIVAL_FILES,
    DEPARTURE_FILES,
    FAA_GROUND_STOPS_FILE,
    FAA_ARR_DELAYS_FILE,
    FAA_DEP_DELAYS_FILE,
    LGA_HOURLY_WEATHER_FILES,
    ARRIVAL_RISK_TIERS,
    DEPARTURE_RISK_TIERS,
    ARRIVAL_THRESHOLDS,
    DEPARTURE_THRESHOLDS,
    SHAP_LABELS,
)

logger = logging.getLogger(__name__)


# === Schema harmonization (ported from notebooks/delay/arrival/01_data_preparation.ipynb) ===
# Some raw files use the v2 schema (Carrier code, Body Type, Delay, Runway, ...)
# Others use the legacy "old" schema (Marketing Airline Desc, Body Type Desc, ...).
# We rename v2 columns to canonical (old) names so downstream code only sees one schema.

CARRIER_TO_AIRLINE: dict[str, str] = {
    # Mainline
    "AAL": "American Airlines", "DAL": "Delta Air Lines", "UAL": "United Airlines",
    "SWA": "Southwest Airlines", "FFT": "Frontier Airlines", "JBU": "JetBlue Airways",
    "NKS": "Spirit Airlines", "ACA": "Air Canada", "POE": "Porter Airlines",
    "GXA": "GlobalX Airlines",
    # Regional flying as a mainline brand at LGA
    "RPA": "American Airlines", "ASH": "American Airlines",
    "EDV": "Delta Air Lines",
    "SKW": "United Airlines", "GJS": "United Airlines",
    "JZA": "Air Canada",
    # GA / Charter
    "EJA": "General Aviation", "LXJ": "General Aviation", "EJM": "General Aviation",
    "GPD": "General Aviation", "CNS": "General Aviation", "VJA": "General Aviation",
    "TWY": "General Aviation", "ASP": "General Aviation", "BOG": "General Aviation",
    "COL": "General Aviation", "WUP": "General Aviation", "JRE": "General Aviation",
    "XFL": "General Aviation",
}

NEW_V2_TO_CANONICAL: dict[str, str] = {
    "Body Type": "Body Type Desc",
    "Delay": "Total Calculated Delay",
    "Movement Time": "Total  Movement Time",   # NB: old schema has DOUBLE space
    "Ramp Time": "Total Ramp Time",
    "total_taxi_time": "Total Taxi Time Calc", # lowercase in v2
    "Gate Occupancy Time": "Total Gate Occ Time",
}


def harmonize_flight_columns(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Detect schema variant and rename to canonical (old) column names.

    - Old (May–Sept files): already canonical, no changes.
    - New v2 (Jan–May, Sept–Oct files): has 'Carrier' code → rename + carrier→airline lookup.
    """
    if "Carrier" in df.columns:
        rename_map = NEW_V2_TO_CANONICAL.copy()
        if "Runway" in df.columns:
            rename_map["Runway"] = "Arrival Runway" if direction == "arrival" else "Departure Runway"
        df = df.rename(columns=rename_map)
        df["Marketing Airline Desc"] = (
            df["Carrier"].map(CARRIER_TO_AIRLINE).fillna("General Aviation")
        )
        if "Body Type Desc" in df.columns:
            df["Body Type Desc"] = df["Body Type Desc"].replace("NULL", np.nan)
        # v2 has both 'Terminal' and 'Terminal Code'; drop the redundant one
        if "Terminal" in df.columns and "Terminal Code" in df.columns:
            df = df.drop(columns=["Terminal"])
    return df


def load_raw_flights() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and concatenate all raw arrival and departure CSVs.

    Handles two schemas (v2 and old) and deduplicates boundary overlaps
    (e.g. Jan-May ends May 22, May-June starts May 22).
    """
    def _load_set(file_list: list[str], direction: str) -> pd.DataFrame:
        frames = []
        for f in file_list:
            path = RAW_DATA_DIR / f
            if not path.exists():
                logger.warning(f"Flight file not found: {path}")
                continue
            df = pd.read_csv(path, encoding="utf-8-sig")
            df = harmonize_flight_columns(df, direction)
            frames.append(df)
            logger.info(f"Loaded {f}: {len(df)} rows")
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        # Dedup boundary overlaps. Natural key: Date + Call Sign + Block Schedule.
        before = len(out)
        if {"Date", "Call Sign", "Block Schedule"}.issubset(out.columns):
            out = out.drop_duplicates(subset=["Date", "Call Sign", "Block Schedule"], keep="first")
            after = len(out)
            if before != after:
                logger.info(f"  → deduped {direction} boundary overlaps: {before:,} → {after:,}")
        return out.reset_index(drop=True)

    arr_df = _load_set(ARRIVAL_FILES, "arrival")
    dep_df = _load_set(DEPARTURE_FILES, "departure")
    return arr_df, dep_df


def load_ground_stops() -> pd.DataFrame:
    """Load FAA Ground Stop events.

    Returns DataFrame with columns: reason, start_time, end_time, cancelled_time, advisory_url.
    Times are tz-naive datetimes (LGA local).
    """
    path = RAW_DATA_DIR / FAA_GROUND_STOPS_FILE
    if not path.exists():
        logger.warning(f"Ground Stops file not found: {path}")
        return pd.DataFrame(columns=["reason", "start_time", "end_time", "cancelled_time", "advisory_url"])

    df = pd.read_csv(path, encoding="utf-8-sig")
    out = pd.DataFrame({
        "reason": df["GSP Reason"].astype(str).str.strip(),
        "start_time": pd.to_datetime(df["GSP Start Time"], errors="coerce"),
        "end_time": pd.to_datetime(df["GSP End Time"], errors="coerce"),
        "cancelled_time": pd.to_datetime(df["GSP Cancelled Time"], errors="coerce"),
        "advisory_url": df["GSP Advisory Url"].astype(str),
    })
    out = out.dropna(subset=["start_time", "end_time"]).reset_index(drop=True)
    logger.info(f"Loaded {len(out)} Ground Stop events")
    return out


def get_active_ground_stops(gs_df: pd.DataFrame, current_time: datetime) -> list[dict]:
    """Return Ground Stops active at the given time.

    A GS is active if start_time <= current_time AND
    (cancelled_time is null OR current_time < cancelled_time) AND
    current_time < end_time.
    """
    if gs_df.empty:
        return []

    ct = pd.Timestamp(current_time).tz_localize(None) if pd.Timestamp(current_time).tzinfo else pd.Timestamp(current_time)

    mask = (gs_df["start_time"] <= ct) & (ct < gs_df["end_time"])
    cancelled = gs_df["cancelled_time"].notna() & (gs_df["cancelled_time"] <= ct)
    mask = mask & ~cancelled

    active = gs_df[mask]
    results = []
    for _, row in active.iterrows():
        # Effective end = cancelled_time if set and earlier than end, else end_time
        effective_end = row["end_time"]
        total_seconds = (effective_end - row["start_time"]).total_seconds()
        remaining_seconds = (effective_end - ct).total_seconds()
        results.append({
            "reason": row["reason"],
            "start_time": row["start_time"].isoformat(),
            "end_time": row["end_time"].isoformat(),
            "duration_minutes": int(total_seconds // 60),
            "remaining_minutes": max(0, int(remaining_seconds // 60)),
            "advisory_url": row["advisory_url"] if isinstance(row["advisory_url"], str) and row["advisory_url"].startswith("http") else None,
        })
    return results


# === Hourly Weather (METAR-style observations) ===

def _parse_weather_full(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the WeatherFull / NonPAAirportWeather METAR-style schema.

    NonPAAirportWeather files contain observations for many airports keyed by
    ICAO code in the `key` column — filter to KLGA. The legacy WeatherFull
    files are LGA-only and have no `key` column.
    """
    if "key" in df.columns:
        df = df[df["key"] == "KLGA"]
    dt = pd.to_datetime(df["valid_time_est"], errors="coerce")
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_localize(None)
    return pd.DataFrame({
        "timestamp": dt,
        "temp_f": pd.to_numeric(df.get("temp"), errors="coerce"),
        "condition": df.get("wx_phrase", "").astype(str),
        "condition_icon": pd.to_numeric(df.get("wx_icon"), errors="coerce").fillna(0).astype(int),
        "wind_dir_deg": pd.to_numeric(df.get("wdir"), errors="coerce"),
        "wind_dir_cardinal": df.get("wdir_cardinal", "").astype(str),
        "wind_speed_kt": pd.to_numeric(df.get("wspd"), errors="coerce"),
        "gust_kt": pd.to_numeric(df.get("gust"), errors="coerce"),
        "visibility_mi": pd.to_numeric(df.get("vis"), errors="coerce"),
    })


def _condition_to_icon_code(desc: str) -> int:
    """Map free-text Weather Desc string → wx_icon code (best-effort)."""
    if not isinstance(desc, str):
        return 26
    d = desc.lower()
    if "thunder" in d or "storm" in d:
        return 4
    if "snow" in d or "flurr" in d or "sleet" in d:
        return 13
    if "rain" in d or "drizzle" in d or "shower" in d:
        return 11
    if "fog" in d or "mist" in d or "haze" in d:
        return 20
    if "cloud" in d or "overcast" in d:
        return 26
    if "partly" in d or "mostly sunny" in d:
        return 29
    if "clear" in d or "sunny" in d or "fair" in d:
        return 32
    return 26


def _parse_weather_summer(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the legacy Summer2025_Weather schema (PA-format aggregated hourly)."""
    # Date is "YYYY-MM-DD HH:MM:SS"; Military Hour is the hour of day (0-23).
    # Combine the calendar date with the hour.
    base_date = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
    hours = pd.to_numeric(df["Military Hour"], errors="coerce").fillna(0).astype(int)
    timestamp = base_date + pd.to_timedelta(hours, unit="h")

    gust_mph = pd.to_numeric(df.get("Avg Wind Gusts (mph)"), errors="coerce")
    gust_kt = gust_mph * 0.868976  # mph → knots

    desc = df.get("Weather Desc", "").astype(str)
    icon_codes = desc.map(_condition_to_icon_code)

    return pd.DataFrame({
        "timestamp": timestamp,
        "temp_f": pd.Series([pd.NA] * len(df), dtype="object"),  # not available
        "condition": desc,
        "condition_icon": icon_codes.astype(int),
        "wind_dir_deg": pd.Series([pd.NA] * len(df), dtype="object"),
        "wind_dir_cardinal": pd.Series([""] * len(df)),
        "wind_speed_kt": pd.Series([pd.NA] * len(df), dtype="object"),
        "gust_kt": gust_kt,
        "visibility_mi": pd.to_numeric(df.get("Avg Visibility (Miles)"), errors="coerce"),
    })


def load_hourly_weather() -> pd.DataFrame:
    """Load hourly LGA weather observations from one or more weather CSVs.

    Supports two schemas auto-detected per file:
      - WeatherFull (METAR-style)  → columns: valid_time_est, temp, wx_phrase, wdir, wspd, gust, vis, ...
      - Summer aggregated         → columns: PA Airport Code, Date, Military Hour, Avg Wind Gusts (mph), Avg Visibility, Weather Desc

    Output columns:
        timestamp (tz-naive datetime, EST/EDT local), temp_f, condition,
        condition_icon, wind_dir_deg, wind_dir_cardinal, wind_speed_kt,
        gust_kt, visibility_mi, severity (clear/moderate/severe).
    """
    # Cols we actually need from any METAR file (saves ~95% memory on the 265 MB NonPA files)
    METAR_USECOLS = [
        "valid_time_est", "key", "temp", "wx_phrase", "wx_icon",
        "wdir", "wdir_cardinal", "wspd", "gust", "vis",
    ]

    frames: list[pd.DataFrame] = []
    for f in LGA_HOURLY_WEATHER_FILES:
        path = RAW_DATA_DIR / f
        if not path.exists():
            logger.warning(f"Hourly weather file not found: {path}")
            continue
        # Peek at the header so we know which schema we're dealing with and
        # which usecols list to pass.
        header = pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns.tolist()
        if "valid_time_est" in header:
            available = [c for c in METAR_USECOLS if c in header]
            df = pd.read_csv(path, encoding="utf-8-sig", usecols=available)
            parsed = _parse_weather_full(df)
            schema = "METAR"
        elif "Military Hour" in header and "Date" in header:
            df = pd.read_csv(path, encoding="utf-8-sig")
            parsed = _parse_weather_summer(df)
            schema = "Summer-aggregated"
        else:
            logger.warning(f"Unknown weather schema in {f}; skipping")
            continue
        logger.info(f"Loaded {f} ({schema}): {len(parsed)} rows")
        frames.append(parsed)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    # Dedup by hour-floor: when multiple sources report the same hour, prefer
    # METAR rows (they're sorted first because Summer file is last in the list,
    # and rows that have a real temp_f are kept first).
    out["_hour"] = out["timestamp"].dt.floor("h")
    out["_has_temp"] = out["temp_f"].notna().astype(int)
    out = (
        out.sort_values(["_hour", "_has_temp"], ascending=[True, False])
        .drop_duplicates(subset=["_hour"], keep="first")
        .drop(columns=["_hour", "_has_temp"])
        .reset_index(drop=True)
    )

    # Compute severity per row (use pd.notna so pd.NA from sparse schemas is handled)
    def _severity(row):
        vis = row["visibility_mi"]
        wspd = row["wind_speed_kt"]
        gust = row["gust_kt"]
        if pd.notna(vis) and vis < 3:
            return "severe"
        if pd.notna(wspd) and wspd > 30:
            return "severe"
        if pd.notna(gust) and gust > 35:
            return "severe"
        if pd.notna(vis) and vis < 6:
            return "moderate"
        if pd.notna(wspd) and wspd > 20:
            return "moderate"
        return "clear"
    out["severity"] = out.apply(_severity, axis=1)

    logger.info(f"Loaded {len(out)} hourly weather observations")
    return out


# Weather icon mapping (TWC wx_icon code → emoji-like glyph)
_WX_ICON_MAP = {
    0:  "\u26C8",  # tornado ⛈
    1:  "\u26C8",  # tropical storm
    2:  "\u26C8",  # hurricane
    4:  "\u26C8",  # thunderstorms ⛈
    11: "\U0001F327",  # showers 🌧
    12: "\U0001F327",
    13: "\U0001F328",  # snow
    14: "\U0001F328",
    15: "\U0001F328",
    16: "\U0001F328",
    19: "\U0001F32B",  # dust 🌫
    20: "\U0001F32B",  # foggy
    21: "\U0001F32B",  # haze
    23: "\U0001F32C",  # windy
    26: "\u2601",      # cloudy ☁
    27: "\u2601",
    28: "\u2601",
    29: "\u26C5",      # partly cloudy ⛅
    30: "\u26C5",
    32: "\u2600",      # sunny ☀
    33: "\u2600",
    34: "\u2600",
}


def _icon_glyph(code: int) -> str:
    return _WX_ICON_MAP.get(int(code) if code else 0, "\u2601")


def get_weather_window(
    weather_df: pd.DataFrame,
    current_time: datetime,
    hours_back: int = 2,
    hours_forward: int = 22,
) -> tuple[dict | None, list[dict], list[dict]]:
    """Pick the current weather observation, a 24h window of hourly slots,
    and derived alerts.

    Returns: (current, hourly_list, alert_list)
    """
    if weather_df.empty:
        return None, [], []

    ct = pd.Timestamp(current_time).tz_localize(None) if pd.Timestamp(current_time).tzinfo else pd.Timestamp(current_time)

    # Current = the latest observation at or before ct (within 2h tolerance)
    past_mask = weather_df["timestamp"] <= ct
    past = weather_df[past_mask]
    if past.empty:
        return None, [], []
    current_row = past.iloc[-1]

    # Compute crosswind for runway 04/22 (heading 040°)
    runway_heading = 40.0
    raw_dir = current_row.get("wind_dir_deg")
    raw_spd = current_row.get("wind_speed_kt")
    wind_dir = float(raw_dir) if pd.notna(raw_dir) else 0.0
    wind_spd = float(raw_spd) if pd.notna(raw_spd) else 0.0
    import math
    angle_diff = abs(((wind_dir - runway_heading + 180) % 360) - 180)
    crosswind = round(abs(wind_spd * math.sin(math.radians(angle_diff))), 1)

    cond_val = current_row["condition"]
    cardinal_val = current_row["wind_dir_cardinal"]
    gust_raw = current_row["gust_kt"]
    current = {
        "temp_f": int(current_row["temp_f"]) if pd.notna(current_row["temp_f"]) else None,
        "condition": cond_val if (pd.notna(cond_val) and str(cond_val).strip()) else "Clear",
        "condition_icon": _icon_glyph(current_row["condition_icon"]),
        "wind_dir_deg": int(wind_dir),
        "wind_dir_cardinal": cardinal_val if pd.notna(cardinal_val) else "",
        "wind_speed_kt": int(wind_spd),
        "gust_kt": int(gust_raw) if pd.notna(gust_raw) else 0,
        "crosswind_kt": crosswind,
        "visibility_mi": float(current_row["visibility_mi"]) if pd.notna(current_row["visibility_mi"]) else 0.0,
        "severity": current_row["severity"],
    }

    # 24h hourly slots (centered on ct)
    start = ct - pd.Timedelta(hours=hours_back)
    end = ct + pd.Timedelta(hours=hours_forward)
    window = weather_df[(weather_df["timestamp"] >= start) & (weather_df["timestamp"] <= end)]
    # Resample to hourly (keep first of each hour)
    window = window.copy()
    window["hour_floor"] = window["timestamp"].dt.floor("h")
    hourly = window.drop_duplicates("hour_floor")

    hourly_list = []
    for _, row in hourly.iterrows():
        hourly_list.append({
            "hour_iso": row["hour_floor"].isoformat(),
            "temp_f": int(row["temp_f"]) if pd.notna(row["temp_f"]) else None,
            "condition_icon": _icon_glyph(row["condition_icon"]),
            "wind_speed_kt": int(row["wind_speed_kt"]) if pd.notna(row["wind_speed_kt"]) else 0,
            "wind_dir_deg": int(row["wind_dir_deg"]) if pd.notna(row["wind_dir_deg"]) else None,
        })

    # Alerts derived from current conditions
    alerts = []
    if current["visibility_mi"] and current["visibility_mi"] < 3:
        alerts.append({
            "severity": "severe",
            "title": "Low Visibility",
            "description": f"Visibility {current['visibility_mi']} mi (below 3 mi minimum)",
        })
    elif current["visibility_mi"] and current["visibility_mi"] < 6:
        alerts.append({
            "severity": "moderate",
            "title": "Reduced Visibility",
            "description": f"Visibility {current['visibility_mi']} mi",
        })
    if current["wind_speed_kt"] > 30:
        alerts.append({
            "severity": "severe",
            "title": "High Wind",
            "description": f"Sustained {current['wind_speed_kt']} kt",
        })
    if current["gust_kt"] > 35:
        alerts.append({
            "severity": "severe",
            "title": "Strong Gusts",
            "description": f"Gusts {current['gust_kt']} kt",
        })
    if current["crosswind_kt"] > 15:
        alerts.append({
            "severity": "moderate",
            "title": "Crosswind",
            "description": f"Crosswind component {current['crosswind_kt']} kt on runway 04/22",
        })
    if current["temp_f"] is not None and current["temp_f"] < 32:
        alerts.append({
            "severity": "moderate",
            "title": "Freezing",
            "description": f"Temperature {current['temp_f']}°F",
        })

    return current, hourly_list, alerts


# === FAA Ground Delays ===

def load_ground_delays() -> pd.DataFrame:
    """Load FAA Arrival + Departure delay programs (soft-throttle delays).

    Output columns:
        update_time, direction (ARR/DEP), reason, reason_code,
        avg_delay_min, min_delay_str, max_delay_str, trend.
    """
    frames = []

    arr_path = RAW_DATA_DIR / FAA_ARR_DELAYS_FILE
    if arr_path.exists():
        a = pd.read_csv(arr_path, encoding="utf-8-sig")
        a_out = pd.DataFrame({
            "update_time": pd.to_datetime(a["AD Update Time"], errors="coerce"),
            "direction": "ARR",
            "reason": a["AD Reason"].astype(str),
            "reason_code": a["AD Reason Code"].astype(str),
            "avg_delay_min": pd.to_numeric(a["AD Avg Delay"], errors="coerce"),
            "min_delay_str": a["AD Min Delay"].astype(str),
            "max_delay_str": a["AD Max Delay"].astype(str),
            "trend": a["AD Trend"].astype(str),
        })
        frames.append(a_out)

    dep_path = RAW_DATA_DIR / FAA_DEP_DELAYS_FILE
    if dep_path.exists():
        d = pd.read_csv(dep_path, encoding="utf-8-sig")
        d_out = pd.DataFrame({
            "update_time": pd.to_datetime(d["DD Update Time"], errors="coerce"),
            "direction": "DEP",
            "reason": d["DD Reason Description"].astype(str),
            "reason_code": d["DD Reason Code"].astype(str),
            "avg_delay_min": pd.to_numeric(d["DD Avg Delay"], errors="coerce"),
            "min_delay_str": d["DD Min Delay"].astype(str),
            "max_delay_str": d["DD Max Delay"].astype(str),
            "trend": d["DD Trend"].astype(str),
        })
        frames.append(d_out)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["update_time"]).sort_values("update_time").reset_index(drop=True)
    logger.info(f"Loaded {len(out)} ground delay events")
    return out


def get_active_ground_delays(
    gd_df: pd.DataFrame,
    current_time: datetime,
    lookback_minutes: int = 60,
) -> list[dict]:
    """Pick the latest GD record per direction within `lookback_minutes` of current_time.

    A GD is considered active if its `update_time` is within the lookback window.
    """
    if gd_df.empty:
        return []

    ct = pd.Timestamp(current_time).tz_localize(None) if pd.Timestamp(current_time).tzinfo else pd.Timestamp(current_time)
    cutoff = ct - pd.Timedelta(minutes=lookback_minutes)

    recent = gd_df[(gd_df["update_time"] >= cutoff) & (gd_df["update_time"] <= ct)]
    if recent.empty:
        return []

    results = []
    # Latest record per direction
    for direction, group in recent.groupby("direction"):
        latest = group.sort_values("update_time").iloc[-1]
        results.append({
            "direction": direction,
            "reason": latest["reason"],
            "reason_code": latest["reason_code"],
            "avg_delay_min": int(latest["avg_delay_min"]) if pd.notna(latest["avg_delay_min"]) else 0,
            "min_delay_str": latest["min_delay_str"],
            "max_delay_str": latest["max_delay_str"],
            "trend": latest["trend"],
            "update_time": latest["update_time"].isoformat(),
        })

    # Sort by avg_delay_min desc
    results.sort(key=lambda r: -r["avg_delay_min"])
    return results


# === Hourly delay statistics (for DABI-style by-hour table) ===

def compute_hourly_delay_stats(flights: pd.DataFrame) -> list[dict]:
    """For each hour with flights, return aggregate delay magnitudes.

    Returns list of dicts: {hour, avg_delay_min, max_delay_min, total_flights, delayed_count}
    Used by the right-column "Arrival Delays by Hour" / "Departure Delays by Hour" tables.
    """
    if flights.empty or "Hour" not in flights.columns:
        return []

    out = []
    for hour in sorted(flights["Hour"].unique()):
        hour_flights = flights[flights["Hour"] == hour]
        delayed = hour_flights[hour_flights["pred_delay_q50"] > 0]
        avg_delay = float(delayed["pred_delay_q50"].mean()) if not delayed.empty else 0.0
        max_delay = float(hour_flights["pred_delay_q50"].max()) if not hour_flights.empty else 0.0
        out.append({
            "hour": int(hour),
            "avg_delay_min": round(avg_delay, 1),
            "max_delay_min": round(max_delay, 1),
            "total_flights": int(len(hour_flights)),
            "delayed_count": int(len(delayed)),
        })
    return out


def clean_flight_data(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Clean raw flight data into a standard format."""
    if df.empty:
        return df

    df = df.copy()

    # Parse dates — use format='mixed' so pandas handles both
    # the v2 schema (7-digit microseconds: 2025-01-01 00:54:00.0000000)
    # and the old schema (no microseconds: 2025-06-19 15:19:00) in the same column.
    df["Date"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")
    df["Block Schedule"] = pd.to_datetime(df["Block Schedule"], format="mixed", errors="coerce")
    df["Block Actual"] = pd.to_datetime(df["Block Actual"], format="mixed", errors="coerce")

    # Total Calculated Delay (minutes)
    df["Total Calculated Delay"] = pd.to_numeric(
        df["Total Calculated Delay"], errors="coerce"
    ).fillna(0)

    # Is_Delayed: DOT standard >15 min
    df["Is_Delayed"] = (df["Total Calculated Delay"] > 15).astype(int)

    # Standard columns
    runway_col = "Arrival Runway" if direction == "arrival" else "Departure Runway"
    df = df.rename(columns={
        "Marketing Airline Desc": "Airline",
        "Non-PA Airport": "Origin" if direction == "arrival" else "Destination",
        "Body Type Desc": "Body_Type",
        "Terminal Code": "Terminal",
        runway_col: "Runway",
        "Call Sign": "Flight",
        "Block Schedule": "Scheduled_Time",
        "Block Actual": "Actual_Time",
        "Total Calculated Delay": "Delay_Minutes",
    })

    # Extract Hour/Month
    df["Hour"] = df["Scheduled_Time"].dt.hour
    df["Month"] = df["Scheduled_Time"].dt.month

    # Direction tag
    df["Direction"] = direction.upper()[:3]  # "ARR" or "DEP"

    # Create a unique flight ID
    df["flight_id"] = (
        df["Flight"].astype(str) + "_" +
        df["Scheduled_Time"].dt.strftime("%Y%m%d%H%M").fillna("unknown")
    )

    # Drop rows without scheduled time
    df = df.dropna(subset=["Scheduled_Time"])

    return df


def assign_risk_tier(prob: float, tiers: dict[str, float]) -> str:
    """Assign risk tier based on calibrated probability."""
    for tier_name in ["CRITICAL", "HIGH", "MEDIUM"]:
        if prob >= tiers[tier_name]:
            return tier_name
    return "LOW"


def generate_mock_predictions(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Generate realistic mock predictions based on actual delay patterns.

    Uses the actual delay data to create synthetic probabilities that
    correlate with real outcomes, providing a realistic demo experience.
    """
    if df.empty:
        return df

    df = df.copy()
    rng = np.random.default_rng(42)

    # Generate probabilities correlated with actual delays
    # For delayed flights: higher probability (centered around 0.5-0.8)
    # For on-time flights: lower probability (centered around 0.1-0.3)
    n = len(df)
    base_noise = rng.beta(2, 5, size=n)  # Skewed toward low values

    # Shift up for actually delayed flights
    delayed_mask = df["Is_Delayed"] == 1
    df["delay_probability"] = np.where(
        delayed_mask,
        np.clip(0.35 + rng.beta(3, 2, size=n) * 0.55 + base_noise * 0.1, 0.05, 0.98),
        np.clip(0.05 + rng.beta(2, 5, size=n) * 0.35 + base_noise * 0.1, 0.02, 0.65),
    )

    # Assign risk tiers
    tiers = ARRIVAL_RISK_TIERS if direction == "arrival" else DEPARTURE_RISK_TIERS
    df["risk_tier"] = df["delay_probability"].apply(lambda p: assign_risk_tier(p, tiers))

    # Generate predicted delay minutes (Q50) — correlated with actual delay
    # For predicted-delayed flights, generate from a reasonable distribution
    df["pred_delay_q50"] = np.where(
        df["delay_probability"] >= 0.15,
        np.clip(
            df["Delay_Minutes"] * 0.6  # Partially correlated with actual
            + rng.normal(0, 10, size=n),  # Plus noise
            5, 180
        ).astype(int),
        0
    )

    # Prediction intervals (Q10, Q90)
    df["pred_delay_q10"] = np.where(
        df["pred_delay_q50"] > 0,
        np.clip(df["pred_delay_q50"] - rng.uniform(8, 18, size=n), 0, 999).astype(int),
        0
    )
    df["pred_delay_q90"] = np.where(
        df["pred_delay_q50"] > 0,
        np.clip(df["pred_delay_q50"] + rng.uniform(10, 25, size=n), 5, 300).astype(int),
        0
    )

    # Confidence: arrivals degrade after 1h lookahead, departures don't
    # For mock, just assign based on time-to-current
    df["confidence"] = "HIGH"  # Will be updated dynamically based on simulation time

    # Generate mock SHAP values (top 5 features per flight)
    feature_pool = list(SHAP_LABELS.keys())[:15]
    shap_values_list = []
    for _, row in df.iterrows():
        n_factors = rng.integers(3, 6)
        selected = rng.choice(feature_pool, size=n_factors, replace=False)
        factors = []
        for i, feat in enumerate(selected):
            # First factors have higher magnitude
            magnitude = rng.uniform(0.02, 0.20) * (1.0 - i * 0.15)
            sign = 1.0 if row["delay_probability"] > 0.3 else rng.choice([-1, 1])
            factors.append({
                "feature": feat,
                "label": SHAP_LABELS.get(feat, feat),
                "value": round(float(sign * magnitude), 4),
                "level": (
                    "major" if abs(magnitude) >= 0.05
                    else "contributing" if abs(magnitude) >= 0.02
                    else "minor"
                ),
            })
        shap_values_list.append(factors)
    df["shap_factors"] = shap_values_list

    # Generate mock delay causes (observable condition categories)
    cause_categories = ["weather", "aircraft", "cascade", "route"]
    cause_weights = np.array([0.35, 0.25, 0.25, 0.15])
    df["delay_cause"] = rng.choice(cause_categories, size=n, p=cause_weights)

    # Generate mock operational context data
    weather_options = [
        ("Clear, 24°C, Wind 8kt", "clear"),
        ("Partly Cloudy, 28°C, Wind 15kt", "clear"),
        ("Overcast, 22°C, Wind 20kt", "moderate"),
        ("Rain, 18°C, Wind 25kt, Vis 5mi", "moderate"),
        ("Thunderstorms, 26°C, Wind 35kt, Vis 3mi", "severe"),
        ("Heavy Rain, 20°C, Gusts 40kt, Vis 2mi", "severe"),
    ]

    weather_idx = rng.integers(0, len(weather_options), size=n)
    # Bias toward severe weather for high-risk flights
    for i in range(n):
        if df.iloc[i]["delay_probability"] > 0.5 and df.iloc[i]["delay_cause"] == "weather":
            weather_idx[i] = rng.integers(4, len(weather_options))

    df["mock_origin_weather"] = [weather_options[idx][0] for idx in weather_idx]
    df["mock_origin_severity"] = [weather_options[idx][1] for idx in weather_idx]

    # Previous aircraft delay
    df["mock_prev_aircraft_delay"] = np.where(
        df["delay_cause"] == "aircraft",
        rng.integers(15, 90, size=n),
        np.where(rng.random(size=n) < 0.2, rng.integers(5, 30, size=n), 0),
    )

    # Turnaround hours
    df["mock_turnaround"] = np.clip(rng.normal(2.5, 1.0, size=n), 0.5, 8.0)

    # Route delay rate
    df["mock_route_delay_rate"] = np.clip(
        rng.normal(22, 10, size=n) + df["delay_probability"] * 15,
        5, 55,
    )

    return df


def build_flight_cache(
    arr_df: pd.DataFrame, dep_df: pd.DataFrame
) -> pd.DataFrame:
    """Combine arrivals and departures into a unified flight cache."""
    # Select common columns for the combined view
    common_cols = [
        "flight_id", "Flight", "Direction", "Airline", "Gate", "Terminal",
        "Runway", "Registration", "Body_Type", "Date", "Scheduled_Time",
        "Actual_Time", "Delay_Minutes", "Is_Delayed", "Hour", "Month",
        "delay_probability", "risk_tier", "pred_delay_q50",
        "pred_delay_q10", "pred_delay_q90", "confidence", "shap_factors",
        "delay_cause", "mock_origin_weather", "mock_origin_severity",
        "mock_prev_aircraft_delay", "mock_turnaround", "mock_route_delay_rate",
    ]

    # Add origin/destination columns
    if "Origin" in arr_df.columns:
        arr_df["Remote_Airport"] = arr_df["Origin"]
    if "Destination" in dep_df.columns:
        dep_df["Remote_Airport"] = dep_df["Destination"]

    common_cols.append("Remote_Airport")

    frames = []
    for df in [arr_df, dep_df]:
        if not df.empty:
            # Only keep columns that exist
            available = [c for c in common_cols if c in df.columns]
            frames.append(df[available])

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("Scheduled_Time").reset_index(drop=True)

    logger.info(
        f"Flight cache built: {len(combined)} flights "
        f"({len(arr_df)} arrivals + {len(dep_df)} departures)"
    )
    return combined


def get_available_dates(flight_cache: pd.DataFrame) -> list[str]:
    """Get sorted list of available dates in the data."""
    if flight_cache.empty:
        return []
    dates = flight_cache["Date"].dt.strftime("%Y-%m-%d").unique().tolist()
    return sorted(dates)


def filter_flights_by_window(
    flight_cache: pd.DataFrame,
    current_time: datetime,
    window_hours: int = 5,
    direction: str | None = None,
    terminal: str | None = None,
    airline: str | None = None,
    risk_tier: str | None = None,
) -> pd.DataFrame:
    """Filter flights within a time window around current_time.

    Shows flights scheduled in [current_time, current_time + window_hours].
    """
    if flight_cache.empty:
        return flight_cache

    start = pd.Timestamp(current_time)
    end = start + pd.Timedelta(hours=window_hours)

    mask = (flight_cache["Scheduled_Time"] >= start) & (
        flight_cache["Scheduled_Time"] <= end
    )

    if direction:
        mask &= flight_cache["Direction"] == direction.upper()[:3]
    if terminal:
        mask &= flight_cache["Terminal"] == terminal
    if airline:
        mask &= flight_cache["Airline"] == airline
    if risk_tier:
        mask &= flight_cache["risk_tier"] == risk_tier.upper()

    result = flight_cache[mask].copy()

    # Update confidence based on lookahead time
    if not result.empty:
        lookahead_hours = (
            result["Scheduled_Time"] - start
        ).dt.total_seconds() / 3600

        # Arrivals: confidence degrades after 1h
        arr_mask = result["Direction"] == "ARR"
        result.loc[arr_mask, "confidence"] = np.where(
            lookahead_hours[arr_mask] <= 1.0, "HIGH", "MODERATE"
        )
        # Departures: always high confidence (no lookahead cliff)
        result.loc[~arr_mask, "confidence"] = "HIGH"

    return result


def filter_flights_by_date(
    flight_cache: pd.DataFrame,
    current_time: datetime,
    direction: str | None = None,
) -> pd.DataFrame:
    """Filter flights for the same calendar date as current_time."""
    if flight_cache.empty:
        return flight_cache

    target_date = pd.Timestamp(current_time).normalize()
    mask = flight_cache["Date"] == target_date

    if direction:
        mask &= flight_cache["Direction"] == direction.upper()[:3]

    return flight_cache[mask].copy()
