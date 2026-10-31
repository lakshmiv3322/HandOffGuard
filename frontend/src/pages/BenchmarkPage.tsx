import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getBenchmarkResults, type BenchmarkReportData } from '../api/insights';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { safeFormat } from '../utils/date';

export function BenchmarkPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<BenchmarkReportData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBenchmark = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getBenchmarkResults();
      setData(res);
    } catch (err) {
      setError((err as Error).message || 'Failed to load benchmark results.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchBenchmark();
  }, []);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message={error || 'Benchmark report not found. Run "npm run benchmark:interval-join" to generate it.'}
        onRetry={fetchBenchmark}
      />
    );
  }

  const { benchmark_date, scale, system_specs, correctness_check, engines } = data;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Shipments
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Exasol Interval Join Performance Benchmark
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300">
                Reproducible
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Empirical multi-engine benchmark comparing non-equi interval join performance over time-series telemetry.
            </p>
          </div>

          <div className="text-left sm:text-right text-xs text-slate-500">
            <p className="font-semibold text-slate-700">Benchmark Date</p>
            <p className="font-mono">{safeFormat(benchmark_date, 'yyyy-MM-dd HH:mm:ss')} UTC</p>
          </div>
        </div>
      </div>

      {/* Dataset Scale and Hardware Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        {/* Scale Card */}
        <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm space-y-3">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
            Dataset Scale
          </span>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <p className="text-[10px] uppercase font-bold text-slate-400">Telemetry Rows</p>
              <p className="text-base font-black text-slate-900 font-mono mt-0.5">
                {scale.readings_row_count.toLocaleString()}
              </p>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <p className="text-[10px] uppercase font-bold text-slate-400">Custody Windows</p>
              <p className="text-base font-black text-slate-900 font-mono mt-0.5">
                {scale.handoff_windows_count.toLocaleString()}
              </p>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <p className="text-[10px] uppercase font-bold text-slate-400">Shipments</p>
              <p className="text-base font-black text-slate-900 font-mono mt-0.5">
                {scale.shipments_count}
              </p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500">
            {scale.scale_rationale}
          </p>
        </div>

        {/* Hardware Specs Card */}
        <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm space-y-3">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
            Hardware & Platform Specifications
          </span>
          <div className="space-y-1.5 text-slate-700">
            <p>
              <span className="text-slate-400">Operating System:</span>{' '}
              <span className="font-mono font-medium">{system_specs.platform}</span>
            </p>
            <p>
              <span className="text-slate-400">Processor:</span>{' '}
              <span className="font-mono font-medium">{system_specs.processor || 'x86_64 / Intel / AMD'}</span>
            </p>
            <p>
              <span className="text-slate-400">Logical CPU Cores:</span>{' '}
              <span className="font-mono font-bold">{system_specs.cpu_logical_cores} Cores</span>
            </p>
            <p>
              <span className="text-slate-400">Memory:</span>{' '}
              <span className="font-mono font-bold">{system_specs.total_ram_gb} GB RAM</span>
            </p>
          </div>
        </div>
      </div>

      {/* Query Description Banner */}
      <div className="p-4 bg-slate-900 text-slate-200 rounded-xl text-xs space-y-2">
        <div className="flex items-center justify-between text-slate-400 text-[10px] uppercase font-bold border-b border-slate-800 pb-1.5">
          <span>Non-Equi Interval Join Query Description</span>
          <span className="text-blue-400">HANDOFFGUARD.v_interval_join_membership</span>
        </div>
        <p className="text-slate-300 leading-relaxed">
          Associates temperature telemetry readings to custody windows dynamically via time-range overlap:
        </p>
        <pre className="p-3 bg-slate-950 rounded font-mono text-[11px] text-amber-300 overflow-x-auto border border-slate-800">
{`SELECT r.reading_id, ld.assigned_shipment_id, h.handoff_id, r.temperature_c
FROM HANDOFFGUARD.logger_readings r
JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
JOIN HANDOFFGUARD.handoffs h ON h.shipment_id = ld.assigned_shipment_id
WHERE r.reading_at_utc BETWEEN ADD_SECONDS(h.window_start_utc, -120)
                          AND ADD_SECONDS(h.window_end_utc, 120);`}
        </pre>
      </div>

      {/* Benchmark Results Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-3 p-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900">
            Multi-Engine Execution Results
          </h2>
          <span className="text-xs text-slate-500">
            Matched Rows: <span className="font-bold text-slate-800">{correctness_check.sqlite_matched_rows.toLocaleString()}</span> (Tolerance ±{correctness_check.tolerance_pct}%)
          </span>
        </div>

        <table className="w-full text-left text-xs border border-slate-200 divide-y divide-slate-200 rounded-lg overflow-hidden">
          <thead className="bg-slate-50 text-slate-600 font-bold">
            <tr className="divide-x divide-slate-200">
              <th className="p-3">Engine</th>
              <th className="p-3 text-right">Readings Processed</th>
              <th className="p-3 text-right">Execution Time</th>
              <th className="p-3 text-right">Throughput</th>
              <th className="p-3 text-center">Benchmark Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {engines.map((eng, idx) => (
              <tr key={idx} className={`divide-x divide-slate-200 ${eng.engine.includes('Exasol') ? 'bg-blue-50/40 font-medium' : ''}`}>
                <td className="p-3">
                  <p className="font-bold text-slate-900">{eng.engine}</p>
                </td>
                <td className="p-3 text-right font-mono">
                  {scale.readings_row_count.toLocaleString()}
                </td>
                <td className="p-3 text-right font-mono font-bold">
                  {eng.execution_time_seconds != null ? `${eng.execution_time_seconds}s` : 'N/A'}
                </td>
                <td className="p-3 text-right font-mono text-emerald-600 font-bold">
                  {eng.throughput_rows_per_second != null
                    ? `${Math.round(eng.throughput_rows_per_second).toLocaleString()} rows/s`
                    : 'N/A'}
                </td>
                <td className="p-3 text-center">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      eng.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-800'
                        : eng.status === 'projected'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {eng.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Reproducibility Instructions */}
        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-[11px] text-slate-600 space-y-1">
          <p className="font-bold text-slate-800">How to Reproduce Locally:</p>
          <p>
            Run <code className="bg-white px-1.5 py-0.5 rounded border border-slate-300 font-mono text-slate-900 font-semibold">npm run benchmark:interval-join</code> from repository root.
          </p>
          <p>
            Full markdown report saved to: <code className="font-mono text-slate-800">reports/interval_join_benchmark.md</code>
          </p>
        </div>
      </div>
    </div>
  );
}
