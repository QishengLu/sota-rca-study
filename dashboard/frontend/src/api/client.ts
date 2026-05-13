// API client for dashboard backend

import type {
  AnalysisParams,
  FilterOptions,
  FingerprintResponse,
  IntentHeatmapResponse,
  MarkovResponse,
  MetricsOverview,
  MetricsParams,
  ModalityProgressionResponse,
  NgramResponse,
  SampleDetail,
  SampleListParams,
  SampleListResponse,
  TransitionResponse,
} from './types';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

function buildQueryString(params: Record<string, unknown> | object): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

export const api = {
  getFilters: (): Promise<FilterOptions> => {
    return fetchJson<FilterOptions>(`${API_BASE}/filters`);
  },

  getMetricsOverview: (params: MetricsParams = {}): Promise<MetricsOverview> => {
    const query = buildQueryString(params);
    return fetchJson<MetricsOverview>(`${API_BASE}/metrics/overview${query}`);
  },

  getSamples: (params: SampleListParams = {}): Promise<SampleListResponse> => {
    const query = buildQueryString(params);
    return fetchJson<SampleListResponse>(`${API_BASE}/samples${query}`);
  },

  getSampleDetail: (id: number): Promise<SampleDetail> => {
    return fetchJson<SampleDetail>(`${API_BASE}/samples/${id}`);
  },

  getNgramAnalysis: (params: AnalysisParams = {}): Promise<NgramResponse> => {
    const searchParams = new URLSearchParams();
    if (params.exp_id) {
      for (const id of params.exp_id) {
        searchParams.append('exp_id', id);
      }
    }
    if (params.n_max !== undefined) searchParams.append('n_max', String(params.n_max));
    if (params.top_k !== undefined) searchParams.append('top_k', String(params.top_k));
    const qs = searchParams.toString();
    return fetchJson<NgramResponse>(`${API_BASE}/analysis/ngrams${qs ? `?${qs}` : ''}`);
  },

  getMarkovAnalysis: (expIds?: string[]): Promise<MarkovResponse> => {
    const searchParams = new URLSearchParams();
    if (expIds) {
      for (const id of expIds) {
        searchParams.append('exp_id', id);
      }
    }
    const qs = searchParams.toString();
    return fetchJson<MarkovResponse>(`${API_BASE}/analysis/markov${qs ? `?${qs}` : ''}`);
  },

  getTransitionAnalysis: (expIds?: string[]): Promise<TransitionResponse> => {
    const searchParams = new URLSearchParams();
    if (expIds) {
      for (const id of expIds) {
        searchParams.append('exp_id', id);
      }
    }
    const qs = searchParams.toString();
    return fetchJson<TransitionResponse>(`${API_BASE}/analysis/transitions${qs ? `?${qs}` : ''}`);
  },
  getFingerprint: (expIds?: string[]): Promise<FingerprintResponse> => {
    const searchParams = new URLSearchParams();
    if (expIds) {
      for (const id of expIds) {
        searchParams.append('exp_id', id);
      }
    }
    const qs = searchParams.toString();
    return fetchJson<FingerprintResponse>(`${API_BASE}/analysis/fingerprint${qs ? `?${qs}` : ''}`);
  },

  getIntentHeatmap: (expIds?: string[]): Promise<IntentHeatmapResponse> => {
    const searchParams = new URLSearchParams();
    if (expIds) {
      for (const id of expIds) {
        searchParams.append('exp_id', id);
      }
    }
    const qs = searchParams.toString();
    return fetchJson<IntentHeatmapResponse>(`${API_BASE}/analysis/intent-heatmap${qs ? `?${qs}` : ''}`);
  },

  getModalityProgression: (expIds?: string[]): Promise<ModalityProgressionResponse> => {
    const searchParams = new URLSearchParams();
    if (expIds) {
      for (const id of expIds) {
        searchParams.append('exp_id', id);
      }
    }
    const qs = searchParams.toString();
    return fetchJson<ModalityProgressionResponse>(`${API_BASE}/analysis/modality-progression${qs ? `?${qs}` : ''}`);
  },
};

export default api;
