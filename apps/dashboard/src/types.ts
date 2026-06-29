// Type contracts mirroring the JSON shapes served by the SIN node's local HTTP
// API. These intentionally track the pydantic models in
// packages/sin-node/src/sin_node/models.py (serialized with mode="json").

export interface StatusResponse {
  version: string;
  adapters: string[];
}

export interface CPUInfo {
  arch: string;
  model: string | null;
  physical_cores: number | null;
  logical_cores: number | null;
  features: string[];
}

export interface GPUInfo {
  vendor: string;
  name: string;
  vram_total_gb: number | null;
}

export interface RuntimeInfo {
  name: string;
  available: boolean;
  version: string | null;
  endpoint: string | null;
}

export interface HardwareProfile {
  os: string;
  os_version: string;
  arch: string;
  cpu: CPUInfo;
  ram_total_gb: number;
  ram_available_gb: number;
  disk_free_gb: number;
  gpus: GPUInfo[];
  accelerator: string;
  unified_memory: boolean;
  runtimes: RuntimeInfo[];
}

export interface MemoryEstimate {
  weights_gb: number;
  kv_cache_gb: number;
  overhead_gb: number;
  total_gb: number;
}

export interface Recommendation {
  model_id: string;
  display_name: string;
  runtime: string;
  quant: string;
  context: number;
  estimate: MemoryEstimate;
  fits: boolean;
  headroom_ratio: number;
  predicted_tps: number | null;
  quality_score: number;
  score: number;
  why: string;
  tradeoffs: string[];
}

// Tasks the recommendation engine accepts via /api/recommend?task=...
export type Task = "coding" | "general-chat" | "embeddings";

export const TASKS: ReadonlyArray<{ id: Task; label: string }> = [
  { id: "coding", label: "Coding" },
  { id: "general-chat", label: "General chat" },
  { id: "embeddings", label: "Embeddings" },
];
