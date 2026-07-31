import { apiClient } from './api-client';
import { LeadIngestRequestDto, LeadIngestResponseDto, LeadListItemDto } from '../dtos/lead-api.dto';

export class LeadApiClient {
  async ingestLead(tenantId: string, payload: LeadIngestRequestDto): Promise<LeadIngestResponseDto> {
    const response = await apiClient.post<LeadIngestResponseDto>(`/tenants/${tenantId}/leads/ingest`, payload);
    return response.data;
  }

  async getLeads(tenantId: string): Promise<LeadListItemDto[]> {
    const response = await apiClient.get<LeadListItemDto[]>(`/tenants/${tenantId}/leads`);
    return response.data;
  }

  async uploadBatch(tenantId: string, file: File): Promise<{ job_id: string; total_rows: number; successful_ingestions: number }> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(`/tenants/${tenantId}/leads/batch-upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }
}
