# sip-openai-proxy

**Use the Sovereign Inference network like a local LLM.** Run this one server and
point any OpenAI-compatible client (the `openai` SDK, LangChain, LM Studio, a
chat UI, `curl`) at it — your requests route across SIP-AI providers with failover,
policy enforcement, and a verified signed receipt for every answer.

```console
# serve providers from a local registry (or a discovery directory)
sip-openai-proxy --registry ~/.sin/providers.json --port 11435
# optionally: --directory ~/.sin/directory.json  --api-key sk-local-...
#             --require-attestation --max-input-per-1m 0.5 --accepted-unit usdc
```

Then just set the base URL:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:11435/v1", api_key="sk-local-...")
client.chat.completions.create(model="qwen-coder-7b", messages=[{"role": "user", "content": "hi"}])
```

Endpoints: `GET /v1/models`, `POST /v1/chat/completions` (streaming and
non-streaming), `GET /healthz`. Unknown providers/models return a clean error; a
[`sip-policy`](../../packages/policy) `Policy` (attestation, price caps, privacy
modes, allow/deny, reputation) gates which providers may serve.

**Status:** implemented. **License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [MVP & demo](../../docs/mvp-and-demo.md), [Architecture](../../docs/architecture.md).
