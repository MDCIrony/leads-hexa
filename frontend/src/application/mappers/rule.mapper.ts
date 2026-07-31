import { ScoringRuleModel, RoutingRuleModel, Operator, AssignmentStrategy } from '../../domain/rule.model';
import { ScoringRuleDto, RoutingRuleDto } from '../../infrastructure/dtos/rule-api.dto';

export class RuleMapper {
  static scoringToDomain(dto: ScoringRuleDto): ScoringRuleModel {
    return {
      id: dto.id,
      name: dto.name,
      field: dto.field,
      operator: dto.operator as Operator,
      value: dto.value,
      scoreDelta: dto.score_delta,
    };
  }

  static scoringToDto(model: ScoringRuleModel): ScoringRuleDto {
    return {
      id: model.id,
      name: model.name,
      field: model.field,
      operator: model.operator,
      value: model.value,
      score_delta: model.scoreDelta,
    };
  }

  static routingToDomain(dto: RoutingRuleDto): RoutingRuleModel {
    return {
      id: dto.id,
      minScore: dto.min_score,
      targetTeam: dto.target_team,
      assignmentStrategy: dto.assignment_strategy as AssignmentStrategy,
      targetAgentIds: dto.target_agent_ids || [],
    };
  }
}
