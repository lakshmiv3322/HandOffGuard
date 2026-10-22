import { useState, useEffect, useCallback } from 'react';
import { getAttribution, recomputeAttribution } from '../api/attribution';
import type { AttributionResult } from '../types/api';

interface UseAttributionState {
  data: AttributionResult | null;
  loading: boolean;
  error: string | null;
  recomputing: boolean;
}

export function useAttribution(
  excursionId: string | number | undefined,
) {
  const [state, setState] = useState<UseAttributionState>({
    data: null,
    loading: true,
    error: null,
    recomputing: false,
  });

  const fetchData = useCallback(async () => {
    if (!excursionId) {
      setState({ data: null, loading: false, error: 'Missing excursion ID.', recomputing: false });
      return;
    }
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const result = await getAttribution(excursionId);
      setState({ data: result, loading: false, error: null, recomputing: false });
    } catch (err) {
      setState({ data: null, loading: false, error: (err as Error).message, recomputing: false });
    }
  }, [excursionId]);

  const recompute = useCallback(async () => {
    if (!excursionId) return;
    setState((prev) => ({ ...prev, recomputing: true, error: null }));
    try {
      const result = await recomputeAttribution(excursionId);
      setState({ data: result, loading: false, error: null, recomputing: false });
    } catch (err) {
      setState((prev) => ({ ...prev, recomputing: false, error: (err as Error).message }));
    }
  }, [excursionId]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return { ...state, refetch: fetchData, recompute };
}
