import React, { useEffect, useState } from 'react';
import { getShipmentMembership, MembershipRecord, MembershipResponse } from '../../api/membership';

interface Props {
  shipmentId: number;
}

export const MembershipTable: React.FC<Props> = ({ shipmentId }) => {
  const [data, setData] = useState<MembershipResponse | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    getShipmentMembership(shipmentId, filter)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [shipmentId, filter]);

  const getStatusBadge = (status: MembershipRecord['membership_status']) => {
    switch (status) {
      case 'matched':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            Matched
          </span>
        );
      case 'matched_with_skew':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Skew-Aligned
          </span>
        );
      case 'ambiguous':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
            ⚠️ Ambiguous Overlap
          </span>
        );
      case 'unmatched':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            🚨 Unmatched Gap
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">
              Interval Join: Reading-to-Handoff Membership
            </h3>
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
              Exasol Time-Overlap
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Derived dynamically by time overlap — temperature telemetry contains no handoff IDs.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {[
            { id: 'all', label: 'All', count: data?.counts.total },
            { id: 'matched', label: 'Matched', count: data?.counts.matched },
            { id: 'matched_with_skew', label: 'Skew-Aligned', count: data?.counts.matched_with_skew },
            { id: 'ambiguous', label: 'Ambiguous', count: data?.counts.ambiguous },
            { id: 'unmatched', label: 'Unmatched', count: data?.counts.unmatched },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                filter === tab.id
                  ? 'bg-slate-900 text-white font-semibold shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab.label} {tab.count !== undefined && <span className="opacity-70">({tab.count})</span>}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-8 text-center text-xs text-slate-400">Loading interval join membership from Exasol...</div>
      ) : error ? (
        <div className="py-4 text-xs text-rose-600">{error}</div>
      ) : !data || data.items.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-400">No telemetry readings match the current filter.</div>
      ) : (
        <div className="overflow-x-auto max-h-96 border border-slate-100 rounded-lg">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-slate-700 font-semibold uppercase tracking-wider sticky top-0 border-b border-slate-200 text-[10px]">
              <tr>
                <th className="py-2.5 px-3">Reading ID</th>
                <th className="py-2.5 px-3">Timestamp (UTC)</th>
                <th className="py-2.5 px-3">Temp (°C)</th>
                <th className="py-2.5 px-3">Logger</th>
                <th className="py-2.5 px-3">Clock Skew</th>
                <th className="py-2.5 px-3">Associated Handoff</th>
                <th className="py-2.5 px-3">Custody Party</th>
                <th className="py-2.5 px-3">Membership Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {data.items.map((row) => {
                return (
                  <tr
                    key={row.reading_id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      row.membership_status === 'ambiguous'
                        ? 'bg-amber-50/40'
                        : row.membership_status === 'unmatched'
                        ? 'bg-rose-50/40'
                        : ''
                    }`}
                  >
                    <td className="py-2 px-3 font-semibold text-slate-800">#{row.reading_id}</td>
                    <td className="py-2 px-3">{row.reading_at_utc}</td>
                    <td className="py-2 px-3 font-bold text-slate-900">
                      <span className={row.temperature_c > 8.0 ? 'text-rose-600 font-black' : row.temperature_c < 2.0 ? 'text-blue-600 font-black' : 'text-slate-800'}>
                        {row.temperature_c.toFixed(1)}°C
                      </span>
                    </td>
                    <td className="py-2 px-3 font-sans text-slate-600">Dev #{row.logger_id}</td>
                    <td className="py-2 px-3 font-sans">
                      {row.skew_seconds !== 0 ? (
                        <span className="text-amber-700 font-medium">+{row.skew_seconds}s</span>
                      ) : (
                        <span className="text-slate-400">0s</span>
                      )}
                    </td>
                    <td className="py-2 px-3 font-sans">
                      {row.handoff_id ? (
                        <span className="font-semibold text-slate-800">
                          Leg #{row.handoff_id} ({row.handoff_type})
                        </span>
                      ) : (
                        <span className="text-rose-600 italic font-semibold">None (Gap)</span>
                      )}
                    </td>
                    <td className="py-2 px-3 font-sans text-slate-600">
                      {row.from_party && row.to_party ? `${row.from_party} → ${row.to_party}` : '—'}
                    </td>
                    <td className="py-2 px-3 font-sans">{getStatusBadge(row.membership_status)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="pt-2 text-[11px] text-slate-400 italic">
        * {data?.disclaimer}
      </div>
    </div>
  );
};
