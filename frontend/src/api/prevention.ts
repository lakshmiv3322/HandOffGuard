import apiClient from './client';
import type { PreventionResult } from '../types/api';

export async function getUpcomingPrevention(): Promise<PreventionResult> {
  const { data } = await apiClient.get<PreventionResult>('/api/prevention/upcoming');
  return data;
}

export async function getShipmentPrevention(
  shipmentId: string | number,
): Promise<PreventionResult> {
  const { data } = await apiClient.get<PreventionResult>(`/api/prevention/shipments/${shipmentId}`);
  return data;
}
