# sin-cli (`sin`)

The operator-facing command-line interface for the Sovereign Inference Node.

**Status:** Phase 1 implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

```console
sin scan [--json]                          # detect hardware + runtimes
sin recommend --task coding [--top N]      # ranked model/quant picks that fit
sin catalog [--json]                       # the curated model catalog
sin serve --runtime ollama --model NAME    # start a local OpenAI-compatible server
sin install --runtime ollama --model NAME  # pull a model
sin benchmark --base-url URL --model NAME [--publish KEYFILE]
sin share --runtime ollama --model NAME    # expose this node as a discoverable SIP provider
sin status                                 # registered runtime adapters
sin version
```

### `sin share` — join the network as a provider

Fronts your local model with the real provider gateway (auth, model allowlist,
context/token caps, rate limit, signed receipts, opt-in PIC payment), advertises a
signed `sovereign-node` manifest carrying the node's public URL, and announces it to
a directory other people's routers can discover.

```console
# publish + announce only (no server), e.g. when a gateway runs elsewhere
sin share --model qwen-coder-7b --advertised-url https://my-node.example \
  --unit usdc --input-per-1m 0.20 --output-per-1m 0.60 \
  --directory ~/.sin/providers.json --manifest-out ~/.sin/manifest.json --no-serve

# serve it for real, requiring PIC payment and capping load
sin share --model qwen-coder-7b --port 8090 --key-file key.json \
  --require-payment --pic-issuer ed25519:... --rate-limit 30 --max-output-tokens 512
```

Use `--key-file` (a `sip-receipt keygen` JSON) for a stable provider identity;
without it an ephemeral identity is generated and changes on restart.

A thin wrapper over [`sin-node`](../sin-node); heavy work is delegated to the
library. Design refs: [SIN PRD](../../docs/prd/sin.md), [ROADMAP](../../ROADMAP.md).
