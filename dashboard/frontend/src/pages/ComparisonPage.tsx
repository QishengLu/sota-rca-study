import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { FingerprintResponse, IntentHeatmapResponse, FilterOptions } from '../api/types';
import { FingerprintRadar } from '../components/analysis/FingerprintRadar';
import { IntentHeatmap } from '../components/analysis/IntentHeatmap';

export function ComparisonPage() {
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [selectedExpIds, setSelectedExpIds] = useState<string[]>([]);
  const [fingerprint, setFingerprint] = useState<FingerprintResponse | null>(null);
  const [heatmap, setHeatmap] = useState<IntentHeatmapResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Load available exp_ids
  useEffect(() => {
    api.getFilters().then(setFilters);
  }, []);

  // Auto-select thinkdepthai experiments on load
  useEffect(() => {
    if (filters && selectedExpIds.length === 0) {
      const thinkExpIds = filters.exp_ids.filter((id) => id.startsWith('thinkdepthai'));
      setSelectedExpIds(thinkExpIds);
    }
  }, [filters]);

  // Fetch data when selection changes
  useEffect(() => {
    if (selectedExpIds.length === 0) return;
    setLoading(true);
    Promise.all([
      api.getFingerprint(selectedExpIds),
      api.getIntentHeatmap(selectedExpIds),
    ]).then(([fp, hm]) => {
      setFingerprint(fp);
      setHeatmap(hm);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [selectedExpIds]);

  const toggleExpId = (id: string) => {
    setSelectedExpIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Model Comparison</h2>
        <p className="text-sm text-slate-500 mt-1">
          Behavioral fingerprint and intent distribution across models
        </p>
      </div>

      {/* Experiment selector */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
        <h4 className="text-sm font-semibold text-slate-600 mb-2">Select Experiments</h4>
        <div className="flex flex-wrap gap-2">
          {filters?.exp_ids.map((id) => (
            <button
              key={id}
              onClick={() => toggleExpId(id)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                selectedExpIds.includes(id)
                  ? 'bg-blue-100 text-blue-700 border border-blue-300'
                  : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
              }`}
            >
              {id}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-center py-8 text-slate-400">Loading analysis...</div>
      )}

      {/* Radar chart */}
      {fingerprint && !loading && <FingerprintRadar data={fingerprint} />}

      {/* Intent heatmap */}
      {heatmap && !loading && <IntentHeatmap data={heatmap} />}
    </div>
  );
}
