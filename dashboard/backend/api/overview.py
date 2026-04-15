"""Overview API: Command Center data endpoint."""

from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

from api.schemas import (
    AirlineDelay,
    DelayCause,
    DirectionOverview,
    FAAAdvisory,
    FlightSummary,
    GateConflict,
    GroundStop,
    GroundDelay,
    HourDelayStat,
    KPIData,
    OverviewResponse,
    RiskDistribution,
    TerminalKPIBlock,
    TerminalStress,
    TimelineSlot,
    WeatherCurrent,
    WeatherHourSlot,
    WeatherAlert,
)
from config import SHAP_CATEGORIES, SHAP_LABELS
from data.processor import (
    compute_hourly_delay_stats,
    filter_flights_by_date,
    filter_flights_by_window,
    get_active_ground_delays,
    get_active_ground_stops,
    get_available_dates,
    get_weather_window,
)

router = APIRouter()


def compute_direction_overview(
    flights: pd.DataFrame,
    window_hours: int,
    full_day_flights: pd.DataFrame | None = None,
) -> DirectionOverview:
    """Compute KPIs, timeline, terminal stress, and risk distribution for one direction.

    KPIs, terminal stress, and risk distribution use the windowed flights.
    Timeline uses full_day_flights (if provided) to show the entire day.
    """
    if flights.empty:
        return DirectionOverview(
            kpi=KPIData(
                predicted_delays=0, delay_rate=0.0, avg_pred_delay=0.0,
                peak_stress_hour=None, total_flights=0,
            ),
            timeline=[],
            terminal_stress=[],
            risk_distribution=RiskDistribution(
                critical=0, high=0, medium=0, low=0, total=0
            ),
            hour_delay_stats=[],
        )

    # Threshold: count flights above MEDIUM as "predicted delayed"
    delayed_mask = flights["risk_tier"].isin(["CRITICAL", "HIGH"])
    pred_delays = delayed_mask.sum()
    total = len(flights)

    avg_delay = float(
        flights.loc[flights["pred_delay_q50"] > 0, "pred_delay_q50"].mean()
    ) if (flights["pred_delay_q50"] > 0).any() else 0.0

    # Peak stress hour: hour with most CRITICAL+HIGH flights
    if delayed_mask.any():
        stress_by_hour = flights.loc[delayed_mask].groupby("Hour").size()
        peak_hour = int(stress_by_hour.idxmax())
    else:
        peak_hour = None

    kpi = KPIData(
        predicted_delays=int(pred_delays),
        delay_rate=round(pred_delays / total * 100, 1) if total > 0 else 0.0,
        avg_pred_delay=round(avg_delay, 1),
        peak_stress_hour=peak_hour,
        total_flights=total,
    )

    # Timeline: use full-day data if available, otherwise windowed data
    timeline_source = full_day_flights if full_day_flights is not None and not full_day_flights.empty else flights
    timeline = []
    if not timeline_source.empty:
        for hour in sorted(timeline_source["Hour"].unique()):
            hour_flights = timeline_source[timeline_source["Hour"] == hour]
            tier_counts = hour_flights["risk_tier"].value_counts()
            timeline.append(TimelineSlot(
                hour=int(hour),
                critical=int(tier_counts.get("CRITICAL", 0)),
                high=int(tier_counts.get("HIGH", 0)),
                medium=int(tier_counts.get("MEDIUM", 0)),
                low=int(tier_counts.get("LOW", 0)),
                total=len(hour_flights),
            ))

    # Terminal stress
    terminal_stress = []
    if not flights.empty:
        for term in sorted(flights["Terminal"].dropna().unique()):
            term_flights = flights[flights["Terminal"] == term]
            term_risk = term_flights["risk_tier"].value_counts()
            terminal_stress.append(TerminalStress(
                terminal=term,
                critical_count=int(term_risk.get("CRITICAL", 0)),
                high_count=int(term_risk.get("HIGH", 0)),
                total_flights=len(term_flights),
            ))

    # Risk distribution
    tier_counts = flights["risk_tier"].value_counts()
    risk_dist = RiskDistribution(
        critical=int(tier_counts.get("CRITICAL", 0)),
        high=int(tier_counts.get("HIGH", 0)),
        medium=int(tier_counts.get("MEDIUM", 0)),
        low=int(tier_counts.get("LOW", 0)),
        total=total,
    )

    # Hourly delay magnitudes (for "Delays by Hour" table) — uses full-day data
    hour_stats_source = full_day_flights if full_day_flights is not None and not full_day_flights.empty else flights
    hour_delay_stats = [
        HourDelayStat(**stat) for stat in compute_hourly_delay_stats(hour_stats_source)
    ]

    return DirectionOverview(
        kpi=kpi,
        timeline=timeline,
        terminal_stress=terminal_stress,
        risk_distribution=risk_dist,
        hour_delay_stats=hour_delay_stats,
    )


