// === API Response Types ===

export interface ShapFactor {
  feature: string;
  label: string;
  value: number;
  level: "major" | "contributing" | "minor";
}

export interface OperationalContext {
  origin_weather: string | null;
  origin_weather_severity: string | null;
  prev_aircraft_delay: number | null;
  turnaround_hours: number | null;
  route_delay_rate: number | null;
}

export interface DelayCause {
  category: string;
  label: string;
  count: number;
  percentage: number;
}

export interface FlightSummary {
  flight_id: string;
  flight: string;
  direction: "ARR" | "DEP";
  airline: string;
  remote_airport: string;
  gate: string | null;
  terminal: string | null;
  scheduled_time: string;
  risk_tier: RiskTier;
  delay_probability: number;
  pred_delay_q50: number;
  pred_delay_q10: number;
  pred_delay_q90: number;
  confidence: "HIGH" | "MODERATE";
  top_shap_label: string | null;
}

export interface FlightDetail extends FlightSummary {
  registration: string | null;
  body_type: string | null;
  runway: string | null;
  actual_time: string | null;
  actual_delay: number | null;
  is_delayed: number | null;
  shap_factors: ShapFactor[];
  operational_context: OperationalContext | null;
}

export interface KPIData {
  predicted_delays: number;
  delay_rate: number;
  avg_pred_delay: number;
  peak_stress_hour: number | null;
  total_flights: number;
}

export interface TimelineSlot {
  hour: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface TerminalStressData {
  terminal: string;
  critical_count: number;
  high_count: number;
  total_flights: number;
}

export interface RiskDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface HourDelayStat {
  hour: number;
  avg_delay_min: number;
  max_delay_min: number;
  total_flights: number;
  delayed_count: number;
}

export interface TerminalKPIBlock {
  terminal: string;
  total_flights: number;
  arr_count: number;
  dep_count: number;
  pred_delay_count: number;
  pred_delay_arr: number;
  pred_delay_dep: number;
  avg_pred_delay_min: number;
  high_risk_count: number;
  gate_conflict_count: number;
  arrivals: DirectionOverview;
  departures: DirectionOverview;
}

export interface DirectionOverview {
  kpi: KPIData;
  timeline: TimelineSlot[];
  terminal_stress: TerminalStressData[];
  risk_distribution: RiskDistribution;
  hour_delay_stats: HourDelayStat[];
}

export interface GateConflict {
  gate: string;
  terminal: string | null;
  flight_a_id: string;
  flight_a_name: string;
  flight_b_id: string;
  flight_b_name: string;
  overlap_minutes: number;
  severity: "CRITICAL" | "HIGH";
}

export interface AirlineDelay {
  airline: string;
  delayed_count: number;
  total_count: number;
  avg_delay: number;
}

export interface FAAAdvisory {
  active: boolean;
  type: string | null;
  severity: string | null;
}

export interface GroundStop {
  reason: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  remaining_minutes: number;
  advisory_url: string | null;
}

export interface GroundDelay {
  direction: "ARR" | "DEP";
  reason: string;
  reason_code: string;
  avg_delay_min: number;
  min_delay_str: string;
  max_delay_str: string;
  trend: string;
  update_time: string;
}

export interface WeatherCurrent {
  temp_f: number | null;
  condition: string;
  condition_icon: string;
  wind_dir_deg: number;
  wind_dir_cardinal: string;
  wind_speed_kt: number;
  gust_kt: number;
  crosswind_kt: number;
  visibility_mi: number;
  severity: "clear" | "moderate" | "severe";
}

export interface WeatherHourSlot {
  hour_iso: string;
  temp_f: number | null;
  condition_icon: string;
  wind_speed_kt: number;
  wind_dir_deg: number | null;
}

export interface WeatherAlert {
  severity: "moderate" | "severe";
  title: string;
  description: string;
}

export interface OverviewResponse {
  current_time: string;
  mode: string;
  arrivals: DirectionOverview;
  departures: DirectionOverview;
  top_risk_flights: FlightSummary[];
  delay_causes: DelayCause[];
  gate_conflicts: GateConflict[];
  airline_delays: AirlineDelay[];
  faa_advisory: FAAAdvisory | null;
  ground_stops: GroundStop[];
  ground_delays: GroundDelay[];
  weather_current: WeatherCurrent | null;
  weather_hourly: WeatherHourSlot[];
  weather_alerts: WeatherAlert[];
  terminal_kpis: Record<string, TerminalKPIBlock>;
  available_dates: string[];
}

export interface FlightListResponse {
  flights: FlightSummary[];
  total: number;
  tier_counts: RiskDistribution;
}

export interface ConfigResponse {
  mode: OperatingMode;
  arrival_threshold: number;
  departure_threshold: number;
}

// === App Types ===

export type RiskTier = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type OperatingMode = "balanced" | "high_precision" | "high_recall";
export type Direction = "ARR" | "DEP";

// Drill-down filter state
export interface DrilldownFilter {
  type: "all_delayed" | "risk_tier" | "hour" | "terminal";
  label: string;
  risk_tier?: RiskTier;
  hour?: number;
  terminal?: string;
}
