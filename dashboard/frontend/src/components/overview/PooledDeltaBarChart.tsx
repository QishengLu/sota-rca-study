import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts';
import type { PooledDeltaChart } from '../../api/types';

interface PooledDeltaBarChartProps {
  chart: PooledDeltaChart;
  title?: string;
  /** Insert a visual separator before labels starting with this prefix */
  separatorPrefix?: string;
}

const BENEFICIAL_COLOR = '#22c55e';
const HARMFUL_COLOR = '#ef4444';
const SEPARATOR_LABEL = '──────';

export function PooledDeltaBarChart({ chart, title, separatorPrefix }: PooledDeltaBarChartProps) {
  // Build chart data, insert separator if requested
  const chartData: { label: string; delta: number; isSeparator?: boolean }[] = [];
  const sepIdx = separatorPrefix
    ? chart.items.findIndex((i) => i.label.startsWith(separatorPrefix))
    : -1;

  chart.items.forEach((item, i) => {
    if (i === sepIdx) {
      chartData.push({ label: SEPARATOR_LABEL, delta: 0, isSeparator: true });
    }
    chartData.push({
      label: item.label,
      delta: +(item.pooled_delta * 100).toFixed(2),
    });
  });

  const maxAbs = Math.max(...chartData.map((d) => Math.abs(d.delta)), 1);
  const domainMax = Math.ceil(maxAbs / 5) * 5;

  return (
    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4 mb-6">
      <h4 className="text-sm font-semibold text-slate-700 mb-1">
        {title || 'Universal Patterns (Method 2 Weighted Δ)'}
      </h4>
      <p className="text-xs text-slate-500 mb-3">
        {chart.total_models} models, {chart.total_cases} cases pooled.
        <span className="ml-2 text-green-600">▮ Positive Δ = enriched in correct</span>
        <span className="ml-2 text-red-500">▮ Negative Δ = enriched in incorrect</span>
      </p>
      <ResponsiveContainer width="100%" height={Math.max(chartData.length * 28 + 40, 200)}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 180, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            domain={[-domainMax, domainMax]}
            tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}pp`}
            fontSize={10}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={170}
            tick={{ fontSize: 10 }}
          />
          <Tooltip
            formatter={(value: number) => [`${value > 0 ? '+' : ''}${value.toFixed(2)}pp`, 'Weighted Δ']}
            labelStyle={{ fontWeight: 'bold', fontSize: 12 }}
          />
          <ReferenceLine x={0} stroke="#64748b" strokeWidth={1} />
          <Bar dataKey="delta" maxBarSize={18}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.isSeparator ? 'transparent' : entry.delta >= 0 ? BENEFICIAL_COLOR : HARMFUL_COLOR}
                opacity={entry.isSeparator ? 0 : 0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