def extract_top_shap_label(row: pd.Series) -> str | None:
    """Extract the most impactful SHAP factor label for a flight."""
    factors = row.get("shap_factors", [])
    if not isinstance(factors, list) or not factors:
        return None
    best = max(
        factors,
        key=lambda f: abs(f["value"] if isinstance(f, dict) else getattr(f, "value", 0)),
    )
    feat = best["feature"] if isinstance(best, dict) else getattr(best, "feature", "")
    label = SHAP_LABELS.get(feat, feat)
    # Shorten for table display
    short_labels = {
        "weather": "Origin WX",
        "aircraft": "Aircraft",
        "cascade": "LGA Cascade",
        "route": "Route",
    }
    cat = SHAP_CATEGORIES.get(feat)
    if cat and cat in short_labels:
        return short_labels[cat]
    # Truncate long labels
    return label[:20] if len(label) > 20 else label


def flight_row_to_summary(row: pd.Series) -> FlightSummary:
    """Convert a DataFrame row to FlightSummary."""
    return FlightSummary(
        flight_id=str(row.get("flight_id", "")),
        flight=str(row.get("Flight", "")),
        direction=str(row.get("Direction", "")),
        airline=str(row.get("Airline", "")),
        remote_airport=str(row.get("Remote_Airport", "")),
        gate=str(row["Gate"]) if pd.notna(row.get("Gate")) else None,
        terminal=str(row["Terminal"]) if pd.notna(row.get("Terminal")) else None,
        scheduled_time=row["Scheduled_Time"].isoformat() if pd.notna(row.get("Scheduled_Time")) else "",
        risk_tier=str(row.get("risk_tier", "LOW")),
        delay_probability=round(float(row.get("delay_probability", 0)), 3),
        pred_delay_q50=int(row.get("pred_delay_q50", 0)),
        pred_delay_q10=int(row.get("pred_delay_q10", 0)),
        pred_delay_q90=int(row.get("pred_delay_q90", 0)),
        confidence=str(row.get("confidence", "HIGH")),
        top_shap_label=extract_top_shap_label(row),
    )


