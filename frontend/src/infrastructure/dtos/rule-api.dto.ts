export interface ScoringRuleDto {
  id: string;
  name: string;
  field: string;
  operator: string;
  value: unknown;
  score_delta: number;
}

export interface RoutingRuleDto {
  id: string;
  min_score: number;
  target_team: string;
  assignment_strategy: string;
  target_agent_ids: string[];
}
