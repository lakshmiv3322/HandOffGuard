import { useState, useEffect, useCallback } from 'react';
import { getCustodyTimeline } from '../api/shipments';
import type { CustodyTimeline } from '../types/api';

interface UseTimelineState {
  data: CustodyTimeline | null;
  loading: boolean;
  error: string | null;
}

export function useTimeline(shipmentId: string | undefined) {
  const [state, setState] = useState<UseTimelineState>({
    data: null,
    loading: true,
    error: null,
  });

  const fetchData = useCallback(async () => {
    if (!shipmentId) {
      setState({ data: null, loading: false, error: 'No shipment ID provided.' });
      return;
    }
    setState({ data: null, loading: true, error: null });
    try {
      const result = await getCustodyTimeline(shipmentId);
      setState({ data: result, loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: (err as Error).message });
    }
  }, [shipmentId]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return { ...state, refetch: fetchData };
}
