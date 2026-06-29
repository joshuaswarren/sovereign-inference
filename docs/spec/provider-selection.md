# Provider Selection

The SIP-AI router selects exactly one provider per request using a transparent, weighted scoring formula. This document explains each weighted term, why jurisdiction and location must be opt-in, and how reputation inputs feed the score.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## One provider per request

In v1, each inference request is handled by one selected provider node that has the full model available — there is no public multi-node model sharding. Failover happens **between** providers, not within a single model execution. The router's job is therefore to pick the single best provider for each request, and to fail over to the next-best provider if a health check, quote, payment, or execution fails.

## Scoring formula

The router scores providers with a transparent weighted formula. The first implementable version is simple and deterministic; it becomes user-tunable as the system matures.

```text
provider_score =
  0.25 * model_fit
+ 0.20 * expected_latency_score
+ 0.15 * price_score
+ 0.15 * receipt_trust_score
+ 0.10 * uptime_score
+ 0.10 * privacy_mode_match
+ 0.05 * geographic_or_jurisdiction_preference
```

## Each weighted term

| Term | Weight | What it measures |
| --- | --- | --- |
| `model_fit` | 0.25 | How well the provider serves the requested model — does it have the exact model artifact, format, quantization, and context length the client needs. The largest single weight, because serving the wrong or a poorly fitting model undermines everything else. |
| `expected_latency_score` | 0.20 | Predicted responsiveness, drawing on benchmarked time-to-first-token and tokens/sec plus observed latency. Higher score for providers expected to respond faster. |
| `price_score` | 0.15 | How favorable the provider's quoted price is, derived from its pricing structure (input/output per-1M-token rates) relative to the client's budget. |
| `receipt_trust_score` | 0.15 | Confidence in the provider's accountability, driven primarily by the validity of its past signed inference receipts. A provider whose receipts consistently verify against its public key scores higher. |
| `uptime_score` | 0.10 | How consistently the provider has responded over a measurement window. |
| `privacy_mode_match` | 0.10 | How well the provider's supported privacy modes match what the client requested (e.g. relay, private-payment). A provider that cannot honor the requested privacy mode scores low here. |
| `geographic_or_jurisdiction_preference` | 0.05 | Optional preference for provider location or jurisdiction. The smallest weight, and **off unless the user opts in** (see below). |

## Why jurisdiction and location must be opt-in

The router should **never make provider location or jurisdiction mandatory unless the user explicitly opts into that criterion.** There are two reasons:

1. **Availability.** Overly strict routing on location reduces the pool of eligible providers and can leave a request with no provider at all.
2. **Fingerprinting risk.** A user who consistently constrains routing to a narrow geography or jurisdiction creates a distinctive routing pattern — a privacy fingerprint — that can reduce, rather than improve, their privacy. Making the term low-weight (0.05) and opt-in keeps it from accidentally degrading both availability and privacy.

This mirrors the broader SIP-AI posture: privacy without magical claims, and transparent tradeoffs rather than rigid defaults that backfire.

## How reputation inputs feed scoring

Provider reputation is built from a set of inputs that the router can collect and weigh over time (SIP-FR-013):

- **Uptime** — feeds `uptime_score` directly.
- **Receipt validity** — feeds `receipt_trust_score`; receipts that verify against the provider's public key build trust, invalid or missing receipts erode it.
- **Benchmark drift** — divergence between a provider's advertised benchmark (in its manifest) and its observed performance lowers trust and expected-latency confidence.
- **Latency** — observed responsiveness feeds `expected_latency_score`.
- **Dispute history** — past disputes lower a provider's standing.

In the first milestone, reputation can be local to each router (a router updates its own local reputation after each request, per the request lifecycle). Whether reputation is later made public, pseudonymous, or kept router-local is an open question deferred beyond the first milestone. Either way, reputation is an input to scoring, not a separate gate, so the formula stays transparent and tunable.

## Failover

When the selected provider's health check, quote, payment, or request execution fails, the router retries with the next-ranked provider — provided the client's budget and privacy settings still permit it (SIP-FR-009). Failover between providers, combined with one-provider-per-request execution, keeps latency, accountability, and verification tractable.

---

See also: [../prd/sip-ai.md](../prd/sip-ai.md) for the full request lifecycle and functional requirements, [manifests.md](manifests.md) for the provider metadata that scoring reads, and [transport-modes.md](transport-modes.md) for the privacy modes matched by `privacy_mode_match`.

_Derived from the v0.1.2 Product Requirements Package._
