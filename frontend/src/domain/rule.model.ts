export enum Operator {
  EQUALS = 'EQUALS',
  NOT_EQUALS = 'NOT_EQUALS',
  GREATER_THAN = 'GREATER_THAN',
  LESS_THAN = 'LESS_THAN',
  CONTAINS = 'CONTAINS',
  IN = 'IN',
  IS_EMPTY = 'IS_EMPTY',
  IS_NOT_EMPTY = 'IS_NOT_EMPTY',
}

export enum AssignmentStrategy {
  ROUND_ROBIN = 'ROUND_ROBIN',
  LOWEST_LOAD = 'LOWEST_LOAD',
  DIRECT_AGENT = 'DIRECT_AGENT',
}

export interface CriterionModel {
  field: string;
  operator: Operator;
  value: unknown;
}

export interface ScoringRuleModel {
  id: string;
  name: string;
  conditions: CriterionModel[];
  scoreDelta: number;
  priority: number;
  isActive: boolean;
}

// Named after what the API calls it — an assignment rule, not a "routing rule".
export interface AssignmentRuleModel {
  id: string;
  name: string;
  minScore: number;
  maxScore: number | null;
  targetGroupId: string | null;
  targetAgentIds: string[];
  agentMatchMode: string;
  strategy: AssignmentStrategy | null;
  priority: number;
  isActive: boolean;
  rrCursor: number;
  conditions: CriterionModel[];
}

// The API vocabulary is not the user's: a manager reads how leads are shared
// out, not an enum name. Kept beside the enum so a new strategy fails to
// compile until it has a label.
const STRATEGY_LABEL: Record<AssignmentStrategy, string> = {
  [AssignmentStrategy.ROUND_ROBIN]: 'Por turnos',
  [AssignmentStrategy.LOWEST_LOAD]: 'Al menos cargado',
  [AssignmentStrategy.DIRECT_AGENT]: 'A los asesores elegidos',
};

export function formatAssignmentStrategyLabel(strategy: AssignmentStrategy): string {
  return STRATEGY_LABEL[strategy] ?? strategy;
}
