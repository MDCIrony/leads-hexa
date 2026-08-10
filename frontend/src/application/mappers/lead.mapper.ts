import type { components } from '../../infrastructure/api/schema';
import { LeadStatus, type LeadModel } from '../../domain/lead.model';

type LeadResponse = components['schemas']['LeadResponse'];
type LeadDetailResponse = components['schemas']['LeadDetailResponse'];

export function mapLead(response: LeadResponse): LeadModel {
  return {
    id: response.id,
    sourceId: response.source_id,
    firstName: response.first_name,
    lastName: response.last_name,
    email: response.email,
    company: response.company,
    budget: response.budget,
    industry: response.industry,
    customAttributes: response.custom_attributes,
    phone: response.phone,
    score: response.score,
    // The contract types status as bare `string`; LeadStatus is the only guard against a bad value.
    status: response.status as LeadStatus,
    assignedAgentId: response.assigned_agent_id,
    createdAt: response.created_at,
  };
}

export function mapLeadDetail(response: LeadDetailResponse): LeadModel {
  return {
    ...mapLead(response),
    scoreBreakdown: response.score_breakdown.map((rule) => ({
      ruleId: rule.rule_id,
      name: rule.name,
      scoreDelta: rule.score_delta,
    })),
    assignedAt: response.assigned_at,
    discardReason: response.discard_reason,
    disqualificationReason: response.disqualification_reason ?? null,
  };
}
