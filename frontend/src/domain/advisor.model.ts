/** Routing's view of an agent: the group and the load live in lead-core, not in the account (ADR-0036). */
export interface AdvisorModel {
  agentId: string;
  name: string;
  groupId: string | null;
  isActive: boolean;
  activeLoad: number;
}
