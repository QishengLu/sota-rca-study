import { useMemo } from 'react';
import type { IntentHeatmapResponse } from '../../api/types';

interface Props {
  data: IntentHeatmapResponse;
}

function getColor(value: number): string {
  if (value >= 0.9) return 'bg-blue-700 text-white';
  if (value >= 0.7) return 'bg-blue-500 text-white';
  if (value >= 0.5) return 'bg-blue-400 text-white';
  if (value >= 0.3) return 'bg-blue-300 text-slate-800';
  if (value >= 0.1) return 'bg-blue-100 text-slate-700';
  if (value > 0) return 'bg-blue-50 text-slate-600';
  return 'bg-slate-50 text-slate-300';
}

function shortExpId(expId: string): string {
  // thinkdepthai-claude-sonnet-4.6 → claude-4.6
  return expId
    .replace('thinkdepthai-', '')
    .replace('claude-sonnet-', 'claude-')
    .replace('-claude-sonnet-4.5', '-claude-4.5');
}

export function IntentHeatmap({ data }: Props) {
  const cellMap = useMemo(() => {
    const map: Record<string, typeof data.cells[0]> = {};
    for (const c of data.cells) {
      map[`${c.intent}|${c.exp_id}`] = c;
    }
    return map;
  }, [data.cells]);

  if (!data.intents.length || !data.experiments.length) {
    return <div className="text-slate-400 text-center py-8">No data</div>;
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 overflow-x-auto">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">Intent Usage Heatmap</h3>
      <p className="text-xs text-slate-500 mb-3">
        Cell value = % of samples using this intent. Hover for correct/incorrect split.
      </p>
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="text-left px-2 py-1 font-semibold text-slate-600 sticky left-0 bg-white min-w-[160px]">
              Intent
            </th>
            {data.experiments.map((eid) => (
              <th key={eid} className="px-2 py-1 font-semibold text-slate-600 text-center min-w-[80px]">
                {shortExpId(eid)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.intents.map((intent) => (
            <tr key={intent} className="border-t border-slate-100">
              <td className="px-2 py-1.5 font-medium text-slate-700 sticky left-0 bg-white">
                {intent}
              </td>
              {data.experiments.map((eid) => {
                const cell = cellMap[`${intent}|${eid}`];
                const rate = cell?.usage_rate ?? 0;
                return (
                  <td key={eid} className="px-1 py-1">
                    <div
                      className={`rounded px-2 py-1 text-center font-mono ${getColor(rate)}`}
                      title={cell
                        ? `${intent} @ ${shortExpId(eid)}\nUsage: ${(rate * 100).toFixed(1)}%\nCorrect: ${(cell.correct_rate * 100).toFixed(1)}%\nIncorrect: ${(cell.incorrect_rate * 100).toFixed(1)}%`
                        : ''}
                    >
                      {rate > 0 ? `${(rate * 100).toFixed(0)}%` : '-'}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
