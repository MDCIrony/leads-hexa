import { LeadApiClient } from '../../infrastructure/api/lead-api.client';
import { LeadMapper } from '../mappers/lead.mapper';
import { LeadModel } from '../../domain/lead.model';

export class LeadService {
  constructor(private readonly client: LeadApiClient = new LeadApiClient()) {}

  async getLeads(tenantId: string): Promise<LeadModel[]> {
    const dtos = await this.client.getLeads(tenantId);
    return dtos.map(LeadMapper.toDomain);
  }

  async ingestLead(tenantId: string, leadData: Partial<LeadModel>) {
    const dto = LeadMapper.toIngestRequestDto(leadData);
    return await this.client.ingestLead(tenantId, dto);
  }
}
