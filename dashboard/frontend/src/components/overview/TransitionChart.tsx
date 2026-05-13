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
import type { TransitionResponse, TransitionExpData } from '../../api/types';
import { PooledDeltaBarChart } from './PooledDeltaBarChart';

interface TransitionChartProps {
  data: TransitionResponse;
}

const SEPARATOR_LABEL = '──── R→T ────';

export function TransitionChart({ data }: TransitionChartProps) {
  if (data.experiments.length === 0) return null;

  const hasMultiple = data.experiments.length > 1;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">
        Step Transition Taxonomy
      </h3>

      {hasMultiple && data.pooled_delta && (
        <PooledDeltaBarChart
          chart={data.pooled_delta}
          title="Universal Patterns — 10+4 Labels (Method 2 Weighted Δ)"
          separatorPrefix="rt:"
        />
      )}

      {hasMultiple ? (
        <div className="grid grid-cols-1 gap-6 border-t border-slate-200 pt-6">
          <h4 className="text-sm font-medium text-slate-500 uppercase tracking-wide">
            Per Experiment
          </h4>
          {data.experiments.map((exp) => (
            <DistributionBarChart key={exp.exp_id} exp={exp} />
          ))}
        </div>
      ) : (
        <DistributionBarChart
          exp={data.aggregated ?? data.experiments[0]}
        />
      )}
    </div>
  );
}

function DistributionBarChart({ exp, title }: { exp: TransitionExpData; title?: string }) {
  const rtStartIndex = exp.label_distribution.findIndex((item) => item.label.startsWith('rt:'));

  // Build chart data with a blank separator row before R→T labels
  const chartData: { label: string; Correct: number; Incorrect: number; isSeparator?: boolean }[] = [];
  exp.label_distribution.forEach((item, i) => {
    if (i === rtStartIndex) {
      chartData.push({
        label: SEPARATOR_LABEL,
        Correct: 0,
        Incorrect: 0,
        isSeparator: true,
      });
    }
    chartData.push({
      label: item.label,
      Correct: +(item.correct_pct * 100).toFixed(1),
      Incorrect: +(item.incorrect_pct * 100).toFixed(1),
    });
  });

  const displayTitle = title ?? exp.exp_id;

  return (
    <div>
      <h4 className="text-sm font-medium text-slate-600 mb-2">
        {displayTitle}
        <span className="text-slate-400 ml-2">
          (correct: {exp.correct_count}, incorrect: {exp.incorrect_count})
        </span>
      </h4>
      <div style={{ height: Math.max(460, chartData.length * 28) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 180, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              type="number"
              tick={{ fontSize: 12, fill: '#64748b' }}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={({ x, y, payload }: { x: number; y: number; payload: { value: string } }) => {
                const isSep = payload.value === SEPARATOR_LABEL;
                return (
                  <text
                    x={x}
                    y={y}
                    textAnchor="end"
                    dominantBaseline="middle"
                    fontSize={isSep ? 10 : 11}
                    fill={isSep ? '#94a3b8' : '#64748b'}
                    fontWeight={isSep ? 600 : 400}
                  >
                    {payload.value}
                  </text>
                );
              }}
              width={170}
            />
            <Tooltip
              formatter={(value: number, _name: string, props: { payload?: { isSeparator?: boolean } }) => {
                if (props.payload?.isSeparator) return null;
                return `${value}%`;
              }}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
              }}
            />
            <Legend />
            <Bar dataKey="Correct" fill="#10b981" />
            <Bar dataKey="Incorrect" fill="#ef4444" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
