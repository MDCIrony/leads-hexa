export interface AgentModel {
  id: string;
  name: string;
  email: string;
  groupId: string | null;
  isActive: boolean;
  role: string;
}

export function isAgentAvailable(agent: AgentModel): boolean {
  return agent.isActive;
}
