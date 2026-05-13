import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ModalityProgressionResponse } from '../../api/types';

interface ModalityChartProps {
  data: ModalityProgressionResponse;
}

export function ModalityChart({ data }: ModalityChartProps) {
  if (data.experiments.length === 0) return null;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-2">
        Modality Progression
      </h3>
      <p className="text-sm text-slate-500 mb-6">
        Distribution of data sources (Traces / Logs / Metrics) over normalized trajectory progress.
        Shows how the agent shifts attention between telemetry layers as investigation progresses.
      </p>
      {data.experiments.map((exp) => (
        <div key={exp.exp_id} className="mb-8 last:mb-0">
          <div className="text-sm font-medium text-slate-600 mb-3">{exp.exp_id}</div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart
              data={exp.bins.map((b) => ({
                progress: Math.round(b.progress * 100),
                Traces: Math.round(b.traces * 100),
                Logs: Math.round(b.logs * 100),
                Metrics: Math.round(b.metrics * 100),
              }))}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="progress"
                tickFormatter={(v: number) => `${v}%`}
                label={{ value: 'Trajectory Progress', position: 'insideBottom', offset: -5, fontSize: 12 }}
                stroke="#94a3b8"
                fontSize={11}
              />
              <YAxis
                tickFormatter={(v: number) => `${v}%`}
                label={{ value: 'Proportion', angle: -90, position: 'insideLeft', offset: 10, fontSize: 12 }}
                stroke="#94a3b8"
                fontSize={11}
                domain={[0, 100]}
              />
              <Tooltip
                formatter={(value: number, name: string) => [`${value}%`, name]}
                labelFormatter={(label: number) => `Progress: ${label}%`}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="Traces"
                stackId="1"
                fill="#3b82f6"
                stroke="#2563eb"
                fillOpacity={0.8}
              />
              <Area
                type="monotone"
                dataKey="Logs"
                stackId="1"
                fill="#22c55e"
                stroke="#16a34a"
                fillOpacity={0.8}
              />
              <Area
                type="monotone"
                dataKey="Metrics"
                stackId="1"
                fill="#f97316"
                stroke="#ea580c"
                fillOpacity={0.8}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}
