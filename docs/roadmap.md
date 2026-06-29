# Roadmap

The phased build plan for Sovereign Inference, from protocol spec through production hardening. Phases 0-4 target the DecentralizeAI hackathon Round 1 (June-October 2026); Phases 5-6 are post-hackathon hardening.

| Phase | Time horizon | Deliverables |
| --- | --- | --- |
| Phase 0: Spec and proof of concept | Week 1 | Protocol spec v0.1, model/provider manifest schemas, receipt format, CLI skeleton. |
| Phase 1: Local node | Weeks 2-3 | Hardware scan, model advisor, local llama.cpp/Ollama serving, benchmark, dashboard. |
| Phase 2: Network routing | Weeks 3-4 | Provider registry, routing, quote, direct request, signed receipts, failover. |
| Phase 3: Payment demo | Weeks 4-5 | x402 path, PIC voucher issuance/redeem/settle flow, provider accounting. |
| Phase 4: Decentralized integration | Weeks 5-6 | Arweave manifest anchor, one compute/provider adapter such as Nosana or Akash, published demo metrics. |
| Phase 5: Privacy modes | Post-MVP | Relay hardening, Tor/I2P/Nym transport experiments, TEE-capable provider metadata. |
| Phase 6: Production hardening | Post-hackathon | Security review, signed releases, plugin SDK, policy framework, provider reputation. |

## Related docs

- [mvp-and-demo.md](mvp-and-demo.md) — the milestone these phases build toward.
- [user-stories.md](user-stories.md) — the stories each phase delivers.
- [go-to-market.md](go-to-market.md) — how the project evolves after the hackathon.
- [references.md](references.md) — source references for the technologies named above.

_Derived from the v0.1.2 Product Requirements Package._
