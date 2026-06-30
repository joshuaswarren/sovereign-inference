import { useCallback, useEffect, useState } from "react";

import {
  type ConfigState,
  type RuntimeStatus,
  type VerifiedChat,
  addDirectory,
  addProvider,
  completeOnboarding,
  getRuntimes,
  startLocalUse,
  testChat,
} from "./api";

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function Onboarding({
  initialConfig,
  onComplete,
}: {
  initialConfig: ConfigState;
  onComplete: (config: ConfigState) => void;
}) {
  const [config, setConfig] = useState<ConfigState>(initialConfig);
  const [runtimes, setRuntimes] = useState<RuntimeStatus[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [dirUrl, setDirUrl] = useState("");
  const [manifestText, setManifestText] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [chatPrompt, setChatPrompt] = useState("Say hello in five words.");
  const [chatResult, setChatResult] = useState<VerifiedChat | null>(null);

  const refreshRuntimes = useCallback(async () => {
    setError(null);
    try {
      setRuntimes(await getRuntimes());
    } catch (err) {
      setError(message(err));
    }
  }, []);

  useEffect(() => {
    void refreshRuntimes();
  }, [refreshRuntimes]);

  const hasModels = config.models.length > 0;

  async function run(label: string, action: () => Promise<ConfigState>): Promise<void> {
    setBusy(label);
    setError(null);
    try {
      setConfig(await action());
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(null);
    }
  }

  function onAddProvider(): void {
    let manifest: unknown;
    try {
      manifest = JSON.parse(manifestText);
    } catch {
      setError("That provider manifest is not valid JSON.");
      return;
    }
    void run("provider", async () => {
      const next = await addProvider(manifest);
      setManifestText("");
      return next;
    });
  }

  async function onTestChat(): Promise<void> {
    const model = chatModel || config.models[0];
    if (!model) return;
    setBusy("chat");
    setError(null);
    setChatResult(null);
    try {
      setChatResult(await testChat(model, chatPrompt));
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(null);
    }
  }

  function onFinish(): void {
    void run("finish", async () => {
      const next = await completeOnboarding();
      onComplete(next);
      return next;
    });
  }

  return (
    <div className="onboard">
      <header className="onboard__head">
        <h1 className="onboard__title">Welcome to Sovereign Inference</h1>
        <p className="muted">
          Choose where inference comes from. When you&rsquo;re set up, point any OpenAI-compatible client at{" "}
          <code>http://localhost:11435/v1</code> — no terminal required.
        </p>
      </header>

      {error && <div className="onboard__error">{error}</div>}

      <section className="onboard__card">
        <h2 className="card__title">1 · Use a model on this computer</h2>
        <p className="muted">Front a model already running locally (Ollama / llama.cpp) — it stays fully local.</p>
        {runtimes === null ? (
          <p className="muted">Detecting local runtimes…</p>
        ) : runtimes.some((r) => r.available) ? (
          <ul className="onboard__runtimes">
            {runtimes
              .filter((r) => r.available)
              .map((r) => (
                <li key={r.name} className="onboard__runtime">
                  <span className="onboard__runtime-name">{r.name}</span>
                  {r.models.length === 0 ? (
                    <span className="muted">no models pulled — pull one, then Refresh</span>
                  ) : (
                    <span className="onboard__models">
                      {r.models.map((m) => (
                        <button
                          key={m}
                          className="chip chip--action"
                          disabled={busy !== null}
                          onClick={() => void run(`local:${r.name}:${m}`, () => startLocalUse(r.name, m))}
                        >
                          Use {m}
                        </button>
                      ))}
                    </span>
                  )}
                </li>
              ))}
          </ul>
        ) : (
          <p className="muted">
            No local runtime detected. Install{" "}
            <a href="https://ollama.com" target="_blank" rel="noreferrer">
              Ollama
            </a>{" "}
            and start it, then refresh.
          </p>
        )}
        <button className="btn btn--ghost" disabled={busy !== null} onClick={() => void refreshRuntimes()}>
          Refresh runtimes
        </button>
      </section>

      <section className="onboard__card">
        <h2 className="card__title">2 · …or connect to the network</h2>
        <p className="muted">Discover providers from a directory, or paste a signed provider manifest.</p>
        <div className="onboard__row">
          <input
            className="onboard__input"
            placeholder="https://directory.example/sip"
            value={dirUrl}
            onChange={(e) => setDirUrl(e.target.value)}
          />
          <button
            className="btn"
            disabled={busy !== null || dirUrl.trim() === ""}
            onClick={() =>
              void run("directory", async () => {
                const next = await addDirectory(dirUrl.trim());
                setDirUrl("");
                return next;
              })
            }
          >
            Add directory
          </button>
        </div>
        <textarea
          className="onboard__textarea"
          placeholder='{"schema":"sip-ai.provider_manifest.v1", ...}'
          value={manifestText}
          onChange={(e) => setManifestText(e.target.value)}
          rows={3}
        />
        <button className="btn" disabled={busy !== null || manifestText.trim() === ""} onClick={onAddProvider}>
          Add provider manifest
        </button>
      </section>

      <section className="onboard__card">
        <h2 className="card__title">3 · You&rsquo;re ready</h2>
        {hasModels ? (
          <p className="onboard__ready">
            ✓ {config.models.length} model{config.models.length === 1 ? "" : "s"} available:{" "}
            {config.models.map((m) => (
              <span key={m} className="chip">
                {m}
              </span>
            ))}
          </p>
        ) : (
          <p className="muted">No models yet — add a local model or a network source above (or finish and add later).</p>
        )}

        {config.warnings.length > 0 && (
          <ul className="onboard__warnings">
            {config.warnings.map((w) => (
              <li key={w}>⚠ {w}</li>
            ))}
          </ul>
        )}

        {hasModels && (
          <div className="onboard__chat">
            <div className="onboard__row">
              <select className="onboard__input" value={chatModel} onChange={(e) => setChatModel(e.target.value)}>
                {config.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <input
                className="onboard__input"
                value={chatPrompt}
                onChange={(e) => setChatPrompt(e.target.value)}
                aria-label="Test prompt"
              />
              <button className="btn" disabled={busy !== null} onClick={() => void onTestChat()}>
                {busy === "chat" ? "Sending…" : "Try it"}
              </button>
            </div>
            {chatResult && (
              <div className="onboard__chat-result">
                <p className="onboard__answer">{chatResult.content}</p>
                {chatResult.receipt_verified && chatResult.provider_pubkey && (
                  <p className="onboard__verified">
                    ✓ verified signed receipt from {chatResult.provider_pubkey.slice(0, 12)}…
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <button className="btn btn--primary" disabled={busy !== null} onClick={onFinish}>
          {busy === "finish" ? "Finishing…" : "Finish setup →"}
        </button>
      </section>
    </div>
  );
}
