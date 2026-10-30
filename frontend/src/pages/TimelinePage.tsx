import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTimeline } from '../hooks/useTimeline';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { TemperatureChart } from '../components/charts/TemperatureChart';
import { LoggerCoverage } from '../components/charts/LoggerCoverage';
import { ExposureBarChart } from '../components/charts/ExposureBarChart';
import { TimelineHeader } from '../components/timeline/TimelineHeader';
import { HandoffCard } from '../components/timeline/HandoffCard';
import { DataQualitySummary } from '../components/timeline/DataQualitySummary';
import { ClockSkewIndicator } from '../components/timeline/ClockSkewIndicator';
import { MembershipTable } from '../components/timeline/MembershipTable';
import { Disclaimer } from '../components/common/Disclaimer';

export function TimelinePage() {
  const { shipment_id } = useParams<{ shipment_id: string }>();
  const navigate = useNavigate();
  const { data: timeline, loading, error, refetch } = useTimeline(shipment_id);
  const [highlightedHandoffId, setHighlightedHandoffId] = useState<string | number | null>(null);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !timeline) {
    return <ErrorState message={error || 'Timeline not available'} onRetry={refetch} />;
  }

  const {
    shipment,
    product,
    handoffs,
    loggers,
    readings,
    excursion_intervals,
    suspected_handoff_id,
    data_quality_summary,
    clock_skew_corrections,
    unassigned_intervals,
  } = timeline;

  const firstExcursion = excursion_intervals.length > 0 ? excursion_intervals[0] : null;

  return (
    <div className="space-y-6">
      {/* Back navigation and header */}
      <div>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-3"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Shipments
        </button>

        <TimelineHeader
          shipment={shipment}
          product={product}
          handoffCount={handoffs.length}
          loggerCount={loggers.length}
          excursionCount={excursion_intervals.length}
        />
      </div>

      {/* Excursion Investigation Quick Banner if exists */}
      {firstExcursion && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-rose-50 border border-rose-200 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600 text-lg">
              ⚠
            </span>
            <div>
              <p className="text-sm font-bold text-rose-900">
                Temperature Excursion Detected ({firstExcursion.severity.toUpperCase()})
              </p>
              <p className="text-xs text-rose-700">
                Peak: {firstExcursion.peak_temp_c}°C | Duration: {firstExcursion.duration_minutes} min outside safe range ({product.min_temp_c}°C – {product.max_temp_c}°C).
              </p>
            </div>
          </div>
          <button
            onClick={() =>
              navigate(`/shipments/${shipment.shipment_id}/excursions/${firstExcursion.excursion_id}`)
            }
            className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm shrink-0"
          >
            Investigate Attribution →
          </button>
        </div>
      )}

      {/* Main Hero Chart Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-800">Shipment Custody Temperature Profile</h2>
            <p className="text-xs text-slate-500">
              Synchronized telemetry from {loggers.length} logger(s) mapped against {handoffs.length} custody handoff intervals.
            </p>
          </div>
          {suspected_handoff_id && (
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-50 border border-amber-200 rounded-lg text-xs font-semibold text-amber-800">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              Suspected Handoff Identified
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-2.5 rounded-sm bg-emerald-500/20 border border-emerald-500" />
            <span>Safe Range ({product.min_temp_c}°C – {product.max_temp_c}°C)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-2.5 rounded-sm bg-rose-500/30 border border-rose-500" />
            <span>Excursion Zone</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 border-t-2 border-dashed border-slate-400" />
            <span>Handoff Window Boundary</span>
          </div>
          {suspected_handoff_id && (
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0.5 border-t-2 border-amber-500" />
              <span className="text-amber-800 font-medium">Suspected Handoff Window</span>
            </div>
          )}
          {unassigned_intervals.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-2.5 rounded-sm bg-slate-200 border border-slate-400" />
              <span>Telemetry Gap</span>
            </div>
          )}
        </div>

        {/* The Recharts Temperature Curve */}
        <TemperatureChart
          readings={readings}
          handoffs={handoffs}
          excursionIntervals={excursion_intervals}
          minTempC={product.min_temp_c}
          maxTempC={product.max_temp_c}
          suspectedHandoffId={suspected_handoff_id}
          highlightedHandoffId={highlightedHandoffId}
        />

        {/* Logger Coverage Visualizer */}
        <LoggerCoverage
          loggers={loggers}
          readings={readings}
          clockSkewCorrections={clock_skew_corrections}
        />

        {/* Thermal Exposure Horizontal Bar Chart */}
        <ExposureBarChart shipmentId={Number(shipment.shipment_id)} />
      </div>

      {/* Custody Handoffs Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Custody Handoff Windows ({handoffs.length})
          </h3>
          <p className="text-xs text-slate-400">
            Hover to isolate in chart. Click an excursion-linked card to inspect attribution.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {handoffs.map((h) => {
            const isSuspected =
              suspected_handoff_id != null && String(h.handoff_id) === String(suspected_handoff_id);
            const isHighlighted =
              highlightedHandoffId != null && String(h.handoff_id) === String(highlightedHandoffId);

            return (
              <HandoffCard
                key={h.handoff_id}
                handoff={h}
                shipmentId={shipment.shipment_id}
                excursions={excursion_intervals}
                isSuspected={isSuspected}
                isHighlighted={isHighlighted}
                onMouseEnter={() => setHighlightedHandoffId(h.handoff_id)}
                onMouseLeave={() => setHighlightedHandoffId(null)}
              />
            );
          })}
        </div>
      </div>

      {/* Telemetry and Clock-skew diagnostics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DataQualitySummary summary={data_quality_summary} />
        <ClockSkewIndicator corrections={clock_skew_corrections} />
      </div>

      {/* Exasol Interval Join: Reading-to-Handoff Membership */}
      <MembershipTable shipmentId={Number(shipment.shipment_id)} />

      {/* Mandatory scientific limitation disclaimer */}
      <Disclaimer
        type="warning"
        message="Exposure is estimated from ambient/logger temperature and time. It is not a direct measurement of product-core temperature; thermal mass, packaging, and product-specific heat transfer are not modelled in this prototype."
      />
    </div>
  );
}
