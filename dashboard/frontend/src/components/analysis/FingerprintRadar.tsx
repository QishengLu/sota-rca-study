import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import type { FingerprintResponse } from '../../api/types';

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

interface Props {
  data: FingerprintResponse;
}

export function FingerprintRadar({ data }: Props) {
  if (!data.experiments.length) {
    return <div className="text-slate-400 text-center py-8">No data</div>;
  }

  // Build chart data: each row is a dimension, with values per experiment
  const chartData = data.dimension_keys.map((key) => {
    const row: Record<string, string | number> = {
      dimension: data.dimension_labels[key] || key,
    };
    for (const exp of data.experiments) {
      const dim = exp.dimensions.find((d) => d.key === key);
      row[exp.exp_id] = dim ? Math.round(dim.value * 100) / 100 : 0;
    }
    return row;
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">Behavioral Fingerprint</h3>
      <ResponsiveContainer width="100%" height={450}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
          <PolarGrid strokeDasharray="3 3" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 11, fill: '#475569' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 1]}
            tick={{ fontSize: 10 }}
            tickCount={5}
          />
          {data.experiments.map((exp, i) => (
            <Radar
              key={exp.exp_id}
              name={`${exp.exp_id} (${exp.accuracy.toFixed(1)}%)`}
              dataKey={exp.exp_id}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.1}
              strokeWidth={2}
            />
          ))}
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number, name: string) => [`${(value * 100).toFixed(1)}%`, name]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
