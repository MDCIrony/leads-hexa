import { describe, it, expect } from 'vitest';
import { LeadMapper } from '../../../src/application/mappers/lead.mapper';
import { LeadListItemDto } from '../../../src/infrastructure/dtos/lead-api.dto';

describe('LeadMapper', () => {
  it('should correctly map LeadListItemDto (snake_case) to LeadModel (camelCase)', () => {
    const dto: LeadListItemDto = {
      id: 'lead-123',
      tenant_id: 'tenant-456',
      first_name: 'Maria',
      last_name: 'Gomez',
      email: 'mgomez@techcorp.com',
      company: 'TechCorp Inc',
      budget: 15000,
      industry: 'Technology',
      custom_attributes: { employee_count: 150 },
      score: 45,
      status: 'QUALIFIED',
      assigned_agent_id: 'agent-789',
      created_at: '2026-07-31T17:40:00Z',
    };

    const domainModel = LeadMapper.toDomain(dto);

    expect(domainModel.id).toBe('lead-123');
    expect(domainModel.tenantId).toBe('tenant-456');
    expect(domainModel.firstName).toBe('Maria');
    expect(domainModel.lastName).toBe('Gomez');
    expect(domainModel.score).toBe(45);
    expect(domainModel.status).toBe('QUALIFIED');
    expect(domainModel.customAttributes).toEqual({ employee_count: 150 });
  });
});
