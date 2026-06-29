# sip-router

The SIP-AI routing client SDK: selects one provider per request from a scoring
policy, optionally requests a signed quote, routes the request, verifies the
provider-signed receipt, and **fails over** to the next provider on any failure.

**Status:** Phase 2 implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

```python
from sip_router import ProviderRegistry, SovereignClient

client = SovereignClient(registry, token="...")
result = client.chat("qwen2.5-coder-7b-instruct", [{"role": "user", "content": "Hi"}])
print(result.content, "served by", result.provider_pubkey)
# result.receipt is verified (signature + provider-key binding + response-body hash)
```

What it does (see [client.py](src/sip_router/client.py)):
- **registry / resolver** — find providers that serve a model.
- **scoring** — rank providers by the weighted formula (spec §6.8).
- **client** — resolve → score → (quote) → route → **verify receipt** → failover.

Receipt trust requires a valid signature, a provider-key matching the manifest,
and `response_hash == hash(response)`. When quotes are used, the receipt price is
enforced against the signed quote's `max_price`. Design refs:
[protocol spec](../../docs/spec/protocol-spec.md),
[provider selection](../../docs/spec/provider-selection.md).
