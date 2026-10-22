import type { Handoff } from '../../types/api';

interface HandoffMarkersProps {
  handoffs: Handoff[];
  suspectedHandoffId?: string | number | null;
  highlightedHandoffId?: string | number | null;
  onHover?: (handoffId: string | number | null) => void;
  onClick?: (handoffId: string | number) => void;
}

export function HandoffMarkers({
  handoffs,
  suspectedHandoffId,
  highlightedHandoffId,
  onHover,
  onClick,
}: HandoffMarkersProps) {
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {handoffs.map((h) => {
        const isSuspected =
          suspectedHandoffId != null && String(h.handoff_id) === String(suspectedHandoffId);
        const isHighlighted =
          highlightedHandoffId != null && String(h.handoff_id) === String(highlightedHandoffId);
        return (
          <button
            key={h.handoff_id}
            type="button"
            aria-label={`Handoff #${h.sequence_no}: ${h.from_party} to ${h.to_party}`}
            aria-pressed={isHighlighted}
            className={`
              inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium
              transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500
              ${
                isSuspected
                  ? 'border-orange-400 bg-orange-100 text-orange-800'
                  : isHighlighted
                    ? 'border-blue-400 bg-blue-100 text-blue-800'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
              }
            `}
            onMouseEnter={() => onHover?.(h.handoff_id)}
            onMouseLeave={() => onHover?.(null)}
            onFocus={() => onHover?.(h.handoff_id)}
            onBlur={() => onHover?.(null)}
            onClick={() => onClick?.(h.handoff_id)}
          >
            {isSuspected && <span aria-hidden="true" className="text-orange-500">●</span>}
            #{h.sequence_no} {h.from_party} → {h.to_party}
          </button>
        );
      })}
    </div>
  );
}
