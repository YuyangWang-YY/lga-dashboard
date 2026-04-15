import { useMemo, useState } from "react";
import { Filter, ArrowUpDown, Clock } from "lucide-react";
import { useSlideOut } from "./SlideOutContext";
import clsx from "clsx";
import { useLocation } from "react-router";
import { useFlights } from "../hooks/useFlights";
import type { FlightSummary } from "../lib/types";
import { formatGate } from "../lib/format";

type SortKey = "risk" | "time" | "delay";
type TerminalFilter = "all" | "A" | "B" | "C";

const SORT_TO_API: Record<SortKey, string> = {
  risk: "delay_probability",
  time: "time",
  delay: "delay",
};

function formatEta(scheduledIso: string): string {
  const sched = new Date(scheduledIso).getTime();
  const now = Date.now();
  const diffMin = Math.round((sched - now) / 60000);
  if (diffMin > 60) {
    const h = Math.floor(diffMin / 60);
    const m = diffMin % 60;
    return `in ${h}h ${m}m`;
  }
  if (diffMin > 0) return `in ${diffMin}m`;
  if (diffMin === 0) return "now";
  if (diffMin > -60) return `${-diffMin}m ago`;
  return "passed";
}

export default function FlightsTab() {
  const { openSlideOut } = useSlideOut();
  const location = useLocation();

  const direction: "ARR" | "DEP" = location.pathname === "/arrivals" ? "ARR" : "DEP";
  const directionLabel = direction === "ARR" ? "Arrivals" : "Departures";

  const [terminal, setTerminal] = useState<TerminalFilter>("all");
  const [airline, setAirline] = useState<string>("all");
  const [sortBy, setSortBy] = useState<SortKey>("risk");

  const { data, loading } = useFlights({
    direction,
    terminal: terminal === "all" ? undefined : terminal,
    airline: airline === "all" ? undefined : airline,
    sortBy: SORT_TO_API[sortBy],
    sortDesc: true,
    limit: 200,
  });

  const flights: FlightSummary[] = data?.flights ?? [];

  // Build airline dropdown options from current results
  const airlineOptions = useMemo(() => {
    const set = new Set<string>();
    flights.forEach((f) => set.add(f.airline));
    return Array.from(set).sort();
  }, [flights]);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* Controls Row */}
      <div className="flex items-center justify-between bg-[#161B22] border border-[#30363D] p-3 rounded-lg shadow-sm">
        <div className="flex gap-2">
          {(["all", "A", "B", "C"] as const).map((term) => {
            const label = term === "all" ? "All Terminals" : `T${term}`;
            const active = terminal === term;
            return (
              <button
                key={term}
                onClick={() => setTerminal(term)}
                className={clsx(
                  "px-4 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-colors",
                  active ? "bg-[#30363D] text-[#E6EDF3]" : "text-[#8B949E] hover:bg-[#21262D] hover:text-[#E6EDF3]"
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 border-r border-[#30363D] pr-4">
            <Filter className="w-3.5 h-3.5 text-[#8B949E]" />
            <select
              value={airline}
              onChange={(e) => setAirline(e.target.value)}
              className="bg-[#0B0C10] border border-[#30363D] text-[#E6EDF3] text-[13px] rounded px-2 py-1 outline-none focus:border-blue-500/50"
            >
              <option value="all">All Airlines</option>
              {airlineOptions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2 border-r border-[#30363D] pr-4">
            <span className="text-[10px] uppercase font-bold tracking-widest text-[#8B949E]">Sort:</span>
            {(["risk", "time", "delay"] as const).map((s) => {
              const active = sortBy === s;
              const label = s === "risk" ? "Risk" : s === "time" ? "Time" : "Delay";
              return (
                <button
                  key={s}
                  onClick={() => setSortBy(s)}
                  className={clsx(
                    "flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest px-2.5 py-1.5 rounded transition-colors",
                    active
                      ? "text-[#E6EDF3] bg-[#30363D] shadow-sm"
                      : "text-[#8B949E] hover:text-[#E6EDF3]"
                  )}
                >
                  {label} {active && <ArrowUpDown className="w-3 h-3" />}
                </button>
              );
            })}
          </div>

          <div className="text-[10px] font-bold text-[#8B949E] uppercase tracking-widest flex items-center gap-2">
            <div className="p-1 bg-[#3B82F6]/10 text-[#3B82F6] rounded">
              <Clock className="w-3.5 h-3.5" />
            </div>
            {flights.length} {directionLabel}
          </div>
        </div>
      </div>

      {/* Flight Table */}
      <div className="bg-[#161B22] border border-[#30363D] rounded-lg overflow-hidden shadow-xl">
        <div className="grid grid-cols-7 gap-4 p-3.5 border-b border-[#30363D] bg-[#0B0C10] text-[9px] font-bold uppercase tracking-widest text-[#8B949E]">
          <div className="col-span-1">Flight</div>
          <div className="col-span-1">Route</div>
          <div className="col-span-1">Gate</div>
          <div className="col-span-1">Deviation</div>
          <div className="col-span-1">Driver</div>
          <div className="col-span-1">Risk Tier</div>
          <div className="col-span-1 text-right">ETA</div>
        </div>

        <div className="divide-y divide-[#30363D]/50 max-h-[600px] overflow-y-auto scrollbar-thin scrollbar-thumb-[#30363D] scrollbar-track-transparent">
          {loading && flights.length === 0 && (
            <div className="p-6 text-[11px] font-mono uppercase tracking-widest text-[#8B949E]">
              Loading flights...
            </div>
          )}
          {!loading && flights.length === 0 && (
            <div className="p-6 text-[11px] font-mono uppercase tracking-widest text-[#8B949E]">
              No flights match the current filters.
            </div>
          )}
          {flights.map((f) => {
            const route = f.direction === "ARR" ? `${f.remote_airport} → LGA` : `LGA → ${f.remote_airport}`;
            const delayMin = Math.max(0, Math.round(f.pred_delay_q50));
            const status = f.risk_tier;
            const eta = formatEta(f.scheduled_time);
            return (
              <div
                key={f.flight_id}
                onClick={() => openSlideOut(f.flight_id)}
                className="grid grid-cols-7 gap-4 p-3.5 items-center hover:bg-[#21262D] cursor-pointer transition-colors group"
              >
                <div className="col-span-1 font-mono font-bold text-[#E6EDF3] group-hover:text-blue-400 transition-colors text-sm">
                  {f.flight}
                </div>
                <div className="col-span-1 text-[13px] text-[#8B949E] flex items-center gap-1 font-mono">
                  {route}
                </div>
                <div className="col-span-1 text-[13px] font-mono font-medium text-[#E6EDF3] flex items-center gap-1.5">
                  {/* No conflict info available per-row from /api/flights — leave icon for future enrichment */}
                  {formatGate(f.gate)}
                </div>
                <div className="col-span-1 flex items-center gap-2.5">
                  <div className="w-16 h-1.5 bg-[#0B0C10] rounded-full overflow-hidden border border-[#30363D]">
                    <div
                      className={clsx("h-full shadow-sm", {
                        "bg-gradient-to-r from-[#F03E3E] to-red-400 shadow-[0_0_8px_rgba(240,62,62,0.6)]": status === "CRITICAL",
                        "bg-gradient-to-r from-[#F59E0B] to-amber-400": status === "HIGH",
                        "bg-[#2EA043]": status === "LOW" || status === "MEDIUM",
                      })}
                      style={{ width: `${Math.min(100, (delayMin / 60) * 100)}%` }}
                    />
                  </div>
                  <span className={clsx("font-mono text-[11px] font-bold", delayMin > 0 ? (status === "CRITICAL" ? "text-[#F03E3E]" : "text-[#F59E0B]") : "text-[#2EA043]")}>
                    {delayMin > 0 ? `+${delayMin}m` : "On time"}
                  </span>
                </div>
                <div className="col-span-1 text-[11px] text-[#8B949E] font-medium tracking-wide">
                  {f.top_shap_label ?? "—"}
                </div>
                <div className="col-span-1">
                  <span className={clsx("px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest rounded flex items-center w-max gap-1.5 border shadow-sm", {
                    "bg-[#F03E3E]/10 text-[#F03E3E] border-[#F03E3E]/30": status === "CRITICAL",
                    "bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30": status === "HIGH",
                    "bg-[#0B0C10] text-[#8B949E] border-[#30363D]": status === "MEDIUM",
                    "bg-[#3FB950]/10 text-[#3FB950] border-[#3FB950]/30": status === "LOW",
                  })}>
                    <div className={clsx("w-1.5 h-1.5 rounded-full shadow-inner", {
                      "bg-[#F03E3E] shadow-[#F03E3E]/50": status === "CRITICAL",
                      "bg-[#F59E0B] shadow-[#F59E0B]/50": status === "HIGH",
                      "bg-[#475569]": status === "MEDIUM",
                      "bg-[#3FB950]": status === "LOW",
                    })} />
                    {status}
                  </span>
                </div>
                <div className="col-span-1 text-right text-[13px] font-mono text-[#8B949E] group-hover:text-[#E6EDF3] transition-colors">
                  {eta}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
