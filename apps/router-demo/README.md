# router-demo

An end-to-end demo of Sovereign Inference **Phase 2 (network routing)**: the real
[`sip-router`](../../packages/router) client routes an OpenAI-compatible chat
request across **two real [`sip-provider-gateway`](../../packages/provider-gateway)
gateways**, verifies the provider-signed receipt, then — when the top-ranked
provider goes down — transparently **fails over** to the second provider and
verifies its receipt too.

Everything runs **in-process**: the two gateways are real
`sip_gateway.create_app(...)` ASGI apps, reached over an httpx ASGI transport, so
there are no sockets, no ports, and no mocked business logic. Only the network
boundary is bridged — the gateways run their real auth, quota, and
receipt-signing code, and the client runs its real resolution, failover, and
[`sip_protocol.verify_receipt`](../../packages/sip-protocol) verification.

## Run it

```bash
uv run sip-router-demo
# or
uv run python -m sip_router_demo.demo
```

Expected output (provider pubkeys are freshly generated each run):

```text
=== Sovereign Inference: routing + failover demo ===
model: qwen-coder-7b
registered providers: http://provider-a (ed25519:...), http://provider-b (ed25519:...)

--- routing request (both providers healthy) ---
served by: http://provider-a (provider-a)
provider pubkey: ed25519:...
response: 'echo: In one sentence, what is sovereign inference?'
receipt verified: OK (signature + schema valid)

--- http://provider-a goes DOWN; routing again ---
attempts: [('http://provider-a', 'unhealthy'), ('http://provider-b', 'ok')]
FAILED OVER to: http://provider-b (provider-b)
provider pubkey: ed25519:...
response: 'echo: In one sentence, what is sovereign inference?'
receipt verified: OK (signature + schema valid)

=== demo complete: routed, verified, and failed over successfully ===
```

`main()` returns `0` on success.

## How it works

`src/sip_router_demo/demo.py` wires the real components together:

- **Two gateways.** Each provider is `create_app(adapter=MockAdapter(),
  keypair=KeyPair.generate(), allowed_models=[MODEL], token=TOKEN)`. The
  `MockAdapter` echoes the prompt, so receipts and usage are populated without a
  real model server.
- **In-process transport.** `_SyncASGITransport` bridges the router's
  synchronous `httpx.Client` to each async ASGI app (httpx's `ASGITransport` is
  async-only), driving the app on a fresh event loop per request and
  materializing the response. `sync_client_factory({base_url: app})` is the
  `SovereignClient` `client_factory`, mapping `http://provider-a` /
  `http://provider-b` to the right app.
- **Registry.** Each provider is registered via `make_provider_entry`, which
  fetches the gateway's signed `/sip/v1/provider-manifest` and builds a
  `ProviderEntry`.
- **Failover.** `down_client_factory(apps, down={...})` hands a 503-everywhere
  transport for any "down" provider, so the router records it as failed and
  routes to the next candidate.

## Tests

The end-to-end proof of Phase 2 lives in `tests/test_e2e.py`:

```bash
uv run pytest apps/router-demo/tests/
```

- `test_routes_and_returns_verified_receipt` — routes through a real gateway and
  asserts the content is non-empty, the receipt verifies, and the provider
  pubkey matches the serving gateway.
- `test_fails_over_when_first_provider_unhealthy` — the top provider returns 503;
  the request still succeeds on the other provider with a valid receipt, and
  `attempts` records the failed provider first.
- `test_raises_when_all_providers_fail` — both providers down ⇒
  `NoProviderAvailable`.
- `test_main_runs_and_returns_zero` — the `main()` demo runs end to end and
  returns `0`.

This is the centerpiece of the [demo script](../../docs/mvp-and-demo.md) and the
hackathon [evidence plan](../../docs/hackathon/evidence-plan.md), built in
Phase 2 of the [ROADMAP](../../ROADMAP.md).

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).