def compute_delay_causes(flights: pd.DataFrame) -> list[DelayCause]:
    """Categorize predicted delays by primary delay driver.

    Uses the per-flight `delay_cause` column (computed from real feature
    thresholds in predictor.py) when available.  Falls back to SHAP-based
    aggregation for flights that have stored shap_factors but no delay_cause.

    Returns counts and percentages for weather/aircraft/cascade/route.
    """
    delayed = flights[flights["risk_tier"].isin(["CRITICAL", "HIGH", "MEDIUM"])]
    if delayed.empty:
        return []

    labels = {
        "weather": "Origin Weather",
        "aircraft": "Aircraft Propagation",
        "cascade": "LGA Delay Cascade",
        "route": "Route Congestion",
    }
    valid_cats = set(labels.keys())

    category_flight_count: dict[str, int] = {k: 0 for k in valid_cats}

    # Primary path: use real delay_cause column
    if "delay_cause" in delayed.columns:
        cause_col = delayed["delay_cause"].astype(str)
        real_mask = cause_col.isin(valid_cats)
        if real_mask.any():
            for cat in valid_cats:
                category_flight_count[cat] = int((cause_col == cat).sum())

            total = sum(category_flight_count.values())
            if total == 0:
                return []

            causes = []
            for cat, count in category_flight_count.items():
                pct = count / total * 100
                if pct < 1.0:
                    continue
                causes.append(DelayCause(
                    category=cat,
                    label=labels[cat],
                    count=count,
                    percentage=round(pct, 1),
                ))
            return sorted(causes, key=lambda c: c.percentage, reverse=True)

    # Fallback: aggregate |SHAP| values per category
    category_abs_shap: dict[str, float] = {k: 0.0 for k in valid_cats}
    shap_flight_count: dict[str, int] = {k: 0 for k in valid_cats}

    for _, row in delayed.iterrows():
        factors = row.get("shap_factors", [])
        if not isinstance(factors, list) or not factors:
            continue
        flight_cat_shap: dict[str, float] = {}
        for f in factors:
            feat = f["feature"] if isinstance(f, dict) else getattr(f, "feature", None)
            val  = f["value"]   if isinstance(f, dict) else getattr(f, "value", 0)
            if feat is None:
                continue
            cat = SHAP_CATEGORIES.get(feat)
            if cat:
                flight_cat_shap[cat] = flight_cat_shap.get(cat, 0) + abs(val)
                category_abs_shap[cat] += abs(val)
        if flight_cat_shap:
            top_cat = max(flight_cat_shap, key=flight_cat_shap.get)  # type: ignore[arg-type]
            shap_flight_count[top_cat] += 1

    total_shap = sum(category_abs_shap.values())
    if total_shap == 0:
        return []

    causes = []
    for cat in category_abs_shap:
        pct = category_abs_shap[cat] / total_shap * 100
        if pct < 1.0:
            continue
        causes.append(DelayCause(
            category=cat,
            label=labels.get(cat, cat),
            count=shap_flight_count[cat],
            percentage=round(pct, 1),
        ))
    return sorted(causes, key=lambda c: c.percentage, reverse=True)


MIN_TURNAROUND_MINUTES = 45


def detect_gate_conflicts(flights: pd.DataFrame) -> list[GateConflict]:
    """Detect gate conflicts where a delayed flight may block the next occupant.

    For each gate, sorts flights by scheduled time. If the gap between
    consecutive flights is < MIN_TURNAROUND_MINUTES and the first flight's
    predicted delay eats into that gap, flag as a conflict.
    """
    if flights.empty or "Gate" not in flights.columns:
        return []

    # Only consider flights with a gate assignment
    gated = flights.dropna(subset=["Gate"])
    if gated.empty:
        return []

    conflicts: list[GateConflict] = []

    for gate, group in gated.groupby("Gate"):
        if len(group) < 2:
            continue

        ordered = group.sort_values("Scheduled_Time")
        rows = list(ordered.itertuples(index=False))

        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            gap_min = (b.Scheduled_Time - a.Scheduled_Time).total_seconds() / 60

            if gap_min > MIN_TURNAROUND_MINUTES:
                continue

            pred_delay = getattr(a, "pred_delay_q50", 0) or 0
            if pred_delay <= 0:
                continue

            overlap = pred_delay - gap_min
            if overlap <= -15:
                continue

            severity = "CRITICAL" if overlap > 0 else "HIGH"

            conflicts.append(GateConflict(
                gate=str(gate),
                terminal=getattr(a, "Terminal", None),
                flight_a_id=str(a.flight_id),
                flight_a_name=str(a.Flight),
                flight_b_id=str(b.flight_id),
                flight_b_name=str(b.Flight),
                overlap_minutes=max(int(overlap), 0),
                severity=severity,
            ))

    # Sort by severity (CRITICAL first) then overlap descending
    conflicts.sort(key=lambda c: (0 if c.severity == "CRITICAL" else 1, -c.overlap_minutes))
    return conflicts[:10]  # Cap at 10 to keep the UI clean


