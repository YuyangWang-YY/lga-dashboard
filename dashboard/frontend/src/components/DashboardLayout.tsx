import { Outlet, NavLink } from "react-router";
import { Clock, Settings, Play, Pause } from "lucide-react";
import { SlideOutProvider } from "./SlideOutContext";
import SlideOutPanel from "./SlideOutPanel";
import clsx from "clsx";
import logoSvg from "../imports/svg-j3v6qd5w0g";
import { useSimulation } from "../context/SimulationContext";
import { useConfig } from "../context/ConfigContext";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "./ui/popover";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "./ui/dropdown-menu";
import type { OperatingMode } from "../lib/types";

/* ─── SVG Logo: Figma FaPlane vector ─── */
function LogoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 21.8994 21.898" fill="none">
      <path d={logoSvg.p42e1900} fill="white" />
    </svg>
  );
}

const MODE_LABELS: Record<OperatingMode, string> = {
  balanced: "Balanced",
  high_precision: "High Precision",
  high_recall: "High Recall",
};

export default function DashboardLayout() {
  const sim = useSimulation();
  const config = useConfig();

  // datetime-local expects "YYYY-MM-DDTHH:mm" in local time (no Z)
  const dtLocalValue = (() => {
    const d = sim.currentTime;
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  })();

  return (
    <SlideOutProvider>
      <div className="h-screen w-screen bg-[#050505] text-zinc-100 flex flex-col font-sans overflow-hidden selection:bg-[#00B4E2]/30">

        {/* TOP BAR */}
        <header className="relative h-12 px-5 flex items-center justify-between shrink-0 border-b border-white/[0.04] z-20">
          {/* Left: Logo */}
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#00B4E2] to-[#0088AD] flex items-center justify-center shadow-[0_0_15px_rgba(0,180,226,0.3)]">
              <LogoIcon />
            </div>
            <span className="text-[13px] font-bold tracking-widest text-zinc-100 whitespace-nowrap">
              LGA DELAY PREDICTION
            </span>
          </div>

          {/* Center: Tabs (absolutely centered relative to header) */}
          <nav className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1 bg-white/[0.02] rounded-full p-1 ring-1 ring-white/[0.04]">
            {["Overview", "Terminal A", "Terminal B", "Terminal C"].map((tab) => (
              <NavLink
                key={tab}
                to={tab === "Overview" ? "/" : `/${tab.toLowerCase().replace(" ", "-")}`}
                end={tab === "Overview"}
                className={({ isActive }) => clsx(
                  "px-6 py-1.5 rounded-full text-[11px] font-bold tracking-widest transition-all whitespace-nowrap",
                  isActive
                    ? "bg-white/[0.08] text-white"
                    : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                {tab}
              </NavLink>
            ))}
          </nav>

          {/* Right: Time Sim + Mode */}
          <div className="flex items-center gap-4">
            {/* Time Simulation */}
            <div className="flex items-center gap-2 bg-white/[0.03] px-3 py-1.5 rounded-lg ring-1 ring-white/[0.05]">
              <Clock className="w-3.5 h-3.5 text-zinc-500" />
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    className="text-[12px] font-mono text-zinc-200 hover:text-white transition-colors cursor-pointer focus:outline-none"
                    title="Click to change simulation time"
                  >
                    {sim.formattedTime}
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="end"
                  className="w-auto p-3 bg-[#0F0F11] border border-white/[0.08] text-zinc-200"
                >
                  <div className="flex flex-col gap-2">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">
                      Simulation Time
                    </span>
                    <input
                      type="datetime-local"
                      value={dtLocalValue}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v) sim.jumpTo(new Date(v));
                      }}
                      className="bg-[#050505] border border-white/[0.08] rounded px-2 py-1 text-[12px] font-mono text-zinc-100 outline-none focus:border-[#00B4E2]/50"
                    />
                    {sim.availableDates.length > 0 && (
                      <span className="text-[9px] text-zinc-600 font-mono">
                        Range: {sim.availableDates[0]} → {sim.availableDates[sim.availableDates.length - 1]}
                      </span>
                    )}
                  </div>
                </PopoverContent>
              </Popover>
              <div className="w-px h-3 bg-zinc-800 mx-1" />
              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-emerald-400">
                <span className="relative flex h-1.5 w-1.5">
                  {sim.isPlaying && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  )}
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                </span>
                {sim.isPlaying ? "LIVE" : "PAUSED"}
              </div>
              <div className="w-px h-3 bg-zinc-800 mx-1" />
              <div className="flex items-center gap-1">
                <button
                  onClick={sim.togglePlay}
                  className="p-1 rounded hover:bg-white/[0.06] text-zinc-400 hover:text-white transition-colors"
                >
                  {sim.isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                </button>
                <button
                  onClick={() => {
                    const cycle = [1, 5, 15, 60];
                    const idx = cycle.indexOf(sim.speed);
                    sim.setSpeed(cycle[(idx + 1) % cycle.length]);
                  }}
                  title="Click to change simulation speed"
                  className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold text-zinc-400 hover:bg-white/[0.06] hover:text-white transition-colors min-w-[24px] tabular-nums"
                >
                  {sim.speed}x
                </button>
              </div>
            </div>

            {/* Mode */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-zinc-500 hover:text-zinc-300 transition-colors focus:outline-none">
                  <Settings className="w-3.5 h-3.5" />
                  <span>{MODE_LABELS[config.mode]}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="bg-[#0F0F11] border border-white/[0.08] text-zinc-200 min-w-[180px]"
              >
                <DropdownMenuLabel className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">
                  Operating Mode
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-white/[0.06]" />
                {(Object.keys(MODE_LABELS) as OperatingMode[]).map((m) => (
                  <DropdownMenuItem
                    key={m}
                    onClick={() => config.changeMode(m)}
                    className={clsx(
                      "text-[11px] font-bold uppercase tracking-widest cursor-pointer focus:bg-white/[0.06] focus:text-white",
                      config.mode === m ? "text-[#00B4E2]" : "text-zinc-300"
                    )}
                  >
                    {MODE_LABELS[m]}
                    {config.mode === m && <span className="ml-auto text-[9px]">●</span>}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 flex flex-col min-h-0 p-4 pt-3 gap-3 overflow-hidden">
          <Outlet />
        </main>

        <SlideOutPanel />
      </div>
    </SlideOutProvider>
  );
}
