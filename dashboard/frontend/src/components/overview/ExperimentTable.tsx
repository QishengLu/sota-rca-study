import { useNavigate } from 'react-router-dom';
import type { ExperimentMetrics } from '../../api/types';
import { getAccuracyColorClass, getMetricColorClass } from './StatCard';
import { clsx } from 'clsx';

interface ExperimentTableProps {
  data: ExperimentMetrics[];
}

function MetricCell({ f1, precision, recall }: { f1: number; precision: number; recall: number }) {
  return (
    <div className="text-right">
      <div className={clsx('font-semibold', getMetricColorClass(f1))}>
        {f1.toFixed(3)}
      </div>
      <div className="text-xs text-slate-500">
        P:{precision.toFixed(2)} R:{recall.toFixed(2)}
      </div>
    </div>
  );
}

export function ExperimentTable({ data }: ExperimentTableProps) {
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200">
        <h3 className="text-lg font-semibold text-slate-800">Experiment Results</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50">
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Experiment ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Model
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Agent
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Samples
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Accuracy
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>RC F1</div>
                <div className="text-[10px] font-normal normal-case">P / R</div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>Node F1</div>
                <div className="text-[10px] font-normal normal-case">P / R</div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>Edge F1</div>
                <div className="text-[10px] font-normal normal-case">P / R</div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Path Reach
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Avg Time
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>Avg Tokens</div>
                <div className="text-[10px] font-normal normal-case">per sample</div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Avg Rounds
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>Avg Cost</div>
                <div className="text-[10px] font-normal normal-case">USD/sample</div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <div>Total Cost</div>
                <div className="text-[10px] font-normal normal-case">USD</div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data.map((exp) => (
              <tr
                key={exp.exp_id}
                className="hover:bg-slate-50 cursor-pointer transition-colors"
                onClick={() => navigate(`/cases?exp_id=${encodeURIComponent(exp.exp_id)}`)}
              >
                <td className="px-6 py-4 text-sm font-medium text-slate-800 max-w-xs truncate">
                  {exp.exp_id}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600">
                  {exp.model_name || '-'}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600">
                  {exp.agent_type || '-'}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600 text-right">
                  {exp.total_samples}
                </td>
                <td className={clsx('px-6 py-4 text-sm font-semibold text-right', getAccuracyColorClass(exp.accuracy))}>
                  {exp.accuracy.toFixed(1)}%
                </td>
                <td className="px-6 py-4 text-sm">
                  <MetricCell
                    f1={exp.metrics.root_cause_f1}
                    precision={exp.metrics.root_cause_precision}
                    recall={exp.metrics.root_cause_recall}
                  />
                </td>
                <td className="px-6 py-4 text-sm">
                  <MetricCell
                    f1={exp.metrics.node_f1}
                    precision={exp.metrics.node_precision}
                    recall={exp.metrics.node_recall}
                  />
                </td>
                <td className="px-6 py-4 text-sm">
                  <MetricCell
                    f1={exp.metrics.edge_f1}
                    precision={exp.metrics.edge_precision}
                    recall={exp.metrics.edge_recall}
                  />
                </td>
                <td className="px-6 py-4 text-sm text-right">
                  {exp.metrics.path_reachability !== null && exp.metrics.path_reachability !== undefined ? (
                    <span className={clsx(
                      'font-semibold',
                      exp.metrics.path_reachability >= 0.8 ? 'text-emerald-600' :
                      exp.metrics.path_reachability >= 0.5 ? 'text-amber-600' : 'text-red-600'
                    )}>
                      {(exp.metrics.path_reachability * 100).toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-slate-400">-</span>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600 text-right">
                  {exp.avg_time_cost.toFixed(1)}s
                </td>
                <td className="px-6 py-4 text-sm text-slate-600 text-right">
                  {exp.avg_tokens > 0 ? (exp.avg_tokens >= 1000000 ? `${(exp.avg_tokens / 1000000).toFixed(2)}M` : `${(exp.avg_tokens / 1000).toFixed(1)}K`) : '-'}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600 text-right">
                  {exp.avg_rounds > 0 ? exp.avg_rounds.toFixed(1) : '-'}
                </td>
                <td className="px-6 py-4 text-sm text-right font-medium">
                  {exp.avg_cost_usd > 0 ? (
                    <span className={exp.avg_cost_usd > 5 ? 'text-red-600' : exp.avg_cost_usd > 1 ? 'text-amber-600' : 'text-emerald-600'}>
                      ${exp.avg_cost_usd.toFixed(4)}
                    </span>
                  ) : <span className="text-slate-400">-</span>}
                </td>
                <td className="px-6 py-4 text-sm text-right font-medium">
                  {exp.total_cost_usd > 0 ? (
                    <span className={exp.total_cost_usd > 100 ? 'text-red-600' : exp.total_cost_usd > 10 ? 'text-amber-600' : 'text-emerald-600'}>
                      ${exp.total_cost_usd.toFixed(2)}
                    </span>
                  ) : <span className="text-slate-400">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
