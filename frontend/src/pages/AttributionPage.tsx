import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAttribution } from '../hooks/useAttribution';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { Disclaimer } from '../components/common/Disclaimer';
import { HorizontalShipmentStepper } from '../components/attribution/HorizontalShipmentStepper';
import { EvidenceReportCard } from '../components/attribution/EvidenceReportCard';
import { ExasolQueryInsights } from '../components/common/ExasolQueryInsights';

export function AttributionPage() {
  const { shipment_id, excursion_id } = useParams<{ shipment_id: string; excursion_id: string }>();
  const navigate = useNavigate();
  const { data, loading, error, recomputing, refetch, recompute } = useAttribution(excursion_id);

  // Selected handoff for detailed evidence report card inspection
  const [selectedHandoffId, setSelectedHandoffId] = useState<number | string | null>(null);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return <ErrorState message={error || 'Attribution data not found.'} onRetry={refetch} />;
  }

  const { excursion, ranked_handoffs, top_ranked_handoff, naive_baseline } = data;

  // Active handoff in focus: selected one, or default to top ranked
  const activeHandoff =
    ranked_handoffs.find((h) => String(h.handoff_id) === String(selectedHandoffId)) ||
    top_ranked_handoff ||
    ranked_handoffs[0];

  // Alternative handoffs (all except the currently selected one or top one)
  const alternativeHandoffs = ranked_handoffs.filter(
    (h) => h.handoff_id !== activeHandoff?.handoff_id
  );

  return (
    <div className="space-y-6">
      {/* Header and Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => navigate(`/shipments/${shipment_id}`)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Custody Timeline
          </button>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
              Excursion Attribution Panel
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
              Investigation Aid
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Explainable ranking of custody segments contributing to excursion incident #{excursion.excursion_id}.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={recompute}
            disabled={recomputing}
            className="px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-sm disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            <svg
              className={`w-3.5 h-3.5 ${recomputing ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {recomputing ? 'Recomputing...' : 'Recompute Attribution'}
          </button>
          <button
            onClick={() => navigate(`/shipments/${shipment_id}/excursions/${excursion_id}/report`)}
            className="px-3.5 py-2 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm inline-flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print Evidence Report
          </button>
        </div>
      </div>

      {/* Mandatory Investigation Aid Disclaimer */}
      <Disclaimer
        type="warning"
        message="This is an investigation aid. It does not determine product temperature, liability, or responsibility. Final disposition remains with the quality team."
      />

      {/* Horizontal Shipment Stepper */}
      <HorizontalShipmentStepper
        handoffs={ranked_handoffs}
        topHandoff={top_ranked_handoff}
        selectedHandoffId={activeHandoff?.handoff_id ?? null}
        onSelectHandoff={(hid) => setSelectedHandoffId(hid)}
      />

      {/* Active Focused Evidence Report Card */}
      {activeHandoff && (
        <EvidenceReportCard
          handoff={activeHandoff}
          excursion={excursion}
        />
      )}

      {/* Methodology Comparison: HandoffGuard vs. Naive Baseline */}
      {naive_baseline && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                Methodology Comparison: Cumulative Degree-Minutes vs. Naive Baseline
              </h2>
              <p className="text-xs text-slate-500">
                Demonstrating why naive first-threshold-crossing alerts misattribute thermal damage.
              </p>
            </div>
            {naive_baseline.agrees_with_top_ranked ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                ✓ Models Agree
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
                ⚠ Attribution Divergence
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-blue-50/40 border border-blue-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700">
                HandoffGuard Attribution (Exasol Degree-Minutes)
              </span>
              <p className="text-sm font-bold text-slate-900 mt-1">
                {top_ranked_handoff ? top_ranked_handoff.handoff_label : 'None'}
              </p>
              <p className="text-xs text-slate-600 mt-1">
                Share: <span className="font-semibold text-rose-600">{top_ranked_handoff?.exposure_share_pct}%</span> |{' '}
                Exposure: <span className="font-semibold">{top_ranked_handoff?.exposure_degree_minutes} °C·min</span> |{' '}
                Confidence: <span className="font-semibold uppercase">{top_ranked_handoff?.confidence_label}</span>
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Naive Baseline (First Threshold Crossing)
              </span>
              <p className="text-sm font-bold text-slate-900 mt-1">
                {naive_baseline.handoff_label}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Attributes initial crossing to whichever custody segment crossed the limit first.
              </p>
            </div>
          </div>

          <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-100 text-xs text-blue-900 leading-relaxed">
            <span className="font-bold">Attribution Analysis: </span>
            {naive_baseline.explanation}
          </div>
        </div>
      )}

      {/* Exasol Query Insights Panel */}
      <ExasolQueryInsights
        queryIdentifier="excursion_attribution"
        shipmentId={shipment_id || 1}
      />

      {/* Ranked Alternative Handoffs Section */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
          Ranked Alternative Custody Handoffs ({alternativeHandoffs.length})
        </h2>
        <p className="text-xs text-slate-500">
          Other custody segments evaluated during excursion window:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {alternativeHandoffs.map((h) => (
            <div
              key={h.handoff_id}
              onClick={() => setSelectedHandoffId(Number(h.handoff_id))}
              className="p-4 bg-white rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900">
                  #{h.rank} — Leg #{h.sequence_no}: {h.handoff_label}
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                  {h.confidence_label}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-600 pt-1 border-t border-slate-100">
                <div>
                  <span className="text-slate-400">Share:</span>{' '}
                  <span className="font-bold">{h.exposure_share_pct.toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-slate-400">Exposure:</span>{' '}
                  <span className="font-mono">{h.exposure_degree_minutes.toFixed(1)} °C·m</span>
                </div>
                <div>
                  <span className="text-slate-400">Peak:</span>{' '}
                  <span className="font-mono">{h.peak_temp_c}°C</span>
                </div>
              </div>

              {h.evidence_notes.length > 0 && (
                <p className="text-[11px] text-slate-500 italic truncate">
                  {h.evidence_notes[0]}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
