import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAttribution } from '../hooks/useAttribution';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { Badge } from '../components/common/Badge';
import { Disclaimer } from '../components/common/Disclaimer';
import { format } from 'date-fns';

export function AttributionPage() {
  const { shipment_id, excursion_id } = useParams<{ shipment_id: string; excursion_id: string }>();
  const navigate = useNavigate();
  const { data, loading, error, recomputing, refetch, recompute } = useAttribution(excursion_id);
  const [expandedHandoffId, setExpandedHandoffId] = useState<string | number | null>(null);

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

  const { excursion, ranked_handoffs, top_ranked_handoff, naive_baseline, disclaimer } = data;

  const toggleEvidence = (id: string | number) => {
    setExpandedHandoffId((prev) => (prev === id ? null : id));
  };

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
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Thermal Excursion Custody Attribution
          </h1>
          <p className="text-xs text-slate-500">
            Explainable ranking of custody segments contributing to excursion #{excursion.excursion_id}.
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

      {/* Prominent Legal Disclaimer */}
      <Disclaimer
        type="warning"
        message={disclaimer || "This is an evidence-based estimate of likely contribution, not a legal determination of liability. Exposure is estimated from ambient/logger temperature and time."}
      />

      {/* Excursion Summary Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Excursion Event Summary
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div>
            <p className="text-xs text-slate-500">Severity</p>
            <div className="mt-1">
              <Badge variant="severity" value={excursion.severity} />
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-500">Duration</p>
            <p className="text-base font-bold text-slate-800 mt-0.5">
              {excursion.duration_minutes.toFixed(0)} mins
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Peak Temperature</p>
            <p className="text-base font-bold text-rose-600 mt-0.5">
              {excursion.peak_temp_c.toFixed(1)}°C
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Breach Started (UTC)</p>
            <p className="text-xs font-semibold text-slate-700 mt-1">
              {format(new Date(excursion.started_at_utc), 'MMM dd, HH:mm')}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Breach Resolved (UTC)</p>
            <p className="text-xs font-semibold text-slate-700 mt-1">
              {format(new Date(excursion.ended_at_utc), 'MMM dd, HH:mm')}
            </p>
          </div>
        </div>
      </div>

      {/* Naive Baseline Comparison Section */}
      {naive_baseline && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                Methodology Comparison: HandoffGuard vs. Naive Baseline
              </h2>
              <p className="text-xs text-slate-500">
                Evaluating degree-minute cumulative exposure versus the naive first-threshold-crossing rule.
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
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                HandoffGuard Attribution (Cumulative Degree-Minutes)
              </span>
              <p className="text-sm font-bold text-slate-800 mt-1">
                {top_ranked_handoff ? top_ranked_handoff.handoff_label : 'None'}
              </p>
              <p className="text-xs text-slate-600 mt-1">
                Share: <span className="font-semibold">{top_ranked_handoff?.exposure_share_pct}%</span> |{' '}
                Exposure: <span className="font-semibold">{top_ranked_handoff?.exposure_degree_minutes} °C·min</span> |{' '}
                Confidence: <span className="font-semibold">{top_ranked_handoff?.confidence_label}</span>
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Naive Baseline (First Threshold Crossing)
              </span>
              <p className="text-sm font-bold text-slate-800 mt-1">
                {naive_baseline.handoff_label}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Attributes sole liability to whichever custody segment crossed the limit first.
              </p>
            </div>
          </div>

          <div className="mt-3 p-3 bg-blue-50/70 rounded-lg border border-blue-100 text-xs text-blue-900 leading-relaxed">
            <span className="font-bold">Attribution Rationale: </span>
            {naive_baseline.explanation}
          </div>
        </div>
      )}

      {/* Ranked Handoffs List */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-slate-800">
          Ranked Custody Handoff Attribution ({ranked_handoffs.length})
        </h2>

        <div className="space-y-3">
          {ranked_handoffs.map((h) => {
            const isTop = h.rank === 1;
            const isExpanded = expandedHandoffId === h.handoff_id;

            return (
              <div
                key={h.handoff_id}
                className={`rounded-xl border transition-all ${
                  isTop
                    ? 'border-blue-300 bg-white shadow-md ring-1 ring-blue-200'
                    : 'border-slate-200 bg-white shadow-sm'
                }`}
              >
                <div className="p-4 sm:p-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                          isTop ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        #{h.rank}
                      </span>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-sm font-bold text-slate-900">
                            {h.handoff_label}
                          </h3>
                          {isTop && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-300">
                              ★ Most Likely Contributing Handoff
                            </span>
                          )}
                          {h.matches_naive_baseline && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600">
                              Matches Naive Baseline
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Segment #{h.sequence_no} • {h.handoff_type.toUpperCase()} • {h.location}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <p className="text-base font-black text-slate-900">
                          {h.exposure_degree_minutes.toFixed(1)}{' '}
                          <span className="text-xs font-normal text-slate-500">°C·min</span>
                        </p>
                        <p className="text-xs font-bold text-rose-600">
                          {h.exposure_share_pct.toFixed(1)}% of total exposure
                        </p>
                      </div>
                      <Badge variant="confidence" value={h.confidence_label} />
                    </div>
                  </div>

                  {/* Quick Metrics Bar */}
                  <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-slate-100 text-xs">
                    <div>
                      <span className="text-slate-400">Peak Temp:</span>{' '}
                      <span className="font-semibold text-slate-800">{h.peak_temp_c}°C</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Time in Excursion:</span>{' '}
                      <span className="font-semibold text-slate-800">
                        {h.duration_outside_safe_range_minutes.toFixed(0)} min
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">Excursion Budget Consumed:</span>{' '}
                      <span className="font-semibold text-slate-800">
                        {h.allowed_excursion_time_consumed_pct.toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">Readings Analyzed:</span>{' '}
                      <span className="font-semibold text-slate-800">{h.reading_count}</span>
                    </div>
                  </div>

                  {/* Toggle Why This Result */}
                  <div className="mt-3 pt-2 flex justify-between items-center text-xs">
                    <button
                      onClick={() => toggleEvidence(h.handoff_id)}
                      className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:text-blue-800"
                    >
                      {isExpanded ? 'Hide Evidence Details ▲' : 'Why this result? View Evidence Details ▼'}
                    </button>
                    <span className="text-slate-400 text-[11px]">
                      Confidence Score: {(h.confidence_score * 100).toFixed(0)}/100
                    </span>
                  </div>
                </div>

                {/* Collapsible Evidence Panel */}
                {isExpanded && (
                  <div className="bg-slate-50 border-t border-slate-200 p-4 rounded-b-xl space-y-3 text-xs">
                    <h4 className="font-bold text-slate-700">Detailed Evidence Breakdown</h4>
                    <ul className="space-y-1.5 list-disc list-inside text-slate-600">
                      {h.evidence_notes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                      ))}
                      {h.first_threshold_crossing_utc && (
                        <li>
                          First threshold crossing recorded at:{' '}
                          <span className="font-mono text-slate-800">
                            {format(new Date(h.first_threshold_crossing_utc), 'yyyy-MM-dd HH:mm:ss')} UTC
                          </span>
                        </li>
                      )}
                      <li>Loggers assigned to segment: {h.logger_ids.join(', ')}</li>
                      {h.has_overlapping_windows && (
                        <li className="text-amber-700">
                          Overlapping handoff windows detected; exposure was assigned proportionally by window overlap duration.
                        </li>
                      )}
                      {h.has_missing_gaps && (
                        <li className="text-amber-700">
                          Data coverage was reduced due to telemetry transmission delays or gaps.
                        </li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
