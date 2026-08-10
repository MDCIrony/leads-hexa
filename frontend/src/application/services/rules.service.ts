import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';
import type { AssignmentRuleModel, ScoringRuleModel } from '../../domain/rule.model';
import { mapAssignmentRule, mapScoringRule } from '../mappers/rule.mapper';

type ScoringRuleResponse = components['schemas']['ScoringRuleResponse'];
type AssignmentRuleResponse = components['schemas']['AssignmentRuleResponse'];
export type DisqualificationRule = components['schemas']['DisqualificationRuleResponse'];

export const scoring = {
  async list(limit: number, offset: number): Promise<PaginatedEnvelope<ScoringRuleModel>> {
    const { data } = await apiClient.get<components['schemas']['PaginatedScoringRulesResponse']>(
      '/api/v1/rules/scoring',
      { params: { limit, offset } }
    );
    return { ...data, items: data.items.map(mapScoringRule) };
  },
  async create(body: components['schemas']['ScoringRuleCreate']): Promise<ScoringRuleModel> {
    const { data } = await apiClient.post<ScoringRuleResponse>('/api/v1/rules/scoring', body);
    return mapScoringRule(data);
  },
  async update(id: string, body: components['schemas']['ScoringRuleUpdate']): Promise<ScoringRuleModel> {
    const { data } = await apiClient.patch<ScoringRuleResponse>(`/api/v1/rules/scoring/${id}`, body);
    return mapScoringRule(data);
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/rules/scoring/${id}`);
  },
};

export const assignment = {
  async list(limit: number, offset: number): Promise<PaginatedEnvelope<AssignmentRuleModel>> {
    // Paginates in memory server-side; the client sends limit/offset the same as any other list.
    const { data } = await apiClient.get<components['schemas']['PaginatedAssignmentRulesResponse']>(
      '/api/v1/rules/assignment',
      { params: { limit, offset } }
    );
    return { ...data, items: data.items.map(mapAssignmentRule) };
  },
  /** Without target_group_id or target_agent_ids the API responds 400 RULE_WITHOUT_TARGET. */
  async create(body: components['schemas']['AssignmentRuleCreate']): Promise<AssignmentRuleModel> {
    const { data } = await apiClient.post<AssignmentRuleResponse>('/api/v1/rules/assignment', body);
    return mapAssignmentRule(data);
  },
  async update(id: string, body: components['schemas']['AssignmentRuleUpdate']): Promise<AssignmentRuleModel> {
    const { data } = await apiClient.patch<AssignmentRuleResponse>(`/api/v1/rules/assignment/${id}`, body);
    return mapAssignmentRule(data);
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/rules/assignment/${id}`);
  },
};

export const disqualification = {
  async list(limit: number, offset: number): Promise<PaginatedEnvelope<DisqualificationRule>> {
    const { data } = await apiClient.get<components['schemas']['PaginatedDisqualificationRulesResponse']>(
      '/api/v1/rules/disqualification',
      { params: { limit, offset } }
    );
    return data;
  },
  async create(body: components['schemas']['DisqualificationRuleCreate']): Promise<DisqualificationRule> {
    const { data } = await apiClient.post<DisqualificationRule>('/api/v1/rules/disqualification', body);
    return data;
  },
  async update(
    id: string,
    body: components['schemas']['DisqualificationRuleUpdate']
  ): Promise<DisqualificationRule> {
    const { data } = await apiClient.patch<DisqualificationRule>(`/api/v1/rules/disqualification/${id}`, body);
    return data;
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/rules/disqualification/${id}`);
  },
};
