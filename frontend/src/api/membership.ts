import apiClient from './client';

export interface MembershipRecord {
  reading_id: number;
  logger_id: number;
  reading_at_utc: string;
  temperature_c: number;
  battery_pct: number | null;
  shipment_id: number;
  handoff_id: number | null;
  handoff_type: string | null;
  from_party: string | null;
  to_party: string | null;
  membership_status: 'matched' | 'matched_with_skew' | 'ambiguous' | 'unmatched';
  skew_seconds: number;
  ambiguity_flag: boolean;
}

export interface MembershipResponse {
  shipment_id: number;
  shipment_code: string;
  engine: string;
  counts: {
    total: number;
    matched: number;
    matched_with_skew: number;
    ambiguous: number;
    unmatched: number;
  };
  items: MembershipRecord[];
  disclaimer: string;
}

export async function getShipmentMembership(
  shipmentId: number,
  statusFilter?: string
): Promise<MembershipResponse> {
  const params: Record<string, any> = { limit: 100 };
  if (statusFilter && statusFilter !== 'all') {
    params.status_filter = statusFilter;
  }
  const res = await apiClient.get<MembershipResponse>(`/api/shipments/${shipmentId}/membership`, {
    params,
  });
  return res.data;
}
