export enum LeadStatus {
  NEW = 'NEW',
  QUALIFIED = 'QUALIFIED',
  DISQUALIFIED = 'DISQUALIFIED',
  UNASSIGNED = 'UNASSIGNED',
  ASSIGNED = 'ASSIGNED',
  DISCARDED = 'DISCARDED',
}

export interface AppliedRuleModel {
  ruleId: string;
  name: string;
  scoreDelta: number;
}

// LeadResponse and LeadDetailResponse share every field below `createdAt`; the
// detail-only ones stay optional so a single model fits both list and detail views.
export interface LeadModel {
  id: string;
  sourceId: string;
  firstName: string;
  lastName: string;
  email: string | null;
  company: string;
  budget: number;
  industry: string;
  customAttributes: Record<string, unknown>;
  phone: string | null;
  score: number;
  status: LeadStatus;
  assignedAgentId: string | null;
  createdAt: string;
  scoreBreakdown?: AppliedRuleModel[];
  assignedAt?: string | null;
  discardReason?: string | null;
  disqualificationReason?: string | null;
}

export function formatLeadStatusLabel(status: LeadStatus): string {
  const map: Record<LeadStatus, string> = {
    [LeadStatus.NEW]: 'Nuevo',
    [LeadStatus.QUALIFIED]: 'Calificado',
    [LeadStatus.DISQUALIFIED]: 'Descalificado',
    [LeadStatus.UNASSIGNED]: 'Sin asignar',
    [LeadStatus.ASSIGNED]: 'Asignado',
    [LeadStatus.DISCARDED]: 'Descartado',
  };
  return map[status] || status;
}

export function isLeadQualified(lead: LeadModel): boolean {
  return lead.status === LeadStatus.QUALIFIED || lead.status === LeadStatus.ASSIGNED;
}
