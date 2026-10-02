import type { components } from '../../infrastructure/api/schema';
import type { AdvisorModel } from '../../domain/advisor.model';

export type AdvisorResponse = components['schemas']['AdvisorResponse'];

export function mapAdvisor(response: AdvisorResponse): AdvisorModel {
  return {
    agentId: response.agent_id,
    name: response.name,
    groupId: response.group_id,
    isActive: response.is_active,
    activeLoad: response.active_load,
  };
}
