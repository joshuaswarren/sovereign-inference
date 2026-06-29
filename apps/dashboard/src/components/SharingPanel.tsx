// Stub panel: network capacity sharing (provider gateway, quotas, manifest
// publication) lands in Phase 2/3. Shown here so the layout is complete.
export function SharingPanel() {
  return (
    <section className="card card--stub">
      <h2 className="card__title">Capacity sharing</h2>
      <p className="muted">Capacity sharing — Phase 2/3</p>
      <p className="stub-note">
        Publish spare capacity to the SIP-AI network with quotas, rate limits, a hardened
        provider gateway, and a signed provider manifest. Local-only by default.
      </p>
    </section>
  );
}
