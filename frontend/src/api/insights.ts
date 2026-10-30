import apiClient from './client';

export interface QueryInsightsData {
  query_identifier: string;
  query_name: string;
  sql_view: string;
  rows_examined: number;
  rows_returned: number;
  execution_time_ms: number;
  latest_reading_timestamp: string | null;
  exasol_connection_status: 'connected' | 'dev_fallback';
  sql_file_path: string;
  sql_query: string;
  measured_at: string;
  disclaimer: string;
}

export interface BenchmarkEngineResult {
  engine: string;
  status: string;
  execution_time_seconds?: number;
  throughput_rows_per_second?: number;
  rows_matched?: number;
  query?: string;
  error?: string;
  notice?: string;
}

export interface BenchmarkReportData {
  benchmark_date: string;
  scale: {
    readings_row_count: number;
    shipments_count: number;
    handoff_windows_count: number;
    scale_rationale: string;
  };
  system_specs: {
    platform: string;
    processor: string;
    cpu_logical_cores: number;
    total_ram_gb: string;
  };
  correctness_check: {
    status: string;
    description: string;
    sqlite_matched_rows: number;
    tolerance_pct: number;
    correctness_verified: boolean;
  };
  engines: BenchmarkEngineResult[];
}

export async function getQueryInsights(
  query: string = 'shipment_interval_membership',
  shipmentId: string | number = 1
): Promise<QueryInsightsData> {
  const response = await apiClient.get<QueryInsightsData>('/api/exasol/query-insights', {
    params: { query, shipment_id: shipmentId },
  });
  return response.data;
}

export async function getBenchmarkResults(): Promise<BenchmarkReportData> {
  const response = await apiClient.get<BenchmarkReportData>('/api/exasol/benchmark-results');
  return response.data;
}
