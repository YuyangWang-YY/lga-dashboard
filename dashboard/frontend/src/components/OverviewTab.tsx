import { useCallback, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { useLocation } from "react-router";
import {
  AlertTriangle,
  ShieldAlert,
  Timer,
  Plane,
  DoorOpen,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import departureSvg from "../imports/svg-cjk4n837oh";
import arrivalSvg from "../imports/svg-rqufs46kfk";
import FlightTable from "./FlightTable";
import { useOverview } from "../hooks/useOverview";
import { useSlideOut } from "./SlideOutContext";
import { useSimulation } from "../context/SimulationContext";
import type {
  DirectionOverview,
  FlightSummary,
  HourDelayStat,
  TimelineSlot,
} from "../lib/types";
import { formatGate } from "../lib/format";

/* ─── Inline SVG Icons ─── */
function VisibilityIcon({
  className = "w-3 h-3",
}: {
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

/* ─── Weather SVG Icons ─── */
function WeatherCloudIcon({
  className = "w-10 h-10",
}: {
  className?: string;
}) {
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none">
      <path
        d="M48 38H18a10 10 0 0 1-1.5-19.9A14 14 0 0 1 44 16a12 12 0 0 1 4 22Z"
        fill="#64748B"
        fillOpacity="0.3"
        stroke="#94A3B8"
        strokeWidth="1.5"
      />
      <line x1="22" y1="42" x2="20" y2="50" stroke="#60A5FA" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="30" y1="42" x2="28" y2="52" stroke="#60A5FA" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="38" y1="42" x2="36" y2="48" stroke="#60A5FA" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function WindCompassIcon({
  className = "w-12 h-12",
  speed,
  dirDeg,
}: {
  className?: string;
  speed?: number;
  dirDeg?: number;
}) {
  const arrowDeg = (dirDeg ?? 90) - 90; // 0=N → arrow up; subtract 90 because we draw arrow east-pointing by default
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none">
      <circle cx="32" cy="32" r="26" stroke="#3F3F46" strokeWidth="1" />
      <circle cx="32" cy="32" r="20" stroke="#27272A" strokeWidth="0.5" />
      <text x="32" y="10" textAnchor="middle" fill="#71717A" fontSize="7" fontWeight="bold">N</text>
      <text x="32" y="60" textAnchor="middle" fill="#71717A" fontSize="7" fontWeight="bold">S</text>
      <text x="7" y="35" textAnchor="middle" fill="#71717A" fontSize="7" fontWeight="bold">W</text>
      <text x="57" y="35" textAnchor="middle" fill="#71717A" fontSize="7" fontWeight="bold">E</text>
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
        <line key={deg} x1="32" y1="8" x2="32" y2="12" stroke="#3F3F46" strokeWidth="1" transform={`rotate(${deg} 32 32)`} />
      ))}
      {/* Wind direction arrow */}
      <g transform={`rotate(${arrowDeg} 32 32)`}>
        <line x1="32" y1="32" x2="52" y2="32" stroke="#00B4E2" strokeWidth="2" strokeLinecap="round" />
        <polygon points="50,28 58,32 50,36" fill="#00B4E2" />
      </g>
      <circle cx="32" cy="32" r="3" fill="#00B4E2" filter="url(#glow)" />
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <text x="32" y="46" textAnchor="middle" fill="#E4E4E7" fontSize="8" fontWeight="bold" fontFamily="monospace">
        {speed != null ? `${Math.round(speed)}kt` : "--kt"}
      </text>
    </svg>
  );
}

/* ─── Figma Arrival & Departure Icons ─── */
function ArrivalIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18.609 16.015" fill="none">
      <path d={arrivalSvg.p2a909bb0} fill="currentColor" />
    </svg>
  );
}
function DepartureIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18.2417 14.857" fill="none">
      <path d={departureSvg.p3fc25c00} fill="currentColor" />
    </svg>
  );
}

/* ─── ResizeObserver hook (callback-ref pattern so it works after conditional mount) ─── */
function useContainerSize(): {
  ref: (node: HTMLDivElement | null) => void;
  size: { width: number; height: number };
} {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const observerRef = useRef<ResizeObserver | null>(null);
  const ref = useCallback((node: HTMLDivElement | null) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (node) {
      observerRef.current = new ResizeObserver((entries) => {
        const { width, height } = entries[0].contentRect;
        setSize({ width: Math.floor(width), height: Math.floor(height) });
      });
      observerRef.current.observe(node);
    }
  }, []);
  return { ref, size };
}

/* ─── Colors ─── */
const COLORS = {
  text: "#F4F4F5",
  muted: "#71717A",
  grid: "rgba(255,255,255,0.03)",
  pastOnTime: "#27272A",
  pastDelay: "#9F1239",
  predCrit: "#F43F5E",
  predHigh: "#FBBF24",
  predMed: "#00B4E2",
  predLow: "#036A4E",
};

