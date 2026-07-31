import { AgentModel } from '../../domain/agent.model';
import { AgentDto } from '../../infrastructure/dtos/agent-api.dto';

export class AgentMapper {
  static toDomain(dto: AgentDto): AgentModel {
    return {
      id: dto.id,
      name: dto.name,
      email: dto.email,
      team: dto.team,
      activeLeadsCount: dto.active_leads_count,
      isActive: dto.is_active,
    };
  }

  static toDto(model: AgentModel): AgentDto {
    return {
      id: model.id,
      name: model.name,
      email: model.email,
      team: model.team,
      active_leads_count: model.activeLeadsCount,
      is_active: model.isActive,
    };
  }
}
