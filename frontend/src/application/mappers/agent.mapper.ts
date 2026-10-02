import type { components } from '../../infrastructure/api/schema';
import type { AgentModel } from '../../domain/agent.model';

// ADR-0036: identity's /agents no longer carries group_id (sending it is a 422; the group lives in
// /advisors). schema.d.ts still lists it until it is regenerated from identity, so it is cut here.
export type AgentResponse = Omit<components['schemas']['AgentResponse'], 'group_id'>;

export function mapAgent(response: AgentResponse): AgentModel {
  return {
    id: response.id,
    name: response.name,
    email: response.email,
    isActive: response.is_active,
    role: response.role,
  };
}
