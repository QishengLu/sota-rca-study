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
import type { DistributionItem } from '../../api/types';

interface DistributionChartProps {
  title: string;
  data: DistributionItem[];
}

export function DistributionChart({ title, data }: DistributionChartProps) {
  const chartData = data.slice(0, 15).map((item) => ({
    name: item.name.length > 15 ? item.name.slice(0, 15) + '...' : item.name,
    fullName: item.name,
    Success: item.success,
    Fail: item.fail,
  }));

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{title}</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 12, fill: '#64748b' }}
              width={90}
            />
            <Tooltip
              labelFormatter={(_, payload) => payload[0]?.payload?.fullName || ''}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
              }}
            />
            <Legend />
            <Bar dataKey="Success" stackId="a" fill="#10b981" />
            <Bar dataKey="Fail" stackId="a" fill="#ef4444" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
