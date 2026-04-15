import { useEffect, useState } from "react";
import { getFlights } from "../lib/api";
import type { FlightListResponse } from "../lib/types";
import { useSimulation } from "../context/SimulationContext";
import { useConfig } from "../context/ConfigContext";

interface UseFlightsParams {
  direction?: "ARR" | "DEP";
  terminal?: string;
  airline?: string;
  riskTier?: string;
  sortBy?: string;
  sortDesc?: boolean;
  limit?: number;
}

interface UseFlightsResult {
  data: FlightListResponse | null;
  loading: boolean;
  error: string | null;
}

export function useFlights(params: UseFlightsParams = {}): UseFlightsResult {
  const sim = useSimulation();
  const config = useConfig();
  const [data, setData] = useState<FlightListResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify({
    iso: sim.isoString,
    mode: config.mode,
    ...params,
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getFlights({
      datetime: sim.isoString,
      mode: config.mode,
      direction: params.direction,
      terminal: params.terminal,
      airline: params.airline,
      risk_tier: params.riskTier,
      sort_by: params.sortBy,
      sort_desc: params.sortDesc,
      limit: params.limit ?? 200,
    })
      .then((res) => {
        if (cancelled) return;
        setData(res);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, loading, error };
}
