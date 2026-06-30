// Typed client for the desktop app server's onboarding/admin surface and the
// OpenAI test-chat endpoint. Mutations hit `/api/*` (admin-token guarded);
// the test chat hits the public `/v1` OpenAI surface.
import { ApiError } from "../api";
import { apiHeaders, apiUrl } from "../runtime";

export interface ProviderSummary {
  provider_pubkey: string;
  base_url: string;
  models: string[];
}

export interface ConfigState {
  onboarding_complete: boolean;
  providers: ProviderSummary[];
  directories: string[];
  models: string[];
  local_use: { runtime: string; model: string } | null;
  warnings: string[];
}

export interface RuntimeStatus {
  name: string;
  available: boolean;
  models: string[];
}

export interface VerifiedChat {
  content: string;
  provider_pubkey: string | null;
  base_url: string | null;
  receipt_verified: boolean;
}

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown; error?: { message?: unknown } };
    if (typeof body.detail === "string") return body.detail;
    if (body.error && typeof body.error.message === "string") return body.error.message;
  } catch {
    /* fall through to status text */
  }
  return res.statusText || `request failed (${res.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), init);
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Could not reach the app server: ${detail}`, 0);
  }
  if (!res.ok) {
    throw new ApiError(await readError(res), res.status);
  }
  return (await res.json()) as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path, { headers: apiHeaders() });
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: apiHeaders(body === undefined ? {} : { "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const getConfig = (): Promise<ConfigState> => get<ConfigState>("/api/config");
export const getRuntimes = (): Promise<RuntimeStatus[]> => get<RuntimeStatus[]>("/api/runtimes");
export const startLocalUse = (runtime: string, model: string): Promise<ConfigState> =>
  post<ConfigState>("/api/local-use", { runtime, model });
export const addDirectory = (spec: string): Promise<ConfigState> => post<ConfigState>("/api/directory", { spec });
export const addProvider = (manifest: unknown, base_url?: string): Promise<ConfigState> =>
  post<ConfigState>("/api/providers", { manifest, base_url });
export const completeOnboarding = (): Promise<ConfigState> => post<ConfigState>("/api/onboarding/complete");

interface OpenAIChatResponse {
  choices: { message: { content: string } }[];
  sip?: { provider_pubkey?: string; base_url?: string; receipt_verified?: boolean };
}

export async function testChat(model: string, content: string): Promise<VerifiedChat> {
  const res = await request<OpenAIChatResponse>("/v1/chat/completions", {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ model, messages: [{ role: "user", content }] }),
  });
  return {
    content: res.choices[0]?.message.content ?? "",
    provider_pubkey: res.sip?.provider_pubkey ?? null,
    base_url: res.sip?.base_url ?? null,
    receipt_verified: Boolean(res.sip?.receipt_verified),
  };
}
