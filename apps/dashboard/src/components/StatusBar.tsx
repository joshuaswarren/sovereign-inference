import type { StatusResponse } from "../types";

interface StatusBarProps {
  status: StatusResponse | null;
  loading: boolean;
  error: string | null;
}

export function StatusBar({ status, loading, error }: StatusBarProps) {
  return (
    <header className="statusbar">
      <div className="statusbar__brand">
        <span className="statusbar__dot" data-state={error ? "error" : status ? "ok" : "pending"} />
        <span className="statusbar__title">Sovereign Inference Node</span>
        {status ? <span className="statusbar__version">v{status.version}</span> : null}
      </div>
      <div className="statusbar__adapters">
        {loading ? <span className="muted">Connecting…</span> : null}
        {error ? <span className="chip chip--error">offline</span> : null}
        {!loading && !error && status
          ? status.adapters.length > 0
            ? status.adapters.map((name) => (
                <span key={name} className="chip">
                  {name}
                </span>
              ))
            : <span className="muted">no adapters</span>
          : null}
      </div>
    </header>
  );
}
