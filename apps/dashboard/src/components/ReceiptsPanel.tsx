// Stub panel: signed receipts / PIC vouchers are introduced alongside network
// sharing in Phase 2/3.
export function ReceiptsPanel() {
  return (
    <section className="card card--stub">
      <h2 className="card__title">Receipts</h2>
      <p className="muted">Receipts — Phase 2/3</p>
      <p className="stub-note">
        Signed receipts for served requests and Private Inference Credits will appear here once
        network sharing is enabled.
      </p>
    </section>
  );
}
