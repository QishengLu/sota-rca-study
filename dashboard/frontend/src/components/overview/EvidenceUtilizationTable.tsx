import { Fragment } from 'react';
import type { TransitionResponse } from '../../api/types';

interface EvidenceUtilizationTableProps {
  data: TransitionResponse;
}

const RT_KEYS = ['rt_utilized_rate', 'rt_partial_rate', 'rt_ignored_rate', 'rt_no_data_rate'] as const;
const RT_LABELS: Record<string, string> = {
  rt_utilized_rate: 'R→T Utilized',
  rt_partial_rate: 'R→T Partial',
  rt_ignored_rate: 'R→T Ignored',
  rt_no_data_rate: 'R→T No Data',
};

export function EvidenceUtilizationTable({ data }: EvidenceUtilizationTableProps) {
  if (data.experiments.length === 0) return null;

  const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-2">
        R→T Utilization Analysis
      </h3>
      <p className="text-sm text-slate-500 mb-4">
        Round-level R→T: whether the agent's next actions target services discovered in previous results.
        Utilized = full overlap, Partial = some overlap, Ignored = no overlap, No Data = no GT services in results.
      </p>
      <div className="overflow-x-auto">
        <table className="text-left" style={{ minWidth: Math.max(700, data.experiments.length * 320 + 160) }}>
          <thead>
            <tr className="border-b-2 border-slate-200">
              <th className="py-2 px-3 text-sm font-semibold text-slate-600 whitespace-nowrap" rowSpan={2} style={{ minWidth: 140 }}>
                Metric
              </th>
              {data.experiments.map((exp) => (
                <th
                  key={exp.exp_id}
                  colSpan={3}
                  className="py-2 px-3 text-sm font-semibold text-center text-slate-700 border-l border-slate-200"
                  style={{ minWidth: 300 }}
                >
                  {exp.exp_id}
                  <div className="text-xs font-normal text-slate-400">
                    C:{exp.correct_count} / I:{exp.incorrect_count}
                  </div>
                </th>
              ))}
            </tr>
            <tr className="border-b border-slate-200">
              {data.experiments.map((exp) => (
                <Fragment key={exp.exp_id}>
                  <th className="py-1 px-3 text-xs text-center text-emerald-600 border-l border-slate-200" style={{ minWidth: 90 }}>
                    Correct
                  </th>
                  <th className="py-1 px-3 text-xs text-center text-red-500" style={{ minWidth: 90 }}>
                    Incorrect
                  </th>
                  <th className="py-1 px-3 text-xs text-center text-slate-400" style={{ minWidth: 90 }}>
                    Δ
                  </th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {RT_KEYS.map((metricKey) => {
              const label = RT_LABELS[metricKey] ?? metricKey;
              return (
                <tr key={metricKey} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-3 text-sm text-slate-700 font-medium whitespace-nowrap">{label}</td>
                  {data.experiments.map((exp) => {
                    const cv = exp.correct_rates[metricKey] ?? 0;
                    const iv = exp.incorrect_rates[metricKey] ?? 0;
                    const diff = cv - iv;
                    return (
                      <Fragment key={exp.exp_id}>
                        <td className="py-2 px-3 text-sm text-center border-l border-slate-100" style={{ minWidth: 90 }}>
                          <span className="text-emerald-600 font-medium">{fmtPct(cv)}</span>
                        </td>
                        <td className="py-2 px-3 text-sm text-center" style={{ minWidth: 90 }}>
                          <span className="text-red-500 font-medium">{fmtPct(iv)}</span>
                        </td>
                        <td className="py-2 px-3 text-sm text-center" style={{ minWidth: 90 }}>
                          <span className={`font-medium ${diff > 0.02 ? 'text-emerald-600' : diff < -0.02 ? 'text-red-500' : 'text-slate-400'}`}>
                            {diff > 0 ? '+' : ''}{(diff * 100).toFixed(1)}pp
                          </span>
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
