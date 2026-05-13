import { useState } from 'react';
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
import type { MarkovResponse, MarkovExpData, MarkovTransitionCell, MarkovStateMetrics } from '../../api/types';

interface MarkovChartProps {
  data: MarkovResponse;
}

export function MarkovChart({ data }: MarkovChartProps) {
  if (data.experiments.length === 0) return null;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">
        Markov Chain Analysis
      </h3>
      <p className="text-sm text-slate-500 mb-6">
        Transition probabilities, stationary distributions, and behavioral divergence between correct and incorrect diagnostic trajectories.
      </p>
      {data.experiments.map((exp) => (
        <ExpMarkovView key={exp.exp_id} exp={exp} />
      ))}
    </div>
  );
}

type ViewTab = 'heatmap' | 'stationary' | 'kl';
type LayerMode = 'phase' | 'intent';

const PHASE_LABELS: Record<string, string> = {
  triage: 'Triage',
  trace_investigate: 'Trace Investigate',
  log_investigate: 'Log Investigate',
  metric_diagnose: 'Metric Diagnose',
  baseline: 'Baseline',
};

/** Unified view data that both layers share */
interface LayerViewData {
  states: string[];
  transitions: MarkovTransitionCell[];
  state_metrics: MarkovStateMetrics[];
  correct_entropy: number;
  incorrect_entropy: number;
  total_kl: number;
}

function toLayerViewData(exp: MarkovExpData): LayerViewData {
  return {
    states: exp.states,
    transitions: exp.transitions,
    state_metrics: exp.state_metrics,
    correct_entropy: exp.correct_entropy,
    incorrect_entropy: exp.incorrect_entropy,
    total_kl: exp.total_kl,
  };
}

