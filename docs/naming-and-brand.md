# Naming and Brand Strategy

How the Sovereign Inference names map to public copy, engineering docs, and package names, plus the guardrails that keep the brand precise and collision-free.

## Why the names matter

The name Sovereign Inference Protocol is strong. It communicates user ownership, self-hosting, open access, and exit from centralized AI chokepoints. There is one practical issue: SIP is already widely used for the Session Initiation Protocol defined by IETF RFC 3261, especially in VoIP and multimedia session signaling [S4]. The naming strategy below resolves that collision while keeping the brand memorable.

## Names and recommendations

| Name | Use | Risk | Recommendation |
| --- | --- | --- | --- |
| Sovereign Inference Protocol | Public concept and protocol name | SIP acronym collision with Session Initiation Protocol | Use the full name in public copy and SIP-AI in technical docs |
| SIP-AI | Engineering and spec acronym | Still close to SIP, but differentiated | Use for repository names, package names, and protocol docs |
| Sovereign Inference Node | Installable local serving node | SIN acronym is memorable but polarizing | Use SIN in hackathon/dev community; use Sovereign Node for enterprise-facing copy |
| Private Inference Credits | Payment/voucher layer | PIC is generic but clear | Use PIC as the privacy-preserving credit primitive |
| Sovereign Receipts | Signed proof of execution | Could imply stronger verification than provided | Use Signed Inference Receipt until verification matures |

## Naming guardrails

- **Do not use `sip://` as a URL scheme.** It creates unnecessary collision with existing telephony infrastructure (Session Initiation Protocol / VoIP) [S4].
- **Use SIP-AI in technical contexts.** Reserve the full name "Sovereign Inference Protocol" for public-facing copy and use SIP-AI in repository names, package names, and protocol docs.
- **Prefer package names** like `sovinfer`, `sovereign-inference`, `sip-ai-sdk`, and `sovereign-node`.
- **Use SIN as an internal and hackathon-friendly acronym,** but default to "Sovereign Node" in conservative or enterprise-facing contexts.
- **Use precise privacy language.** Avoid promising invisibility, undetectability, or guaranteed censorship bypass. Use *resilient*, *privacy-preserving*, *censorship-resistant*, and *hard to block* instead. The network promises layered resilience and transparent tradeoffs, not absolute anonymity.

## Quick reference

- **SIP-AI** = Sovereign Inference Protocol — the routing, payment, manifest, transport, and receipt protocol.
- **SIN** = Sovereign Inference Node — the local-first installable node for running and optionally sharing models.
- **PIC** = Private Inference Credits — the voucher/token primitive used to pay for inference without directly linking the provider request to the original wallet purchase.

See also: [Vision](vision.md), [Opportunity](opportunity.md), [Product Principles](product-principles.md).

_Derived from the v0.1.2 Product Requirements Package._
