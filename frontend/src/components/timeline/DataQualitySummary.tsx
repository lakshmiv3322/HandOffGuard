import type { DataQualitySummary as DataQualitySummaryType } from '../../types/api';

interface DataQualitySummaryProps {
  summary: DataQualitySummaryType;
}

export function DataQualitySummary({ summary }: DataQualitySummaryProps) {
  const totalReadings = summary?.total_readings ?? 0;
  const goodReadings = summary?.good_readings ?? 0;
  const missingGaps = summary?.missing_gaps ?? 0;
  const loggersWithSkew = summary?.loggers_with_skew ?? 0;

  const goodPct =
    totalReadings > 0
      ? Math.round((goodReadings / totalReadings) * 100)
      : 100;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Logger Data Quality & Telemetry Audit
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <div className="rounded-md bg-slate-50 p-2.5">
          <p className="text-xs text-slate-500">Total Observations</p>
          <p className="text-lg font-bold text-slate-800">{totalReadings.toLocaleString()}</p>
        </div>
        <div className="rounded-md bg-emerald-50 p-2.5">
          <p className="text-xs text-emerald-700">Valid Readings</p>
          <p className="text-lg font-bold text-emerald-700">{goodPct}%</p>
        </div>
        <div className="rounded-md bg-amber-50 p-2.5">
          <p className="text-xs text-amber-700">Transmission Gaps</p>
          <p className="text-lg font-bold text-amber-700">{missingGaps}</p>
        </div>
        <div className="rounded-md bg-blue-50 p-2.5">
          <p className="text-xs text-blue-700">Skew Adjustments</p>
          <p className="text-lg font-bold text-blue-700">{loggersWithSkew}</p>
        </div>
      </div>
    </div>
  );
}
