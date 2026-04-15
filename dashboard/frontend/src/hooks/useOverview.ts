import { useEffect, useState } from "react";
import { getOverview } from "../lib/api";
import type { OverviewResponse } from "../lib/types";
import { useSimulation } from "../context/SimulationContext";
import { useConfig } from "../context/ConfigContext";

interface UseOverviewResult {
  data: OverviewResponse | null;
  loading: boolean;
  error: string | null;
}

export function useOverview(): UseOverviewResult {
  const sim = useSimulation();
  const config = useConfig();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getOverview(sim.isoString, config.mode)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        if (res.available_dates && res.available_dates.length > 0) {
          sim.setAvailableDates(res.available_dates);
        }
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
  }, [sim.isoString, config.mode]);

  return { data, loading, error };
}
