import { clsx } from 'clsx';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  colorClass?: string;
}

export function StatCard({ label, value, unit, colorClass }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <div className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-2">
        {label}
      </div>
      <div className={clsx('text-3xl font-bold', colorClass || 'text-slate-800')}>
        {value}
        {unit && <span className="text-lg font-normal text-slate-400 ml-1">{unit}</span>}
      </div>
    </div>
  );
}

export function getMetricColorClass(value: number): string {
  if (value >= 0.8) return 'text-emerald-600';
  if (value >= 0.5) return 'text-amber-600';
  return 'text-red-600';
}

export function getAccuracyColorClass(value: number): string {
  if (value >= 80) return 'text-emerald-600';
  if (value >= 50) return 'text-amber-600';
  return 'text-red-600';
}
