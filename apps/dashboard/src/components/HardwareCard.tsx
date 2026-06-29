import type { HardwareProfile } from "../types";

interface HardwareCardProps {
  profile: HardwareProfile | null;
  loading: boolean;
  error: string | null;
}

function gb(value: number): string {
  return `${value.toFixed(1)} GB`;
}

export function HardwareCard({ profile, loading, error }: HardwareCardProps) {
  return (
    <section className="card">
      <h2 className="card__title">Hardware</h2>
      {loading ? <p className="muted">Scanning hardware…</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && !error && profile ? (
        <div className="hw-grid">
          <Field label="OS">
            {profile.os} {profile.os_version} ({profile.arch})
          </Field>
          <Field label="CPU">
            {profile.cpu.model ?? "unknown"}
            {profile.cpu.physical_cores != null ? ` — ${profile.cpu.physical_cores} cores` : ""}
            {profile.cpu.logical_cores != null ? ` / ${profile.cpu.logical_cores} threads` : ""}
          </Field>
          <Field label="RAM">
            {gb(profile.ram_available_gb)} free of {gb(profile.ram_total_gb)}
            {profile.unified_memory ? " (unified)" : ""}
          </Field>
          <Field label="Disk">{gb(profile.disk_free_gb)} free</Field>
          <Field label="Accelerator">
            <span className="chip chip--accent">{profile.accelerator}</span>
          </Field>
          <Field label="GPU">
            {profile.gpus.length > 0 ? (
              <ul className="bare-list">
                {profile.gpus.map((g, i) => (
                  <li key={`${g.name}-${i}`}>
                    <span className="chip chip--vendor">{g.vendor}</span> {g.name}
                    {g.vram_total_gb != null ? ` — ${gb(g.vram_total_gb)} VRAM` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="muted">none detected</span>
            )}
          </Field>
        </div>
      ) : null}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <span className="field__label">{label}</span>
      <span className="field__value">{children}</span>
    </div>
  );
}
