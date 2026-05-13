import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ExperimentMetrics } from '../../api/types';

interface MetricsChartProps {
  data: ExperimentMetrics[];
}

export function MetricsChart({ data }: MetricsChartProps) {
  const chartData = data.map((exp) => ({
    name: exp.exp_id.length > 20 ? exp.exp_id.slice(0, 20) + '...' : exp.exp_id,
    fullName: exp.exp_id,
    Accuracy: exp.accuracy,
    'RC F1': exp.metrics.root_cause_f1 * 100,
    'Node F1': exp.metrics.node_f1 * 100,
    'Edge F1': exp.metrics.edge_f1 * 100,
  }));

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">Metrics Comparison</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: '#64748b' }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#64748b' }}
              domain={[0, 100]}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              formatter={(value: number) => `${value.toFixed(1)}%`}
              labelFormatter={(_, payload) => payload[0]?.payload?.fullName || ''}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
              }}
            />
            <Legend />
            <Bar dataKey="Accuracy" fill="#2563eb" radius={[4, 4, 0, 0]} />
            <Bar dataKey="RC F1" fill="#10b981" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Node F1" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Edge F1" fill="#ef4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
