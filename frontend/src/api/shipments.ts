import apiClient from './client';
import type {
  CustodyTimeline,
  Handoff,
  PaginatedResponse,
  ShipmentDetail,
  ShipmentListItem,
} from '../types/api';

export interface GetShipmentsParams {
  page?: number;
  page_size?: number;
  search?: string;
  has_excursion?: boolean;
  status?: string;
}

export async function getShipments(
  params: GetShipmentsParams = {},
): Promise<PaginatedResponse<ShipmentListItem>> {
  const cleanParams: Record<string, string | number | boolean> = {};
  if (params.page !== undefined) cleanParams['page'] = params.page;
  if (params.page_size !== undefined) cleanParams['page_size'] = params.page_size;
  if (params.search) cleanParams['search'] = params.search;
  if (params.has_excursion !== undefined) cleanParams['has_excursion'] = params.has_excursion;
  if (params.status) cleanParams['status'] = params.status;

  const { data } = await apiClient.get<PaginatedResponse<ShipmentListItem>>('/api/shipments', {
    params: cleanParams,
  });
  return data;
}

export async function getShipmentDetail(shipmentId: string | number): Promise<ShipmentDetail> {
  const { data } = await apiClient.get<ShipmentDetail>(`/api/shipments/${shipmentId}`);
  return data;
}

export async function getCustodyTimeline(shipmentId: string | number): Promise<CustodyTimeline> {
  const { data } = await apiClient.get<CustodyTimeline>(
    `/api/shipments/${shipmentId}/custody-timeline`,
  );
  return data;
}

export async function getShipmentHandoffs(shipmentId: string | number): Promise<Handoff[]> {
  const { data } = await apiClient.get<Handoff[]>(`/api/shipments/${shipmentId}/handoffs`);
  return data;
}
