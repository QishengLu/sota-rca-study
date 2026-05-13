/**
 * MatrixView — framework × model heatmap dashboard.
 *
 * Renders three views for one matrix run:
 *  1. Accuracy heatmap (AC@1)
 *  2. Node F1 heatmap
 *  3. Cost heatmap (avg total tokens per sample)
 *
 * Data from GET /api/v1/matrix/{run_id}
 */
import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

type CellMetrics = {
  n_total: number;
  n_judged: number;
  n_correct: number;
  ac_at_1: number;
  avg_node_f1: number;
  avg_total_tokens: number;
};

type Cell = {
  exp_id: string;
  framework: string;
  model_alias: string;
  status: string;
  metrics: CellMetrics;
};

type MatrixResponse = {
  run_id: string;
  started_at: string;
  ended_at: string | null;
  frameworks: string[];
  model_aliases: string[];
  cells: Cell[];
};

export function MatrixView() {
  const { runId } = useParams<{ runId: string }>();
  const [params] = useSearchParams();
  const queryRunId = runId || params.get('run_id') || 'latest';
  const [data, setData] = useState<MatrixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metricKind, setMetricKind] = useState<'ac_at_1' | 'avg_node_f1' | 'avg_total_tokens'>('ac_at_1');

  useEffect(() => {
    const url = queryRunId === 'latest'
      ? '/api/v1/matrix/latest'
      : `/api/v1/matrix/${queryRunId}`;
    fetch(url)
      .then(r => r.json())
      .then((d: MatrixResponse) => setData(d))
      .catch(e => setError(String(e)));
  }, [queryRunId]);

  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;
  if (!data) return <div className="p-4">Loading...</div>;

  const colorFor = (val: number | undefined) => {
    if (val === undefined || isNaN(val)) return '#f3f4f6';
    if (metricKind === 'avg_total_tokens') {
      // Lower is better; clip to [0, 100K]
      const norm = Math.min(1, val / 100000);
      const intensity = 1 - norm;
      return `rgba(34, 197, 94, ${0.2 + 0.6 * intensity})`;
    }
    // For AC@1 (0-100) and Node F1 (0-1) — higher is better
    const norm = metricKind === 'ac_at_1' ? val / 100 : val;
    return `rgba(34, 197, 94, ${0.2 + 0.6 * Math.min(1, norm)})`;
  };

  const fmt = (val: number | undefined) => {
    if (val === undefined || isNaN(val)) return '—';
    if (metricKind === 'ac_at_1') return `${val.toFixed(1)}%`;
    if (metricKind === 'avg_node_f1') return val.toFixed(3);
    return val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(0);
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-2">Matrix View — Run {data.run_id}</h1>
      <p className="text-sm text-gray-600 mb-4">
        Started: {data.started_at}
        {data.ended_at && <span> · Ended: {data.ended_at}</span>}
      </p>

      <div className="mb-4 flex gap-2">
        {(['ac_at_1', 'avg_node_f1', 'avg_total_tokens'] as const).map(k => (
          <button
            key={k}
            onClick={() => setMetricKind(k)}
            className={`px-3 py-1 rounded ${metricKind === k ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
          >
            {k === 'ac_at_1' ? 'AC@1' : k === 'avg_node_f1' ? 'Node F1' : 'Avg Tokens'}
          </button>
        ))}
      </div>

      <table className="border-collapse">
        <thead>
          <tr>
            <th className="border p-2 bg-gray-100">Framework \ Model</th>
            {data.model_aliases.map(m => (
              <th key={m} className="border p-2 bg-gray-100">{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.frameworks.map(fw => (
            <tr key={fw}>
              <th className="border p-2 bg-gray-50 text-left">{fw}</th>
              {data.model_aliases.map(m => {
                const cell = data.cells.find(c => c.framework === fw && c.model_alias === m);
                const val = cell?.metrics?.[metricKind];
                return (
                  <td
                    key={m}
                    className="border p-3 text-center"
                    style={{ backgroundColor: colorFor(val) }}
                    title={cell?.exp_id || ''}
                  >
                    <div className="font-bold text-lg">{fmt(val)}</div>
                    {cell?.metrics && (
                      <div className="text-xs text-gray-600">
                        {cell.metrics.n_correct}/{cell.metrics.n_total}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="text-xl font-bold mt-8 mb-2">Cells detail</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100">
            <th className="p-2 text-left">exp_id</th>
            <th className="p-2">Status</th>
            <th className="p-2">N</th>
            <th className="p-2">AC@1</th>
            <th className="p-2">Node F1</th>
            <th className="p-2">Avg Tokens</th>
          </tr>
        </thead>
        <tbody>
          {data.cells.map(c => (
            <tr key={c.exp_id} className="border-b">
              <td className="p-2 font-mono text-xs">{c.exp_id}</td>
              <td className="p-2">{c.status}</td>
              <td className="p-2">{c.metrics?.n_total ?? '—'}</td>
              <td className="p-2">{c.metrics?.ac_at_1?.toFixed(1) ?? '—'}%</td>
              <td className="p-2">{c.metrics?.avg_node_f1?.toFixed(3) ?? '—'}</td>
              <td className="p-2">{c.metrics?.avg_total_tokens?.toFixed(0) ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
