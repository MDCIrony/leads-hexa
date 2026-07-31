export enum Operator {
  EQUALS = 'EQUALS',
  NOT_EQUALS = 'NOT_EQUALS',
  GREATER_THAN = 'GREATER_THAN',
  LESS_THAN = 'LESS_THAN',
  CONTAINS = 'CONTAINS',
  IN = 'IN',
}

export enum AssignmentStrategy {
  ROUND_ROBIN = 'ROUND_ROBIN',
  LOWEST_LOAD = 'LOWEST_LOAD',
  DIRECT_AGENT = 'DIRECT_AGENT',
}

export interface ScoringRuleModel {
  id: string;
  name: str;
  field: string;
  operator: Operator;
  value: unknown;
  scoreDelta: number;
}

export interface RoutingRuleModel {
  id: string;
  minScore: number;
  targetTeam: string;
  assignmentStrategy: AssignmentStrategy;
  targetAgentIds: string[];
}
