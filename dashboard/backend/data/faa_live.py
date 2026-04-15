"""FAA NAS Status Live API client.

Fetches current airport events from https://nasstatus.faa.gov/api/airport-events
and transforms the response into the dashboard's GroundStop / GroundDelay schema.

Falls back gracefully (returns None) when the API is unavailable so callers
can fall back to the historical CSV data already loaded at startup.

Response field mapping (verified 2026-04-11):
  groundDelay.impactingCondition  → reason
  groundDelay.fadtParamType       → reason_code  (e.g. "GDP")
  groundDelay.avgDelay            → avg_delay_min (float → int)
  groundDelay.maxDelay            → max_delay (used for max_delay_str)
  groundDelay.startTime           → start_time
  groundDelay.endTime             → end_time
  groundDelay.advisoryUrl         → advisory_url

  arrivalDelay / departureDelay:
    .reason                       → reason        (e.g. "WX:Thunderstorms")
    .arrivalDeparture.min/max     → min/max_delay_str
    .arrivalDeparture.trend       → trend
    .averageDelay                 → avg_delay_min
    .updateTime                   → update_time

  groundStop:
    .reason / .impactingCondition → reason
    .startTime / .endTime         → start/end_time
    .advisoryUrl                  → advisory_url

  airportConfig:
    .arrivalRunwayConfig          → exposed as extra metadata (not in schema yet)
    .departureRunwayConfig        → same
    .arrivalRate                  → same
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

FAA_EVENTS_URL = "https://nasstatus.faa.gov/api/airport-events"
REQUEST_TIMEOUT = 8  # seconds


def fetch_faa_live_status(airport_id: str = "LGA") -> dict | None:
    """Call FAA NAS API and return ground_stops + ground_delays for the airport.

    Returns:
        {
            "ground_stops":  [list of GroundStop-compatible dicts],
            "ground_delays": [list of GroundDelay-compatible dicts],
            "airport_config": dict | None,   # runway config, arrival rate
            "fetched_at":    ISO timestamp,
        }
        or None on network / parsing failure.
    """
    try:
        resp = requests.get(FAA_EVENTS_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        api_data = resp.json()
    except Exception as exc:
        logger.warning(f"FAA live API request failed: {exc}")
        return None

    # Find our airport in the events list
    airport: dict | None = None
    for entry in api_data:
        if entry.get("airportId") == airport_id:
            airport = entry
            break

    fetched_at = datetime.now(timezone.utc).isoformat()

    if airport is None:
        # Not in the list = no active events right now
        logger.info(f"FAA API: {airport_id} has no active events currently")
        return {
            "ground_stops":  [],
            "ground_delays": [],
            "airport_config": None,
            "fetched_at": fetched_at,
        }

    ground_stops  = _parse_ground_stop(airport.get("groundStop"))
    ground_delays = _parse_delays(airport)
    airport_cfg   = _parse_airport_config(airport.get("airportConfig"))

    logger.info(
        f"FAA live ({airport_id}): "
        f"{len(ground_stops)} ground stop(s), "
        f"{len(ground_delays)} delay program(s)"
        + (f", runway cfg: {airport_cfg}" if airport_cfg else "")
    )

    return {
        "ground_stops":  ground_stops,
        "ground_delays": ground_delays,
        "airport_config": airport_cfg,
        "fetched_at": fetched_at,
    }


# ── parsers ──────────────────────────────────────────────────────────────────

def _parse_ground_stop(gs: dict | None) -> list[dict]:
    if not gs:
        return []
    now = datetime.now(timezone.utc)
    try:
        reason   = gs.get("reason") or gs.get("impactingCondition") or "Unknown"
        start_dt = _parse_dt(gs.get("startTime") or gs.get("start_time") or "")
        end_dt   = _parse_dt(gs.get("endTime")   or gs.get("end_time")   or "")
        advisory = gs.get("advisoryUrl") or ""

        duration  = int((end_dt - start_dt).total_seconds() / 60) if start_dt and end_dt else 0
        remaining = max(0, int((end_dt - now).total_seconds() / 60)) if end_dt else 0

        return [{
            "reason":             str(reason),
            "start_time":         start_dt.isoformat() if start_dt else now.isoformat(),
            "end_time":           end_dt.isoformat()   if end_dt   else now.isoformat(),
            "duration_minutes":   duration,
            "remaining_minutes":  remaining,
            "advisory_url":       str(advisory) if advisory else None,
        }]
    except Exception as exc:
        logger.warning(f"Failed to parse FAA ground stop: {exc}")
        return []


def _parse_delays(airport: dict) -> list[dict]:
    """Extract all delay programs (GDP, arrival delay, departure delay) for the airport."""
    delays = []
    now = datetime.now(timezone.utc)

    # ── Ground Delay Program (GDP) — targets arriving flights ──────────────
    gd = airport.get("groundDelay")
    if gd:
        try:
            reason      = gd.get("impactingCondition") or "Unknown"
            reason_code = gd.get("fadtParamType") or "GDP"
            avg_min     = int(float(gd.get("avgDelay") or 0))
            max_min     = int(float(gd.get("maxDelay") or 0))
            update_raw  = gd.get("sourceTimeStamp") or gd.get("updatedAt") or now.isoformat()
            advisory    = gd.get("advisoryUrl") or ""

            delays.append({
                "direction":     "ARR",
                "reason":        str(reason),
                "reason_code":   str(reason_code),
                "avg_delay_min": avg_min,
                "min_delay_str": f"{max(0, avg_min - 15)} minutes",
                "max_delay_str": f"{max_min} minutes",
                "trend":         "No Change",
                "update_time":   _dt_str(update_raw),
            })
        except Exception as exc:
            logger.warning(f"Failed to parse FAA groundDelay: {exc}")

    # ── Arrival Delay program ─────────────────────────────���────────────────
    ad = airport.get("arrivalDelay")
    if ad:
        try:
            inner = ad.get("arrivalDeparture") or {}
            delays.append({
                "direction":     "ARR",
                "reason":        str(ad.get("reason") or "Unknown"),
                "reason_code":   "DELAY",
                "avg_delay_min": int(float(ad.get("averageDelay") or 0)),
                "min_delay_str": str(inner.get("min") or "0 minutes"),
                "max_delay_str": str(inner.get("max") or "0 minutes"),
                "trend":         _normalise_trend(ad.get("trend") or inner.get("trend")),
                "update_time":   _dt_str(ad.get("updateTime") or now.isoformat()),
            })
        except Exception as exc:
            logger.warning(f"Failed to parse FAA arrivalDelay: {exc}")

    # ── Departure Delay program ────────────────────────────────────────────
    dd = airport.get("departureDelay")
    if dd:
        try:
            inner = dd.get("arrivalDeparture") or {}
            delays.append({
                "direction":     "DEP",
                "reason":        str(dd.get("reason") or "Unknown"),
                "reason_code":   "DELAY",
                "avg_delay_min": int(float(dd.get("averageDelay") or 0)),
                "min_delay_str": str(inner.get("min") or "0 minutes"),
                "max_delay_str": str(inner.get("max") or "0 minutes"),
                "trend":         _normalise_trend(dd.get("trend") or inner.get("trend")),
                "update_time":   _dt_str(dd.get("updateTime") or now.isoformat()),
            })
        except Exception as exc:
            logger.warning(f"Failed to parse FAA departureDelay: {exc}")

    return delays


def _parse_airport_config(cfg: dict | None) -> dict | None:
    if not cfg:
        return None
    return {
        "arr_runway":   cfg.get("arrivalRunwayConfig"),
        "dep_runway":   cfg.get("departureRunwayConfig"),
        "arrival_rate": cfg.get("arrivalRate"),
    }


# ── utilities ─────────────────────────────────────────────────────────────────

def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _dt_str(s: str) -> str:
    dt = _parse_dt(s)
    return dt.isoformat() if dt else datetime.now(timezone.utc).isoformat()


def _normalise_trend(raw: str | None) -> str:
    if not raw:
        return "No Change"
    r = str(raw).strip().lower()
    if "increas" in r:
        return "Increasing"
    if "decreas" in r:
        return "Decreasing"
    return "No Change"
