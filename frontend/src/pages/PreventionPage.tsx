import { usePrevention } from '../hooks/usePrevention';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorState } from '../components/common/ErrorState';
import { Disclaimer } from '../components/common/Disclaimer';
import { PageHeader } from '../components/common/PageHeader';
import { format } from 'date-fns';

export function PreventionPage() {
  const { data, loading, error, refetch } = usePrevention();

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return <ErrorState message={error || 'Unable to load prevention data.'} onRetry={refetch} />;
  }

  const { shipment, handoffs, riskiest_handoff, suggestion } = data;

  const riskPct = Math.round(suggestion.risk_score * 100);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <PageHeader
        title="Proactive Risk & Prevention Advisory"
        description="Rule-based pre-dispatch risk assessment for upcoming custody segments."
      />

      {/* Prominent Mandatory Prototype Disclaimer */}
      <Disclaimer
        type="prototype"
        message="PROTOTYPE ADVISORY: Suggestion based on synthetic historical patterns. Not an operational or legal recommendation. All logic is rule-based; no autonomous ML/AI makes operational changes."
      />

      {/* Upcoming In-Transit Shipment Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
              ● Monitored Active Shipment
            </span>
            <h2 className="text-xl font-black text-slate-900 tracking-tight mt-1">
              {shipment.shipment_code}
            </h2>
            <p className="text-xs text-slate-500">
              Payload: <span className="font-semibold text-slate-800">{shipment.product_name}</span>
            </p>
          </div>
          <div className="text-left sm:text-right text-xs text-slate-500">
            <p>Dispatched: {format(new Date(shipment.dispatched_at), 'MMM dd, HH:mm')} UTC</p>
            <p>Expected Arrival: {format(new Date(shipment.expected_delivery_at), 'MMM dd, HH:mm')} UTC</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm text-slate-700">
          <span className="font-semibold">{shipment.origin}</span>
          <span className="text-slate-400">───────✈───────</span>
          <span className="font-semibold">{shipment.destination}</span>
        </div>
      </div>

      {/* Riskiest Handoff & Prevention Suggestion Card */}
      <div className="rounded-xl border-2 border-amber-300 bg-amber-50/50 p-6 shadow-md space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-amber-200 pb-3">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white font-black text-lg shadow-sm">
              !
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Highest Risk Custody Segment Identified
              </h3>
              <p className="text-xs text-amber-900">
                Segment #{riskiest_handoff.sequence_no}: {riskiest_handoff.from_party} → {riskiest_handoff.to_party}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-600">Calculated Risk Index:</span>
            <div className="flex items-center gap-2 bg-white px-3 py-1 rounded-lg border border-amber-200">
              <div className="w-16 bg-slate-200 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    riskPct > 70 ? 'bg-rose-500' : riskPct > 40 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${riskPct}%` }}
                />
              </div>
              <span className="text-xs font-bold font-mono text-slate-800">{riskPct}/100</span>
            </div>
          </div>
        </div>

        {/* Actionable Rule-Based Suggestion */}
        <div className="p-4 bg-white rounded-lg border border-amber-200 shadow-sm space-y-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-amber-800 bg-amber-100 px-2 py-0.5 rounded">
            Prototype Recommendation
          </span>
          <p className="text-sm font-bold text-slate-900">
            {suggestion.suggestion}
          </p>
          <div className="text-xs text-slate-600 pt-1">
            <span className="font-semibold text-slate-700">Underlying Rationale: </span>
            {suggestion.rationale}
          </div>
        </div>

        {/* Handoff Details */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-white/70 p-3 rounded-lg border border-amber-100">
          <div>
            <span className="text-slate-400">Location:</span>
            <p className="font-medium text-slate-800">{riskiest_handoff.location}</p>
          </div>
          <div>
            <span className="text-slate-400">Custody Type:</span>
            <p className="font-medium text-slate-800 capitalize">{riskiest_handoff.handoff_type}</p>
          </div>
          <div>
            <span className="text-slate-400">Scheduled Dwell:</span>
            <p className="font-medium text-slate-800">{riskiest_handoff.dwell_minutes} minutes</p>
          </div>
          <div>
            <span className="text-slate-400">Window:</span>
            <p className="font-medium text-slate-800">
              {format(new Date(riskiest_handoff.window_start_utc), 'HH:mm')} –{' '}
              {format(new Date(riskiest_handoff.window_end_utc), 'HH:mm')} UTC
            </p>
          </div>
        </div>
      </div>

      {/* Upcoming Handoffs Sequence */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
          Scheduled Custody Segment Pipeline ({handoffs.length} Handoffs)
        </h3>

        <div className="space-y-2">
          {handoffs.map((h) => {
            const isRiskiest = String(h.handoff_id) === String(riskiest_handoff.handoff_id);

            return (
              <div
                key={h.handoff_id}
                className={`p-3 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs transition-colors ${
                  isRiskiest
                    ? 'border-amber-300 bg-amber-50/60 font-medium'
                    : 'border-slate-200 bg-slate-50/50 text-slate-700'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                      isRiskiest ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    #{h.sequence_no}
                  </span>
                  <span className="font-semibold text-slate-900">
                    {h.from_party} → {h.to_party}
                  </span>
                  <span className="text-slate-500">({h.location})</span>
                  {isRiskiest && (
                    <span className="ml-1 text-[10px] font-bold text-amber-800 bg-amber-200 px-1.5 py-0.5 rounded">
                      Riskiest
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4 text-slate-500 text-[11px] shrink-0">
                  <span>Type: <strong className="text-slate-700 capitalize">{h.handoff_type}</strong></span>
                  <span>Dwell: <strong className="text-slate-700">{h.dwell_minutes}m</strong></span>
                  <span>
                    {format(new Date(h.window_start_utc), 'HH:mm')} – {format(new Date(h.window_end_utc), 'HH:mm')} UTC
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
