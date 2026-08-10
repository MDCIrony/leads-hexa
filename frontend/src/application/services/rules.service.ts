import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type ScoringRule = components['schemas']['ScoringRuleResponse'];
export type AssignmentRule = components['schemas']['AssignmentRuleResponse'];
export type DisqualificationRule = components['schemas']['DisqualificationRuleResponse'];

export const scoring = {
  async list(limit: number, offset: number): Promise<PaginatedEnvelope<ScoringRule>> {
    const { data } = await apiClient.get<components['schemas']['PaginatedScoringRulesResponse']>(
      '/api/v1/rules/scoring',
      { params: { limit, offset } }
    );
    return data;
  },
  async create(body: components['schemas']['ScoringRuleCreate']): Promise<ScoringRule> {
    const { data } = await apiClient.post<ScoringRule>('/api/v1/rules/scoring', body);
    return data;
  },
  async update(id: string, body: components['schemas']['ScoringRuleUpdate']): Promise<ScoringRule> {
    const { data } = await apiClient.patch<ScoringRule>(`/api/v1/rules/scoring/${id}`, body);
    return data;
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/rules/scoring/${id}`);
  },
};

export const assignment = {
  async list(limit: number, offset: number): Promise<PaginatedEnvelope<AssignmentRule>> {
    // Paginates in memory server-side; the client sends limit/offset the same as any other list.
    const { data } = await apiClient.get<components['schemas']['PaginatedAssignmentRulesResponse']>(
      '/api/v1/rules/assignment',
      { params: { limit, offset } }
    );
    return data;
  },
  /** Without target_group_id or target_agent_ids the API responds 400 RULE_WITHOUT_TARGET. */
  async create(body: components['schemas']['AssignmentRuleCreate']): Promise<AssignmentRule> {
    const { data } = await apiClient.post<AssignmentRule>('/api/v1/rules/assignment', body);
    return data;
  },
  async update(id: string, body: components['schemas']['AssignmentRuleUpdate']): Promise<AssignmentRule> {
    const { data } = await apiClient.patch<AssignmentRule>(`/api/v1/rules/assignment/${id}`, body);
    return data;
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
