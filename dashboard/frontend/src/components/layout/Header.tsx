import type { FilterOptions } from '../../api/types';

interface HeaderProps {
  filters: FilterOptions | undefined;
  selectedExpId: string;
  selectedModel: string;
  selectedTag: string;
  selectedFaultCategory: string;
  selectedSpl: string;
  onExpIdChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onTagChange: (value: string) => void;
  onFaultCategoryChange: (value: string) => void;
  onSplChange: (value: string) => void;
}

export function Header({
  filters,
  selectedExpId,
  selectedModel,
  selectedTag,
  selectedFaultCategory,
  selectedSpl,
  onExpIdChange,
  onModelChange,
  onTagChange,
  onFaultCategoryChange,
  onSplChange,
}: HeaderProps) {
  return (
    <header className="bg-white border-b border-slate-200 px-6 py-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Experiment:</label>
          <select
            value={selectedExpId}
            onChange={(e) => onExpIdChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All Experiments</option>
            {filters?.exp_ids.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Model:</label>
          <select
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All Models</option>
            {filters?.models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Tag:</label>
          <select
            value={selectedTag}
            onChange={(e) => onTagChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All Tags</option>
            {filters?.tags.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Fault Category:</label>
          <select
            value={selectedFaultCategory}
            onChange={(e) => onFaultCategoryChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All Categories</option>
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
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All</option>
            {filters?.spl_values?.map((v) => (
              <option key={v} value={String(v)}>
                {v}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}
