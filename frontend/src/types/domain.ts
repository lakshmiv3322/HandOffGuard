// ─── Frontend domain types ────────────────────────────────────
// These extend/transform the raw API types for UI convenience.

import type { TemperatureReading, Logger } from './api';

/** A temperature reading enriched with a parsed Date for charting. */
export interface ChartReading {
  ts: number;            // Unix ms — used as Recharts x-axis value
  timestamp: Date;
  logger_id: string;
  temperature_c: number;
  quality_flag: string;
  humidity_pct: number | null;
  battery_pct: number | null;
  /** keyed by logger_id so ComposedChart can use dataKey per line */
  [loggerKey: string]: number | string | null | Date;
}

/** A single series for the temperature chart. */
export interface LoggerSeries {
  logger: Logger;
  readings: TemperatureReading[];
  color: string;
}

/** Filter state for the shipments list. */
export interface ShipmentFilters {
  search: string;
  excursionFilter: 'all' | 'has_excursion' | 'no_excursion';
  page: number;
}

/** Collapsible panel state keyed by handoff_id. */
export type EvidencePanelState = Record<string, boolean>;

/** Severity levels in ascending order. */
export type SeverityLevel = 'minor' | 'moderate' | 'severe' | 'critical';

/** Confidence levels. */
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/** Shipment status values. */
export type ShipmentStatus = 'pending' | 'in_transit' | 'delivered' | 'excursion';

/** Data gap indicator used in chart. */
export interface ChartGap {
  startTs: number;
  endTs: number;
}
