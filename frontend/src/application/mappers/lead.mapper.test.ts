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

    expect(lead.scoreBreakdown).toEqual([
      { ruleId: '49571876-6e2e-4305-8dd1-4e56da8c400e', name: 'Presupuesto alto 1786390701184', scoreDelta: 25 },
      { ruleId: 'e6f800cd-674b-4e23-9789-aa990c3e6a17', name: 'Sector tecnologico 1786390701184', scoreDelta: 15 },
    ]);
    expect(lead.assignedAt).toBe(leadDetailFixture.assigned_at);
    expect(lead.disqualificationReason).toBeNull();
  });
});
