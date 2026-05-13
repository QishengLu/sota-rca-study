// API Types matching backend Pydantic schemas

export interface RangeMinMax {
  min: number;
  max: number;
}

export interface FilterOptions {
  exp_ids: string[];
  models: string[];
  agent_types: string[];
  tags: string[];
  fault_types: string[];
  fault_categories: string[];
  spl_values: number[];
  n_svc_range: RangeMinMax;
  n_edge_range: RangeMinMax;
}

export interface PrimaryMetrics {
  root_cause_f1: number;
  root_cause_precision: number;
  root_cause_recall: number;
  node_f1: number;
  node_precision: number;
  node_recall: number;
  edge_f1: number;
  edge_precision: number;
  edge_recall: number;
  path_reachability: number | null;
}

export interface ExperimentMetrics {
  exp_id: string;
  model_name: string | null;
  agent_type: string | null;
  total_samples: number;
  correct_count: number;
  accuracy: number;
  avg_time_cost: number;
  avg_tokens: number;
  avg_cost_usd: number;
  total_cost_usd: number;
  avg_rounds: number;
  metrics: PrimaryMetrics;
}

export interface DistributionItem {
  name: string;
  success: number;
  fail: number;
  total: number;
  accuracy: number;
}

export interface MetricsOverview {
  total_samples: number;
  correct_count: number;
  accuracy: number;
  avg_time_cost: number;
  metrics: PrimaryMetrics;
  by_experiment: ExperimentMetrics[];
  by_fault_type: DistributionItem[];
  by_root_cause_service: DistributionItem[];
  by_fault_category: DistributionItem[];
  by_spl: DistributionItem[];
  by_n_svc: DistributionItem[];
  by_n_edge: DistributionItem[];
}

export interface SampleMetrics {
  root_cause_f1: number | null;
  root_cause_precision: number | null;
  root_cause_recall: number | null;
  node_f1: number | null;
  node_precision: number | null;
  node_recall: number | null;
  edge_f1: number | null;
  edge_precision: number | null;
  edge_recall: number | null;
  path_reachability: boolean | null;
}

export interface SampleListItem {
  id: number;
  exp_id: string;
  model_name: string | null;
  agent_type: string | null;
  dataset_index: number | null;
  datapack_name: string | null;
  correct: boolean | null;
  time_cost: number | null;
  fault_type: string | null;
  fault_category: string | null;
  root_cause_service: string | null;
  spl: number | null;
  n_svc: number | null;
  n_edge: number | null;
  metrics: SampleMetrics;
}

export interface SampleListResponse {
  items: SampleListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TrajectoryItem {
  role: string;
  content: string | null;
  tool_calls: ToolCall[] | null;
  tool_call_id: string | null;
  name: string | null;
}

export interface ToolCall {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
}

export interface GraphNode {
  id: string;
  component: string;
  state: string[];
  is_root_cause: boolean;
  match_status: 'matched' | 'missed' | 'hallucinated' | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  match_status: 'matched' | 'missed' | 'hallucinated' | null;
}

export interface ParsedGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  root_causes: string[];
}

export interface DiagnosticInfo {
  matched_services: string[];
  missed_services: string[];
  hallucinated_services: string[];
  matched_service_edges: [string, string][];
  missed_service_edges: [string, string][];
  hallucinated_service_edges: [string, string][];
}

export interface ToolUsageStats {
  total_calls: number;
  success_count: number;
  failure_count: number;
  tools_used: string[];
}

export interface SampleMeta {
  ground_truth: string[];
  datapack_name: string | null;
  graph_metrics: {
    primary: PrimaryMetrics;
    diagnostic: DiagnosticInfo;
  } | null;
  tool_usage: ToolUsageStats;
}

export interface SampleDetail {
  id: number;
  exp_id: string;
  model_name: string | null;
  agent_type: string | null;
  dataset_index: number | null;
  raw_question: string;
  augmented_question: string | null;
  correct_answer: string | null;
  response: string | null;
  correct: boolean | null;
  time_cost: number | null;
  reasoning: string | null;
  trajectories: TrajectoryItem[];
  meta: SampleMeta;
  parsed_response: ParsedGraph;
  ground_truth_graph: ParsedGraph;
  diagnostic: DiagnosticInfo;
  component_to_service: Record<string, string>;
}

