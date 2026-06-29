# sip-receipts (`sip-receipt` CLI)

A small, dependency-light command-line tool to generate provider keys, sign
inference receipts, and **verify** them against a provider public key — without
trusting any central service.

**License:** Apache-2.0 (a client-side verification tool meant for wide use —
see [LICENSING.md](../../LICENSING.md)).

```console
$ sip-receipt keygen -o provider.json
$ sip-receipt demo > receipt.json
$ sip-receipt verify receipt.json
OK   receipt verified — provider ed25519:...
```

See [docs/spec/receipts.md](../../docs/spec/receipts.md) for the receipt format
and signing rules.
