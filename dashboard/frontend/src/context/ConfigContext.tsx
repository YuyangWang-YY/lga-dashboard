import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { OperatingMode } from "../lib/types";
import { setMode as apiSetMode } from "../lib/api";

interface ConfigState {
  mode: OperatingMode;
  arrivalThreshold: number;
  departureThreshold: number;
}

interface ConfigContextValue extends ConfigState {
  changeMode: (mode: OperatingMode) => Promise<void>;
}

const THRESHOLDS: Record<OperatingMode, { arrival: number; departure: number }> = {
  balanced: { arrival: 0.39, departure: 0.53 },
  high_precision: { arrival: 0.46, departure: 0.64 },
  high_recall: { arrival: 0.29, departure: 0.23 },
};

const ConfigContext = createContext<ConfigContextValue | null>(null);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConfigState>({
    mode: "balanced",
    arrivalThreshold: 0.39,
    departureThreshold: 0.53,
  });

  const changeMode = useCallback(async (mode: OperatingMode) => {
    try {
      await apiSetMode(mode);
    } catch {
      // API call is best-effort; still update local state
    }
    setState({
      mode,
      arrivalThreshold: THRESHOLDS[mode].arrival,
      departureThreshold: THRESHOLDS[mode].departure,
    });
  }, []);

  return (
    <ConfigContext.Provider value={{ ...state, changeMode }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig() {
  const ctx = useContext(ConfigContext);
  if (!ctx) throw new Error("useConfig must be used within ConfigProvider");
  return ctx;
}
