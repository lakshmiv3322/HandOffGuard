import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getQueryInsights, type QueryInsightsData } from '../../api/insights';
import { safeFormat } from '../../utils/date';

interface ExasolQueryInsightsProps {
  queryIdentifier?: string;
  shipmentId?: string | number;
}

export function ExasolQueryInsights({
  queryIdentifier = 'shipment_interval_membership',
  shipmentId = 1,
}: ExasolQueryInsightsProps) {
  const [data, setData] = useState<QueryInsightsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isSqlExpanded, setIsSqlExpanded] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    getQueryInsights(queryIdentifier, shipmentId)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch(() => {
        // Handle gracefully
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [queryIdentifier, shipmentId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-400 animate-pulse">
        Measuring Exasol query execution...
      </div>
    );
  }

  if (!data) return null;

  const raw = data as any;
  const queryName = data.query_name ?? raw.query_name ?? 'Interval Join';
  const sqlView = data.sql_view ?? raw.sql_view ?? 'HANDOFFGUARD.v_reading_handoff_membership';
  const rowsExamined = data.rows_examined ?? raw.execution_metrics?.rows_examined ?? 0;
  const rowsReturned = data.rows_returned ?? raw.execution_metrics?.rows_returned ?? 0;
  const executionTimeMs = data.execution_time_ms ?? raw.execution_metrics?.execution_time_ms ?? 0;
  const connectionStatus = data.exasol_connection_status ?? raw.execution_metrics?.engine ?? 'connected';
  const latestTs = data.latest_reading_timestamp ?? raw.execution_metrics?.latest_reading_at_utc ?? null;
  const sqlFilePath = data.sql_file_path ?? raw.sql_file_path ?? 'setup_exasol.sql';
  const sqlQuery = data.sql_query ?? raw.sql_source ?? '';
  const measuredAt = data.measured_at ?? raw.execution_metrics?.measured_at_utc ?? '';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3 text-xs">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-blue-600 text-white font-black text-[10px]">
            EX
          </span>
          <h3 className="font-bold text-slate-900 text-xs">
            Exasol Query Insights
          </h3>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
              connectionStatus === 'connected'
                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                : 'bg-slate-100 text-slate-700 border border-slate-300'
            }`}
          >
            {connectionStatus === 'connected'
              ? '● Exasol Personal Live'
              : '● Dev SQL Engine (Measured)'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/exasol/benchmark"
            className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center gap-1"
          >
            <span>View 100k Benchmark</span>
            <span>→</span>
          </Link>
        </div>
      </div>

      {/* Grid of Measured Real Metrics (No invented throughput) */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-[10px] uppercase font-bold text-slate-400">Query Name</p>
          <p className="text-xs font-bold text-slate-800 truncate mt-0.5" title={queryName}>
            {queryName}
          </p>
        </div>

        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-[10px] uppercase font-bold text-slate-400">SQL View</p>
          <p className="text-xs font-mono font-bold text-blue-700 truncate mt-0.5" title={sqlView}>
            {sqlView}
          </p>
        </div>

        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-[10px] uppercase font-bold text-slate-400">Rows Examined</p>
          <p className="text-sm font-black font-mono text-slate-900 mt-0.5">
            {Number(rowsExamined || 0).toLocaleString()}
          </p>
        </div>

        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-[10px] uppercase font-bold text-slate-400">Rows Returned</p>
          <p className="text-sm font-black font-mono text-slate-900 mt-0.5">
            {Number(rowsReturned || 0).toLocaleString()}
          </p>
        </div>

        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-[10px] uppercase font-bold text-slate-400">Execution Time</p>
          <p className="text-sm font-black font-mono text-emerald-600 mt-0.5">
            {Number(executionTimeMs || 0).toFixed(2)} ms
          </p>
        </div>
      </div>

      {/* Footer Info: Latest timestamp & SQL file link */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-slate-500 pt-1">
        <div className="flex items-center gap-3">
          {latestTs && (
            <span>
              Latest Reading:{' '}
              <span className="font-mono text-slate-700">
                {safeFormat(latestTs, 'yyyy-MM-dd HH:mm:ss')} UTC
              </span>
            </span>
          )}
          <span>
            Schema Source:{' '}
            <code className="text-[10px] bg-slate-100 px-1 py-0.5 rounded text-slate-700">
              {sqlFilePath}
            </code>
          </span>
        </div>

        <button
          onClick={() => setIsSqlExpanded(!isSqlExpanded)}
          className="text-blue-600 hover:text-blue-800 font-semibold self-start sm:self-auto"
        >
          {isSqlExpanded ? 'Hide Query SQL ▲' : 'View Query SQL ▼'}
        </button>
      </div>

      {/* Collapsible SQL Query Viewer */}
      {isSqlExpanded && (
        <div className="mt-2 p-3 bg-slate-900 rounded-lg text-slate-200 font-mono text-[11px] overflow-x-auto border border-slate-800">
          <div className="flex justify-between text-slate-400 text-[10px] mb-1.5 border-b border-slate-800 pb-1">
            <span>EXASOL SQL SPECIFICATION</span>
            <span>Measured at {safeFormat(measuredAt, 'HH:mm:ss')} UTC</span>
          </div>
          <pre>{sqlQuery}</pre>
        </div>
      )}
    </div>
  );
}