def compute_terminal_kpis(
    arr_flights: pd.DataFrame,
    dep_flights: pd.DataFrame,
    gate_conflicts: list[GateConflict],
    window_hours: int,
    arr_full_day: pd.DataFrame,
    dep_full_day: pd.DataFrame,
) -> dict[str, TerminalKPIBlock]:
    """Compute per-terminal scoped views of the Overview tab.

    Mirrors compute_direction_overview() filtered by Terminal so the frontend
    can render the full Overview layout (KPIs + timeline + risk distribution)
    scoped to a single terminal when the user is on a Terminal A/B/C tab.
    """
    result: dict[str, TerminalKPIBlock] = {}
    terminals = ("Terminal A", "Terminal B", "Terminal C")

    for term in terminals:
        arr_t = arr_flights[arr_flights["Terminal"] == term] if not arr_flights.empty else arr_flights
        dep_t = dep_flights[dep_flights["Terminal"] == term] if not dep_flights.empty else dep_flights
        arr_t_full = arr_full_day[arr_full_day["Terminal"] == term] if not arr_full_day.empty else arr_full_day
        dep_t_full = dep_full_day[dep_full_day["Terminal"] == term] if not dep_full_day.empty else dep_full_day

        arr_count = len(arr_t)
        dep_count = len(dep_t)
        total_flights = arr_count + dep_count

        # Build per-direction scoped overviews (timeline uses full-day, KPIs use window)
        arr_dir = compute_direction_overview(arr_t, window_hours, arr_t_full)
        dep_dir = compute_direction_overview(dep_t, window_hours, dep_t_full)

        pred_arr = int(arr_t["risk_tier"].isin(["CRITICAL", "HIGH"]).sum()) if not arr_t.empty else 0
        pred_dep = int(dep_t["risk_tier"].isin(["CRITICAL", "HIGH"]).sum()) if not dep_t.empty else 0

        combined = pd.concat([arr_t, dep_t], ignore_index=True) if not (arr_t.empty and dep_t.empty) else arr_t
        avg_delay = 0.0
        if not combined.empty and (combined["pred_delay_q50"] > 0).any():
            avg_delay = float(combined.loc[combined["pred_delay_q50"] > 0, "pred_delay_q50"].mean())

        high_risk = int((combined["risk_tier"] == "CRITICAL").sum()) if not combined.empty else 0
        conflict_count = sum(1 for gc in gate_conflicts if gc.terminal == term)

        result[term] = TerminalKPIBlock(
            terminal=term,
            total_flights=total_flights,
            arr_count=arr_count,
            dep_count=dep_count,
            pred_delay_count=pred_arr + pred_dep,
            pred_delay_arr=pred_arr,
            pred_delay_dep=pred_dep,
            avg_pred_delay_min=round(avg_delay, 1),
            high_risk_count=high_risk,
            gate_conflict_count=conflict_count,
            arrivals=arr_dir,
            departures=dep_dir,
        )

    return result


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    datetime_str: str = Query(
        default="2025-08-13T10:00:00",
        alias="datetime",
        description="Current simulation datetime (ISO format)",
    ),
    mode: str = Query(default="balanced", description="Operating mode"),
    window_hours: int = Query(default=5, description="Lookahead window in hours"),
):
    """Get Command Center overview data."""
    from main import app_state

    current_time = datetime.fromisoformat(datetime_str)
    flight_cache = app_state["flight_cache"]
    gs_cache = app_state.get("ground_stops", pd.DataFrame())
    gd_cache = app_state.get("ground_delays", pd.DataFrame())
    weather_cache = app_state.get("hourly_weather", pd.DataFrame())

    # Filter arrivals and departures separately (5h window for KPIs)
    arr_flights = filter_flights_by_window(
        flight_cache, current_time, window_hours, direction="ARR"
    )
    dep_flights = filter_flights_by_window(
        flight_cache, current_time, window_hours, direction="DEP"
    )

    # Full-day flights for timeline chart
    arr_full_day = filter_flights_by_date(flight_cache, current_time, direction="ARR")
    dep_full_day = filter_flights_by_date(flight_cache, current_time, direction="DEP")

    # Compute overviews (KPIs from window, timeline from full day)
    arr_overview = compute_direction_overview(arr_flights, window_hours, arr_full_day)
    dep_overview = compute_direction_overview(dep_flights, window_hours, dep_full_day)

    # Top risk flights (combined, sorted by probability, top 8)
    all_flights = pd.concat([arr_flights, dep_flights], ignore_index=True)
    top_risk = (
        all_flights.sort_values("delay_probability", ascending=False)
        .head(8)
    )
    top_risk_summaries = [
        flight_row_to_summary(row) for _, row in top_risk.iterrows()
    ]

    # Compute delay causes from observable conditions
    delay_causes = compute_delay_causes(all_flights)

    # Detect gate conflicts in the current window
    gate_conflicts = detect_gate_conflicts(all_flights)

    # Per-terminal KPI blocks (for KPIRow scoping on Terminal tabs)
    terminal_kpis = compute_terminal_kpis(
        arr_flights, dep_flights, gate_conflicts,
        window_hours, arr_full_day, dep_full_day,
    )

    # Airline delay aggregation (top 5 by predicted delay count)
    airline_delays: list[AirlineDelay] = []
    if not all_flights.empty and "Airline" in all_flights.columns:
        delayed_mask = all_flights["risk_tier"].isin(["CRITICAL", "HIGH"])
        for airline, group in all_flights.groupby("Airline"):
            delayed_count = delayed_mask[group.index].sum()
            if delayed_count > 0:
                delayed_flights = group[delayed_mask[group.index]]
                avg_d = float(delayed_flights["pred_delay_q50"].mean()) if not delayed_flights.empty else 0.0
                airline_delays.append(AirlineDelay(
                    airline=str(airline),
                    delayed_count=int(delayed_count),
                    total_count=len(group),
                    avg_delay=round(avg_d, 1),
                ))
        airline_delays.sort(key=lambda a: a.delayed_count, reverse=True)
        airline_delays = airline_delays[:5]

    # FAA Advisory detection (from faa_delay_severity in flight data)
    faa_advisory: FAAAdvisory | None = None
    if not all_flights.empty and "faa_delay_severity" in all_flights.columns:
        faa_active = (all_flights["faa_delay_severity"] > 0).sum()
        if faa_active > 0:
            avg_sev = float(all_flights.loc[all_flights["faa_delay_severity"] > 0, "faa_delay_severity"].mean())
            faa_advisory = FAAAdvisory(
                active=True,
                type="Ground Delay Program" if avg_sev > 0.5 else "Advisory",
                severity="high" if avg_sev > 0.7 else "moderate" if avg_sev > 0.3 else "low",
            )

    # Active Ground Stops + Ground Delays
    # Track C: prefer live FAA API data; fall back to historical CSV
    faa_live = app_state.get("faa_live")
    if faa_live is not None:
        ground_stops  = [GroundStop(**gs)  for gs  in faa_live.get("ground_stops",  [])]
        ground_delays = [GroundDelay(**gd) for gd  in faa_live.get("ground_delays", [])]
    else:
        active_gs     = get_active_ground_stops(gs_cache, current_time)
        ground_stops  = [GroundStop(**gs)  for gs  in active_gs]
        active_gd     = get_active_ground_delays(gd_cache, current_time)
        ground_delays = [GroundDelay(**gd) for gd  in active_gd]

    # Weather window
    wx_current_dict, wx_hourly_list, wx_alerts_list = get_weather_window(
        weather_cache, current_time
    )
    weather_current = WeatherCurrent(**wx_current_dict) if wx_current_dict else None
    weather_hourly = [WeatherHourSlot(**w) for w in wx_hourly_list]
    weather_alerts = [WeatherAlert(**a) for a in wx_alerts_list]

    return OverviewResponse(
        current_time=current_time.isoformat(),
        mode=mode,
        arrivals=arr_overview,
        departures=dep_overview,
        top_risk_flights=top_risk_summaries,
        delay_causes=delay_causes,
        gate_conflicts=gate_conflicts,
        airline_delays=airline_delays,
        faa_advisory=faa_advisory,
        ground_stops=ground_stops,
        ground_delays=ground_delays,
        weather_current=weather_current,
        weather_hourly=weather_hourly,
        weather_alerts=weather_alerts,
        terminal_kpis=terminal_kpis,
        available_dates=get_available_dates(flight_cache),
    )
