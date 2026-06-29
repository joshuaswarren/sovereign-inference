# Examples

Real, runnable artifacts you can verify yourself.

## `sample-receipt.json`

A genuine [signed inference receipt](../docs/spec/receipts.md). Its Ed25519
signature verifies against its embedded `provider_pubkey`:

```console
uv run sip-receipt verify examples/sample-receipt.json
# -> OK   receipt verified — provider ed25519:...
```

Tamper with any field (a token count, the price, the response hash) and
verification fails with exit code 1 — that's the whole point.

## More to come

End-to-end routing, payment, and failover examples land with Phases 2–3 of the
[ROADMAP](../ROADMAP.md) under [`apps/router-demo`](../apps/router-demo).
