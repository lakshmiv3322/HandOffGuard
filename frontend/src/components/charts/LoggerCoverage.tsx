import { format } from 'date-fns';
import type { Logger, TemperatureReading } from '../../types/api';

// Palette matches TemperatureChart
const LOGGER_COLORS = [
  '#3b82f6',
  '#8b5cf6',
  '#06b6d4',
  '#f59e0b',
  '#10b981',
  '#ef4444',
  '#ec4899',
  '#64748b',
];

interface LoggerCoverageProps {
  loggers: Logger[];
  readings: TemperatureReading[];
  clockSkewCorrections: Array<{ logger_id: string; skew_seconds: number }>;
}

export function LoggerCoverage({ loggers, readings, clockSkewCorrections }: LoggerCoverageProps) {
  if (!loggers.length) return null;

  // Determine overall time range
  const allTs = readings.map((r) => new Date(r.recorded_at_utc).getTime());
  const globalMin = Math.min(...allTs);
  const globalMax = Math.max(...allTs);
  const totalSpan = globalMax - globalMin || 1;

  // Per-logger start/end
  const loggerRanges = loggers.map((logger) => {
    const loggerTs = readings
      .filter((r) => String(r.logger_id) === String(logger.logger_id))
      .map((r) => new Date(r.recorded_at_utc).getTime());
    const start = loggerTs.length ? Math.min(...loggerTs) : globalMin;
    const end = loggerTs.length ? Math.max(...loggerTs) : globalMax;
    return { logger, start, end };
  });

  const skewMap = new Map(clockSkewCorrections.map((c) => [String(c.logger_id), c.skew_seconds]));

  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
        Logger Coverage
      </p>
      <div className="space-y-2">
        {loggerRanges.map(({ logger, start, end }, idx) => {
          const leftPct = ((start - globalMin) / totalSpan) * 100;
          const widthPct = ((end - start) / totalSpan) * 100;
          const skew = skewMap.get(String(logger.logger_id));
          const color = LOGGER_COLORS[idx % LOGGER_COLORS.length];

          return (
            <div key={logger.logger_id} className="flex items-center gap-2">
              {/* Logger label */}
              <div className="w-32 shrink-0 text-xs text-slate-600 truncate" title={String(logger.logger_id)}>
                <span className="inline-block h-2 w-2 rounded-full mr-1" style={{ background: color }} />
                {String(logger.logger_id)}
              </div>

              {/* Coverage bar track */}
              <div className="relative flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                <div
                  className="absolute top-0 h-full rounded"
                  style={{
                    left: `${leftPct}%`,
                    width: `${Math.max(widthPct, 1)}%`,
                    background: color,
                    opacity: 0.75,
                  }}
                  title={`${format(new Date(start), 'HH:mm')} – ${format(new Date(end), 'HH:mm')} UTC`}
                />
              </div>

              {/* Times */}
              <div className="w-28 shrink-0 text-xs text-slate-400 text-right">
                {format(new Date(start), 'HH:mm')} – {format(new Date(end), 'HH:mm')}
              </div>

              {/* Skew indicator */}
              {skew !== undefined && skew !== 0 && (
                <div
                  className="shrink-0 text-xs font-medium text-orange-600"
                  title={`Clock skew corrected: ${skew > 0 ? '+' : ''}${skew}s`}
                >
                  Δ{skew > 0 ? '+' : ''}{skew}s
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
