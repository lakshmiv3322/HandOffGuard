import { useState, useEffect, useCallback } from 'react';
import { getTelemetryDrilldown, type TelemetryDrilldownData } from '../api/telemetry';

export function useTelemetryDrilldown(shipmentId?: string | number) {
  const [data, setData] = useState<TelemetryDrilldownData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDrilldown = useCallback(async () => {
    if (!shipmentId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getTelemetryDrilldown(shipmentId);
      setData(res);
    } catch (err) {
      setError((err as Error).message || 'Failed to fetch telemetry drilldown');
    } finally {
      setLoading(false);
    }
  }, [shipmentId]);

  useEffect(() => {
    void fetchDrilldown();
  }, [fetchDrilldown]);

  return {
    data,
    loading,
    error,
    refetch: fetchDrilldown,
  };
}
