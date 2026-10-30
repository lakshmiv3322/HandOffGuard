import type { AttributionHandoff } from '../../types/api';

interface HorizontalShipmentStepperProps {
  handoffs: AttributionHandoff[];
  topHandoff: AttributionHandoff | null;
  selectedHandoffId: number | string | null;
  onSelectHandoff: (handoffId: number) => void;
}

// Canonical custody stage archetypes requested
const DEFAULT_STAGES = [
  { label: 'Warehouse', icon: '🏭', typePattern: 'warehouse' },
  { label: 'Reefer Truck', icon: '🚛', typePattern: 'reefer' },
  { label: 'Dock Transfer', icon: '📦', typePattern: 'dock' },
  { label: 'Delivery Bike', icon: '🛵', typePattern: 'bike' },
  { label: 'Local Agent', icon: '🏪', typePattern: 'agent' },
  { label: 'Customer', icon: '🏥', typePattern: 'customer' },
];

export function HorizontalShipmentStepper({
  handoffs,
  topHandoff,
  selectedHandoffId,
  onSelectHandoff,
}: HorizontalShipmentStepperProps) {
  // Sort handoffs by sequence number
  const sortedHandoffs = [...handoffs].sort((a, b) => a.sequence_no - b.sequence_no);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <h2 className="text-sm font-bold text-slate-900">
            Shipment Custody Stepper
          </h2>
          <p className="text-xs text-slate-500">
            Multi-modal chain of custody with highlighted excursion contribution.
          </p>
        </div>

        {topHandoff && (
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                topHandoff.confidence_label.toLowerCase() === 'high'
                  ? 'bg-rose-50 text-rose-800 border-rose-300'
                  : 'bg-amber-50 text-amber-800 border-amber-300'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  topHandoff.confidence_label.toLowerCase() === 'high'
                    ? 'bg-rose-500 animate-pulse'
                    : 'bg-amber-500 animate-pulse'
                }`}
              />
              Most Likely Custody Leg: #{topHandoff.sequence_no} ({topHandoff.exposure_share_pct}% share)
            </span>
          </div>
        )}
      </div>

      {/* Horizontal Stepper Timeline */}
      <div className="relative py-2 overflow-x-auto">
        <div className="flex items-center min-w-[700px] justify-between relative">
          {/* Background Connecting Track */}
          <div className="absolute top-1/2 left-6 right-6 -translate-y-1/2 h-1 bg-slate-200 z-0" />

          {sortedHandoffs.map((h, idx) => {
            const isTop = topHandoff?.handoff_id === h.handoff_id;
            const isSelected = selectedHandoffId === h.handoff_id;
            const conf = h.confidence_label.toLowerCase();

            // Stage archetype mapping
            const archetype = DEFAULT_STAGES[idx % DEFAULT_STAGES.length];

            // Color scheme based on confidence: red for high, amber for medium, slate for normal
            let circleColor = 'bg-white border-slate-300 text-slate-700 hover:border-slate-400';
            let badgeColor = 'bg-slate-100 text-slate-600';

            if (isTop) {
              if (conf === 'high') {
                circleColor = 'bg-rose-600 border-rose-600 text-white shadow-md ring-4 ring-rose-100';
                badgeColor = 'bg-rose-100 text-rose-800 border border-rose-300 font-bold';
              } else {
                circleColor = 'bg-amber-500 border-amber-500 text-white shadow-md ring-4 ring-amber-100';
                badgeColor = 'bg-amber-100 text-amber-800 border border-amber-300 font-bold';
              }
            } else if (isSelected) {
              circleColor = 'bg-blue-600 border-blue-600 text-white shadow ring-4 ring-blue-100';
              badgeColor = 'bg-blue-100 text-blue-800 font-bold';
            }

            return (
              <div
                key={h.handoff_id}
                onClick={() => onSelectHandoff(Number(h.handoff_id))}
                className="relative z-10 flex flex-col items-center group cursor-pointer text-center px-2 flex-1 max-w-[160px]"
              >
                {/* Step Circle */}
                <div
                  className={`w-12 h-12 rounded-full border-2 flex items-center justify-center transition-all ${circleColor}`}
                >
                  <span className="text-lg" role="img" aria-label={h.handoff_type}>
                    {archetype.icon}
                  </span>
                </div>

                {/* Step Title */}
                <p className="mt-2 text-xs font-bold text-slate-800 group-hover:text-blue-600 transition-colors truncate w-full">
                  {archetype.label}
                </p>

                <p className="text-[10px] text-slate-500 truncate w-full">
                  Leg #{h.sequence_no}
                </p>

                {/* Exposure Share Badge */}
                <span className={`mt-1 inline-block px-1.5 py-0.5 rounded text-[10px] ${badgeColor}`}>
                  {h.exposure_share_pct.toFixed(0)}% share
                </span>

                {isTop && (
                  <span className="mt-1 text-[9px] font-black uppercase tracking-wider text-rose-700">
                    Culprit
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-[11px] text-slate-400 text-center">
        Click any stage in the custody stepper to inspect its evidence report card and diagnostics below.
      </p>
    </div>
  );
}
