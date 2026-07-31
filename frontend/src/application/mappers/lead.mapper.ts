import { LeadModel, LeadStatus } from '../../domain/lead.model';
import { LeadListItemDto, LeadIngestRequestDto } from '../../infrastructure/dtos/lead-api.dto';

export class LeadMapper {
  static toDomain(dto: LeadListItemDto): LeadModel {
    return {
      id: dto.id,
      tenantId: dto.tenant_id,
      firstName: dto.first_name,
      lastName: dto.last_name,
      email: dto.email,
      company: dto.company,
      budget: dto.budget,
      industry: dto.industry,
      customAttributes: dto.custom_attributes || {},
      phone: dto.phone,
      score: dto.score,
      status: (dto.status as LeadStatus) || LeadStatus.NEW,
      assignedAgentId: dto.assigned_agent_id,
      createdAt: dto.created_at,
    };
  }

  static toIngestRequestDto(model: Partial<LeadModel>): LeadIngestRequestDto {
    return {
      first_name: model.firstName || '',
      last_name: model.lastName || '',
      email: model.email || '',
      company: model.company || '',
      budget: model.budget || 0,
      industry: model.industry || '',
      custom_attributes: model.customAttributes || {},
      phone: model.phone,
    };
  }
}
