// SPDX-License-Identifier: Apache-2.0

/** Privacy/transport mode requested for an inference call. */
export type PrivacyMode =
  | "local-only"
  | "direct"
  | "relay"
  | "private-payment"
  | "private-payment-relay"
  | "confidential"
  | "batch";

export type VerificationLevel = "none" | "signed-receipt" | "confidential";

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
}

export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  max_tokens?: number;
  temperature?: number;
}

/** SIP-AI routing controls, sent as `X-SIP-*` headers. */
export interface SipOptions {
  privacyMode?: PrivacyMode;
  /** Maximum spend for this request, decimal string in the negotiated unit. */
  budget?: string;
  verification?: VerificationLevel;
}

/** Mirrors docs/spec/schemas/inference_receipt.schema.json. */
export interface SignedReceipt {
  receipt_version: "sip-ai.receipt.v1";
  request_id: string;
  provider_pubkey: string;
  model_manifest_hash: string;
  model_alias: string;
  runtime: string;
  runtime_version?: string;
  input_tokens: number;
  output_tokens: number;
  price_units: string;
  price_amount: string;
  privacy_mode: PrivacyMode;
  started_at: string;
  completed_at: string;
  response_hash: string;
  signature: string;
}

export interface ChatCompletionResponse {
  id: string;
  choices: Array<{ index: number; message: ChatMessage; finish_reason: string }>;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  /** Present when verification was requested. */
  sip_receipt?: SignedReceipt;
}
