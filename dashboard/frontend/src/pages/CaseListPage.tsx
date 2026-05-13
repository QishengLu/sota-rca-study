import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { CaseTable, CaseFilters } from '../components/case-list';
import { Pagination } from '../components/common';

export function CaseListPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const [selectedExpId, setSelectedExpId] = useState(searchParams.get('exp_id') || '');
  const [selectedCorrect, setSelectedCorrect] = useState(searchParams.get('correct') || '');
  const [minRcF1, setMinRcF1] = useState(searchParams.get('min_rc_f1') || '');
  const [maxRcF1, setMaxRcF1] = useState(searchParams.get('max_rc_f1') || '');
  const [selectedFaultCategory, setSelectedFaultCategory] = useState(searchParams.get('fault_category') || '');
  const [selectedSpl, setSelectedSpl] = useState(searchParams.get('spl') || '');
  const [minNSvc, setMinNSvc] = useState(searchParams.get('min_n_svc') || '');
  const [maxNSvc, setMaxNSvc] = useState(searchParams.get('max_n_svc') || '');
  const [minNEdge, setMinNEdge] = useState(searchParams.get('min_n_edge') || '');
  const [maxNEdge, setMaxNEdge] = useState(searchParams.get('max_n_edge') || '');
  const [sortBy, setSortBy] = useState(searchParams.get('sort_by') || 'dataset_index');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>(
    (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc'
  );

  const { data: filters } = useQuery({
    queryKey: ['filters'],
    queryFn: api.getFilters,
  });

  const { data: samples, isLoading, error } = useQuery({
    queryKey: ['samples', page, selectedExpId, selectedCorrect, minRcF1, maxRcF1,
               selectedFaultCategory, selectedSpl, minNSvc, maxNSvc, minNEdge, maxNEdge,
               sortBy, sortOrder],
    queryFn: () =>
      api.getSamples({
        page,
        page_size: 50,
        exp_id: selectedExpId || undefined,
        correct: selectedCorrect ? selectedCorrect === 'true' : undefined,
        min_rc_f1: minRcF1 ? parseFloat(minRcF1) : undefined,
        max_rc_f1: maxRcF1 ? parseFloat(maxRcF1) : undefined,
        fault_category: selectedFaultCategory || undefined,
        spl: selectedSpl ? parseInt(selectedSpl) : undefined,
        min_n_svc: minNSvc ? parseInt(minNSvc) : undefined,
        max_n_svc: maxNSvc ? parseInt(maxNSvc) : undefined,
        min_n_edge: minNEdge ? parseInt(minNEdge) : undefined,
        max_n_edge: maxNEdge ? parseInt(maxNEdge) : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
  });

  const updateParams = (updates: Record<string, string>) => {
    const newParams = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value) {
        newParams.set(key, value);
      } else {
        newParams.delete(key);
      }
    }
    setSearchParams(newParams);
  };

  const handleExpIdChange = (value: string) => {
    setSelectedExpId(value);
    setPage(1);
    updateParams({ exp_id: value, page: '1' });
  };

  const handleCorrectChange = (value: string) => {
    setSelectedCorrect(value);
    setPage(1);
    updateParams({ correct: value, page: '1' });
  };

  const handleMinRcF1Change = (value: string) => {
    setMinRcF1(value);
    setPage(1);
    updateParams({ min_rc_f1: value, page: '1' });
  };

  const handleMaxRcF1Change = (value: string) => {
    setMaxRcF1(value);
    setPage(1);
    updateParams({ max_rc_f1: value, page: '1' });
  };

  const handleFaultCategoryChange = (value: string) => {
    setSelectedFaultCategory(value);
    setPage(1);
    updateParams({ fault_category: value, page: '1' });
  };

  const handleSplChange = (value: string) => {
    setSelectedSpl(value);
    setPage(1);
    updateParams({ spl: value, page: '1' });
  };

  const handleMinNSvcChange = (value: string) => {
    setMinNSvc(value);
    setPage(1);
    updateParams({ min_n_svc: value, page: '1' });
  };

  const handleMaxNSvcChange = (value: string) => {
    setMaxNSvc(value);
    setPage(1);
    updateParams({ max_n_svc: value, page: '1' });
  };

  const handleMinNEdgeChange = (value: string) => {
    setMinNEdge(value);
    setPage(1);
    updateParams({ min_n_edge: value, page: '1' });
  };

  const handleMaxNEdgeChange = (value: string) => {
    setMaxNEdge(value);
    setPage(1);
    updateParams({ max_n_edge: value, page: '1' });
  };

  const handleSort = (field: string) => {
    const newOrder = sortBy === field && sortOrder === 'asc' ? 'desc' : 'asc';
    setSortBy(field);
    setSortOrder(newOrder);
    updateParams({ sort_by: field, sort_order: newOrder });
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    updateParams({ page: String(newPage) });
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
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Case List</h1>
        {samples && (
          <span className="text-sm text-slate-500">
            {samples.total} total samples
          </span>
        )}
      </div>

      <CaseFilters
        filters={filters}
        selectedExpId={selectedExpId}
        selectedCorrect={selectedCorrect}
        minRcF1={minRcF1}
        maxRcF1={maxRcF1}
        selectedFaultCategory={selectedFaultCategory}
        selectedSpl={selectedSpl}
        minNSvc={minNSvc}
        maxNSvc={maxNSvc}
        minNEdge={minNEdge}
        maxNEdge={maxNEdge}
        onExpIdChange={handleExpIdChange}
        onCorrectChange={handleCorrectChange}
        onMinRcF1Change={handleMinRcF1Change}
        onMaxRcF1Change={handleMaxRcF1Change}
        onFaultCategoryChange={handleFaultCategoryChange}
        onSplChange={handleSplChange}
        onMinNSvcChange={handleMinNSvcChange}
        onMaxNSvcChange={handleMaxNSvcChange}
        onMinNEdgeChange={handleMinNEdgeChange}
        onMaxNEdgeChange={handleMaxNEdgeChange}
      />

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-500">Loading...</div>
        </div>
      ) : samples ? (
        <>
          <CaseTable
            data={samples.items}
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
          />

          {samples.total_pages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={samples.total_pages}
              onPageChange={handlePageChange}
            />
          )}
        </>
      ) : null}
    </div>
  );
}
