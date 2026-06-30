# sip-relay

A SIP-AI **privacy relay**. A client sends its inference request to the relay; the
relay forwards it to the chosen provider, so the **provider sees the relay, not the
client**. Combined with bearer credits (PIC / issuer-unlinkable blind credits), the
provider learns nothing about who the buyer is.

The relay is **untrusted for integrity**: the provider signs the receipt over both
the response *and the request* (`request_hash`), so the client detects tampering
**and** a relay that substitutes a genuine answer from a different prompt. The relay
only forwards to a provider's **signed `manifest_uri`** and refuses private/loopback/
link-local/metadata addresses (a basic SSRF guard).

**Trust note (honest):** a manifest verifying its *own* embedded key is not a trust
anchor — any party can self-sign one. A production relay should gate forwarding on a
trusted provider set / signed directory (and add DNS-resolution + rebinding
protection); the built-in checks block the obvious SSRF literals but are not a
substitute for an allowlist.

```console
sip-relay --host 0.0.0.0 --port 8099
```

**Scope (honest):** this is a single-hop relay — it hides the client from the
provider but the relay itself sees the plaintext request. Multi-hop onion routing
and end-to-end request encryption are future work.

**Status:** implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [Transport modes](../../docs/transport.md), [Architecture](../../docs/architecture.md).
