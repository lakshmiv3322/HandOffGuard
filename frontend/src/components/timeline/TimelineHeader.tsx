import { format } from 'date-fns';
import type { Product, ShipmentDetail } from '../../types/api';
import { StatusBadge } from '../common/Badge';

interface TimelineHeaderProps {
  shipment: ShipmentDetail;
  product?: Product;
  handoffCount?: number;
  loggerCount?: number;
  excursionCount?: number;
}

export function TimelineHeader({
  shipment,
  product,
  handoffCount,
  loggerCount,
  excursionCount,
}: TimelineHeaderProps) {
  const dispatched = format(new Date(shipment.dispatched_at), 'PPpp');
  const expected = format(new Date(shipment.expected_delivery_at), 'PPpp');
  const prodName = product ? product.name : shipment.product?.name;
  const hCount = handoffCount ?? shipment.handoff_count;
  const lCount = loggerCount ?? shipment.logger_count;
  const eCount = excursionCount ?? shipment.excursion_count;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      {/* Top row */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-slate-900">{shipment.shipment_code}</h2>
            <StatusBadge status={shipment.status} />
            {shipment.has_excursion && (
              <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200">
                <span aria-hidden="true">⚠</span> Excursion
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-600 font-medium">{prodName}</p>
          <p className="text-sm text-slate-500">
            {shipment.origin}
            <span aria-hidden="true" className="mx-2">→</span>
            {shipment.destination}
          </p>
        </div>

        {/* Quick stats */}
        <div className="flex gap-6">
          <Stat label="Loggers" value={lCount} />
          <Stat label="Handoffs" value={hCount} />
          <Stat label="Excursions" value={eCount} highlight={eCount > 0} />
        </div>
      </div>

      {/* Dates row */}
      <div className="mt-4 flex flex-wrap gap-6 border-t border-slate-100 pt-4 text-sm text-slate-500">
        <span>
          <span className="font-medium text-slate-700">Dispatched:</span> {dispatched}
        </span>
        <span>
          <span className="font-medium text-slate-700">Expected Delivery:</span> {expected}
        </span>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="text-center">
      <p className={`text-2xl font-bold ${highlight ? 'text-red-600' : 'text-slate-900'}`}>
        {value}
      </p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
