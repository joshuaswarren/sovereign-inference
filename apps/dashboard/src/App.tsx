import { useEffect, useState } from "react";

import { fetchHardware, fetchRecommendations, fetchStatus } from "./api";
import { HardwareCard } from "./components/HardwareCard";
import { ReceiptsPanel } from "./components/ReceiptsPanel";
import { RecommendationsTable } from "./components/RecommendationsTable";
import { SharingPanel } from "./components/SharingPanel";
import { StatusBar } from "./components/StatusBar";
import type { HardwareProfile, Recommendation, StatusResponse, Task } from "./types";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function App() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [hardware, setHardware] = useState<HardwareProfile | null>(null);
  const [hardwareLoading, setHardwareLoading] = useState(true);
  const [hardwareError, setHardwareError] = useState<string | null>(null);

  const [task, setTask] = useState<Task>("coding");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recLoading, setRecLoading] = useState(true);
  const [recError, setRecError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setStatusLoading(true);
    setStatusError(null);
    fetchStatus(controller.signal)
      .then(setStatus)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setStatusError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setStatusLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setHardwareLoading(true);
    setHardwareError(null);
    fetchHardware(controller.signal)
      .then(setHardware)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setHardwareError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setHardwareLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setRecLoading(true);
    setRecError(null);
    fetchRecommendations(task, controller.signal)
      .then(setRecommendations)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setRecError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setRecLoading(false);
      });
    return () => controller.abort();
  }, [task]);

  return (
    <div className="app">
      <StatusBar status={status} loading={statusLoading} error={statusError} />
      <main className="app__main">
        <HardwareCard profile={hardware} loading={hardwareLoading} error={hardwareError} />
        <RecommendationsTable
          task={task}
          onTaskChange={setTask}
          recommendations={recommendations}
          loading={recLoading}
          error={recError}
        />
        <div className="panel-row">
          <SharingPanel />
          <ReceiptsPanel />
        </div>
      </main>
    </div>
  );
}
