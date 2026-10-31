// ExcursionShading renders a visual summary list of excursion intervals
// (the actual red shading is done inside TemperatureChart via ReferenceArea).

import { safeFormat } from '../../utils/date';
import type { ExcursionEvent } from '../../types/api';
import { SeverityBadge } from '../common/Badge';

interface ExcursionShadingProps {
  excursions: ExcursionEvent[];
}

export function ExcursionShading({ excursions }: ExcursionShadingProps) {
  if (!excursions.length) return null;

  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
        Excursion Intervals (red shading)
      </p>
      <div className="flex flex-col gap-1">
        {excursions.map((ex) => (
          <div
            key={ex.excursion_id}
            className="flex items-center gap-2 text-xs text-slate-600"
          >
            <span className="inline-block h-2 w-4 rounded-sm bg-red-400 opacity-70" />
            <span>
              {safeFormat(ex.started_at_utc, 'HH:mm')} –{' '}
              {safeFormat(ex.ended_at_utc, 'HH:mm')} UTC
            </span>
            <span>({ex.duration_minutes.toFixed(0)} min)</span>
            <span>Peak: {ex.peak_temp_c.toFixed(1)}°C</span>
            <SeverityBadge severity={ex.severity} />
          </div>
        ))}
      </div>
    </div>
  );
}
