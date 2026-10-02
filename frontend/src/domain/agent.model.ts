export interface AgentModel {
  id: string;
  name: string;
  email: string;
  isActive: boolean;
  role: string;
}

export function isAgentAvailable(agent: AgentModel): boolean {
  return agent.isActive;
}
