import { useState, useMemo } from 'react';
import type { NgramChartData, NgramBarItem, NgramResponse } from '../../api/types';
import { PooledDeltaBarChart } from './PooledDeltaBarChart';

interface NgramChartProps {
  data: NgramResponse;
}

type ViewMode = 'heatmap' | 'compare';

function shortLabel(s: string, maxLen = 28): string {
  return s.length > maxLen ? s.slice(0, maxLen - 1) + '\u2026' : s;
}

export function NgramChart({ data }: NgramChartProps) {
  const { charts, pooled_deltas } = data;
  const nValues = [...new Set(charts.map((c) => c.n))].sort();
  const [selectedN, setSelectedN] = useState(nValues.length > 1 ? nValues[1] : nValues[0] ?? 2);
  const [viewMode, setViewMode] = useState<ViewMode>('heatmap');
  const [topK, setTopK] = useState(8);

  const filtered = useMemo(() => charts.filter((c) => c.n === selectedN), [charts, selectedN]);
  const expIds = useMemo(() => [...new Set(filtered.map((c) => c.exp_id))], [filtered]);
  const pooledForN = useMemo(
    () => pooled_deltas?.find((pd) => pd.n === selectedN),
    [pooled_deltas, selectedN],
  );

  if (charts.length === 0) return null;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
      {/* Header + Controls */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-lg font-semibold text-slate-800">N-gram Analysis</h3>
        <div className="flex items-center gap-3 flex-wrap">
          {/* View mode toggle */}
          <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('heatmap')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'heatmap' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'
              }`}
            >
              Cross-Model
            </button>
            <button
              onClick={() => setViewMode('compare')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'compare' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'
              }`}
            >
              Correct vs Incorrect
            </button>
          </div>
          {/* N selector */}
          <div className="flex gap-1">
            {nValues.map((n) => (
              <button
                key={n}
                onClick={() => setSelectedN(n)}
                className={`px-3 py-1 text-xs rounded-md transition-colors ${
                  selectedN === n ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {n}-gram
              </button>
            ))}
          </div>
          {/* K selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500">Top</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white"
            >
              {[5, 8, 10, 15, 20].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {pooledForN && pooledForN.items.length > 0 && (
        <PooledDeltaBarChart
          chart={{
            method: 'method2_weighted_delta',
            total_models: new Set(
              pooledForN.items.flatMap((item) => Object.keys(item.model_deltas)),
            ).size,
            total_cases: (() => {
              const pooledExpIds = new Set(
                pooledForN.items.flatMap((item) => Object.keys(item.model_deltas)),
              );
              return filtered
                .filter((c) => pooledExpIds.has(c.exp_id))
                .reduce((s, c) => s + c.total_samples, 0);
            })(),
            items: pooledForN.items,
          }}
          title={`Universal ${selectedN}-gram Patterns (Method 2 Weighted Δ)`}
        />
      )}

      {viewMode === 'heatmap' ? (
        <CrossModelHeatmap charts={filtered} topK={topK} expIds={expIds} />
      ) : (
        <CorrectVsIncorrect charts={filtered} topK={topK} expIds={expIds} />
      )}
    </div>
  );
}

// ── Tab 1: Cross-Model Heatmap ──────────────────────────────

function CrossModelHeatmap({ charts, topK, expIds }: { charts: NgramChartData[]; topK: number; expIds: string[] }) {
  // Build per-exp lookup: exp_id → { ngram → usage_rate (count / total_samples) }
  const { expRates, expTotals } = useMemo(() => {
    const rates: Record<string, Record<string, number>> = {};
    const totals: Record<string, number> = {};
    for (const c of charts) {
      const n = c.total_samples || 1;
      totals[c.exp_id] = n;
      if (!rates[c.exp_id]) rates[c.exp_id] = {};
      for (const item of c.items) {
        const count = item.correct_count + item.incorrect_count;
        rates[c.exp_id][item.ngram] = count / n;
      }
    }
    return { expRates: rates, expTotals: totals };
  }, [charts]);

  // Union of top-K n-grams across all models, sorted by avg rate
  const allNgrams = useMemo(() => {
    const avgRate: Record<string, number> = {};
    for (const exp of Object.values(expRates)) {
      for (const [ng, rate] of Object.entries(exp)) {
        avgRate[ng] = (avgRate[ng] || 0) + rate;
      }
    }
    // Divide by number of experiments for true average
    const nExp = Object.keys(expRates).length || 1;
    return Object.entries(avgRate)
      .map(([ng, sum]) => [ng, sum / nExp] as [string, number])
      .sort((a, b) => b[1] - a[1])
      .slice(0, topK)
      .map(([ng]) => ng);
  }, [expRates, topK]);

  // Max rate for color scaling
  const maxRate = useMemo(() => {
    let m = 0.01;
    for (const exp of Object.values(expRates)) {
      for (const ng of allNgrams) {
        m = Math.max(m, exp[ng] || 0);
      }
    }
    return m;
  }, [expRates, allNgrams]);

  const cellSize = 52;
  const fmtPct = (v: number) => `${(v * 100).toFixed(0)}%`;

  return (
    <div>
      <p className="text-sm text-slate-500 mb-3">
        Top-{topK} {charts[0]?.n ?? '?'}-gram patterns across all models. Values = % of samples containing this pattern.
      </p>
      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Column headers = experiments */}
          <div className="flex">
            <div style={{ width: 240, minWidth: 240 }} />
            {expIds.map((eid) => (
              <div key={eid} style={{ width: cellSize, minWidth: cellSize }} className="text-center" title={`${eid} (n=${expTotals[eid] || '?'})`}>
                <span
                  className="text-[9px] text-slate-500 inline-block"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 100 }}
                >
                  {shortLabel(eid, 28)}
                </span>
              </div>
            ))}
          </div>

          {/* Rows = n-grams */}
          {allNgrams.map((ng) => (
            <div key={ng} className="flex items-center">
              <div style={{ width: 240, minWidth: 240 }} className="text-[11px] text-slate-600 text-right pr-2 truncate" title={ng}>
                {shortLabel(ng, 40)}
              </div>
              {expIds.map((eid) => {
                const rate = expRates[eid]?.[ng] || 0;
                const intensity = rate / maxRate;
                return (
                  <div
                    key={eid}
                    style={{
                      width: cellSize,
                      height: 36,
                      minWidth: cellSize,
                      backgroundColor: rate > 0 ? `rgba(59, 130, 246, ${Math.max(intensity, 0.08)})` : '#f8fafc',
                    }}
                    className="border border-white/50 flex items-center justify-center cursor-default"
                    title={`${ng}\n${eid}\nRate: ${(rate * 100).toFixed(1)}%`}
                  >
                    <span className="text-[9px] text-slate-700">{rate > 0.005 ? fmtPct(rate) : ''}</span>
                  </div>
                );
              })}
            </div>
          ))}

          {/* Color legend */}
          <div className="flex items-center gap-3 mt-3 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0' }} />
              0%
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(59,130,246,0.2)' }} />
              Low
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(59,130,246,0.8)' }} />
              High
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Tab 2: Correct vs Incorrect (dual bar chart) ────────────

function CorrectVsIncorrect({ charts, topK, expIds }: { charts: NgramChartData[]; topK: number; expIds: string[] }) {
  const expItems = useMemo(() => {
    const map: Record<string, NgramBarItem[]> = {};
    for (const c of charts) map[c.exp_id] = c.items;
    return map;
  }, [charts]);

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        Top-{topK} {charts[0]?.n ?? '?'}-gram patterns. Bar length = % of samples containing this pattern.{' '}
        <span className="text-emerald-600 font-medium">Green highlight</span> = correct-only.{' '}
        <span className="text-red-500 font-medium">Red highlight</span> = incorrect-only.
      </p>
      {expIds.map((eid) => {
        const items = expItems[eid] || [];
        const chart = charts.find((c) => c.exp_id === eid);
        const nCorrect = chart?.correct_samples || 1;
        const nIncorrect = chart?.incorrect_samples || 1;

        const correctTop = [...items].sort((a, b) => b.correct_count - a.correct_count).slice(0, topK);
        const incorrectTop = [...items].sort((a, b) => b.incorrect_count - a.incorrect_count).filter((i) => i.incorrect_count > 0).slice(0, topK);

        const correctNgrams = new Set(correctTop.map((i) => i.ngram));
        const incorrectNgrams = new Set(incorrectTop.map((i) => i.ngram));

        return (
          <div key={eid} className="border border-slate-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-slate-700 mb-3">
              {eid} <span className="text-slate-400 font-normal">(✅{nCorrect} / ❌{nIncorrect})</span>
            </h4>
            <div className="grid grid-cols-2 gap-4">
              {/* Correct column */}
              <div>
                <div className="text-xs font-semibold text-emerald-600 mb-2 uppercase tracking-wide">
                  Correct Top-{topK}
                </div>
                <BarColumn items={correctTop} total={nCorrect} color="emerald" otherSet={incorrectNgrams} />
              </div>
              {/* Incorrect column */}
              <div>
                <div className="text-xs font-semibold text-red-500 mb-2 uppercase tracking-wide">
                  Incorrect Top-{Math.min(topK, incorrectTop.length)}
                </div>
                {incorrectTop.length === 0 ? (
                  <div className="text-xs text-slate-400 italic py-2">No incorrect samples</div>
                ) : (
                  <BarColumn items={incorrectTop} total={nIncorrect} color="red" otherSet={correctNgrams} />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BarColumn({ items, total, color, otherSet }: {
  items: NgramBarItem[];
  total: number;
  color: 'emerald' | 'red';
  otherSet: Set<string>;
}) {
  const getCount = (item: NgramBarItem) => color === 'emerald' ? item.correct_count : item.incorrect_count;
  const maxRate = Math.max(...items.map((i) => getCount(i) / total), 0.01);

  const barColor = color === 'emerald' ? '#10b981' : '#ef4444';
  const bgHighlight = color === 'emerald' ? 'bg-emerald-50 border-l-2 border-emerald-400' : 'bg-red-50 border-l-2 border-red-400';

  return (
    <div className="space-y-1">
      {items.map((item, i) => {
        const count = getCount(item);
        const rate = count / total;
        const barWidth = (rate / maxRate) * 100;
        const isUnique = !otherSet.has(item.ngram);

        return (
          <div
            key={item.ngram}
            className={`py-1 px-2 rounded ${isUnique ? bgHighlight : ''}`}
            title={`${item.ngram}\n${count}/${total} = ${(rate * 100).toFixed(1)}%`}
          >
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[11px] text-slate-600 truncate mr-2" style={{ maxWidth: '70%' }}>
                <span className="text-slate-400 mr-0.5">{i + 1}.</span>
                {shortLabel(item.ngram)}
                {isUnique && <span className="ml-1 text-xs">●</span>}
              </span>
              <span className="text-[11px] font-medium whitespace-nowrap" style={{ color: barColor }}>
                {(rate * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${barWidth}%`, backgroundColor: barColor }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
