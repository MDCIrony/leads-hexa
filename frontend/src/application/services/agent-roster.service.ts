import type { AgentModel } from '../../domain/agent.model';
import type { AdvisorModel } from '../../domain/advisor.model';
import type { PaginatedEnvelope } from '../data/use-paginated';
import * as agentsService from './agents.service';
import * as advisorsService from './advisors.service';

/** An account from identity next to its routing data from lead-core, joined by agent id. */
export interface RosterEntry {
  agent: AgentModel;
  /** null while lead-core's projection has not caught up with a just-created agent. */
  advisor: AdvisorModel | null;
}

// ponytail: one page of 1000 advisors covers an MVP organization; follow has_more if one outgrows it.
const ADVISORS_PAGE = 1000;

export async function listRoster(
  limit: number,
  offset: number,
  filters: agentsService.ListAgentsFilters = {}
): Promise<PaginatedEnvelope<RosterEntry>> {
  // The two lists sort differently, so the agents page can't be aligned with an advisors page.
  const [agents, advisors] = await Promise.all([
    agentsService.list(limit, offset, filters),
    advisorsService.list(ADVISORS_PAGE, 0),
  ]);
  const byAgentId = new Map(advisors.items.map((advisor) => [advisor.agentId, advisor]));
  return { ...agents, items: agents.items.map((agent) => ({ agent, advisor: byAgentId.get(agent.id) ?? null })) };
}

/** The agent was created; only the group assignment that followed failed. */
export class GroupNotAssignedError extends Error {
  constructor(
    readonly agent: AgentModel,
    cause: unknown
  ) {
    super(`agent ${agent.id} created without its group`, { cause });
  }
}

/**
 * Two calls since the group moved to lead-core (ADR-0036). No rollback when the second fails:
 * the account is valid without a group, and its row offers the group again.
 */
export async function createWithGroup(body: agentsService.AgentCreate, groupId: string | null): Promise<AgentModel> {
  const agent = await agentsService.create(body);
  if (groupId) {
    try {
      await advisorsService.setGroup(agent.id, groupId);
    } catch (err) {
      throw new GroupNotAssignedError(agent, err);
    }
  }
  return agent;
}
