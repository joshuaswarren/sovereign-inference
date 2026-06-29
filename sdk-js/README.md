# @sovereign-inference/sdk

TypeScript client SDK for the Sovereign Inference Protocol (SIP-AI). Thin,
dependency-free, and OpenAI-compatible.

**License:** Apache-2.0 — see [LICENSING.md](../LICENSING.md).

```ts
import { SovereignInferenceClient } from "@sovereign-inference/sdk";

const client = new SovereignInferenceClient({
  baseUrl: "http://localhost:8080",
  defaults: { privacyMode: "direct", verification: "signed-receipt" },
});

const res = await client.chatCompletions({
  model: "qwen-coder-7b-instruct-gguf-q4_k_m",
  messages: [{ role: "user", content: "Write a small parser." }],
  max_tokens: 256,
});

console.log(res.choices[0]?.message.content);
if (res.sip_receipt) console.log("served by", res.sip_receipt.provider_pubkey);
```

See the [protocol spec](../docs/spec/protocol-spec.md) for headers and endpoints.
