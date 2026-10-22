import apiClient from './client';
import type { AttributionResult, EvidenceReportData } from '../types/api';

export async function getAttribution(
  excursionId: string | number,
): Promise<AttributionResult> {
  const { data } = await apiClient.get<AttributionResult>(
    `/api/excursions/${excursionId}/attribution`,
  );
  return data;
}

export async function recomputeAttribution(
  excursionId: string | number,
): Promise<AttributionResult> {
  const { data } = await apiClient.post<AttributionResult>(
    `/api/excursions/${excursionId}/recompute`,
  );
  return data;
}

export async function getEvidenceReport(
  excursionId: string | number,
): Promise<EvidenceReportData> {
  const { data } = await apiClient.get<EvidenceReportData>(
    `/api/excursions/${excursionId}/evidence-report`,
  );
  return data;
}
