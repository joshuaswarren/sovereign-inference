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
sin status                                 # registered runtime adapters
sin version
```

A thin wrapper over [`sin-node`](../sin-node); heavy work is delegated to the
library. Design refs: [SIN PRD](../../docs/prd/sin.md), [ROADMAP](../../ROADMAP.md).
