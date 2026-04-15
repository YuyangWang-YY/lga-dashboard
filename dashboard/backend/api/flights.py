"""Flights API: flight list and flight detail endpoints."""

from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    FlightDetail,
    FlightListResponse,
    FlightSummary,
    OperationalContext,
    RiskDistribution,
    ShapFactor,
)
from api.overview import flight_row_to_summary
from data.processor import filter_flights_by_window

router = APIRouter()


@router.get("/flights", response_model=FlightListResponse)
async def get_flights(
    datetime_str: str = Query(
        default="2025-08-13T10:00:00",
        alias="datetime",
        description="Current simulation datetime",
    ),
    mode: str = Query(default="balanced"),
    window_hours: int = Query(default=5),
    direction: str | None = Query(default=None, description="ARR or DEP"),
    terminal: str | None = Query(default=None),
    airline: str | None = Query(default=None),
    risk_tier: str | None = Query(default=None),
    sort_by: str = Query(default="delay_probability", description="Sort field"),
    sort_desc: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get filtered and sorted flight list."""
    from main import app_state

    current_time = datetime.fromisoformat(datetime_str)
    flight_cache = app_state["flight_cache"]

    filtered = filter_flights_by_window(
        flight_cache, current_time, window_hours,
        direction=direction, terminal=terminal,
        airline=airline, risk_tier=risk_tier,
    )

    # Sort
    sort_col_map = {
        "delay_probability": "delay_probability",
        "risk": "delay_probability",
        "time": "Scheduled_Time",
        "delay": "pred_delay_q50",
        "airline": "Airline",
    }
    sort_col = sort_col_map.get(sort_by, "delay_probability")
    if sort_col in filtered.columns:
        filtered = filtered.sort_values(sort_col, ascending=not sort_desc)

    total = len(filtered)

    # Tier counts
    tier_counts = filtered["risk_tier"].value_counts() if not filtered.empty else pd.Series()
    risk_dist = RiskDistribution(
        critical=int(tier_counts.get("CRITICAL", 0)),
        high=int(tier_counts.get("HIGH", 0)),
        medium=int(tier_counts.get("MEDIUM", 0)),
        low=int(tier_counts.get("LOW", 0)),
        total=total,
    )

    # Paginate
    page = filtered.iloc[offset:offset + limit]

    flights = [flight_row_to_summary(row) for _, row in page.iterrows()]

    return FlightListResponse(
        flights=flights,
        total=total,
        tier_counts=risk_dist,
    )


@router.get("/flights/{flight_id}", response_model=FlightDetail)
async def get_flight_detail(flight_id: str):
    """Get detailed info for a single flight including SHAP factors."""
    from main import app_state

    flight_cache = app_state["flight_cache"]

    match = flight_cache[flight_cache["flight_id"] == flight_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")

    row = match.iloc[0]

    # Track A: try real SHAP first; fall back to stored mock factors
    real_shap = []
    predictor = app_state.get("predictor")
    if predictor is not None:
        direction = str(row.get("Direction", "ARR"))
        real_shap = predictor.explain_flight(flight_id, direction)

    if real_shap:
        shap_factors = [ShapFactor(**f) for f in real_shap]
    else:
        raw_factors = row.get("shap_factors", [])
        shap_factors = [
            ShapFactor(**f) if isinstance(f, dict) else f
            for f in (raw_factors if isinstance(raw_factors, list) else [])
        ]

    # Build operational context
    op_ctx = OperationalContext(
        origin_weather=row.get("mock_origin_weather") if pd.notna(row.get("mock_origin_weather")) else None,
        origin_weather_severity=row.get("mock_origin_severity") if pd.notna(row.get("mock_origin_severity")) else None,
        prev_aircraft_delay=int(row["mock_prev_aircraft_delay"]) if pd.notna(row.get("mock_prev_aircraft_delay")) else None,
        turnaround_hours=round(float(row["mock_turnaround"]), 1) if pd.notna(row.get("mock_turnaround")) else None,
        route_delay_rate=round(float(row["mock_route_delay_rate"]), 1) if pd.notna(row.get("mock_route_delay_rate")) else None,
    )

    return FlightDetail(
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
        registration=str(row["Registration"]) if pd.notna(row.get("Registration")) else None,
        body_type=str(row["Body_Type"]) if pd.notna(row.get("Body_Type")) else None,
        runway=str(row["Runway"]) if pd.notna(row.get("Runway")) else None,
        actual_time=row["Actual_Time"].isoformat() if pd.notna(row.get("Actual_Time")) else None,
        actual_delay=float(row["Delay_Minutes"]) if pd.notna(row.get("Delay_Minutes")) else None,
        is_delayed=int(row["Is_Delayed"]) if pd.notna(row.get("Is_Delayed")) else None,
        shap_factors=shap_factors,
        operational_context=op_ctx,
    )
