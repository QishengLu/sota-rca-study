import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Header } from '../components/layout/Header';
import {
  StatCard,
  MetricsChart,
  DistributionChart,
  ExperimentTable,
  NgramChart,
  TransitionChart,
  MarkovChart,
  EvidenceUtilizationTable,
  ModalityChart,
  getMetricColorClass,
  getAccuracyColorClass,
} from '../components/overview';

export function OverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedExpId, setSelectedExpId] = useState(searchParams.get('exp_id') || '');
  const [selectedModel, setSelectedModel] = useState(searchParams.get('model') || '');
  const [selectedTag, setSelectedTag] = useState(searchParams.get('tag') || '');
  const [selectedFaultCategory, setSelectedFaultCategory] = useState(searchParams.get('fault_category') || '');
  const [selectedSpl, setSelectedSpl] = useState(searchParams.get('spl') || '');

  const { data: filters } = useQuery({
    queryKey: ['filters'],
    queryFn: api.getFilters,
  });

  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['metrics', selectedExpId, selectedModel, selectedTag, selectedFaultCategory, selectedSpl],
    queryFn: () =>
      api.getMetricsOverview({
        exp_id: selectedExpId || undefined,
        model_name: selectedModel || undefined,
        tag: selectedTag || undefined,
        fault_category: selectedFaultCategory || undefined,
        spl: selectedSpl ? parseInt(selectedSpl) : undefined,
      }),
  });

  const expIdList = selectedExpId ? [selectedExpId] : undefined;

  const { data: ngramData, isLoading: ngramLoading, error: ngramError } = useQuery({
    queryKey: ['ngrams', selectedExpId],
    queryFn: () => api.getNgramAnalysis({ exp_id: expIdList }),
  });

  const { data: transitionData, isLoading: transitionLoading, error: transitionError } = useQuery({
    queryKey: ['transitions', selectedExpId],
    queryFn: () => api.getTransitionAnalysis(expIdList),
  });

  const { data: markovData, isLoading: markovLoading, error: markovError } = useQuery({
    queryKey: ['markov', selectedExpId],
    queryFn: () => api.getMarkovAnalysis(expIdList),
  });

  // EvidenceUtilizationTable now uses transitionData for R→T, no separate coherence fetch needed

  const { data: modalityData, isLoading: modalityLoading, error: modalityError } = useQuery({
    queryKey: ['modality-progression', selectedExpId],
    queryFn: () => api.getModalityProgression(expIdList),
  });

  const updateFilter = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    setSearchParams(newParams);
  };

  const handleExpIdChange = (value: string) => {
    setSelectedExpId(value);
    updateFilter('exp_id', value);
  };

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    updateFilter('model', value);
  };

  const handleTagChange = (value: string) => {
    setSelectedTag(value);
    updateFilter('tag', value);
  };

  const handleFaultCategoryChange = (value: string) => {
    setSelectedFaultCategory(value);
    updateFilter('fault_category', value);
  };

  const handleSplChange = (value: string) => {
    setSelectedSpl(value);
    updateFilter('spl', value);
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          Failed to load data: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header
        filters={filters}
        selectedExpId={selectedExpId}
        selectedModel={selectedModel}
        selectedTag={selectedTag}
        selectedFaultCategory={selectedFaultCategory}
        selectedSpl={selectedSpl}
        onExpIdChange={handleExpIdChange}
        onModelChange={handleModelChange}
        onTagChange={handleTagChange}
        onFaultCategoryChange={handleFaultCategoryChange}
        onSplChange={handleSplChange}
      />

      <div className="p-6 space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-slate-500">Loading...</div>
          </div>
        ) : metrics ? (
          <>
            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <StatCard label="Total Samples" value={metrics.total_samples} />
              <StatCard
                label="Accuracy"
                value={metrics.accuracy.toFixed(1)}
                unit="%"
                colorClass={getAccuracyColorClass(metrics.accuracy)}
              />
              <StatCard
                label="Root Cause F1"
                value={metrics.metrics.root_cause_f1.toFixed(3)}
                colorClass={getMetricColorClass(metrics.metrics.root_cause_f1)}
              />
              <StatCard
                label="Node F1"
                value={metrics.metrics.node_f1.toFixed(3)}
                colorClass={getMetricColorClass(metrics.metrics.node_f1)}
              />
              <StatCard
                label="Edge F1"
                value={metrics.metrics.edge_f1.toFixed(3)}
                colorClass={getMetricColorClass(metrics.metrics.edge_f1)}
              />
              <StatCard
                label="Avg Time"
                value={metrics.avg_time_cost.toFixed(1)}
                unit="s"
              />
            </div>

            {/* Metrics Chart */}
            {metrics.by_experiment.length > 0 && (
              <MetricsChart data={metrics.by_experiment} />
            )}

            {/* Distribution Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {metrics.by_fault_category.length > 0 && (
                <DistributionChart
                  title="Distribution by Fault Category"
                  data={metrics.by_fault_category}
                />
              )}
              {metrics.by_spl.length > 0 && (
                <DistributionChart
                  title="Distribution by SPL"
                  data={metrics.by_spl}
                />
              )}
              {metrics.by_n_svc.length > 0 && (
                <DistributionChart
                  title="Distribution by N_svc"
                  data={metrics.by_n_svc}
                />
              )}
              {metrics.by_n_edge.length > 0 && (
                <DistributionChart
                  title="Distribution by N_edge"
                  data={metrics.by_n_edge}
                />
              )}
              {metrics.by_fault_type.length > 0 && (
                <DistributionChart
                  title="Distribution by Fault Type"
                  data={metrics.by_fault_type}
                />
              )}
              {metrics.by_root_cause_service.length > 0 && (
                <DistributionChart
                  title="Distribution by Root Cause Service"
                  data={metrics.by_root_cause_service}
                />
              )}
            </div>

            {/* Experiment Table */}
            {metrics.by_experiment.length > 0 && (
              <ExperimentTable data={metrics.by_experiment} />
            )}

            {/* Analysis Section */}
            {/* Analysis Section - loading states */}
            {(ngramLoading || transitionLoading || markovLoading || modalityLoading) && (
              <div className="text-sm text-slate-400">Loading analysis...</div>
            )}
            {ngramError && (
              <div className="text-sm text-red-500">N-gram error: {String(ngramError)}</div>
            )}
            {transitionError && (
              <div className="text-sm text-red-500">Transition error: {String(transitionError)}</div>
            )}
            {markovError && (
              <div className="text-sm text-red-500">Markov error: {String(markovError)}</div>
            )}
            {modalityError && (
              <div className="text-sm text-red-500">Modality error: {String(modalityError)}</div>
            )}
            {/* Layer 2: Modality Progression */}
            {modalityData && modalityData.experiments.length > 0 && (
              <ModalityChart data={modalityData} />
            )}
            {/* Layer 1: Markov Transition (5-phase / 19-intent) */}
            {markovData && markovData.experiments.length > 0 && (
              <MarkovChart data={markovData} />
            )}
            {/* Layer 3: N-gram patterns */}
            {ngramData && ngramData.charts.length > 0 && (
              <NgramChart data={ngramData} />
            )}
            {transitionData && transitionData.experiments.length > 0 && (
              <TransitionChart data={transitionData} />
            )}
            {transitionData && transitionData.experiments.length > 0 && (
              <EvidenceUtilizationTable data={transitionData} />
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
