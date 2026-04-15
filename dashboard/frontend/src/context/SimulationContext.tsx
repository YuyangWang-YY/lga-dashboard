import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from "react";

interface SimulationState {
  currentTime: Date;
  isPlaying: boolean;
  speed: number; // minutes per real second
  availableDates: string[];
}

interface SimulationContextValue extends SimulationState {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (speed: number) => void;
  jumpTo: (date: Date) => void;
  setAvailableDates: (dates: string[]) => void;
  formattedTime: string;
  formattedDate: string;
  isoString: string;
}

const SimulationContext = createContext<SimulationContextValue | null>(null);

const SPEED_OPTIONS = [
  { label: "1x", value: 1 },
  { label: "5x", value: 5 },
  { label: "15x", value: 15 },
  { label: "60x", value: 60 },
];

export { SPEED_OPTIONS };

export function SimulationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SimulationState>({
    currentTime: new Date("2025-08-13T08:00:00"),
    isPlaying: false,
    speed: 15, // 15 minutes per second
    availableDates: [],
  });

  const intervalRef = useRef<number | null>(null);

  // Advance time when playing
  useEffect(() => {
    if (state.isPlaying) {
      intervalRef.current = window.setInterval(() => {
        setState((prev) => {
          const newTime = new Date(
            prev.currentTime.getTime() + prev.speed * 60 * 1000
          );
          return { ...prev, currentTime: newTime };
        });
      }, 1000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [state.isPlaying, state.speed]);

  const play = useCallback(
    () => setState((s) => ({ ...s, isPlaying: true })),
    []
  );
  const pause = useCallback(
    () => setState((s) => ({ ...s, isPlaying: false })),
    []
  );
  const togglePlay = useCallback(
    () => setState((s) => ({ ...s, isPlaying: !s.isPlaying })),
    []
  );
  const setSpeed = useCallback(
    (speed: number) => setState((s) => ({ ...s, speed })),
    []
  );
  const jumpTo = useCallback(
    (date: Date) => setState((s) => ({ ...s, currentTime: date })),
    []
  );
  const setAvailableDates = useCallback(
    (dates: string[]) => setState((s) => ({ ...s, availableDates: dates })),
    []
  );

  const formattedTime = state.currentTime.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });

  const formattedDate = state.currentTime.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const isoString = state.currentTime.toISOString().slice(0, 19);

  return (
    <SimulationContext.Provider
      value={{
        ...state,
        play,
        pause,
        togglePlay,
        setSpeed,
        jumpTo,
        setAvailableDates,
        formattedTime,
        formattedDate,
        isoString,
      }}
    >
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulation() {
  const ctx = useContext(SimulationContext);
  if (!ctx) throw new Error("useSimulation must be used within SimulationProvider");
  return ctx;
}
