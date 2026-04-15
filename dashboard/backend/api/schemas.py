"""Pydantic schemas for API responses."""

from pydantic import BaseModel


class ShapFactor(BaseModel):
    feature: str
    label: str
    value: float
    level: str  # "major", "contributing", "minor"


class FlightSummary(BaseModel):
    flight_id: str
    flight: str
    direction: str  # "ARR" or "DEP"
    airline: str
    remote_airport: str  # Origin (arrivals) or Destination (departures)
    gate: str | None
    terminal: str | None
    scheduled_time: str
    risk_tier: str
    delay_probability: float
    pred_delay_q50: int
    pred_delay_q10: int
    pred_delay_q90: int
    confidence: str  # "HIGH" or "MODERATE"
    top_shap_label: str | None = None  # Top SHAP factor label for L2 display


class OperationalContext(BaseModel):
    origin_weather: str | None  # e.g. "⛈ Thunderstorms, 28°C, Wind 35kt"
    origin_weather_severity: str | None  # "severe", "moderate", "clear"
    prev_aircraft_delay: int | None  # Previous aircraft delay in minutes
    turnaround_hours: float | None
    route_delay_rate: float | None  # Historical delay rate for this route


class FlightDetail(FlightSummary):
    registration: str | None
    body_type: str | None
    runway: str | None
    actual_time: str | None
    actual_delay: float | None
    is_delayed: int | None
    shap_factors: list[ShapFactor]
    operational_context: OperationalContext | None = None


class KPIData(BaseModel):
    predicted_delays: int
    delay_rate: float
    avg_pred_delay: float
    peak_stress_hour: int | None
    total_flights: int


class TimelineSlot(BaseModel):
    hour: int
    critical: int
    high: int
    medium: int
    low: int
    total: int


class TerminalStress(BaseModel):
    terminal: str
    critical_count: int
    high_count: int
    total_flights: int


class RiskDistribution(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total: int


class DelayCause(BaseModel):
    category: str  # "weather", "aircraft", "cascade", "route"
    label: str  # Human-readable label
    count: int
    percentage: float


class GateConflict(BaseModel):
    gate: str
    terminal: str | None
    flight_a_id: str
    flight_a_name: str
    flight_b_id: str
    flight_b_name: str
    overlap_minutes: int
    severity: str  # "CRITICAL" or "HIGH"


class AirlineDelay(BaseModel):
    airline: str
    delayed_count: int  # CRITICAL+HIGH flights
    total_count: int
    avg_delay: float  # Q50 avg for delayed flights


class FAAAdvisory(BaseModel):
    active: bool
    type: str | None = None  # "GDP", "GS", "Ground Delay"
    severity: str | None = None  # "low", "moderate", "high"


class GroundStop(BaseModel):
    reason: str  # e.g. "wind", "airspace volume", "weather"
    start_time: str  # ISO datetime
    end_time: str  # ISO datetime (scheduled end)
    duration_minutes: int  # Total scheduled duration
    remaining_minutes: int  # Remaining at current_time
    advisory_url: str | None = None


class GroundDelay(BaseModel):
    direction: str  # "ARR" or "DEP"
    reason: str
    reason_code: str
    avg_delay_min: int
    min_delay_str: str
    max_delay_str: str
    trend: str  # "Increasing" / "Decreasing" / "No Change"
    update_time: str


class WeatherCurrent(BaseModel):
    temp_f: int | None
    condition: str
    condition_icon: str
    wind_dir_deg: int
    wind_dir_cardinal: str
    wind_speed_kt: int
    gust_kt: int
    crosswind_kt: float
    visibility_mi: float
    severity: str  # "clear" / "moderate" / "severe"


class WeatherHourSlot(BaseModel):
    hour_iso: str
    temp_f: int | None
    condition_icon: str
    wind_speed_kt: int
    wind_dir_deg: int | None


class WeatherAlert(BaseModel):
    severity: str  # "moderate" / "severe"
    title: str
    description: str


class HourDelayStat(BaseModel):
    hour: int
    avg_delay_min: float
    max_delay_min: float
    total_flights: int
    delayed_count: int


class TerminalKPIBlock(BaseModel):
    """Per-terminal block consumed when the user is on a Terminal A/B/C tab.
    Mirrors the top-level OverviewResponse arrivals/departures shape so the
    frontend can render the full Overview layout scoped to one terminal.
    """
    terminal: str
    total_flights: int
    arr_count: int
    dep_count: int
    pred_delay_count: int
    pred_delay_arr: int
    pred_delay_dep: int
    avg_pred_delay_min: float
    high_risk_count: int  # CRITICAL only
    gate_conflict_count: int
    # Per-terminal direction overviews (timeline + hour_delay_stats + risk dist)
    arrivals: "DirectionOverview"
    departures: "DirectionOverview"


class OverviewResponse(BaseModel):
    current_time: str
    mode: str
    arrivals: "DirectionOverview"
    departures: "DirectionOverview"
    top_risk_flights: list[FlightSummary]
    delay_causes: list[DelayCause]
    gate_conflicts: list[GateConflict]
    airline_delays: list[AirlineDelay]
    faa_advisory: FAAAdvisory | None
    ground_stops: list[GroundStop]
    ground_delays: list[GroundDelay]
    weather_current: WeatherCurrent | None
    weather_hourly: list[WeatherHourSlot]
    weather_alerts: list[WeatherAlert]
    terminal_kpis: dict[str, TerminalKPIBlock]
    available_dates: list[str]


class DirectionOverview(BaseModel):
    kpi: KPIData
    timeline: list[TimelineSlot]
    terminal_stress: list[TerminalStress]
    risk_distribution: RiskDistribution
    hour_delay_stats: list[HourDelayStat]


class FlightListResponse(BaseModel):
    flights: list[FlightSummary]
    total: int
    tier_counts: RiskDistribution


class ConfigResponse(BaseModel):
    mode: str
    arrival_threshold: float
    departure_threshold: float


# Rebuild forward references
OverviewResponse.model_rebuild()
