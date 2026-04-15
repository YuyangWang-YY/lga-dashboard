import type {
  OverviewResponse,
  FlightListResponse,
  FlightDetail,
  ConfigResponse,
  OperatingMode,
} from "./types";

const _viteApiUrl = import.meta.env.VITE_API_URL as string | undefined;
const BASE_URL = _viteApiUrl
  ? `${_viteApiUrl.replace(/\/+$/, "")}/api`
  : "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getOverview(
  datetime: string,
  mode: string = "balanced",
  windowHours: number = 5
): Promise<OverviewResponse> {
  const params = new URLSearchParams({
    datetime,
    mode,
    window_hours: String(windowHours),
  });
  return fetchJSON(`${BASE_URL}/overview?${params}`);
}

export async function getFlights(params: {
  datetime: string;
  mode?: string;
  direction?: string;
  terminal?: string;
  airline?: string;
  risk_tier?: string;
  sort_by?: string;
  sort_desc?: boolean;
  limit?: number;
  offset?: number;
}): Promise<FlightListResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("datetime", params.datetime);
  if (params.mode) searchParams.set("mode", params.mode);
  if (params.direction) searchParams.set("direction", params.direction);
  if (params.terminal) searchParams.set("terminal", params.terminal);
  if (params.airline) searchParams.set("airline", params.airline);
  if (params.risk_tier) searchParams.set("risk_tier", params.risk_tier);
  if (params.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params.sort_desc !== undefined)
    searchParams.set("sort_desc", String(params.sort_desc));
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));

  return fetchJSON(`${BASE_URL}/flights?${searchParams}`);
}

export async function getFlightDetail(
  flightId: string
): Promise<FlightDetail> {
  return fetchJSON(`${BASE_URL}/flights/${encodeURIComponent(flightId)}`);
}

export async function getConfig(): Promise<ConfigResponse> {
  return fetchJSON(`${BASE_URL}/config`);
}

export async function setMode(mode: OperatingMode): Promise<ConfigResponse> {
  const res = await fetch(`${BASE_URL}/config/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}
