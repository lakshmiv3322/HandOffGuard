import { useState, useEffect, useCallback } from 'react';
import { getUpcomingPrevention } from '../api/prevention';
import type { PreventionResult } from '../types/api';

interface UsePreventionState {
  data: PreventionResult | null;
  loading: boolean;
  error: string | null;
}

export function usePrevention() {
  const [state, setState] = useState<UsePreventionState>({
    data: null,
    loading: true,
    error: null,
  });

  const fetchData = useCallback(async () => {
    setState({ data: null, loading: true, error: null });
    try {
      const result = await getUpcomingPrevention();
      setState({ data: result, loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: (err as Error).message });
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return { ...state, refetch: fetchData };
}
