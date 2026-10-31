import apiClient from './client';

export interface HandoffExposureRecord {
  handoff_id: string | number;
  sequence_no: number;
  handoff_type: string;
  from_party: string;
  to_party: string;
  location: string;
  window_source?: string;
  window_start_utc: string;
  window_end_utc: string;
  window_duration_minutes: number;
  custody_duration_minutes?: number;
  reading_count: number;
  assigned_logger_count?: number;
  supported_observation_minutes?: number;
  ambiguous_minutes?: number;
  unsupported_gap_minutes?: number;
  coverage_pct?: number;
  coverage_status?: string;
  min_temp_c: number | null;
  max_temp_c: number | null;
  avg_temp_c: number | null;
  safe_min_temp_c: number;
  safe_max_temp_c: number;
  minutes_above_safe: number;
  minutes_below_safe: number;
  degree_minutes_above: number;
  degree_minutes_below: number;
  total_degree_minutes: number;
  ambiguous_reading_count: number;
  exposure_severity: 'none' | 'medium' | 'high' | 'critical' | string;
  share_pct: number;
}

export interface ShipmentExposureResponse {
  shipment_id: string | number;
  shipment_code: string;
  product_name: string;
  safe_range_c: string;
  total_shipment_degree_minutes: number;
  handoffs: HandoffExposureRecord[];
  disclaimer: string;
}

export async function getShipmentExposure(shipmentId: string | number): Promise<ShipmentExposureResponse> {
  const res = await apiClient.get<ShipmentExposureResponse>(`/api/shipments/${shipmentId}/exposure`);
  return res.data;
}
