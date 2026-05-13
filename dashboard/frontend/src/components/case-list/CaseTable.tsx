import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import type { SampleListItem } from '../../api/types';
import { Badge } from '../common/Badge';

interface CaseTableProps {
  data: SampleListItem[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (field: string) => void;
}

function getMetricColor(value: number | null) {
  if (value === null) return 'text-slate-400';
  if (value >= 0.8) return 'text-emerald-600';
  if (value >= 0.5) return 'text-amber-600';
  return 'text-red-600';
}

function MetricCell({ f1, precision, recall }: { f1: number | null; precision: number | null; recall: number | null }) {
  if (f1 === null) return <span className="text-slate-400">-</span>;
  return (
    <div>
      <div className={clsx('font-semibold', getMetricColor(f1))}>
        {f1.toFixed(3)}
      </div>
      <div className="text-xs text-slate-500">
        P:{precision?.toFixed(2) ?? '-'} R:{recall?.toFixed(2) ?? '-'}
      </div>
    </div>
  );
}

export function CaseTable({ data, sortBy, sortOrder, onSort }: CaseTableProps) {
  const navigate = useNavigate();

  const SortHeader = ({ field, children, subtext }: { field: string; children: React.ReactNode; subtext?: string }) => (
    <th
      className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider cursor-pointer hover:bg-slate-100 select-none"
      onClick={() => onSort(field)}
    >
      <div className="flex items-center gap-1">
        <div>
          <div className="flex items-center gap-1">
            {children}
            {sortBy === field && (
              <span className="text-primary-600">{sortOrder === 'asc' ? '↑' : '↓'}</span>
            )}
          </div>
          {subtext && <div className="text-[10px] font-normal normal-case">{subtext}</div>}
        </div>
      </div>
    </th>
  );

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <SortHeader field="dataset_index">Index</SortHeader>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Case Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Experiment
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Model
              </th>
              <SortHeader field="correct">Status</SortHeader>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Fault Type
              </th>
              <SortHeader field="spl">SPL</SortHeader>
              <SortHeader field="n_svc">N_svc</SortHeader>
              <SortHeader field="n_edge">N_edge</SortHeader>
              <SortHeader field="root_cause_f1" subtext="P / R">RC F1</SortHeader>
              <SortHeader field="node_f1" subtext="P / R">Node F1</SortHeader>
              <SortHeader field="edge_f1" subtext="P / R">Edge F1</SortHeader>
              <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Path Reach
              </th>
              <SortHeader field="time_cost">Time</SortHeader>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data.map((sample) => (
              <tr
                key={sample.id}
                className="hover:bg-slate-50 cursor-pointer transition-colors"
                onClick={() => navigate(`/cases/${sample.id}`)}
              >
                <td className="px-4 py-3 text-sm text-slate-800 font-medium">
                  #{sample.dataset_index}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600 font-mono text-xs" title={sample.datapack_name || ''}>
                  {sample.datapack_name || '-'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600 max-w-[200px] truncate">
                  {sample.exp_id}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.model_name || '-'}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={sample.correct ? 'success' : 'error'}>
                    {sample.correct ? 'Correct' : 'Incorrect'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.fault_type || '-'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.spl ?? '-'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.n_svc ?? '-'}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.n_edge ?? '-'}
                </td>
                <td className="px-4 py-3 text-sm">
                  <MetricCell
                    f1={sample.metrics.root_cause_f1}
                    precision={sample.metrics.root_cause_precision}
                    recall={sample.metrics.root_cause_recall}
                  />
                </td>
                <td className="px-4 py-3 text-sm">
                  <MetricCell
                    f1={sample.metrics.node_f1}
                    precision={sample.metrics.node_precision}
                    recall={sample.metrics.node_recall}
                  />
                </td>
                <td className="px-4 py-3 text-sm">
                  <MetricCell
                    f1={sample.metrics.edge_f1}
                    precision={sample.metrics.edge_precision}
                    recall={sample.metrics.edge_recall}
                  />
                </td>
                <td className="px-4 py-3 text-center">
                  {sample.metrics.path_reachability === null || sample.metrics.path_reachability === undefined ? (
                    <span className="text-xs text-slate-400">N/A</span>
                  ) : sample.metrics.path_reachability ? (
                    <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500" title="Reachable" />
                  ) : (
                    <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500" title="Not reachable" />
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  {sample.time_cost?.toFixed(1)}s
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
