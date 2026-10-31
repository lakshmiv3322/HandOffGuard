import { useNavigate } from 'react-router-dom';
import { safeFormat } from '../../utils/date';
import type { Handoff, ExcursionEvent } from '../../types/api';

interface HandoffCardProps {
  handoff: Handoff;
  shipmentId: string | number;
  excursions: ExcursionEvent[];
  isSuspected: boolean;
  isHighlighted: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick?: () => void;
}

export function HandoffCard({
  handoff,
  shipmentId,
  excursions,
  isSuspected,
  isHighlighted,
  onMouseEnter,
  onMouseLeave,
  onClick,
}: HandoffCardProps) {
  const navigate = useNavigate();

  // Find if any excursion overlaps with this handoff window
  const overlappingExcursion = excursions.find((ex) => {
    const exStart = new Date(ex.started_at_utc).getTime();
    const exEnd = new Date(ex.ended_at_utc).getTime();
    const hStart = new Date(handoff.window_start_utc).getTime();
    const hEnd = new Date(handoff.window_end_utc).getTime();
    return exStart < hEnd && exEnd > hStart;
  });

  const handleCardClick = () => {
    if (onClick) {
      onClick();
    } else if (overlappingExcursion) {
      navigate(
        `/shipments/${shipmentId}/excursions/${overlappingExcursion.excursion_id}`,
      );
    }
  };

  return (
    <div
      id={`handoff-${handoff.handoff_id}`}
      role="button"
      tabIndex={0}
      aria-label={`Handoff #${handoff.sequence_no}: ${handoff.from_party} to ${handoff.to_party}. Click to open telemetry drilldown.`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onFocus={onMouseEnter}
      onBlur={onMouseLeave}
      onClick={handleCardClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') handleCardClick();
      }}
      className={`
        relative rounded-lg border p-4 transition-all cursor-pointer text-left
        ${isSuspected
          ? 'border-orange-400 bg-orange-50 shadow-md ring-2 ring-orange-300'
          : isHighlighted
            ? 'border-blue-400 bg-blue-50 shadow-sm ring-1 ring-blue-300'
            : 'border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm hover:bg-slate-50'}
      `}
    >
      {/* Sequence badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold
              ${isSuspected ? 'bg-orange-500 text-white' : 'bg-slate-200 text-slate-700'}`}
          >
            {handoff.sequence_no}
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {handoff.from_party}
              <span aria-hidden="true" className="mx-1 text-slate-400">→</span>
              {handoff.to_party}
            </p>
            <p className="text-xs text-slate-500">{handoff.location}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isSuspected && (
            <span className="rounded-full bg-orange-500 px-2 py-0.5 text-xs font-bold text-white">
              Suspected
            </span>
          )}
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 capitalize">
            {handoff.handoff_type.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {/* Details */}
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>
          <span className="font-medium">Window:</span>{' '}
          {safeFormat(handoff.window_start_utc, 'HH:mm')} –{' '}
          {safeFormat(handoff.window_end_utc, 'HH:mm')} UTC
        </span>
        <span>
          <span className="font-medium">Dwell:</span>{' '}
          {handoff.dwell_minutes != null ? `${Number(handoff.dwell_minutes).toFixed(0)} min` : '—'}
        </span>
        {handoff.clock_skew_seconds !== 0 && (
          <span className="text-orange-600 font-medium">
            Clock skew: {handoff.clock_skew_seconds > 0 ? '+' : ''}
            {handoff.clock_skew_seconds}s
          </span>
        )}
      </div>

      {/* Excursion link hint */}
      {overlappingExcursion && (
        <div className="mt-2 flex items-center gap-1 text-xs font-medium text-blue-600">
          <svg aria-hidden="true" className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-11.25a.75.75 0 00-1.5 0v4.59L7.3 9.24a.75.75 0 00-1.06 1.06l3.25 3.25a.75.75 0 001.06 0l3.25-3.25a.75.75 0 10-1.06-1.06l-1.95 1.95V6.75z" clipRule="evenodd" />
          </svg>
          View attribution for this excursion
        </div>
      )}
    </div>
  );
}