function ExpMarkovView({ exp }: { exp: MarkovExpData }) {
  const [activeTab, setActiveTab] = useState<ViewTab>('heatmap');
  const [layerMode, setLayerMode] = useState<LayerMode>('phase');

  const viewData: LayerViewData = layerMode === 'phase' && exp.phase_layer
    ? exp.phase_layer
    : toLayerViewData(exp);

  const stateLabel = (s: string) => layerMode === 'phase' ? (PHASE_LABELS[s] || s) : s;
  const stateCount = viewData.states.length;

  const tabs: { key: ViewTab; label: string }[] = [
    { key: 'heatmap', label: 'Transition Matrix' },
    { key: 'stationary', label: 'Stationary Distribution' },
    { key: 'kl', label: 'KL Divergence' },
  ];

  return (
    <div className="mb-8 last:mb-0">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-medium text-slate-600">
          {exp.exp_id}
          <span className="text-slate-400 ml-2">
            (correct: {exp.correct_count}, incorrect: {exp.incorrect_count},
            {stateCount} states)
          </span>
        </h4>
        {/* Layer toggle */}
        <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
          <button
            onClick={() => setLayerMode('phase')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              layerMode === 'phase' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            5 Phases
          </button>
          <button
            onClick={() => setLayerMode('intent')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              layerMode === 'intent' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            19 Intents
          </button>
        </div>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-slate-50 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500">Correct Entropy</div>
          <div className="text-lg font-semibold text-emerald-600">
            {viewData.correct_entropy.toFixed(3)}
          </div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500">Incorrect Entropy</div>
          <div className="text-lg font-semibold text-red-500">
            {viewData.incorrect_entropy.toFixed(3)}
          </div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500">Total KL Divergence</div>
          <div className="text-lg font-semibold text-blue-600">
            {viewData.total_kl.toFixed(3)}
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-4 border-b border-slate-200">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-blue-600 border border-b-white border-slate-200 -mb-px'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'heatmap' && <TransitionHeatmap data={viewData} labelFn={stateLabel} />}
      {activeTab === 'stationary' && <StationaryChart data={viewData} labelFn={stateLabel} />}
      {activeTab === 'kl' && <KLDivergenceChart data={viewData} labelFn={stateLabel} />}
    </div>
  );
}

// ── Transition Matrix Heatmap ──────────────────────────────────

function TransitionHeatmap({ data, labelFn }: { data: LayerViewData; labelFn?: (s: string) => string }) {
  const [showGroup, setShowGroup] = useState<'correct' | 'incorrect' | 'diff'>('diff');
  const { states, transitions } = data;
  const n = states.length;

  // Build matrix lookup
  const matrix: Record<string, Record<string, { correct: number; incorrect: number }>> = {};
  for (const t of transitions) {
    if (!matrix[t.from_state]) matrix[t.from_state] = {};
    matrix[t.from_state][t.to_state] = {
      correct: t.correct_prob,
      incorrect: t.incorrect_prob,
    };
  }

  const shortLabel = (s: string) => {
    if (labelFn) return labelFn(s);
    return s.length > 12 ? s.slice(0, 11) + '…' : s;
  };

  const cellSize = Math.max(32, Math.min(48, 600 / n));
  const labelWidth = n <= 12 ? 100 : 80;

  const getValue = (from: string, to: string): number => {
    const cell = matrix[from]?.[to];
    if (!cell) return 0;
    if (showGroup === 'correct') return cell.correct;
    if (showGroup === 'incorrect') return cell.incorrect;
    return cell.correct - cell.incorrect;
  };

  const getColor = (value: number): string => {
    if (showGroup === 'diff') {
      if (value > 0) return `rgba(16, 185, 129, ${Math.min(Math.abs(value) * 3, 1)})`;
      if (value < 0) return `rgba(239, 68, 68, ${Math.min(Math.abs(value) * 3, 1)})`;
      return '#f8fafc';
    }
    return `rgba(59, 130, 246, ${Math.min(value * 2.5, 1)})`;
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        {(['correct', 'incorrect', 'diff'] as const).map((g) => (
          <button
            key={g}
            onClick={() => setShowGroup(g)}
            className={`px-3 py-1 text-xs rounded-full ${
              showGroup === g
                ? 'bg-blue-100 text-blue-700 font-medium'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }`}
          >
            {g === 'diff' ? 'Correct - Incorrect' : g.charAt(0).toUpperCase() + g.slice(1)}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Header row */}
          <div className="flex">
            <div style={{ width: labelWidth, minWidth: labelWidth }} />
            {states.map((s) => (
              <div
                key={s}
                style={{ width: cellSize, minWidth: cellSize }}
                className="text-center"
              >
                <span
                  className="text-[10px] text-slate-500 inline-block"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 60 }}
                >
                  {shortLabel(s)}
                </span>
              </div>
            ))}
          </div>

          {/* Matrix rows */}
          {states.map((from) => (
            <div key={from} className="flex items-center">
              <div
                style={{ width: labelWidth, minWidth: labelWidth }}
                className="text-[10px] text-slate-600 text-right pr-2 truncate"
                title={from}
              >
                {shortLabel(from)}
              </div>
              {states.map((to) => {
                const val = getValue(from, to);
                return (
                  <div
                    key={to}
                    style={{
                      width: cellSize,
                      height: cellSize,
                      minWidth: cellSize,
                      backgroundColor: getColor(val),
                    }}
                    className="border border-white/50 flex items-center justify-center cursor-default"
                    title={`${from} → ${to}\nCorrect: ${(matrix[from]?.[to]?.correct ?? 0).toFixed(3)}\nIncorrect: ${(matrix[from]?.[to]?.incorrect ?? 0).toFixed(3)}\nDiff: ${val.toFixed(3)}`}
                  >
                    <span className="text-[8px] text-slate-700">
                      {Math.abs(val) >= 0.005 ? val.toFixed(2) : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
        {showGroup === 'diff' ? (
          <>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(16,185,129,0.6)' }} />
              Correct &gt; Incorrect
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(239,68,68,0.6)' }} />
              Incorrect &gt; Correct
            </span>
          </>
        ) : (
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(59,130,246,0.6)' }} />
            Higher probability = darker
          </span>
        )}
      </div>
    </div>
  );
}

// ── Stationary Distribution ──────────────────────────────────

function StationaryChart({ data, labelFn }: { data: LayerViewData; labelFn?: (s: string) => string }) {
  const fmt = labelFn || ((s: string) => s);
  const chartData = data.state_metrics.map((m) => ({
    state: fmt(m.state),
    Correct: +(m.correct_stationary * 100).toFixed(2),
    Incorrect: +(m.incorrect_stationary * 100).toFixed(2),
  }));

  return (
    <div style={{ height: Math.max(300, chartData.length * 32) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            tick={{ fontSize: 12, fill: '#64748b' }}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="state"
            tick={{ fontSize: 11, fill: '#64748b' }}
            width={130}
          />
          <Tooltip
            formatter={(value: number) => `${value}%`}
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
  );
}

// ── KL Divergence per State ──────────────────────────────────

function KLDivergenceChart({ data, labelFn }: { data: LayerViewData; labelFn?: (s: string) => string }) {
  const fmt = labelFn || ((s: string) => s);
  const chartData = data.state_metrics
    .map((m) => ({
      state: fmt(m.state),
      KL: +m.kl_divergence.toFixed(4),
    }))
    .sort((a, b) => b.KL - a.KL);

  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">
        Per-state KL divergence D_KL(P_correct || P_incorrect). Higher values indicate states where correct and incorrect trajectories diverge most — key decision fork points.
      </p>
      <div style={{ height: Math.max(300, chartData.length * 32) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              type="number"
              tick={{ fontSize: 12, fill: '#64748b' }}
              label={{ value: 'KL Divergence (bits)', position: 'insideBottom', offset: -2, fontSize: 11, fill: '#94a3b8' }}
            />
            <YAxis
              type="category"
              dataKey="state"
              tick={{ fontSize: 11, fill: '#64748b' }}
              width={130}
            />
            <Tooltip
              formatter={(value: number) => value.toFixed(4)}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
              }}
            />
            <Bar dataKey="KL" fill="#6366f1" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
