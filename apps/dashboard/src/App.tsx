import { useEffect, useState } from "react";

import { Dashboard } from "./Dashboard";
import { Onboarding } from "./onboarding/Onboarding";
import { type ConfigState, getConfig } from "./onboarding/api";

type Gate = { phase: "loading" } | { phase: "onboarding"; config: ConfigState } | { phase: "ready" };

/** Root gate: decide between first-run onboarding and the node dashboard BEFORE
 * any dashboard data fetch runs. We ask the app server for its config first; an
 * unconfigured node shows the wizard, a configured one shows the dashboard. */
export function App() {
  const [gate, setGate] = useState<Gate>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((config) => {
        if (cancelled) return;
        setGate(config.onboarding_complete ? { phase: "ready" } : { phase: "onboarding", config });
      })
      .catch(() => {
        // No admin API reachable (e.g. the dashboard served standalone) — fall
        // back to the dashboard rather than blocking on the wizard.
        if (!cancelled) setGate({ phase: "ready" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (gate.phase === "loading") {
    return <div className="app app--center">Starting Sovereign Inference…</div>;
  }
  if (gate.phase === "onboarding") {
    return <Onboarding initialConfig={gate.config} onComplete={() => setGate({ phase: "ready" })} />;
  }
  return <Dashboard />;
}
