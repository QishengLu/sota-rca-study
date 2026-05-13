import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { api } from '../api';
import { Badge } from '../components/common/Badge';
import {
  ConversationView,
  ComparisonView,
  MetricsBreakdown,
  CausalGraphView,
} from '../components/case-detail';

type TabId = 'conversation' | 'comparison' | 'graph' | 'metrics';

const tabs: { id: TabId; label: string }[] = [
  { id: 'conversation', label: 'Conversation' },
  { id: 'comparison', label: 'Comparison' },
  { id: 'graph', label: 'Causal Graph' },
  { id: 'metrics', label: 'Metrics' },
];

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<TabId>('conversation');

  const { data: sample, isLoading, error } = useQuery({
    queryKey: ['sample', id],
    queryFn: () => api.getSampleDetail(Number(id)),
    enabled: !!id,
  });

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          Failed to load sample: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  if (isLoading || !sample) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-3">
          <Link to="/" className="hover:text-primary-600">Overview</Link>
          <span>/</span>
          <Link to="/cases" className="hover:text-primary-600">Case List</Link>
          <span>/</span>
          <span className="text-slate-800">Case #{sample.dataset_index}</span>
        </div>

        {/* Title and Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-slate-800">
              Case #{sample.dataset_index}
            </h1>
            <Badge variant={sample.correct ? 'success' : 'error'} size="md">
              {sample.correct ? 'Correct' : 'Incorrect'}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-500">
            <span>Exp: {sample.exp_id}</span>
            <span>Model: {sample.model_name || '-'}</span>
            <span>Time: {sample.time_cost?.toFixed(1)}s</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-slate-200 px-6">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {activeTab === 'conversation' && (
          <div className="space-y-6">
            {/* Question */}
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-600 mb-2">Question</h3>
              <p className="text-slate-800 whitespace-pre-wrap">
                {sample.augmented_question || sample.raw_question}
              </p>
            </div>

            {/* Response */}
            {sample.response && (
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-600 mb-2">Final Response</h3>
                <p className="text-slate-800 whitespace-pre-wrap">{sample.response}</p>
              </div>
            )}

            {/* Conversation History */}
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-600 mb-4">Conversation History</h3>
              <ConversationView trajectories={sample.trajectories} />
            </div>
          </div>
        )}

        {activeTab === 'comparison' && (
          <ComparisonView
            parsedResponse={sample.parsed_response}
            groundTruthGraph={sample.ground_truth_graph}
            diagnostic={sample.diagnostic}
          />
        )}

        {activeTab === 'graph' && (
          <CausalGraphView
            parsedResponse={sample.parsed_response}
            groundTruthGraph={sample.ground_truth_graph}
            diagnostic={sample.diagnostic}
            componentToService={sample.component_to_service}
          />
        )}

        {activeTab === 'metrics' && (
          <MetricsBreakdown meta={sample.meta} />
        )}
      </div>
    </div>
  );
}
