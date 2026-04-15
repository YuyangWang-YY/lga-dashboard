import { motion, AnimatePresence } from "motion/react";
import { useSlideOut } from "./SlideOutContext";
import { X, Clock, MapPin, Plane, ShieldAlert, Zap } from "lucide-react";
import clsx from "clsx";
import { useFlightDetail } from "../hooks/useFlightDetail";
import type { RiskTier } from "../lib/types";
import { formatGate } from "../lib/format";

/* ─── Action recommendations per risk tier (from spec) ─── */
const ACTIONS_BY_TIER: Record<RiskTier, string[]> = {
  CRITICAL: [
    "Alert ground crew immediately",
    "Notify passengers via app/SMS",
    "Prepare backup gate",
  ],
  HIGH: [
    "Monitor weather/upstream",
    "Place standby resources",
    "Track inbound aircraft",
  ],
  MEDIUM: [
    "Track delay trend",
    "Monitor for escalation",
  ],
  LOW: [
    "Normal operations",
  ],
};

/* ─── ETA helpers ─── */
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

function formatScheduled(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

/* ─── Activity icon stub (kept from mockup) ─── */
function Activity(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
  );
}

export default function SlideOutPanel() {
  const { isOpen, closeSlideOut, selectedFlightId } = useSlideOut();
  const { data: flight, loading } = useFlightDetail(selectedFlightId);

  // Map risk_tier → tone classes (preserves mockup styling for CRITICAL/HIGH/LOW;
  // MEDIUM falls back to cyan tone since mockup didn't define it explicitly)
  const tone = flight?.risk_tier ?? "LOW";
  const isCrit = tone === "CRITICAL";
  const isHigh = tone === "HIGH";
  const isMed = tone === "MEDIUM";
  const isLow = tone === "LOW";

  const probPct = flight ? Math.round(flight.delay_probability * 100) : 0;
  const route = flight
    ? flight.direction === "ARR"
      ? `${flight.remote_airport} → LGA`
      : `LGA → ${flight.remote_airport}`
    : "";
  const actions = flight ? ACTIONS_BY_TIER[flight.risk_tier] : [];

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop Blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-[#050505]/70 z-40 backdrop-blur-sm"
            onClick={closeSlideOut}
          />

          {/* Main Slideout Panel - Exact Surface Token #0F0F11 */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 w-[420px] h-full bg-[#0F0F11] shadow-[0_0_50px_rgba(0,0,0,0.6)] z-50 overflow-y-auto border-l border-white/[0.04] selection:bg-[#00B4E2]/30"
          >
            {loading && !flight && (
              <div className="p-8 text-[11px] font-mono uppercase tracking-widest text-zinc-500">
                Loading flight detail...
              </div>
            )}

            {flight && (
              <div className="p-8 space-y-8">

                {/* Header */}
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">{flight.flight}</h2>
                      <span className={clsx("px-2 py-0.5 text-[9px] font-bold rounded flex items-center gap-1.5 uppercase tracking-widest border", {
                        "bg-rose-500/10 text-rose-500 border-rose-500/20": isCrit,
                        "bg-amber-400/10 text-amber-400 border-amber-400/20": isHigh,
                        "bg-[#00B4E2]/10 text-[#00B4E2] border-[#00B4E2]/20": isMed,
                        "bg-emerald-500/10 text-emerald-500 border-emerald-500/20": isLow,
                      })}>
                        <span className={clsx("w-1.5 h-1.5 rounded-full shadow-[0_0_8px_currentColor]", {
                          "bg-rose-500": isCrit,
                          "bg-amber-400": isHigh,
                          "bg-[#00B4E2]": isMed,
                          "bg-emerald-500": isLow,
                        })} />
                        {flight.risk_tier}
                      </span>
                    </div>
                    <div className="text-zinc-500 flex flex-col gap-1.5 text-[11px] font-mono uppercase tracking-wide">
                      <div className="flex items-center gap-2"><Plane className="w-3.5 h-3.5" /> {flight.airline}</div>
                      <div className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5" /> {route} &bull; Gate {formatGate(flight.gate)}</div>
                      <div className="flex items-center gap-2"><Clock className="w-3.5 h-3.5" /> ETA: <span className="text-zinc-300 font-bold">{formatEta(flight.scheduled_time)}</span></div>
                      {flight.registration && (
                        <div className="flex items-center gap-2 text-zinc-600"><span className="w-3.5 h-3.5" /> {formatScheduled(flight.scheduled_time)} • {flight.registration}{flight.body_type ? ` • ${flight.body_type}` : ""}</div>
                      )}
                    </div>
                  </div>
                  <button onClick={closeSlideOut} className="text-zinc-500 hover:text-zinc-100 transition-colors p-2 hover:bg-white/[0.05] rounded-full">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Action Section (The core AOC value prop) */}
                <div className="p-5 rounded-2xl bg-white/[0.02] ring-1 ring-white/[0.04] relative overflow-hidden shadow-inner">
                  <div className={clsx("absolute top-0 left-0 right-0 h-0.5", {
                    "bg-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.6)]": isCrit,
                    "bg-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.6)]": isHigh,
                    "bg-[#00B4E2] shadow-[0_0_15px_rgba(0,180,226,0.6)]": isMed,
                    "bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.6)]": isLow,
                  })} />

                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
                    <ShieldAlert className="w-3.5 h-3.5 text-zinc-300" />
                    Risk Assessment & Actions
                  </h3>

                  <div className="space-y-5">
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-[11px] text-zinc-500 uppercase tracking-widest">Delay Probability</span>
                        <span className="text-[12px] font-mono font-bold text-zinc-100">{probPct}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-black rounded-full overflow-hidden ring-1 ring-white/[0.05]">
                        <div
                          className={clsx("h-full", {
                            "bg-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.8)]": isCrit,
                            "bg-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.8)]": isHigh,
                            "bg-[#00B4E2] shadow-[0_0_15px_rgba(0,180,226,0.8)]": isMed,
                            "bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.8)]": isLow,
                          })}
                          style={{ width: `${probPct}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-2">
                        Confidence: <span className={clsx("font-bold", flight.confidence === "HIGH" ? "text-[#00B4E2]" : "text-amber-400")}>{flight.confidence}</span>
                        {flight.confidence === "MODERATE" && (
                          <span className="block mt-1 italic text-zinc-600">
                            This flight is 3+ hours out. Predictions rely more on route history than real-time signals.
                          </span>
                        )}
                      </div>
                    </div>

                    <div className={clsx("text-[11px] p-3 rounded-xl text-zinc-200 ring-1", {
                      "bg-rose-500/5 ring-rose-500/20": isCrit,
                      "bg-amber-400/5 ring-amber-400/20": isHigh,
                      "bg-[#00B4E2]/5 ring-[#00B4E2]/20": isMed,
                      "bg-emerald-500/5 ring-emerald-500/20": isLow,
                    })}>
                      <span className={clsx("font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5", {
                        "text-rose-500": isCrit,
                        "text-amber-400": isHigh,
                        "text-[#00B4E2]": isMed,
                        "text-emerald-500": isLow,
                      })}>
                        <Zap className="w-3.5 h-3.5 drop-shadow-[0_0_5px_currentColor]" /> Recommended Actions:
                      </span>
                      <ul className="list-disc list-inside space-y-1.5 text-zinc-400 ml-1 font-medium">
                        {actions.map((a, i) => (<li key={i}>{a}</li>))}
                      </ul>
                    </div>

                    {/* Prediction Range (Q10/Q50/Q90) */}
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-2">Predicted Delay Range</div>
                      <div className="text-[11px] font-mono text-zinc-300">
                        Predicted +{Math.round(flight.pred_delay_q50)}m
                        <span className="text-zinc-600"> (80%: {Math.round(flight.pred_delay_q10)}–{Math.round(flight.pred_delay_q90)}m)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Top Delay Factors (SHAP) */}
                <div>
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
                    <Activity className="w-3.5 h-3.5" /> Delay Drivers (SHAP)
                  </h3>
                  <div className="space-y-2">
                    {flight.shap_factors.length === 0 && (
                      <div className="text-[11px] text-zinc-600 italic">No SHAP data available.</div>
                    )}
                    {flight.shap_factors.slice(0, 6).map((sf, i) => {
                      const isMajor = sf.level === "major";
                      const isContrib = sf.level === "contributing";
                      const positive = sf.value > 0;
                      return (
                        <div key={i} className="flex items-center justify-between text-[11px] p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] transition-colors ring-1 ring-white/[0.03]">
                          <div className="flex items-center gap-3">
                            <span className={clsx("w-2 h-2 rounded-full shadow-[0_0_8px_currentColor]", {
                              "bg-rose-500": isMajor,
                              "bg-amber-400": isContrib,
                              "bg-zinc-600": !isMajor && !isContrib,
                            })} />
                            <span className={clsx(isMajor || isContrib ? "text-zinc-200" : "text-zinc-400", "font-medium")}>{sf.label}</span>
                          </div>
                          <span className={clsx("font-mono font-bold", {
                            "text-rose-500": positive && isMajor,
                            "text-amber-400": positive && isContrib,
                            "text-zinc-500": !positive || (!isMajor && !isContrib),
                          })}>
                            {positive ? "+" : ""}{sf.value.toFixed(4)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Operational Context */}
                <div>
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-4">Operational Context</h3>
                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div className="bg-white/[0.02] ring-1 ring-white/[0.03] p-3 rounded-xl text-zinc-200">
                      <span className="block text-zinc-500 mb-1 text-[9px] uppercase tracking-widest font-bold">Origin Weather</span>
                      <span className={clsx("block font-medium", {
                        "text-rose-500 drop-shadow-[0_0_5px_rgba(244,63,94,0.4)]": flight.operational_context?.origin_weather_severity === "severe",
                        "text-amber-400": flight.operational_context?.origin_weather_severity === "moderate",
                        "text-zinc-300": !flight.operational_context?.origin_weather_severity || flight.operational_context.origin_weather_severity === "clear",
                      })}>
                        {flight.operational_context?.origin_weather ?? "—"}
                      </span>
                    </div>
                    <div className="bg-white/[0.02] ring-1 ring-white/[0.03] p-3 rounded-xl text-zinc-200">
                      <span className="block text-zinc-500 mb-1 text-[9px] uppercase tracking-widest font-bold">Inbound AC</span>
                      <span className="block font-mono font-medium">
                        {flight.registration ?? "—"}
                        {flight.operational_context?.prev_aircraft_delay != null && (
                          <span className="text-zinc-500"> (prev +{Math.round(flight.operational_context.prev_aircraft_delay)}m)</span>
                        )}
                      </span>
                    </div>
                    <div className="bg-white/[0.02] ring-1 ring-white/[0.03] p-3 rounded-xl text-zinc-200">
                      <span className="block text-zinc-500 mb-1 text-[9px] uppercase tracking-widest font-bold">Turnaround</span>
                      <span className={clsx("block font-medium", {
                        "text-amber-400": (flight.operational_context?.turnaround_hours ?? 99) < 1,
                        "text-zinc-300": (flight.operational_context?.turnaround_hours ?? 99) >= 1,
                      })}>
                        {flight.operational_context?.turnaround_hours != null
                          ? `${flight.operational_context.turnaround_hours.toFixed(1)}h`
                          : "—"}
                      </span>
                    </div>
                    <div className="bg-white/[0.02] ring-1 ring-white/[0.03] p-3 rounded-xl text-zinc-200">
                      <span className="block text-zinc-500 mb-1 text-[9px] uppercase tracking-widest font-bold">Route Hist. Delay</span>
                      <span className="block font-mono text-amber-400 font-medium">
                        {flight.operational_context?.route_delay_rate != null
                          ? `${Math.round(flight.operational_context.route_delay_rate * 100)}% rate`
                          : "—"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actual outcome (past flights only) */}
                {flight.actual_delay != null && (
                  <div className="bg-white/[0.02] ring-1 ring-white/[0.04] rounded-2xl p-5">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-3">Actual Outcome</h3>
                    <div className="flex items-center gap-6">
                      <span className="text-[11px] text-zinc-500">
                        Delay: <span className={clsx("font-bold font-mono", flight.actual_delay > 15 ? "text-rose-400" : "text-emerald-400")}>{Math.round(flight.actual_delay)} min</span>
                      </span>
                      <span className="text-[11px] text-zinc-500">
                        Status: <span className={clsx("font-bold uppercase", flight.actual_delay > 15 ? "text-rose-400" : "text-emerald-400")}>{flight.actual_delay > 15 ? "DELAYED" : "ON TIME"}</span>
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
