import { describe, expect, it } from 'vitest';
import scoringRulesPage from '../../test/fixtures/scoring-rules-page.json';
import assignmentRulesPage from '../../test/fixtures/assignment-rules-page.json';
import { Operator, AssignmentStrategy } from '../../domain/rule.model';
import type { components } from '../../infrastructure/api/schema';
import { mapAssignmentRule, mapScoringRule } from './rule.mapper';

describe('mapScoringRule', () => {
  it('maps conditions[] instead of a flattened field/operator/value', () => {
    const rule = mapScoringRule(scoringRulesPage.items[0] as components['schemas']['ScoringRuleResponse']);

    expect(rule.conditions).toEqual([{ field: 'budget', operator: Operator.GREATER_THAN, value: 5000 }]);
    expect(rule.scoreDelta).toBe(25);
    expect(rule.priority).toBe(5);
  });
});

describe('mapAssignmentRule', () => {
  it('maps a real AssignmentRuleResponse, including target and strategy', () => {
    const rule = mapAssignmentRule(assignmentRulesPage.items[0] as components['schemas']['AssignmentRuleResponse']);

    expect(rule.targetAgentIds).toEqual(assignmentRulesPage.items[0].target_agent_ids);
    expect(rule.strategy).toBe(AssignmentStrategy.DIRECT_AGENT);
    expect(rule.maxScore).toBeNull();
    expect(rule.conditions).toEqual([]);
  });
});
