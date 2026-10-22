import type { ClockSkewCorrection } from '../../types/api';

interface ClockSkewIndicatorProps {
  corrections: ClockSkewCorrection[];
}

export function ClockSkewIndicator({ corrections }: ClockSkewIndicatorProps) {
  if (!corrections || corrections.length === 0) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-800 mb-2 flex items-center gap-2">
        <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Clock-Skew Synchronization
      </h3>
      <p className="text-xs text-slate-500 mb-3">
        Logger timestamps were corrected using per-device hardware clock skew before matching handoff intervals.
      </p>
      <div className="flex flex-wrap gap-2">
        {corrections.map((c) => {
          const hasSkew = c.skew_seconds !== 0;
          return (
            <div
              key={c.logger_id}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border ${
                hasSkew
                  ? 'bg-amber-50 border-amber-200 text-amber-800'
                  : 'bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <span>Logger #{c.logger_id}:</span>
              <span className="font-bold">
                {c.skew_seconds > 0 ? `+${c.skew_seconds}s` : `${c.skew_seconds}s`}
              </span>
              {hasSkew && (
                <span className="text-[10px] uppercase tracking-wide bg-amber-200 text-amber-900 px-1 py-0.5 rounded">
                  Corrected
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
