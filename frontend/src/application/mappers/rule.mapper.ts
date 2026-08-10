import type { components } from '../../infrastructure/api/schema';
import type { AssignmentRuleModel, CriterionModel, ScoringRuleModel } from '../../domain/rule.model';
import { AssignmentStrategy, Operator } from '../../domain/rule.model';

type ScoringRuleResponse = components['schemas']['ScoringRuleResponse'];
type AssignmentRuleResponse = components['schemas']['AssignmentRuleResponse'];
type CriterionSchema = components['schemas']['CriterionSchema'];

function mapCriterion(criterion: CriterionSchema): CriterionModel {
  return { field: criterion.field, operator: criterion.operator as Operator, value: criterion.value };
}

export function mapScoringRule(response: ScoringRuleResponse): ScoringRuleModel {
  return {
    id: response.id,
    name: response.name,
    conditions: response.conditions.map(mapCriterion),
    scoreDelta: response.score_delta,
    priority: response.priority,
    isActive: response.is_active,
  };
}

export function mapAssignmentRule(response: AssignmentRuleResponse): AssignmentRuleModel {
  return {
    id: response.id,
    name: response.name,
    minScore: response.min_score,
    maxScore: response.max_score ?? null,
    targetGroupId: response.target_group_id ?? null,
    targetAgentIds: response.target_agent_ids,
    agentMatchMode: response.agent_match_mode,
    // The response types strategy as a bare string; the request-side enum already covers its values.
    strategy: (response.strategy as AssignmentStrategy | null) ?? null,
    priority: response.priority,
    isActive: response.is_active,
    rrCursor: response.rr_cursor,
    conditions: response.conditions.map(mapCriterion),
  };
}
