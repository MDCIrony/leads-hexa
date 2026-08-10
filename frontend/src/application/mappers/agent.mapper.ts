import type { components } from '../../infrastructure/api/schema';
import type { AgentModel } from '../../domain/agent.model';

type AgentResponse = components['schemas']['AgentResponse'];

export function mapAgent(response: AgentResponse): AgentModel {
  return {
    id: response.id,
    name: response.name,
    email: response.email,
    groupId: response.group_id ?? null,
    isActive: response.is_active,
    role: response.role,
  };
}
