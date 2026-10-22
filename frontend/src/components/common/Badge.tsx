import type { ShipmentStatus, SeverityLevel, ConfidenceLevel } from '../../types/domain';

// ─── Status Badge ─────────────────────────────────────────────
const statusStyles: Record<ShipmentStatus | string, string> = {
  pending: 'bg-slate-100 text-slate-700 ring-slate-200',
  in_transit: 'bg-blue-100 text-blue-700 ring-blue-200',
  delivered: 'bg-green-100 text-green-700 ring-green-200',
  excursion: 'bg-red-100 text-red-700 ring-red-200',
};

const statusLabels: Record<string, string> = {
  pending: 'Pending',
  in_transit: 'In Transit',
  delivered: 'Delivered',
  excursion: 'Excursion',
};

export function StatusBadge({ status }: { status: string }) {
  const styles = statusStyles[status] ?? 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${styles}`}
    >
      {statusLabels[status] ?? status}
    </span>
  );
}

// ─── Excursion Badge ──────────────────────────────────────────
export function ExcursionBadge({ hasExcursion }: { hasExcursion: boolean }) {
  if (hasExcursion) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200">
        <span aria-hidden="true">⚠</span> Excursion
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200">
      OK
    </span>
  );
}

// ─── Severity Badge ───────────────────────────────────────────
const severityStyles: Record<SeverityLevel | string, string> = {
  minor: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  moderate: 'bg-orange-100 text-orange-800 ring-orange-200',
  medium: 'bg-orange-100 text-orange-800 ring-orange-200',
  severe: 'bg-red-100 text-red-800 ring-red-200',
  critical: 'bg-red-200 text-red-900 ring-red-300',
};

export function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return <span className="text-slate-400 text-xs">—</span>;
  const styles = severityStyles[severity.toLowerCase()] ?? 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset capitalize ${styles}`}
    >
      {severity}
    </span>
  );
}

// ─── Confidence Badge ─────────────────────────────────────────
const confidenceStyles: Record<ConfidenceLevel | string, string> = {
  high: 'bg-green-100 text-green-800 ring-green-200',
  medium: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
};

export function ConfidenceBadge({ label }: { label: string }) {
  const styles = confidenceStyles[label.toLowerCase()] ?? 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset capitalize ${styles}`}
    >
      {label}
    </span>
  );
}

// ─── Generic Rank Badge ───────────────────────────────────────
export function RankBadge({ rank }: { rank: number }) {
  const isTop = rank === 1;
  return (
    <span
      className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
        isTop
          ? 'bg-blue-600 text-white'
          : 'bg-slate-200 text-slate-700'
      }`}
    >
      #{rank}
    </span>
  );
}

// ─── Unified Badge Component ─────────────────────────────────
export function Badge({
  variant,
  value,
}: {
  variant: 'status' | 'severity' | 'confidence' | 'excursion';
  value: string | boolean | null;
}) {
  if (variant === 'status') return <StatusBadge status={String(value || '')} />;
  if (variant === 'severity') return <SeverityBadge severity={value ? String(value) : null} />;
  if (variant === 'confidence') return <ConfidenceBadge label={String(value || '')} />;
  if (variant === 'excursion') return <ExcursionBadge hasExcursion={Boolean(value)} />;
  return null;
}
