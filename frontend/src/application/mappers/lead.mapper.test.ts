import { describe, expect, it } from 'vitest';
import leadsPageFixture from '../../test/fixtures/leads-page.json';
import leadDetailFixture from '../../test/fixtures/lead-detail.json';
import { LeadStatus } from '../../domain/lead.model';
import { mapLead, mapLeadDetail } from './lead.mapper';

describe('mapLead', () => {
  it('maps a real LeadResponse without the detail-only fields', () => {
    const lead = mapLead(leadsPageFixture.items[0]);

    expect(lead.status).toBe(LeadStatus.ASSIGNED);
    expect(lead.assignedAgentId).toBe(leadsPageFixture.items[0].assigned_agent_id);
    expect(lead.scoreBreakdown).toBeUndefined();
  });
});

describe('mapLeadDetail', () => {
  it('maps a real LeadDetailResponse, including the score breakdown', () => {
    const lead = mapLeadDetail(leadDetailFixture);

    expect(lead.scoreBreakdown).toEqual(leadDetailFixture.score_breakdown.map((rule) => ({
      ruleId: rule.rule_id,
      name: rule.name,
      scoreDelta: rule.score_delta,
    })));
    expect(lead.assignedAt).toBe(leadDetailFixture.assigned_at);
    expect(lead.disqualificationReason).toBeNull();
  });
});
