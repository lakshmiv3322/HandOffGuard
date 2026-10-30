import { format } from 'date-fns';
import type { AttributionHandoff, ExcursionEvent } from '../../types/api';

interface EvidenceReportCardProps {
  handoff: AttributionHandoff;
  excursion: ExcursionEvent;
}

export function EvidenceReportCard({ handoff, excursion }: EvidenceReportCardProps) {
  // Generate practical recommended investigation steps based on metrics
  const recommendedSteps: string[] = [];

  if (handoff.exposure_share_pct > 50) {
    recommendedSteps.push(
      `Issue formal Carrier Inquiry to ${handoff.to_party || 'receiving party'} regarding thermal management during ${handoff.handoff_type}.`
    );
  }
  if (handoff.peak_temp_c > 12.0) {
    recommendedSteps.push(
      `Audit dock loading logs at ${handoff.location || 'transfer hub'} for unshaded tarmac exposure or delayed reefer plug-in.`
    );
  }
  if (handoff.has_missing_gaps) {
    recommendedSteps.push(
      `Request cellular gateway connectivity logs from logger manufacturer for logger(s) ${handoff.logger_ids.join(', ')}.`
    );
  }
  if (handoff.clock_skew_corrections.some((s) => Math.abs(s) > 60)) {
    recommendedSteps.push(
      'Schedule physical logger time-synchronization and calibration verification before re-deployment.'
    );
  }
  if (handoff.has_overlapping_windows) {
    recommendedSteps.push(
      'Cross-examine physical signed bills of lading against electronic gate check-in timestamps to reconcile window overlap.'
    );
  }
  if (recommendedSteps.length === 0) {
    recommendedSteps.push('Review secondary logger readings and package insulation condition upon destination receipt.');
  }

  const isTopCulprit = handoff.rank === 1;

  return (
    <div
      className={`rounded-xl border p-5 shadow-sm space-y-4 ${
        isTopCulprit
          ? 'bg-rose-50/40 border-rose-200'
          : 'bg-white border-slate-200'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200/80 pb-3">
        <div>
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
            Evidence Report Card
          </span>
          <h3 className="text-base font-bold text-slate-900 mt-0.5">
            Leg #{handoff.sequence_no}: {handoff.handoff_label}
          </h3>
          <p className="text-xs text-slate-500">
            📍 Location: {handoff.location} • Type: {handoff.handoff_type.toUpperCase()}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
              handoff.confidence_label.toLowerCase() === 'high'
                ? 'bg-rose-100 text-rose-800 border border-rose-300'
                : handoff.confidence_label.toLowerCase() === 'medium'
                ? 'bg-amber-100 text-amber-800 border border-amber-300'
                : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
            }`}
          >
            Attribution Score: {(handoff.confidence_score * 100).toFixed(0)}/100 ({handoff.confidence_label})
          </span>
        </div>
      </div>

      {/* Grid of Measured Evidence Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        {/* Metric 1: Excursion Window */}
        <div className="p-3 bg-white rounded-lg border border-slate-200">
          <p className="text-[10px] uppercase font-bold text-slate-400">Excursion Window</p>
          <p className="text-xs font-bold text-slate-800 font-mono mt-1">
            {format(new Date(excursion.started_at_utc), 'HH:mm')} – {format(new Date(excursion.ended_at_utc), 'HH:mm')} UTC
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Duration: {excursion.duration_minutes} min (Peak: {excursion.peak_temp_c}°C)
          </p>
        </div>

        {/* Metric 2: Window Overlap */}
        <div className="p-3 bg-white rounded-lg border border-slate-200">
          <p className="text-[10px] uppercase font-bold text-slate-400">Window Overlap</p>
          <p className="text-sm font-black text-slate-800 font-mono mt-1">
            {handoff.duration_outside_safe_range_minutes.toFixed(0)} min
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Active excursion overlap duration
          </p>
        </div>

        {/* Metric 3: Thermal Exposure */}
        <div className="p-3 bg-white rounded-lg border border-slate-200">
          <p className="text-[10px] uppercase font-bold text-slate-400">Degree-Minutes Outside Safe</p>
          <p className="text-sm font-black text-rose-600 font-mono mt-1">
            {handoff.exposure_degree_minutes.toFixed(1)} °C·min
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {handoff.exposure_share_pct.toFixed(1)}% of total shipment breach
          </p>
        </div>

        {/* Metric 4: Reading Coverage & Loggers */}
        <div className="p-3 bg-white rounded-lg border border-slate-200">
          <p className="text-[10px] uppercase font-bold text-slate-400">Reading Coverage</p>
          <p className="text-sm font-black text-slate-800 font-mono mt-1">
            {handoff.reading_count} readings
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5 truncate">
            Loggers: {handoff.logger_ids.join(', ') || 'N/A'}
          </p>
        </div>
      </div>

      {/* Clock Skew & Data Quality Warnings */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-white rounded-lg border border-slate-200 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Clock-Skew Adjustment
          </span>
          <p className="text-xs text-slate-700">
            Applied offset:{' '}
            <span className="font-mono font-bold text-slate-900">
              {handoff.clock_skew_corrections.length > 0
                ? handoff.clock_skew_corrections.map((s) => `${s > 0 ? '+' : ''}${s}s`).join(', ')
                : '0s'}
            </span>
          </p>
          <p className="text-[11px] text-slate-500">
            Readings were time-shifted before interval join evaluation to prevent misattribution near custody borders.
          </p>
        </div>

        <div className="p-3 bg-white rounded-lg border border-slate-200 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Data Quality & Telemetry Warnings
          </span>
          <div className="space-y-1 text-[11px]">
            {handoff.has_missing_gaps && (
              <p className="text-amber-700 font-medium">
                ⚠️ Telemetry gap detected during custody window (transmission blackout).
              </p>
            )}
            {handoff.has_overlapping_windows && (
              <p className="text-amber-700 font-medium">
                ⚠️ Overlapping custody timestamps with adjacent leg; exposure divided proportionally.
              </p>
            )}
            {!handoff.has_missing_gaps && !handoff.has_overlapping_windows && (
              <p className="text-emerald-700 font-medium">
                ✓ Full continuous telemetry coverage with nominal quality flags.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Recommended Investigation Steps */}
      <div className="p-4 bg-white rounded-lg border border-slate-200 space-y-2 text-xs">
        <h4 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
          <span>📋 Recommended Quality Investigation Steps</span>
        </h4>
        <ul className="space-y-1.5 list-disc list-inside text-slate-700">
          {recommendedSteps.map((step, idx) => (
            <li key={idx} className="leading-relaxed">
              {step}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
