import { AssignmentStrategy } from './rule.model';

export interface AgentModel {
  id: string;
  name: string;
  email: string;
  team: string;
  activeLeadsCount: number;
  isActive: boolean;
}

export function isAgentAvailable(agent: AgentModel): boolean {
  return agent.isActive;
}
