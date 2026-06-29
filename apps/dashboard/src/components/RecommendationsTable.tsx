import type { Recommendation, Task } from "../types";
import { TASKS } from "../types";

interface RecommendationsTableProps {
  task: Task;
  onTaskChange: (task: Task) => void;
  recommendations: Recommendation[];
  loading: boolean;
  error: string | null;
}

function tps(value: number | null): string {
  return value != null ? `${value.toFixed(1)} tok/s` : "—";
}

export function RecommendationsTable({
  task,
  onTaskChange,
  recommendations,
  loading,
  error,
}: RecommendationsTableProps) {
  return (
    <section className="card">
      <div className="card__header">
        <h2 className="card__title">Recommendations</h2>
        <label className="task-select">
          <span className="task-select__label">Task</span>
          <select
            value={task}
            onChange={(e) => onTaskChange(e.target.value as Task)}
            aria-label="Task"
          >
            {TASKS.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? <p className="muted">Computing recommendations…</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && !error ? (
        recommendations.length > 0 ? (
          <div className="table-wrap">
            <table className="rec-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Runtime</th>
                  <th>Quant</th>
                  <th className="num">Est. total</th>
                  <th>Fits</th>
                  <th className="num">Speed</th>
                  <th>Why</th>
                </tr>
              </thead>
              <tbody>
                {recommendations.map((r) => (
                  <tr key={`${r.model_id}-${r.runtime}-${r.quant}-${r.context}`}>
                    <td>
                      <div className="rec-model">{r.display_name}</div>
                      <div className="rec-model__id muted">{r.model_id}</div>
                    </td>
                    <td>{r.runtime}</td>
                    <td>{r.quant}</td>
                    <td className="num">{r.estimate.total_gb.toFixed(1)} GB</td>
                    <td>
                      <span className={`chip ${r.fits ? "chip--ok" : "chip--error"}`}>
                        {r.fits ? "fits" : "too big"}
                      </span>
                    </td>
                    <td className="num">{tps(r.predicted_tps)}</td>
                    <td className="rec-why">
                      {r.why}
                      {r.tradeoffs.length > 0 ? (
                        <ul className="rec-tradeoffs">
                          {r.tradeoffs.map((t, i) => (
                            <li key={i}>{t}</li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No recommendations for this task on this machine.</p>
        )
      ) : null}
    </section>
  );
}
