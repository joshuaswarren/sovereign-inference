# Risk Register

The risks that could threaten Sovereign Inference, with their impact, likelihood, and the mitigation we are building in. This register is reviewed as the protocol and node mature.

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| SIP acronym conflict | Confusion with VoIP protocol | High | Use SIP-AI in technical contexts and avoid the `sip://` scheme [S4]. |
| Too much overlap with existing decentralized inference projects | Judges see it as derivative | Medium | Position as adapter-first access and provider onboarding layer; demo integrations. |
| Privacy overclaim | Credibility or legal risk | Medium | Use precise claims: reduced linkability, layered transport, no guarantee of undetectability. |
| Payment complexity slows the build | Demo slips | Medium | Ship the x402 and PIC voucher paths in a simple-but-real first form; document the cryptographic upgrade path. |
| Provider abuse or illegal use | Network reputational and legal risk | Medium | Provider policy controls, model allowlists, rate limits, abuse throttles, no default public sharing. |
| Provider node security vulnerability | User machine compromise | Medium | Gateway isolation, no arbitrary remote code/model loads, container sandboxing, least privilege, auto-update path. |
| Latency through private transport | Poor UX | High | Default to direct or relay mode; private transport is opt-in with warning. |
| Model licensing mistakes | Commercial/legal risk | Medium | Model catalog stores license flags and warnings; provider must accept license terms before serving. |
| Cold start supply problem | No providers available | Medium | SIN makes provider onboarding easy; also integrate existing compute networks. |
| Verification weaker than users assume | Trust gap | Medium | Call receipts accountability artifacts, not full cryptographic proof of model execution. |

## Related docs

- [threat-model.md](threat-model.md) — the security and abuse risks above, expanded into trust boundaries and STRIDE-style threats.
- [open-questions.md](open-questions.md) — unresolved design questions, several of which touch these risks.
- [references.md](references.md) — sources behind the [S#] citations above.

_Derived from the v0.1.2 Product Requirements Package._
