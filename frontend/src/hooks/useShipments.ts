import { useState, useEffect, useCallback, useRef } from 'react';
import { getShipments, type GetShipmentsParams } from '../api/shipments';
import type { PaginatedResponse, ShipmentListItem } from '../types/api';

interface UseShipmentsState {
  data: PaginatedResponse<ShipmentListItem> | null;
  loading: boolean;
  error: string | null;
}

export function useShipments(params: GetShipmentsParams) {
  const [state, setState] = useState<UseShipmentsState>({
    data: null,
    loading: true,
    error: null,
  });

  // Stable ref to abort in-flight requests on param change
  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const result = await getShipments(params);
      setState({ data: result, loading: false, error: null });
    } catch (err) {
      if ((err as Error).name === 'CanceledError') return;
      setState({ data: null, loading: false, error: (err as Error).message });
    }
  }, [
    params.page,
    params.page_size,
    params.search,
    params.has_excursion,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void fetchData();
    return () => abortRef.current?.abort();
  }, [fetchData]);

  return { ...state, refetch: fetchData };
}