// Query parameters
export interface SampleListParams {
  page?: number;
  page_size?: number;
  exp_id?: string;
  model_name?: string;
  correct?: boolean;
  min_rc_f1?: number;
  max_rc_f1?: number;
  fault_type?: string;
  fault_category?: string;
  spl?: number;
  min_n_svc?: number;
  max_n_svc?: number;
  min_n_edge?: number;
  max_n_edge?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface MetricsParams {
  exp_id?: string;
  model_name?: string;
  tag?: string;
  fault_category?: string;
  spl?: number;
}

// ── Analysis Types ──────────────────────────────────────────────

export interface NgramBarItem {
  ngram: string;
  correct_count: number;
  incorrect_count: number;
}

export interface NgramChartData {
  exp_id: string;
  n: number;
  total_samples: number;
  correct_samples: number;
  incorrect_samples: number;
  items: NgramBarItem[];
}

export interface PooledDeltaItem {
  label: string;
  pooled_delta: number;
  model_deltas: Record<string, number>;
}

export interface PooledDeltaChart {
  method: string;
  total_models: number;
  total_cases: number;
  items: PooledDeltaItem[];
}

export interface NgramPooledDelta {
  n: number;
  items: PooledDeltaItem[];
}

export interface NgramResponse {
  charts: NgramChartData[];
  pooled_deltas: NgramPooledDelta[];
}

export interface AnalysisParams {
  exp_id?: string[];
  n_max?: number;
  top_k?: number;
}

// ── Transition Taxonomy Types ──────────────────────────────────

export interface TransitionLabelItem {
  label: string;
  correct_pct: number;
  incorrect_pct: number;
  all_pct: number;
}

export interface TransitionExpData {
  exp_id: string;
  correct_count: number;
  incorrect_count: number;
  correct_rates: Record<string, number>;
  incorrect_rates: Record<string, number>;
  label_distribution: TransitionLabelItem[];
  total_transitions: number;
}

export interface TransitionResponse {
  rate_keys: string[];
  rate_labels: Record<string, string>;
  experiments: TransitionExpData[];
  aggregated: TransitionExpData | null;
  pooled_delta: PooledDeltaChart | null;
}

// ── Markov Chain Analysis Types ──────────────────────────────────

export interface MarkovTransitionCell {
  from_state: string;
  to_state: string;
  correct_prob: number;
  incorrect_prob: number;
}

export interface MarkovStateMetrics {
  state: string;
  correct_stationary: number;
  incorrect_stationary: number;
  kl_divergence: number;
}

export interface MarkovLayerData {
  states: string[];
  transitions: MarkovTransitionCell[];
  state_metrics: MarkovStateMetrics[];
  correct_entropy: number;
  incorrect_entropy: number;
  total_kl: number;
}

export interface MarkovExpData {
  exp_id: string;
  correct_count: number;
  incorrect_count: number;
  states: string[];
  transitions: MarkovTransitionCell[];
  state_metrics: MarkovStateMetrics[];
  correct_entropy: number;
  incorrect_entropy: number;
  total_kl: number;
  intent_only?: MarkovLayerData;
  phase_layer?: MarkovLayerData;
}

export interface MarkovResponse {
  experiments: MarkovExpData[];
}

// ── Fingerprint Types ──────────────────────────────────────────

export interface FingerprintDimension {
  key: string;
  label: string;
  value: number;
  raw_value: number;
}

export interface FingerprintExpData {
  exp_id: string;
  model_name: string | null;
  total_samples: number;
  accuracy: number;
  dimensions: FingerprintDimension[];
}

export interface FingerprintResponse {
  dimension_keys: string[];
  dimension_labels: Record<string, string>;
  experiments: FingerprintExpData[];
}

// ── Intent Heatmap Types ───────────────────────────────────────

export interface IntentHeatmapCell {
  intent: string;
  exp_id: string;
  usage_rate: number;
  correct_rate: number;
  incorrect_rate: number;
}

export interface IntentHeatmapResponse {
  intents: string[];
  experiments: string[];
  cells: IntentHeatmapCell[];
}

// ── Modality Progression Types ───────────────────────────────────

export interface ModalityProgressionBin {
  progress: number;
  logs: number;
  traces: number;
  metrics: number;
}

export interface ModalityProgressionExpData {
  exp_id: string;
  bins: ModalityProgressionBin[];
}

export interface ModalityProgressionResponse {
  experiments: ModalityProgressionExpData[];
}
