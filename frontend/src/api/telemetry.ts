import apiClient from './client';

export interface DrilldownReading {
  reading_id: number;
  logger_id: number;
  device_code: string;
  reading_at_utc: string;
  adjusted_reading_at_utc: string;
  temperature_c: number;
  clock_skew_seconds: number;
  quality_flag: string;
  membership_status: 'matched' | 'matched_with_skew' | 'ambiguous' | 'unmatched';
  handoff_id: number | null;
  handoff_type: string | null;
  is_above_safe: boolean;
  is_below_safe: boolean;
}

export interface DrilldownHandoff {
  handoff_id: number;
  sequence_no: number;
  handoff_type: string;
  from_party: string;
  to_party: string;
  location: string;
  window_start_utc: string;
  window_end_utc: string;
  dwell_minutes: number;
  reading_count: number;
  exposure_degree_minutes: number;
  exposure_share_pct: number;
  attribution_confidence: 'high' | 'medium' | 'low';
  confidence_score: number;
  evidence_notes: string[];
}

export interface DrilldownGap {
  logger_id: number;
  device_code: string;
  gap_start_utc: string;
  gap_end_utc: string;
  duration_minutes: number;
}

export interface DrilldownExcursion {
  excursion_id: number;
  started_at_utc: string;
  ended_at_utc: string;
  duration_minutes: number;
  peak_temp_c: number;
  severity: string;
}

export interface TelemetryDrilldownData {
  shipment_id: number;
  shipment_code: string;
  engine: string;
  product: {
    product_id: number;
    name: string;
    min_temp_c: number;
    max_temp_c: number;
    allowed_excursion_minutes: number;
    thermal_mass_class: string;
  };
  readings: DrilldownReading[];
  handoffs: DrilldownHandoff[];
  gaps: DrilldownGap[];
  excursions: DrilldownExcursion[];
  disclaimer: string;
}

export async function getTelemetryDrilldown(shipmentId: string | number): Promise<TelemetryDrilldownData> {
  const response = await apiClient.get<TelemetryDrilldownData>(
    `/api/shipments/${shipmentId}/telemetry-drilldown`
  );
  return response.data;
}
