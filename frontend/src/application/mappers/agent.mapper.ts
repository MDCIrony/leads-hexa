import type { components } from '../../infrastructure/api/identity-schema';
import type { AgentModel } from '../../domain/agent.model';

export type AgentResponse = components['schemas']['AgentResponse'];

export function mapAgent(response: AgentResponse): AgentModel {
  return {
    id: response.id,
    name: response.name,
    email: response.email,
    isActive: response.is_active,
    role: response.role,
  };
}
