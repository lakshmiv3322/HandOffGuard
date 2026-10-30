import apiClient from './client';

export interface HandoffExposureRecord {
  handoff_id: number;
  sequence_no: number;
  handoff_type: string;
  from_party: string;
  to_party: string;
  location: string;
  window_start_utc: string;
  window_end_utc: string;
  window_duration_minutes: number;
  reading_count: number;
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
  exposure_severity: 'none' | 'medium' | 'high' | 'critical';
  share_pct: number;
}

export interface ShipmentExposureResponse {
  shipment_id: number;
  shipment_code: string;
  product_name: string;
  safe_range_c: string;
  total_shipment_degree_minutes: number;
  handoffs: HandoffExposureRecord[];
  disclaimer: string;
}

export async function getShipmentExposure(shipmentId: number): Promise<ShipmentExposureResponse> {
  const res = await apiClient.get<ShipmentExposureResponse>(`/api/shipments/${shipmentId}/exposure`);
  return res.data;
}
