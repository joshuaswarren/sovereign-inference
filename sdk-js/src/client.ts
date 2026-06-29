// SPDX-License-Identifier: Apache-2.0
import type {
  ChatCompletionRequest,
  ChatCompletionResponse,
  SignedReceipt,
  SipOptions,
} from "./types.js";

export interface SovereignInferenceClientOptions {
  /** Base URL of a SIP-AI router or an OpenAI-compatible SIN endpoint. */
  baseUrl: string;
  /** Bearer token (local or network). */
  apiKey?: string;
  /** Default SIP options applied to every request. */
  defaults?: SipOptions;
  /** Injectable fetch (defaults to global fetch). */
  fetch?: typeof fetch;
}

/**
 * Minimal SIP-AI client. Speaks the OpenAI-compatible chat-completions path and
 * attaches `X-SIP-*` routing headers. Provider selection, payment, and receipt
 * verification are performed by the router/node it talks to; this SDK is the
 * thin, dependency-free entry point for apps.
 */
export class SovereignInferenceClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly defaults: SipOptions;
  private readonly fetchImpl: typeof fetch;

  constructor(options: SovereignInferenceClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.defaults = options.defaults ?? {};
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    if (typeof this.fetchImpl !== "function") {
      throw new Error("No fetch implementation available; pass one via options.fetch");
    }
  }

  private headers(sip: SipOptions): Headers {
    const merged: SipOptions = { ...this.defaults, ...sip };
    const headers = new Headers({ "content-type": "application/json" });
    if (this.apiKey) headers.set("authorization", `Bearer ${this.apiKey}`);
    if (merged.privacyMode) headers.set("x-sip-privacy-mode", merged.privacyMode);
    if (merged.budget) headers.set("x-sip-budget", merged.budget);
    if (merged.verification) headers.set("x-sip-verification", merged.verification);
    return headers;
  }

  /** Call the OpenAI-compatible chat-completions endpoint through SIP-AI. */
  async chatCompletions(
    request: ChatCompletionRequest,
    sip: SipOptions = {},
  ): Promise<ChatCompletionResponse> {
    const response = await this.fetchImpl(`${this.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers: this.headers(sip),
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error(`SIP-AI request failed: ${response.status} ${response.statusText}`);
    }
    return (await response.json()) as ChatCompletionResponse;
  }

  /** Verify a signed receipt server-side via the router's verify endpoint. */
  async verifyReceipt(receipt: SignedReceipt): Promise<boolean> {
    const response = await this.fetchImpl(`${this.baseUrl}/sip/v1/verify-receipt`, {
      method: "POST",
      headers: this.headers({}),
      body: JSON.stringify(receipt),
    });
    if (!response.ok) return false;
    const body = (await response.json()) as { valid?: boolean };
    return body.valid === true;
  }
}
