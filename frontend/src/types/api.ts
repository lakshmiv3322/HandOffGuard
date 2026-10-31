// ─── Pagination wrapper ───────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ─── Health ───────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
  database_connection_status?: string;
  db_status?: string;
  database_engine_name?: string;
  db_engine?: string;
  schema_version: string;
  detail?: string;
}

// ─── Product ──────────────────────────────────────────────────
export interface Product {
  product_id: string | number;
  name: string;
  min_temp_c: number;
  max_temp_c: number;
  allowed_excursion_minutes: number;
  thermal_mass_class: string;
}

// ─── Shipment list item ───────────────────────────────────────
export interface ShipmentListItem {
  id?: string | number;
  shipment_id: string | number;
  shipment_code: string;
  product_name: string;
  origin: string;
  destination: string;
  dispatched_at: string;
  expected_delivery_at: string;
  status: string;
  has_excursion: boolean;
  total_exposure_degree_minutes: number;
  worst_severity: string | null;
}

// ─── Shipment detail ──────────────────────────────────────────
export interface ShipmentDetail {
  id?: string | number;
  shipment_id: string | number;
  shipment_code: string;
  product: Product;
  origin: string;
  destination: string;
  dispatched_at: string;
  expected_delivery_at: string;
  status: string;
  handoff_count: number;
  logger_count: number;
  excursion_count: number;
  has_excursion: boolean;
  attribution_status: string;
}

// ─── Handoff ──────────────────────────────────────────────────
export interface Handoff {
  handoff_id: string | number;
  shipment_id: string | number;
  sequence_no: number;
  handoff_type: string;
  from_party: string;
  to_party: string;
  location: string;
  window_start_utc: string;
  window_end_utc: string;
  reported_start_utc?: string | null;
  reported_end_utc?: string | null;
  clock_skew_seconds: number;
  dwell_minutes: number;
}

// ─── Logger ───────────────────────────────────────────────────
export interface Logger {
  logger_id: string | number;
  device_type: string;
  assigned_shipment_id: string | number;
  sampling_interval_seconds: number;
  clock_skew_seconds: number;
  data_quality_flag: string;
}

// ─── Temperature reading ──────────────────────────────────────
export interface TemperatureReading {
  reading_id: string | number;
  logger_id: string | number;
  recorded_at_utc: string;
  temperature_c: number;
  humidity_pct: number | null;
  battery_pct: number | null;
  quality_flag: string;
}

// ─── Excursion event ──────────────────────────────────────────
export interface ExcursionEvent {
  excursion_id: string | number;
  shipment_id: string | number;
  started_at_utc: string;
  ended_at_utc: string;
  duration_minutes: number;
  peak_temp_c: number;
  severity: string;
  ground_truth_handoff_id?: string | number | null;
  ground_truth_cause?: string | null;
}

// ─── Attribution ──────────────────────────────────────────────
export interface AttributionHandoff {
  rank: number | null;
  is_candidate_only?: boolean;
  handoff_id: string | number;
  handoff_label: string;
  sequence_no: number;
  handoff_type: string;
  from_party: string;
  to_party: string;
  location: string;
  observed_reading_count?: number;
  supported_observation_minutes?: number;
  unsupported_gap_minutes?: number;
  exposure_degree_minutes: number | null;
  exposure_share_pct: number | null;
  allowed_excursion_time_consumed_pct: number | null;
  confidence_score: number | null;
  confidence_label: string;
  duration_outside_safe_range_minutes: number;
  peak_temp_c: number;
  reading_count: number;
  logger_ids: string[];
  clock_skew_corrections: number[];
  has_missing_gaps: boolean;
  has_overlapping_windows: boolean;
  first_threshold_crossing_utc: string | null;
  evidence_notes: string[];
  matches_naive_baseline?: boolean | null;
}

export interface NaiveBaseline {
  handoff_id: string | number | null;
  handoff_label: string;
  first_crossing_utc?: string | null;
  agrees_with_top_ranked: boolean;
  explanation: string;
}

export interface AttributionResult {
  excursion_id: string | number;
  shipment_id?: string | number;
  attribution_status?: string;
  selected_handoff_id?: string | number | null;
  excursion: ExcursionEvent;
  ranked_handoffs: AttributionHandoff[];
  top_ranked_handoff: AttributionHandoff | null;
  naive_baseline: NaiveBaseline | null;
  disclaimer: string;
  limitations: string[];
}

// ─── Custody timeline ─────────────────────────────────────────
export interface TimelineDataGap {
  start_utc: string;
  end_utc: string;
  logger_id: string;
}

export interface DataQualitySummary {
  total_readings: number;
  good_readings: number;
  flagged_readings: number;
  missing_gaps: number;
  loggers_with_skew: number;
}

export interface ClockSkewCorrection {
  logger_id: string;
  skew_seconds: number;
}

export interface UnassignedInterval {
  start_utc: string;
  end_utc: string;
}

export interface CustodyTimeline {
  shipment: ShipmentDetail;
  product: Product;
  handoffs: Handoff[];
  loggers: Logger[];
  readings: TemperatureReading[];
  excursion_intervals: ExcursionEvent[];
  suspected_handoff_id: string | number | null;
  data_quality_summary: DataQualitySummary;
  clock_skew_corrections: ClockSkewCorrection[];
  unassigned_intervals: UnassignedInterval[];
}

// ─── Prevention ───────────────────────────────────────────────
export interface PreventionSuggestion {
  shipment_id: string | number;
  handoff_id: string | number;
  risk_score: number;
  suggestion: string;
  rationale: string;
  prototype_flag: boolean;
}

export interface PreventionResult {
  shipment: ShipmentListItem;
  handoffs: Handoff[];
  riskiest_handoff: Handoff;
  suggestion: PreventionSuggestion;
  disclaimer?: string;
}

// ─── Evidence Report ──────────────────────────────────────────
export interface EvidenceReportData {
  report_title: string;
  generated_at: string;
  shipment_details: {
    shipment_id: string | number;
    shipment_code: string;
    origin: string;
    destination: string;
    dispatched_at: string;
    expected_delivery_at: string;
    status: string;
  };
  product_details: {
    name: string;
    min_temp_c: number;
    max_temp_c: number;
    allowed_excursion_minutes: number;
    thermal_mass_class: string;
  };
  excursion_details: {
    excursion_id: string | number;
    started_at_utc: string;
    ended_at_utc: string;
    duration_minutes: number;
    peak_temp_c: number;
    severity: string;
    ground_truth_cause?: string | null;
  };
  custody_timeline_summary: {
    total_handoffs: number;
    total_loggers: number;
    total_readings: number;
    missing_gaps_count: number;
  };
  ranked_handoffs: AttributionHandoff[];
  naive_baseline_comparison?: NaiveBaseline | null;
  data_quality_notes: string[];
  limitations: string[];
  disclaimer?: string;
}
