# Transport Modes

SIP-AI supports multiple transport adapters so the network can adapt to normal, privacy-sensitive, and censorship-heavy environments. Direct HTTPS is the default fast path; private transports are opt-in, with clear latency and reliability tradeoffs.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## Adapter-first transport

SIP-AI is adapter-first: the protocol defines the request, payment, and receipt expectations, while a transport adapter carries the request between client and provider gateway. New transports plug in as adapters rather than requiring protocol changes. The logical path is:

```text
SIP-AI Client SDK
  -> Transport adapter: HTTPS, relay, Tor/I2P/Nym-compatible, or batch
     -> Provider gateway on a Sovereign Inference Node
```

This keeps normal HTTPS as the default fast path while letting privacy- and censorship-resistant transports be added without rewriting clients or providers. We frame these as **privacy-preserving**, **censorship-resistant**, and providing **layered resilience** and **reduced linkability** — never as making traffic undetectable or unblockable.

## Transport modes table

| Mode | Description | MVP status | Tradeoff |
| --- | --- | --- | --- |
| Direct HTTPS | Client talks to provider or gateway over ordinary HTTPS. | P0 | Fast and simple, but weaker metadata privacy. |
| Relay HTTPS | Client routes through one or more SIP-AI relays. | P0/P1 | Better IP separation, extra latency and trust assumptions. |
| Tor/Snowflake-compatible | Use Tor ecosystem or Snowflake-style circumvention path where appropriate. | P2 | Improves reach in censored networks, but can be slow or blocked [S27]. |
| I2P-compatible | Use I2P hidden service or tunnel path. | P2 | Good for anonymous overlay use, but adoption and UX are harder [S28]. |
| Nym-compatible | Use mixnet-style metadata protection. | P2 | Stronger metadata privacy patterns, higher latency [S29]. |
| Batch/offline | Send delayed request and retrieve later. | P2 | Resilient under censorship, no streaming UX. |

## Mode details

### Direct HTTPS (P0 — the default fast path)

The client talks to the provider or gateway over ordinary HTTPS. This is the default and the fastest path, and it works with normal HTTP clients and OpenAI-compatible SDKs. The tradeoff is weaker metadata privacy: the provider and network observers can see connection-level metadata such as client IP. Direct HTTPS is the right choice when latency matters and the user does not need IP separation.

### Relay HTTPS (P0/P1)

The client routes through one or more SIP-AI relays rather than connecting straight to the provider. This gives better IP separation between client and provider — reduced linkability — at the cost of extra latency and additional trust assumptions in the relay operators. Relay mode is part of the first milestone alongside Direct HTTPS, so the demo can show a privacy option without building a full anonymity network.

### Tor/Snowflake-compatible (P2)

Routes over the Tor ecosystem or a Snowflake-style circumvention path where appropriate [S27]. This improves reach in censored networks but can be slow or itself blocked. Documented for the protocol and planned post-MVP; not required for the first milestone.

### I2P-compatible (P2)

Uses an I2P hidden service or tunnel path [S28]. Good for anonymous overlay use, but adoption and UX are harder. Documented and planned post-MVP.

### Nym-compatible (P2)

Uses mixnet-style metadata protection [S29]. Offers stronger metadata-privacy patterns at the cost of higher latency. Documented and planned post-MVP.

### Batch/offline (P2)

The client sends a delayed request and retrieves the result later. This is resilient under censorship because it does not require a live interactive connection, but it gives up streaming UX. Documented and planned post-MVP.

## Security and abuse posture

- Private transport modes are **opt-in** with clear latency and reliability warnings; they are never the default.
- The network does not promise absolute anonymity or guaranteed access against every censor. It promises **layered resilience** and **transparent tradeoffs**.
- The transport a request used is recorded in the signed inference receipt's `privacy_mode` field, so clients can verify which mode was actually used (see [../prd/sip-ai.md](../prd/sip-ai.md) and the authoritative receipt format in [receipts.md](receipts.md)).

## MVP scope for transport

| Capability | Milestone decision |
| --- | --- |
| Direct HTTPS | Included — default fast path. |
| Relay mode | Included — first private option. |
| Tor/I2P/Nym adapters | Documented, not required for the first milestone; defined as a post-MVP path. |
| Batch/offline | Documented, post-MVP. |

---

See also: [../prd/sip-ai.md](../prd/sip-ai.md) for the request lifecycle and transport functional requirements (SIP-FR-010, SIP-FR-015), and [manifests.md](manifests.md) for how providers advertise supported privacy modes.

_Derived from the v0.1.2 Product Requirements Package._
