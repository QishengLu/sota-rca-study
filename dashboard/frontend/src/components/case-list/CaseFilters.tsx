import type { FilterOptions } from '../../api/types';

interface CaseFiltersProps {
  filters: FilterOptions | undefined;
  selectedExpId: string;
  selectedCorrect: string;
  minRcF1: string;
  maxRcF1: string;
  selectedFaultCategory: string;
  selectedSpl: string;
  minNSvc: string;
  maxNSvc: string;
  minNEdge: string;
  maxNEdge: string;
  onExpIdChange: (value: string) => void;
  onCorrectChange: (value: string) => void;
  onMinRcF1Change: (value: string) => void;
  onMaxRcF1Change: (value: string) => void;
  onFaultCategoryChange: (value: string) => void;
  onSplChange: (value: string) => void;
  onMinNSvcChange: (value: string) => void;
  onMaxNSvcChange: (value: string) => void;
  onMinNEdgeChange: (value: string) => void;
  onMaxNEdgeChange: (value: string) => void;
}

export function CaseFilters({
  filters,
  selectedExpId,
  selectedCorrect,
  minRcF1,
  maxRcF1,
  selectedFaultCategory,
  selectedSpl,
  minNSvc,
  maxNSvc,
  minNEdge,
  maxNEdge,
  onExpIdChange,
  onCorrectChange,
  onMinRcF1Change,
  onMaxRcF1Change,
  onFaultCategoryChange,
  onSplChange,
  onMinNSvcChange,
  onMaxNSvcChange,
  onMinNEdgeChange,
  onMaxNEdgeChange,
}: CaseFiltersProps) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Experiment:</label>
          <select
            value={selectedExpId}
            onChange={(e) => onExpIdChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            {filters?.exp_ids.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Status:</label>
          <select
            value={selectedCorrect}
            onChange={(e) => onCorrectChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">Correct Only</option>
            <option value="false">Incorrect Only</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Fault Category:</label>
          <select
            value={selectedFaultCategory}
            onChange={(e) => onFaultCategoryChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            {filters?.fault_categories?.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">SPL:</label>
          <select
            value={selectedSpl}
            onChange={(e) => onSplChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            {filters?.spl_values?.map((v) => (
              <option key={v} value={String(v)}>
                {v}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">RC F1:</label>
          <input
            type="number"
            placeholder="Min"
            value={minRcF1}
            onChange={(e) => onMinRcF1Change(e.target.value)}
            min="0"
            max="1"
            step="0.1"
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <span className="text-slate-400">-</span>
          <input
            type="number"
            placeholder="Max"
            value={maxRcF1}
            onChange={(e) => onMaxRcF1Change(e.target.value)}
            min="0"
            max="1"
            step="0.1"
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">N_svc:</label>
          <input
            type="number"
            placeholder="Min"
            value={minNSvc}
            onChange={(e) => onMinNSvcChange(e.target.value)}
            min={filters?.n_svc_range?.min ?? 0}
            max={filters?.n_svc_range?.max ?? 99}
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <span className="text-slate-400">-</span>
          <input
            type="number"
            placeholder="Max"
            value={maxNSvc}
            onChange={(e) => onMaxNSvcChange(e.target.value)}
            min={filters?.n_svc_range?.min ?? 0}
            max={filters?.n_svc_range?.max ?? 99}
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">N_edge:</label>
          <input
            type="number"
            placeholder="Min"
            value={minNEdge}
            onChange={(e) => onMinNEdgeChange(e.target.value)}
            min={filters?.n_edge_range?.min ?? 0}
            max={filters?.n_edge_range?.max ?? 99}
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <span className="text-slate-400">-</span>
          <input
            type="number"
            placeholder="Max"
            value={maxNEdge}
            onChange={(e) => onMaxNEdgeChange(e.target.value)}
            min={filters?.n_edge_range?.min ?? 0}
            max={filters?.n_edge_range?.max ?? 99}
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      </div>
    </div>
  );
}
