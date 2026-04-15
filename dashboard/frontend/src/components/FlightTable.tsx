import { useMemo, useState } from "react";
import { ArrowLeft, X, Search } from "lucide-react";
import clsx from "clsx";
import { useFlights } from "../hooks/useFlights";
import { useSlideOut } from "./SlideOutContext";
import type { FlightSummary } from "../lib/types";
import { formatGate } from "../lib/format";

/* ─── Risk color helpers ─── */
function riskBadge(risk: string) {
  switch (risk) {
    case "CRITICAL":
      return { label: "Critical", bg: "bg-rose-500/15 text-rose-400" };
    case "HIGH":
      return { label: "High", bg: "bg-amber-500/15 text-amber-400" };
    case "MEDIUM":
      return { label: "Medium", bg: "bg-[#00B4E2]/15 text-[#00B4E2]" };
    default:
      return { label: "Low", bg: "bg-zinc-500/15 text-zinc-500" };
  }
}

function delayColor(d: number) {
  if (d === 0) return "text-zinc-600";
  if (d >= 100) return "text-rose-400";
  if (d >= 40) return "text-amber-400";
  return "text-[#00B4E2]";
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/* ─── Main FlightTable Component ─── */
export default function FlightTable({
  onClose,
  terminal,
}: {
  onClose: () => void;
  /** Optional terminal scope (e.g. "Terminal A"); when set, table only shows that terminal's flights. */
  terminal?: string;
}) {
  const [filter, setFilter] = useState<"all" | "ARR" | "DEP">("all");
  const [riskFilterVal, setRiskFilterVal] = useState<"all" | "CRITICAL" | "HIGH" | "MEDIUM" | "LOW">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const { openSlideOut } = useSlideOut();

  const { data, loading } = useFlights({
    direction: filter === "all" ? undefined : filter,
    terminal,
    riskTier: riskFilterVal === "all" ? undefined : riskFilterVal,
    sortBy: "delay_probability",
    sortDesc: true,
    limit: 300,
  });

  const filtered: FlightSummary[] = useMemo(() => {
    const flights = data?.flights ?? [];
    if (!searchQuery) return flights;
    const q = searchQuery.toLowerCase();
    return flights.filter(
      (f) =>
        f.flight.toLowerCase().includes(q) ||
        f.airline.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  return (
    <div className="flex-1 bg-[#0F0F11] rounded-xl ring-1 ring-white/[0.08] flex flex-col overflow-hidden min-h-0">
      {/* Toolbar */}
      <div className="px-4 py-2 flex items-center gap-3 border-b border-white/[0.03] shrink-0">
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
          {terminal ? `${terminal} Flights` : "All Flights"}
        </span>
        <span className="text-[10px] font-mono text-zinc-400">
          {filtered.length}
        </span>

        {/* Search */}
        <div className="ml-4 flex items-center gap-1.5 bg-[#0A0A0C] rounded-md px-2 py-1 ring-1 ring-white/[0.06]">
          <Search className="w-3 h-3 text-zinc-600" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search flight…"
            className="bg-transparent text-[10px] text-zinc-300 placeholder:text-zinc-700 outline-none w-28"
          />
        </div>

        {/* Type filter */}
        <div className="ml-auto flex gap-0.5 bg-[#0A0A0C] rounded-md p-0.5">
          {(["all", "ARR", "DEP"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded transition-all",
                filter === f ? "bg-white/[0.08] text-zinc-200" : "text-zinc-600 hover:text-zinc-400"
              )}
            >
              {f === "all" ? "All" : f}
            </button>
          ))}
        </div>

        {/* Risk filter */}
        <div className="flex gap-0.5 bg-[#0A0A0C] rounded-md p-0.5">
          {(["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRiskFilterVal(r)}
              className={clsx(
                "text-[8px] font-bold uppercase tracking-widest px-2 py-0.5 rounded transition-all",
                riskFilterVal === r ? "bg-white/[0.08] text-zinc-200" : "text-zinc-600 hover:text-zinc-400"
              )}
            >
              {r === "all" ? "All Risk" : r.charAt(0) + r.slice(1).toLowerCase()}
            </button>
          ))}
        </div>

        <button onClick={onClose} className="text-zinc-600 hover:text-zinc-400 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {loading && filtered.length === 0 && (
          <div className="px-4 py-6 text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            Loading flights...
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="px-4 py-6 text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            No flights match the current filters.
          </div>
        )}
        <table className="w-full text-[10px] font-mono">
          <thead className="sticky top-0 z-10 bg-[#0F0F11]">
            <tr className="text-zinc-600 text-[8px] uppercase tracking-widest border-b border-white/[0.04]">
              <th className="text-left px-4 py-2 font-bold">Flight</th>
              <th className="text-left px-2 py-2 font-bold">Type</th>
              <th className="text-left px-2 py-2 font-bold">Route</th>
              <th className="text-left px-2 py-2 font-bold">Gate</th>
              <th className="text-left px-2 py-2 font-bold">Terminal</th>
              <th className="text-left px-2 py-2 font-bold">Sched</th>
              <th className="text-right px-2 py-2 font-bold">Delay</th>
              <th className="text-left px-2 py-2 font-bold">Delay Risk</th>
              <th className="text-left px-4 py-2 font-bold">Driver</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f) => {
              const rb = riskBadge(f.risk_tier);
              const delay = Math.max(0, Math.round(f.pred_delay_q50));
              const route = f.direction === "ARR" ? `${f.remote_airport} → LGA` : `LGA → ${f.remote_airport}`;
              return (
                <tr
                  key={f.flight_id}
                  onClick={() => openSlideOut(f.flight_id)}
                  className="border-t border-white/[0.02] hover:bg-white/[0.03] cursor-pointer transition-colors group"
                >
                  <td className="px-4 py-2 font-bold text-zinc-200 group-hover:text-zinc-100">{f.flight}</td>
                  <td className="px-2 py-2">
                    <span className={clsx(
                      "text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded",
                      f.direction === "ARR" ? "bg-teal-500/15 text-teal-400" : "bg-violet-500/15 text-violet-400"
                    )}>
                      {f.direction}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-zinc-400">{route}</td>
                  <td className="px-2 py-2 text-zinc-400">{formatGate(f.gate)}</td>
                  <td className="px-2 py-2 text-zinc-500">{f.terminal ?? "—"}</td>
                  <td className="px-2 py-2 text-zinc-500">{formatTime(f.scheduled_time)}</td>
                  <td className={clsx("px-2 py-2 text-right font-bold", delayColor(delay))}>
                    {delay > 0 ? `+${delay}m` : "—"}
                  </td>
                  <td className="px-2 py-2">
                    <span className={clsx("text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded", rb.bg)}>
                      {rb.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-zinc-500">{f.top_shap_label ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
