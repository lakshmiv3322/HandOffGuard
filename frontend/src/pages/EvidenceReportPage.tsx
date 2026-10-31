import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getEvidenceReport } from '../api/attribution';
import type { EvidenceReportData } from '../types/api';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { format } from 'date-fns';

export function EvidenceReportPage() {
  const { shipment_id, excursion_id } = useParams<{ shipment_id: string; excursion_id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<EvidenceReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    if (!excursion_id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getEvidenceReport(excursion_id);
      setData(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchReport();
  }, [excursion_id]);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return <ErrorState message={error || 'Report data could not be generated.'} onRetry={fetchReport} />;
  }

  const {
    report_title,
    generated_at,
    shipment_details,
    product_details,
    excursion_details,
    custody_timeline_summary,
    ranked_handoffs,
    data_quality_notes,
    limitations,
    disclaimer,
  } = data;

  return (
    <div className="max-w-4xl mx-auto space-y-6 print:space-y-4 print:p-0">
      {/* Top action bar — hidden during print */}
      <div className="flex items-center justify-between no-print border-b border-slate-200 pb-4">
        <button
          onClick={() => navigate(`/shipments/${shipment_id}/excursions/${excursion_id}`)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Attribution
        </button>

        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
          </svg>
          Print Report (PDF)
        </button>
      </div>

      {/* Printable Report Canvas */}
      <div className="bg-white p-8 sm:p-12 rounded-xl border border-slate-200 shadow-sm print:border-none print:shadow-none print:p-0 space-y-6 text-slate-800">
        {/* Header */}
        <div className="border-b-2 border-slate-900 pb-4">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-[10px] font-black uppercase tracking-widest text-blue-700">
                HandoffGuard Quality Assurance System
              </span>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight mt-1">
                {report_title}
              </h1>
              <p className="text-xs text-slate-500 mt-1">
                Excursion Reference: EXCURSION-{excursion_details.excursion_id} | Shipment: {shipment_details.shipment_code}
              </p>
            </div>
            <div className="text-right text-xs text-slate-500">
              <p className="font-semibold text-slate-700">Generated On (UTC)</p>
              <p className="font-mono mt-0.5">{format(new Date(generated_at), 'yyyy-MM-dd HH:mm:ss')}</p>
              <span className="inline-block mt-1 px-2 py-0.5 bg-slate-100 border border-slate-200 text-[10px] font-bold rounded">
                PROTOTYPE AUDIT
              </span>
            </div>
          </div>
        </div>

        {/* Shipment & Product Information */}
        <div className="grid grid-cols-2 gap-6 text-xs border-b border-slate-200 pb-4">
          <div>
            <h2 className="font-bold uppercase tracking-wider text-slate-500 mb-2">Shipment Details</h2>
            <div className="space-y-1">
              <p><span className="text-slate-500">Origin:</span> {shipment_details.origin}</p>
              <p><span className="text-slate-500">Destination:</span> {shipment_details.destination}</p>
              <p><span className="text-slate-500">Dispatched:</span> {format(new Date(shipment_details.dispatched_at), 'yyyy-MM-dd HH:mm')} UTC</p>
              <p><span className="text-slate-500">Status:</span> {shipment_details.status.toUpperCase()}</p>
            </div>
          </div>

          <div>
            <h2 className="font-bold uppercase tracking-wider text-slate-500 mb-2">Product Profile</h2>
            <div className="space-y-1">
              <p><span className="text-slate-500">Product:</span> {product_details.name}</p>
              <p><span className="text-slate-500">Safe Temperature Band:</span> <span className="font-bold">{product_details.min_temp_c}°C to {product_details.max_temp_c}°C</span></p>
              <p><span className="text-slate-500">Thermal Mass Class:</span> {product_details.thermal_mass_class}</p>
              <p><span className="text-slate-500">Max Excursion Budget:</span> {product_details.allowed_excursion_minutes} mins</p>
            </div>
          </div>
        </div>

        {/* Excursion & Custody Summary */}
        <div className="grid grid-cols-2 gap-6 text-xs border-b border-slate-200 pb-4">
          <div>
            <h2 className="font-bold uppercase tracking-wider text-slate-500 mb-2">Excursion Incident</h2>
            <div className="space-y-1">
              <p><span className="text-slate-500">Severity:</span> <span className="font-bold uppercase text-rose-700">{excursion_details.severity}</span></p>
              <p><span className="text-slate-500">Peak Temperature:</span> <span className="font-bold text-rose-700">{excursion_details.peak_temp_c}°C</span></p>
              <p><span className="text-slate-500">Duration Outside Limits:</span> {excursion_details.duration_minutes} minutes</p>
              <p><span className="text-slate-500">Started:</span> {format(new Date(excursion_details.started_at_utc), 'yyyy-MM-dd HH:mm')} UTC</p>
              <p><span className="text-slate-500">Ended:</span> {format(new Date(excursion_details.ended_at_utc), 'yyyy-MM-dd HH:mm')} UTC</p>
              {excursion_details.ground_truth_cause && (
                <p className="mt-1"><span className="text-slate-500">Root Cause Note:</span> {excursion_details.ground_truth_cause}</p>
              )}
            </div>
          </div>

          <div>
            <h2 className="font-bold uppercase tracking-wider text-slate-500 mb-2">Custody Timeline Metrics</h2>
            <div className="space-y-1">
              <p><span className="text-slate-500">Total Custody Segments:</span> {custody_timeline_summary.total_handoffs}</p>
              <p><span className="text-slate-500">Temperature Loggers:</span> {custody_timeline_summary.total_loggers}</p>
              <p><span className="text-slate-500">Total Observations:</span> {custody_timeline_summary.total_readings}</p>
              <p><span className="text-slate-500">Telemetry Gaps Flagged:</span> {custody_timeline_summary.missing_gaps_count}</p>
            </div>
          </div>
        </div>

        {/* Methodology Notes */}
        <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs space-y-1">
          <p className="font-bold text-slate-800">Custody Attribution Methodology</p>
          <p className="text-slate-600">
            Attribution is derived strictly via dynamic time-interval joins intersecting supported sensor telemetry (segments &le; 600s) with official custody windows and excursion boundaries.
          </p>
          <p className="text-slate-500 italic pt-1">
            {disclaimer}
          </p>
        </div>

        {/* Ranked Attribution Table */}
        <div>
          <h2 className="font-bold uppercase tracking-wider text-xs text-slate-500 mb-2">
            Custody Handoff Attribution Breakdown
          </h2>
          <table className="w-full text-left text-xs border border-slate-200 divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr className="divide-x divide-slate-200 text-slate-600 font-bold">
                <th className="p-2 text-center w-10">Rank</th>
                <th className="p-2">Handoff Custody Segment</th>
                <th className="p-2 text-center">Type</th>
                <th className="p-2 text-right">Exposure (°C·min)</th>
                <th className="p-2 text-right">Share (%)</th>
                <th className="p-2 text-right">Peak (°C)</th>
                <th className="p-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {ranked_handoffs.map((h) => (
                <tr key={h.handoff_id} className={`divide-x divide-slate-200 ${h.rank === 1 && !h.is_candidate_only ? 'bg-blue-50/50 font-medium' : ''}`}>
                  <td className="p-2 text-center font-bold">
                    {h.rank !== null && h.rank !== undefined ? `#${h.rank}` : '—'}
                  </td>
                  <td className="p-2">
                    <p className="font-semibold">{h.handoff_label}</p>
                    <p className="text-[10px] text-slate-500">Segment #{h.sequence_no} @ {h.location}</p>
                  </td>
                  <td className="p-2 text-center capitalize">{h.handoff_type}</td>
                  <td className={`p-2 text-right font-mono ${h.exposure_degree_minutes === null ? 'text-slate-400 italic' : ''}`}>
                    {h.exposure_degree_minutes !== null && h.exposure_degree_minutes !== undefined ? h.exposure_degree_minutes.toFixed(1) : 'Unavailable'}
                  </td>
                  <td className="p-2 text-right font-mono font-bold">
                    {h.exposure_share_pct !== null && h.exposure_share_pct !== undefined ? `${h.exposure_share_pct.toFixed(1)}%` : 'N/A'}
                  </td>
                  <td className="p-2 text-right font-mono">{h.peak_temp_c}°C</td>
                  <td className="p-2 text-center">{h.confidence_label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Evidence & Quality Notes */}
        <div className="border-t border-slate-200 pt-3 text-xs space-y-2">
          <h2 className="font-bold uppercase tracking-wider text-slate-500">Data Quality & Telemetry Audit Notes</h2>
          <ul className="list-disc list-inside space-y-1 text-slate-600">
            {data_quality_notes.map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>

        {/* Limitations and Disclaimers */}
        <div className="border-t border-slate-200 pt-3 text-[11px] text-slate-500 space-y-1 bg-slate-50/50 p-3 rounded">
          <p className="font-bold uppercase tracking-wider text-slate-600">Limitations & Prototype Disclaimer</p>
          {limitations.map((lim, idx) => (
            <p key={idx}>• {lim}</p>
          ))}
        </div>
      </div>
    </div>
  );
}
