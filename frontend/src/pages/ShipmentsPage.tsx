import { useState, useId } from 'react';
import { useNavigate } from 'react-router-dom';
import { useShipments } from '../hooks/useShipments';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { EmptyState } from '../components/common/EmptyState';
import { PageHeader } from '../components/common/PageHeader';
import { format } from 'date-fns';

export function ShipmentsPage() {
  const navigate = useNavigate();
  const searchInputId = useId();
  const filterSelectId = useId();
  const [search, setSearch] = useState('');
  const [excursionFilter, setExcursionFilter] = useState<'all' | 'true' | 'false'>('all');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, loading, error, refetch } = useShipments({
    page,
    page_size: pageSize,
    search: search.trim() || undefined,
    has_excursion: excursionFilter === 'all' ? undefined : excursionFilter === 'true',
  });

  const handleRowClick = (shipmentId: string | number) => {
    navigate(`/shipments/${shipmentId}`);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Shipments Custody Monitor"
        description="Monitor pharmaceutical cold-chain handoffs, detect thermal excursions, and investigate custody attribution."
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="relative w-full sm:w-80">
          <label htmlFor={searchInputId} className="sr-only">
            Search shipment code or route
          </label>
          <input
            id={searchInputId}
            type="text"
            placeholder="Search shipment code or route..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <svg
            className="absolute left-3 top-2.5 h-4 w-4 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <label htmlFor={filterSelectId} className="text-xs font-semibold text-slate-500 uppercase tracking-wider shrink-0">
            Excursion:
          </label>
          <select
            id={filterSelectId}
            value={excursionFilter}
            onChange={(e) => {
              setExcursionFilter(e.target.value as 'all' | 'true' | 'false');
              setPage(1);
            }}
            className="text-sm rounded-lg border border-slate-300 px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Shipments</option>
            <option value="true">Excursion Detected ⚠</option>
            <option value="false">Compliant Only ✓</option>
          </select>
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="py-20">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          message="No shipments match the selected filters."
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Shipment Code</th>
                  <th className="py-3 px-4">Product Payload</th>
                  <th className="py-3 px-4">Custody Route</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-center">Excursion</th>
                  <th className="py-3 px-4 text-right">Exposure (°C·min)</th>
                  <th className="py-3 px-4 text-center">Worst Severity</th>
                  <th className="py-3 px-4 text-right">Dispatched (UTC)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {data.items.map((s) => (
                  <tr
                    key={s.shipment_id}
                    onClick={() => handleRowClick(s.shipment_id)}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 px-4 font-semibold text-blue-600">
                      {s.shipment_code}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {s.product_name}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate max-w-[140px]">{s.origin}</span>
                        <span className="text-slate-400">→</span>
                        <span className="truncate max-w-[140px]">{s.destination}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant="status" value={s.status} />
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {s.has_excursion ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200">
                          ⚠ Excursion
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                          OK
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-700">
                      {s.total_exposure_degree_minutes > 0 ? (
                        <span className="text-rose-600 font-bold">
                          {s.total_exposure_degree_minutes.toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-slate-400">0.0</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {s.worst_severity ? (
                        <Badge variant="severity" value={s.worst_severity} />
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right text-xs text-slate-500 whitespace-nowrap">
                      {format(new Date(s.dispatched_at), 'yyyy-MM-dd HH:mm')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          {data.total > pageSize && (
            <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 bg-slate-50 text-xs text-slate-600">
              <p>
                Showing {(page - 1) * pageSize + 1} to{' '}
                {Math.min(page * pageSize, data.total)} of {data.total} shipments
              </p>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded bg-white border border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 font-medium"
                >
                  Previous
                </button>
                <button
                  disabled={page * pageSize >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded bg-white border border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 font-medium"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
