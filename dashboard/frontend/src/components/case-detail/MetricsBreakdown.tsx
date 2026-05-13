import type { SampleMeta } from '../../api/types';
import { clsx } from 'clsx';

interface MetricsBreakdownProps {
  meta: SampleMeta;
}

export function MetricsBreakdown({ meta }: MetricsBreakdownProps) {
  const primary = meta.graph_metrics?.primary;
  const toolUsage = meta.tool_usage;

  return (
    <div className="space-y-6">
      {/* Primary Metrics */}
      {primary && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
            <h3 className="font-semibold text-slate-800">Primary Metrics</h3>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <MetricGroup
                title="Root Cause"
                precision={primary.root_cause_precision}
                recall={primary.root_cause_recall}
                f1={primary.root_cause_f1}
              />
              <MetricGroup
                title="Node"
                precision={primary.node_precision}
                recall={primary.node_recall}
                f1={primary.node_f1}
              />
              <MetricGroup
                title="Edge"
                precision={primary.edge_precision}
                recall={primary.edge_recall}
                f1={primary.edge_f1}
              />
            </div>
            {primary.path_reachability !== undefined && (
              <div className="mt-4 pt-4 border-t border-slate-200">
                <PathReachabilityBadge value={primary.path_reachability} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tool Usage */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
          <h3 className="font-semibold text-slate-800">Tool Usage</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center p-3 bg-slate-50 rounded-lg">
              <div className="text-2xl font-bold text-slate-800">{toolUsage.total_calls}</div>
              <div className="text-sm text-slate-500">Total Calls</div>
            </div>
            <div className="text-center p-3 bg-emerald-50 rounded-lg">
              <div className="text-2xl font-bold text-emerald-600">{toolUsage.success_count}</div>
              <div className="text-sm text-slate-500">Successful</div>
            </div>
            <div className="text-center p-3 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">{toolUsage.failure_count}</div>
              <div className="text-sm text-slate-500">Failed</div>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{toolUsage.tools_used.length}</div>
              <div className="text-sm text-slate-500">Tools Used</div>
            </div>
          </div>

          {toolUsage.tools_used.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-600 mb-2">Tools Used</h4>
              <div className="flex flex-wrap gap-2">
                {toolUsage.tools_used.map((tool, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-1 bg-slate-100 text-slate-600 text-sm rounded font-mono"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Ground Truth Info */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
          <h3 className="font-semibold text-slate-800">Ground Truth Info</h3>
        </div>
        <div className="p-4">
          <div className="space-y-3">
            {meta.datapack_name && (
              <div>
                <span className="text-sm font-medium text-slate-600">Datapack: </span>
                <span className="text-sm text-slate-800 font-mono">{meta.datapack_name}</span>
              </div>
            )}
            <div>
              <span className="text-sm font-medium text-slate-600">Expected Root Causes: </span>
              <span className="text-sm text-slate-800">
                {meta.ground_truth.length > 0 ? meta.ground_truth.join(', ') : 'None specified'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface PathReachabilityBadgeProps {
  value: number | null | undefined;
}

function PathReachabilityBadge({ value }: PathReachabilityBadgeProps) {
  const isApplicable = value !== null && value !== undefined;
  // For aggregated view: value is a rate 0-1; for single sample: 0 or 1
  const isSingleSample = isApplicable && (value === 0 || value === 1);

  let label: string;
  let colorClass: string;

  if (!isApplicable) {
    label = 'N/A';
    colorClass = 'bg-slate-100 text-slate-500';
  } else if (isSingleSample) {
    label = value === 1 ? 'Reachable' : 'Not Reachable';
    colorClass = value === 1 ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700';
  } else {
    // Aggregated rate
    label = `${(value * 100).toFixed(1)}%`;
    colorClass = value >= 0.8
      ? 'bg-emerald-100 text-emerald-700'
      : value >= 0.5
        ? 'bg-amber-100 text-amber-700'
        : 'bg-red-100 text-red-700';
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-slate-600">Path Reachability</span>
      <span className={clsx('px-2.5 py-1 rounded-full text-sm font-semibold', colorClass)}>
        {label}
      </span>
      {!isApplicable && (
        <span className="text-xs text-slate-400">(root cause not correctly identified)</span>
      )}
    </div>
  );
}

interface MetricGroupProps {
  title: string;
  precision: number;
  recall: number;
  f1: number;
}

function MetricGroup({ title, precision, recall, f1 }: MetricGroupProps) {
  const getColorClass = (value: number) => {
    if (value >= 0.8) return 'text-emerald-600';
    if (value >= 0.5) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-2">
      <h4 className="font-medium text-slate-700">{title}</h4>
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-sm text-slate-500">Precision</span>
          <span className={clsx('text-sm font-semibold', getColorClass(precision))}>
            {(precision * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-slate-500">Recall</span>
          <span className={clsx('text-sm font-semibold', getColorClass(recall))}>
            {(recall * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex justify-between border-t border-slate-200 pt-1">
          <span className="text-sm font-medium text-slate-600">F1</span>
          <span className={clsx('text-sm font-bold', getColorClass(f1))}>
            {(f1 * 100).toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