/* ─── Custom Tooltip ─── */
const TOOLTIP_LABELS: Record<string, string> = {
  actualOnTime: "On Time",
  actualDelayed: "Delayed",
  predCrit: "Critical",
  predHigh: "High",
  predMed: "Med",
  predLow: "Low",
};
const TOOLTIP_COLORS: Record<string, string> = {
  actualOnTime: "#A1A1AA",
  actualDelayed: COLORS.pastDelay,
  predCrit: COLORS.predCrit,
  predHigh: COLORS.predHigh,
  predMed: COLORS.predMed,
  predLow: COLORS.predLow,
};
function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: any[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const entries = payload.filter((p) => (p.value as number) > 0);
  if (!entries.length) return null;
  return (
    <div style={{
      backgroundColor: "#18181B",
      borderRadius: 6,
      padding: "6px 10px",
      fontSize: 10,
      boxShadow: "0 8px 20px rgba(0,0,0,0.5)",
      color: "#F4F4F5",
      minWidth: 110,
    }}>
      <div style={{ marginBottom: 4, color: "#71717A", fontFamily: "monospace" }}>{label}</div>
      {entries.map((p) => {
        const color = TOOLTIP_COLORS[p.dataKey] ?? p.color;
        return (
          <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={{ width: 6, height: 6, borderRadius: 1, backgroundColor: color, display: "inline-block", flexShrink: 0 }} />
            <span style={{ color }}>{TOOLTIP_LABELS[p.dataKey] ?? p.dataKey}</span>
            <span style={{ marginLeft: "auto", fontFamily: "monospace", paddingLeft: 12 }}>{p.value}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Helper: severity color (for delay-by-hour table rows) ─── */
function delayCellColor(avg: number) {
  if (avg === 0) return "text-zinc-600";
  if (avg >= 100) return "text-rose-400";
  if (avg >= 40) return "text-amber-400";
  return "text-[#00B4E2]";
}

/* ─── Build chart data: merge past actual + future predicted into one 24-row series ─── */
type ChartRow = {
  time: string;
  actualOnTime: number;
  actualDelayed: number;
  predLow: number;
  predMed: number;
  predHigh: number;
  predCrit: number;
};

function buildChartData(
  timeline: TimelineSlot[],
  hourDelayStats: HourDelayStat[],
  nowHour: number
): { rows: ChartRow[]; nowLabel: string } {
  // Map hour → past stats
  const pastByHour = new Map<number, HourDelayStat>();
  hourDelayStats.forEach((s) => pastByHour.set(s.hour, s));
  // Map hour → future tier counts
  const futureByHour = new Map<number, TimelineSlot>();
  timeline.forEach((t) => futureByHour.set(t.hour, t));

  const rows: ChartRow[] = [];
  for (let h = 0; h < 24; h++) {
    const isPast = h < nowHour;
    const time = `${String(h).padStart(2, "0")}:00`;
    if (isPast) {
      const past = pastByHour.get(h);
      const total = past?.total_flights ?? 0;
      const delayed = past?.delayed_count ?? 0;
      rows.push({
        time,
        actualOnTime: Math.max(0, total - delayed),
        actualDelayed: delayed,
        predLow: 0,
        predMed: 0,
        predHigh: 0,
        predCrit: 0,
      });
    } else {
      const future = futureByHour.get(h);
      rows.push({
        time,
        actualOnTime: 0,
        actualDelayed: 0,
        predLow: future?.low ?? 0,
        predMed: future?.medium ?? 0,
        predHigh: future?.high ?? 0,
        predCrit: future?.critical ?? 0,
      });
    }
  }
  return { rows, nowLabel: `${String(nowHour).padStart(2, "0")}:00` };
}

/* ─── Hour delay table rows from stats ─── */
function formatHourDelayRows(stats: HourDelayStat[]) {
  return stats
    .filter((s) => s.total_flights > 0)
    .map((s) => ({
      hour: s.hour,
      avg: s.avg_delay_min,
      max: s.max_delay_min,
    }));
}

/* ═══════════════════════════════════════ COMPONENT ═══════════════════════════════════════ */

export default function OverviewTab() {
  const { ref: arrRef, size: arrSize } = useContainerSize();
  const { ref: depRef, size: depSize } = useContainerSize();
  const [riskFilter, setRiskFilter] = useState<"all" | "arr" | "dep">("all");
  const [showFlightTable, setShowFlightTable] = useState(false);

  const { data, loading } = useOverview();
  const { openSlideOut } = useSlideOut();
  const sim = useSimulation();
  const location = useLocation();

  // Detect terminal scoping from route. Backend keys are "Terminal A/B/C".
  const terminalKey = useMemo(() => {
    if (location.pathname === "/terminal-a") return "Terminal A";
    if (location.pathname === "/terminal-b") return "Terminal B";
    if (location.pathname === "/terminal-c") return "Terminal C";
    return null;
  }, [location.pathname]);

  // Compute "now" hour from sim time
  const nowHour = sim.currentTime.getHours();

  // Pick the right DirectionOverview pair: terminal-scoped if on a Terminal tab,
  // otherwise the airport-wide top-level blocks.
  const arrDir: DirectionOverview | null = useMemo(() => {
    if (!data) return null;
    if (terminalKey && data.terminal_kpis[terminalKey]) {
      return data.terminal_kpis[terminalKey].arrivals;
    }
    return data.arrivals;
  }, [data, terminalKey]);
  const depDir: DirectionOverview | null = useMemo(() => {
    if (!data) return null;
    if (terminalKey && data.terminal_kpis[terminalKey]) {
      return data.terminal_kpis[terminalKey].departures;
    }
    return data.departures;
  }, [data, terminalKey]);

  // Build arrival/departure chart data from the (possibly scoped) DirectionOverviews
  const arrChart = useMemo(() => {
    if (!arrDir) return null;
    return buildChartData(arrDir.timeline, arrDir.hour_delay_stats, nowHour);
  }, [arrDir, nowHour]);
  const depChart = useMemo(() => {
    if (!depDir) return null;
    return buildChartData(depDir.timeline, depDir.hour_delay_stats, nowHour);
  }, [depDir, nowHour]);

  // Filtered top risk flights — when in a terminal tab, the terminal field on
  // FlightSummary is "Terminal A/B/C" too.
  const filteredHighRisk: FlightSummary[] = useMemo(() => {
    if (!data) return [];
    let flights = data.top_risk_flights;
    if (riskFilter === "arr") flights = flights.filter((f) => f.direction === "ARR");
    if (riskFilter === "dep") flights = flights.filter((f) => f.direction === "DEP");
    if (terminalKey) flights = flights.filter((f) => f.terminal === terminalKey);
    return flights;
  }, [data, riskFilter, terminalKey]);

  // KPI block — terminal-scoped if in a terminal route, otherwise full airport
  const kpiBlock = useMemo(() => {
    if (!data) return null;
    if (terminalKey && data.terminal_kpis[terminalKey]) {
      const t = data.terminal_kpis[terminalKey];
      return {
        total: t.total_flights,
        arr: t.arr_count,
        dep: t.dep_count,
        predDelays: t.pred_delay_count,
        predDelayArr: t.pred_delay_arr,
        predDelayDep: t.pred_delay_dep,
        avgPredDelay: t.avg_pred_delay_min,
        highRisk: t.high_risk_count,
        gateConflicts: t.gate_conflict_count,
      };
    }
    const arr = data.arrivals;
    const dep = data.departures;
    return {
      total: arr.kpi.total_flights + dep.kpi.total_flights,
      arr: arr.kpi.total_flights,
      dep: dep.kpi.total_flights,
      predDelays: arr.kpi.predicted_delays + dep.kpi.predicted_delays,
      predDelayArr: arr.kpi.predicted_delays,
      predDelayDep: dep.kpi.predicted_delays,
      avgPredDelay: (arr.kpi.avg_pred_delay + dep.kpi.avg_pred_delay) / 2,
      highRisk:
        arr.risk_distribution.critical +
        arr.risk_distribution.high +
        dep.risk_distribution.critical +
        dep.risk_distribution.high,
      gateConflicts: data.gate_conflicts.length,
    };
  }, [data, terminalKey]);

  if (loading && !data) {
    return (
      <div className="flex-1 flex items-center justify-center text-[11px] font-mono uppercase tracking-widest text-zinc-500">
        Loading dashboard...
      </div>
    );
  }
  if (!data || !kpiBlock || !arrChart || !depChart || !arrDir || !depDir) {
    return (
      <div className="flex-1 flex items-center justify-center text-[11px] font-mono uppercase tracking-widest text-zinc-500">
        No data
      </div>
    );
  }

  // Weather summary
  const wx = data.weather_current;
  const weatherAlerts = data.weather_alerts;
  const groundStops = data.ground_stops;
  const groundDelays = data.ground_delays;

  const arrChartCounts = aggregateRiskCounts(arrDir);
  const depChartCounts = aggregateRiskCounts(depDir);
  const arrDelayedPast = sumDelayed(arrDir.hour_delay_stats);
  const depDelayedPast = sumDelayed(depDir.hour_delay_stats);
  const arrOnTimePast = sumOnTime(arrDir.hour_delay_stats);
  const depOnTimePast = sumOnTime(depDir.hour_delay_stats);

  const arrDelayRows = formatHourDelayRows(arrDir.hour_delay_stats);
  const depDelayRows = formatHourDelayRows(depDir.hour_delay_stats);

  // Total alert count = ground stops + ground delays + weather alerts
  const totalAlerts =
    groundStops.length + groundDelays.length + weatherAlerts.length;

  return (
    <div className="flex flex-col h-full gap-3 animate-in fade-in duration-500 min-h-0">
      {/* ═══ ROW 1 & 2: WEATHER + KPI with merged ALERTS tower ═══ */}
      <div className="flex gap-3 shrink-0">
        {/* Left: Weather + KPI stacked */}
        <div className="flex-1 flex flex-col justify-between gap-3 min-w-0">
          {/* Weather Row */}
          <div className="flex gap-3">
            {/* Current Weather — large temp hero */}
            <div className="flex items-center gap-4 bg-[#0F0F11] rounded-xl px-5 py-1.5 ring-1 ring-white/[0.08]">
              <WeatherCloudIcon className="w-8 h-8" />
              <div className="flex flex-col">
                <span className="font-bold text-zinc-100 leading-none font-mono tracking-tight text-[16px]">
                  {wx?.temp_f != null ? `${Math.round(wx.temp_f)}°F` : "--°F"}
                </span>
                <span className="text-zinc-400 mt-0.5 text-[10px]">
                  {wx?.condition ?? "—"}
                </span>
                <div className="flex items-center gap-1 mt-0.5">
                  <VisibilityIcon className="w-3 h-3 text-zinc-500" />
                  <span className="text-[10px] text-zinc-500">
                    Vis {wx?.visibility_mi?.toFixed(0) ?? "?"}mi
                  </span>
                </div>
              </div>
            </div>

            {/* Wind — compass style */}
            <div className="flex items-center gap-3 bg-[#0F0F11] rounded-xl px-4 py-1.5 ring-1 ring-white/[0.08]">
              <WindCompassIcon
                className="w-10 h-10"
                speed={wx?.wind_speed_kt}
                dirDeg={wx?.wind_dir_deg}
              />
              <div className="flex flex-col">
                <span className="text-[10px] text-zinc-500 mt-0.5">
                  Gust {wx?.gust_kt != null ? Math.round(wx.gust_kt) : "--"}kt
                </span>
                <span className="text-[10px] text-amber-400">
                  Cross {wx?.crosswind_kt != null ? Math.round(wx.crosswind_kt) : "--"}kt
                </span>
              </div>
            </div>

            {/* 24H Forecast */}
            <div className="flex-1 flex items-stretch bg-[#0F0F11] rounded-xl px-2 py-1.5 ring-1 ring-white/[0.08] overflow-hidden gap-1">
              {(() => {
                // Show next 12 hours starting from now (filter out past slots)
                const slots = data.weather_hourly.filter((s) => {
                  const h = new Date(s.hour_iso).getTime();
                  return h >= sim.currentTime.getTime() - 60 * 60 * 1000; // include current hour
                }).slice(0, 12);
                return slots;
              })().map((slot, i) => {
                const slotHour = new Date(slot.hour_iso).getHours();
                const isNow = slotHour === nowHour;
                const labelHour = String(slotHour).padStart(2, "0") + ":00";
                return (
                  <div
                    key={`fc-${i}`}
                    className={clsx(
                      "flex flex-col items-center justify-between gap-0.5 flex-1 rounded-md py-1 px-0.5",
                      isNow
                        ? "bg-[#00B4E2]/10 ring-1 ring-[#00B4E2]/30"
                        : "ring-1 ring-white/[0.04]"
                    )}
                  >
                    {/* Time */}
                    <span
                      className={clsx(
                        "text-[8px] font-mono leading-none uppercase tracking-widest",
                        isNow ? "text-[#00B4E2] font-bold" : "text-zinc-500"
                      )}
                    >
                      {isNow ? "Now" : labelHour}
                    </span>
                    {/* Weather icon */}
                    <span className="text-[14px] leading-none">
                      {slot.condition_icon || "·"}
                    </span>
                    {/* Temp */}
                    <span
                      className={clsx(
                        "text-[11px] font-mono font-bold leading-none",
                        isNow ? "text-zinc-100" : "text-zinc-300"
                      )}
                    >
                      {slot.temp_f != null ? `${slot.temp_f}°` : "—"}
                    </span>
                    {/* Wind arrow + speed */}
                    <span className="flex items-center gap-0.5 text-[8px] font-mono leading-none text-zinc-500">
                      {slot.wind_dir_deg != null ? (
                        <svg
                          width="7"
                          height="7"
                          viewBox="0 0 10 10"
                          className="shrink-0"
                          style={{ transform: `rotate(${slot.wind_dir_deg}deg)` }}
                        >
                          <path
                            d="M5 1 L8 8 L5 6 L2 8 Z"
                            fill="currentColor"
                          />
                        </svg>
                      ) : null}
                      {slot.wind_speed_kt}kt
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* KPI Row */}
          <div className="flex gap-3 flex-1">
            <div
              onClick={() => setShowFlightTable(true)}
              className="flex-1 basis-0 bg-gradient-to-br from-[#00B4E2]/20 to-[#00B4E2]/5 rounded-xl px-4 py-2.5 ring-1 ring-[#00B4E2]/20 flex flex-col justify-center min-w-0 h-full cursor-pointer hover:ring-[#00B4E2]/40 transition-all group relative"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[#00B4E2]">
                  <Plane className="w-4 h-4" />
                </span>
                <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500 truncate">
                  TOTAL FLIGHTS
                </span>
                <span className="ml-auto text-[8px] font-bold uppercase tracking-widest text-[#00B4E2]/60 group-hover:text-[#00B4E2] transition-colors flex items-center gap-0.5">
                  View All
                  <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-bold text-zinc-100 leading-none font-mono text-[20px]">
                  {kpiBlock.total}
                </span>
              </div>
              <span className="text-[10px] text-zinc-600 mt-1 truncate">
                {kpiBlock.arr} ARR · {kpiBlock.dep} DEP
              </span>
            </div>
            <KPICard
              icon={<AlertTriangle className="w-4 h-4" />}
              label="PREDICTED DELAYS"
              value={String(kpiBlock.predDelays)}
              sub={`${kpiBlock.predDelayArr} ARR · ${kpiBlock.predDelayDep} DEP`}
              accent="rose"
            />
            <KPICard
              icon={<Timer className="w-4 h-4" />}
              label="AVG DELAY"
              value={`+${Math.round(kpiBlock.avgPredDelay)}m`}
              sub="predicted average"
              accent="amber"
            />
            <KPICard
              icon={<ShieldAlert className="w-4 h-4" />}
              label="HIGH RISK"
              value={String(kpiBlock.highRisk)}
              sub="act now"
              accent="rose"
            />
            <KPICard
              icon={<DoorOpen className="w-4 h-4" />}
              label="GATE CONFLICTS"
              value={String(kpiBlock.gateConflicts)}
              sub={
                data.gate_conflicts.length > 0
                  ? `${Array.from(
                      new Set(data.gate_conflicts.map((g) => g.terminal).filter(Boolean))
                    )
                      .map((t) => `Terminal ${t}`)
                      .join(", ")}`
                  : "no conflicts"
              }
              accent="amber"
            />
          </div>
        </div>

        {/* Right: Merged Alerts Tower */}
        <div className="w-[220px] shrink-0 bg-[#0F0F11] rounded-xl ring-1 ring-white/[0.08] flex flex-col overflow-hidden">
          {/* Header */}
          <div className="px-3 py-1.5 flex items-center gap-2 border-b border-white/[0.03]">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">
              Alerts
            </span>
            <span className="ml-auto text-[9px] font-bold font-mono text-amber-400 bg-amber-500/15 px-1.5 py-0.5 rounded">
              {totalAlerts}
            </span>
          </div>

          {/* Compact alert list */}
          <div className="px-3 py-1.5 flex-1 space-y-2 overflow-y-auto">
            {weatherAlerts.length > 0 && (
              <div>
                <span className="text-[8px] font-bold uppercase tracking-widest text-zinc-600 block mb-1">
                  Weather
                </span>
                <div className="space-y-0.5">
                  {weatherAlerts.map((wa, i) => (
                    <div key={`wa-${i}`} className="flex items-center gap-1.5">
                      <span className={clsx("text-[9px]", wa.severity === "severe" ? "text-rose-400" : "text-amber-400")}>
                        ⚠
                      </span>
                      <span className={clsx("text-[10px] truncate", wa.severity === "severe" ? "text-rose-400" : "text-amber-400")}>
                        {wa.title}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {(groundStops.length > 0 || groundDelays.length > 0) && (
              <div>
                <span className="text-[8px] font-bold uppercase tracking-widest text-zinc-600 block mb-1">
                  FAA
                </span>
                <div className="space-y-0.5">
                  {groundStops.map((gs, i) => (
                    <div key={`gs-${i}`} className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-rose-500 shrink-0" />
                      <span className="text-[10px] text-rose-400 truncate">
                        Ground Stop · {gs.reason}
                      </span>
                    </div>
                  ))}
                  {groundDelays.map((gd, i) => (
                    <div key={`gd-${i}`} className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-amber-400 shrink-0" />
                      <span className="text-[10px] text-amber-400 truncate">
                        {gd.direction} GDP · avg +{Math.round(gd.avg_delay_min)}m
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {totalAlerts === 0 && (
              <div className="text-[10px] text-zinc-600 italic">No active alerts</div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ ROW 3: MAIN 3-COLUMN ═══ */}
      {showFlightTable ? (
        <FlightTable
          onClose={() => setShowFlightTable(false)}
          terminal={terminalKey ?? undefined}
        />
      ) : (
        <div className="flex-1 flex gap-3 min-h-0 overflow-hidden">
          {/* LEFT: High Risk Flights */}
          <div className="w-[280px] shrink-0 flex flex-col bg-[#0F0F11] rounded-xl ring-1 ring-white/[0.08] overflow-hidden">
            <div className="px-4 py-2.5 flex items-center gap-2 shrink-0 border-b border-white/[0.03]">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                High risk
              </span>
              <div className="ml-auto flex gap-0.5 bg-[#0A0A0C] rounded-md p-0.5">
                {(["all", "arr", "dep"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setRiskFilter(f)}
                    className={clsx(
                      "text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded transition-all",
                      riskFilter === f ? "bg-white/[0.08] text-zinc-200" : "text-zinc-600 hover:text-zinc-400"
                    )}
                  >
                    {f === "all" ? "All" : f === "arr" ? "Arr" : "Dep"}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {filteredHighRisk.length === 0 && (
                <div className="text-[10px] text-zinc-600 italic px-2 py-4">No high-risk flights</div>
              )}
              {filteredHighRisk.map((flt) => {
                const isCrit = flt.risk_tier === "CRITICAL";
                const isHigh = flt.risk_tier === "HIGH";
                const gateLabel = formatGate(flt.gate);
                const route =
                  flt.direction === "ARR"
                    ? `${flt.remote_airport} → LGA · Gate ${gateLabel}`
                    : `LGA → ${flt.remote_airport} · Gate ${gateLabel}`;
                const delayMin = Math.max(0, Math.round(flt.pred_delay_q50));
                return (
                  <div
                    key={flt.flight_id}
                    onClick={() => openSlideOut(flt.flight_id)}
                    className="bg-[#0A0A0C] rounded-lg p-3 ring-1 ring-white/[0.08] hover:ring-white/[0.12] transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-[13px] text-zinc-100">
                          {flt.flight}
                        </span>
                        <span
                          className={clsx(
                            "text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded flex items-center gap-1",
                            flt.direction === "ARR"
                              ? "bg-teal-500/15 text-teal-400"
                              : "bg-violet-500/15 text-violet-400"
                          )}
                        >
                          {flt.direction === "ARR" ? <ArrivalIcon className="w-3 h-3" /> : <DepartureIcon className="w-3 h-3" />}
                          {flt.direction}
                        </span>
                      </div>
                      <span
                        className={clsx(
                          "text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded",
                          isCrit
                            ? "bg-rose-500/15 text-rose-400"
                            : isHigh
                            ? "bg-amber-500/15 text-amber-400"
                            : "bg-[#00B4E2]/15 text-[#00B4E2]"
                        )}
                      >
                        {flt.risk_tier}
                      </span>
                    </div>
                    <div className="text-[10px] text-zinc-500 mb-1 truncate">{route}</div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-zinc-400">{flt.airline}</span>
                      <span
                        className={clsx(
                          "font-mono font-bold text-[13px]",
                          isCrit ? "text-rose-400" : isHigh ? "text-amber-400" : "text-[#00B4E2]"
                        )}
                      >
                        +{delayMin}m
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* CENTER: Charts */}
          <div className="flex-1 flex flex-col gap-3 min-h-0 min-w-0">
            {/* Arrivals Chart */}
            <div className="flex-1 bg-[#0F0F11] rounded-xl flex flex-col overflow-hidden relative ring-1 ring-white/[0.08] min-h-0">
              <div className="absolute top-3 left-4 flex items-center gap-2 z-10 pointer-events-none">
                <span className="text-teal-400">
                  <ArrivalIcon />
                </span>
                <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">Arrivals</span>
                <span className="text-[15px] font-bold text-zinc-100 font-mono ml-2">
                  {arrDir.kpi.total_flights}
                </span>
                <span className="text-[10px] text-zinc-500 ml-0">flights</span>
              </div>
              <div className="absolute top-3 right-4 flex gap-3 text-[8px] font-bold uppercase tracking-widest text-zinc-600 z-10 pointer-events-none">
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-zinc-700" />
                  <span className="text-zinc-400 font-mono normal-case">{arrOnTimePast}</span>{" "}
                  On Time
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-rose-900" />
                  <span className="text-zinc-500 font-mono normal-case">{arrDelayedPast}</span>{" "}
                  Delayed
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-rose-500" />
                  <span className="text-rose-400 font-mono normal-case">{arrChartCounts.crit}</span>{" "}
                  Crit
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-amber-400" />
                  <span className="text-amber-400 font-mono normal-case">{arrChartCounts.high}</span>{" "}
                  High
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-[#00B4E2]" />
                  <span className="text-[#00B4E2] font-mono normal-case">{arrChartCounts.med}</span>{" "}
                  Med
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-sm" style={{ backgroundColor: "#036A4E" }} />
                  <span className="text-emerald-500 font-mono normal-case">{arrChartCounts.low}</span>{" "}
                  Low
                </div>
              </div>
              <div ref={arrRef} className="flex-1 w-full px-2 pt-10 pb-1 min-h-0">
                {arrSize.width > 0 && arrSize.height > 0 && (
                  <BarChart
                    width={arrSize.width}
                    height={arrSize.height}
                    data={arrChart.rows}
                    margin={{ top: 5, right: 5, left: -25, bottom: 0 }}
                    barGap={2}
                  >
                    <CartesianGrid key="arr-grid" strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
                    <XAxis key="arr-x" dataKey="time" stroke={COLORS.muted} fontSize={8} tickLine={false} axisLine={false} dy={4} />
                    <YAxis key="arr-y" stroke={COLORS.muted} fontSize={8} tickLine={false} axisLine={false} dx={-4} />
                    <Tooltip
                      key="arr-tip"
                      cursor={{ fill: "rgba(255,255,255,0.02)" }}
                      content={<ChartTooltip />}
                    />
                    <ReferenceLine key="arr-cap" y={30} stroke={COLORS.muted} strokeDasharray="2 4" />
                    <ReferenceLine key="arr-now" x={arrChart.nowLabel} stroke={COLORS.text} strokeWidth={1.5} />
                    <Bar key="arr-ontime" dataKey="actualOnTime" stackId="a" fill={COLORS.pastOnTime} onClick={() => setShowFlightTable(true)} />
                    <Bar key="arr-delayed" dataKey="actualDelayed" stackId="a" fill={COLORS.pastDelay} onClick={() => setShowFlightTable(true)} />
                    <Bar key="arr-low" dataKey="predLow" stackId="b" fill={COLORS.predLow} onClick={() => setShowFlightTable(true)} />
                    <Bar key="arr-med" dataKey="predMed" stackId="b" fill={COLORS.predMed} onClick={() => setShowFlightTable(true)} />
                    <Bar key="arr-high" dataKey="predHigh" stackId="b" fill={COLORS.predHigh} onClick={() => setShowFlightTable(true)} />
                    <Bar key="arr-crit" dataKey="predCrit" stackId="b" fill={COLORS.predCrit} onClick={() => setShowFlightTable(true)} />
                  </BarChart>
                )}
              </div>
            </div>

            {/* Departures Chart */}
            <div className="flex-1 bg-[#0F0F11] rounded-xl flex flex-col overflow-hidden relative ring-1 ring-white/[0.08] min-h-0">
              <div className="absolute top-3 left-4 flex items-center gap-2 z-10 pointer-events-none">
                <span className="text-violet-400">
                  <DepartureIcon />
                </span>
                <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">Departures</span>
                <span className="text-[15px] font-bold text-zinc-100 font-mono ml-2">
                  {depDir.kpi.total_flights}
                </span>
                <span className="text-[10px] text-zinc-500 ml-0">flights</span>
              </div>
              <div className="absolute top-3 right-4 flex gap-3 text-[8px] font-bold uppercase tracking-widest text-zinc-600 z-10 pointer-events-none">
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-zinc-700" />
                  <span className="text-zinc-400 font-mono normal-case">{depOnTimePast}</span>{" "}
                  On Time
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-rose-900" />
                  <span className="text-zinc-500 font-mono normal-case">{depDelayedPast}</span>{" "}
                  Delayed
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-rose-500" />
                  <span className="text-rose-400 font-mono normal-case">{depChartCounts.crit}</span>{" "}
                  Crit
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-amber-400" />
                  <span className="text-amber-400 font-mono normal-case">{depChartCounts.high}</span>{" "}
                  High
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-[#00B4E2]" />
                  <span className="text-[#00B4E2] font-mono normal-case">{depChartCounts.med}</span>{" "}
                  Med
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-sm" style={{ backgroundColor: "#036A4E" }} />
                  <span className="text-emerald-500 font-mono normal-case">{depChartCounts.low}</span>{" "}
                  Low
                </div>
              </div>
              <div ref={depRef} className="flex-1 w-full px-2 pt-10 pb-1 min-h-0">
                {depSize.width > 0 && depSize.height > 0 && (
                  <BarChart
                    width={depSize.width}
                    height={depSize.height}
                    data={depChart.rows}
                    margin={{ top: 5, right: 5, left: -25, bottom: 0 }}
                    barGap={2}
                  >
                    <CartesianGrid key="dep-grid" strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
                    <XAxis key="dep-x" dataKey="time" stroke={COLORS.muted} fontSize={8} tickLine={false} axisLine={false} dy={4} />
                    <YAxis key="dep-y" stroke={COLORS.muted} fontSize={8} tickLine={false} axisLine={false} dx={-4} />
                    <Tooltip
                      key="dep-tip"
                      cursor={{ fill: "rgba(255,255,255,0.02)" }}
                      content={<ChartTooltip />}
                    />
                    <ReferenceLine key="dep-cap" y={32} stroke={COLORS.muted} strokeDasharray="2 4" />
                    <ReferenceLine key="dep-now" x={depChart.nowLabel} stroke={COLORS.text} strokeWidth={1.5} />
                    <Bar key="dep-ontime" dataKey="actualOnTime" stackId="a" fill={COLORS.pastOnTime} onClick={() => setShowFlightTable(true)} />
                    <Bar key="dep-delayed" dataKey="actualDelayed" stackId="a" fill={COLORS.pastDelay} onClick={() => setShowFlightTable(true)} />
                    <Bar key="dep-low" dataKey="predLow" stackId="b" fill={COLORS.predLow} onClick={() => setShowFlightTable(true)} />
                    <Bar key="dep-med" dataKey="predMed" stackId="b" fill={COLORS.predMed} onClick={() => setShowFlightTable(true)} />
                    <Bar key="dep-high" dataKey="predHigh" stackId="b" fill={COLORS.predHigh} onClick={() => setShowFlightTable(true)} />
                    <Bar key="dep-crit" dataKey="predCrit" stackId="b" fill={COLORS.predCrit} onClick={() => setShowFlightTable(true)} />
                  </BarChart>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT: Delay Tables */}
          <div className="w-[220px] shrink-0 flex flex-col gap-3 min-h-0">
            <DelayByHourTable title="Arrival Delays by Hour" rows={arrDelayRows} />
            <DelayByHourTable title="Depart Delays by Hour" rows={depDelayRows} />
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Risk count aggregator (sum across timeline slots) ─── */
function aggregateRiskCounts(direction: DirectionOverview) {
  return direction.timeline.reduce(
    (acc, t) => ({
      crit: acc.crit + t.critical,
      high: acc.high + t.high,
      med: acc.med + t.medium,
      low: acc.low + t.low,
    }),
    { crit: 0, high: 0, med: 0, low: 0 }
  );
}

function sumDelayed(stats: HourDelayStat[]) {
  return stats.reduce((s, r) => s + r.delayed_count, 0);
}

function sumOnTime(stats: HourDelayStat[]) {
  return stats.reduce((s, r) => s + Math.max(0, r.total_flights - r.delayed_count), 0);
}

/* ─── Delay-by-hour table component ─── */
function DelayByHourTable({
  title,
  rows,
}: {
  title: string;
  rows: { hour: number; avg: number; max: number }[];
}) {
  const avgRows = rows.filter((r) => r.avg > 0);
  const totalAvg = avgRows.length > 0 ? avgRows.reduce((s, r) => s + r.avg, 0) / avgRows.length : 0;
  const totalMax = rows.length > 0 ? Math.max(...rows.map((r) => r.max)) : 0;
  return (
    <div className="flex-1 bg-[#0F0F11] rounded-xl ring-1 ring-white/[0.08] flex flex-col overflow-hidden min-h-0">
      <div className="px-3 py-2 shrink-0 border-b border-white/[0.03]">
        <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">{title}</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[10px] font-mono">
          <thead>
            <tr className="text-zinc-600 text-[8px] uppercase tracking-widest">
              <th className="text-left px-3 py-1.5 font-bold">Hour</th>
              <th className="text-right px-2 py-1.5 font-bold">Avg Delay</th>
              <th className="text-right px-3 py-1.5 font-bold">Max in Block</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-2 text-zinc-600 italic text-center">
                  No delay data
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={`row-${r.hour}`} className="border-t border-white/[0.02]">
                <td className="px-3 py-1.5 text-zinc-300">{r.hour}</td>
                <td className={clsx("text-right px-2 py-1.5", delayCellColor(r.avg))}>{r.avg.toFixed(1)}</td>
                <td className={clsx("text-right px-3 py-1.5", delayCellColor(r.max))}>{Math.round(r.max)}</td>
              </tr>
            ))}
            {rows.length > 0 && (
              <tr className="border-t border-white/[0.04] bg-white/[0.02]">
                <td className="px-3 py-1.5 font-bold text-zinc-300">Total</td>
                <td className="text-right px-2 py-1.5 font-bold text-zinc-200">{totalAvg.toFixed(1)}</td>
                <td className="text-right px-3 py-1.5 font-bold text-zinc-200">{Math.round(totalMax)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── KPI Card Component ─── */
function KPICard({
  icon,
  label,
  value,
  valueSuffix,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueSuffix?: string;
  sub: string;
  accent: "blue" | "amber" | "rose";
}) {
  const accentMap = {
    blue: "from-[#00B4E2]/20 to-[#00B4E2]/5 ring-[#00B4E2]/20",
    amber: "from-amber-500/20 to-amber-500/5 ring-amber-500/20",
    rose: "from-rose-500/20 to-rose-500/5 ring-rose-500/20",
  };
  const iconColor = {
    blue: "text-[#00B4E2]",
    amber: "text-amber-400",
    rose: "text-rose-400",
  };
  return (
    <div
      className={clsx(
        "flex-1 basis-0 bg-gradient-to-br rounded-xl px-4 py-2.5 ring-1 flex flex-col justify-center min-w-0 h-full",
        accentMap[accent]
      )}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className={iconColor[accent]}>{icon}</span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500 truncate">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-bold text-zinc-100 leading-none font-mono text-[20px]">{value}</span>
        {valueSuffix && <span className="text-[10px] text-zinc-500">{valueSuffix}</span>}
      </div>
      <span className="text-[10px] text-zinc-600 mt-1 truncate">{sub}</span>
    </div>
  );
}
