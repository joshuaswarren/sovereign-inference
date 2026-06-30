// Typed fetchers for the SIN node's local HTTP API. Requests resolve against
// API_BASE (same-origin under `sin serve`; the app server's loopback URL inside
// the desktop app) and carry the admin token when one was injected.
import { apiHeaders, apiUrl } from "./runtime";
import type { HardwareProfile, Recommendation, StatusResponse, Task } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), { headers: apiHeaders(), signal });
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Could not reach the node at ${path}: ${detail}`, 0);
  }
  if (!res.ok) {
    throw new ApiError(`Request to ${path} failed (${res.status} ${res.statusText})`, res.status);
  }
  return (await res.json()) as T;
}

export function fetchStatus(signal?: AbortSignal): Promise<StatusResponse> {
  return getJson<StatusResponse>("/api/status", signal);
}

export function fetchHardware(signal?: AbortSignal): Promise<HardwareProfile> {
  return getJson<HardwareProfile>("/api/scan", signal);
}

export function fetchRecommendations(task: Task, signal?: AbortSignal): Promise<Recommendation[]> {
  const query = new URLSearchParams({ task });
  return getJson<Recommendation[]>(`/api/recommend?${query.toString()}`, signal);
}
