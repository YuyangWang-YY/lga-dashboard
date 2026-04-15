import { useEffect, useState } from "react";
import { getFlightDetail } from "../lib/api";
import type { FlightDetail } from "../lib/types";

interface UseFlightDetailResult {
  data: FlightDetail | null;
  loading: boolean;
  error: string | null;
}

export function useFlightDetail(flightId: string | null): UseFlightDetailResult {
  const [data, setData] = useState<FlightDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!flightId) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getFlightDetail(flightId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [flightId]);

  return { data, loading, error };
}
