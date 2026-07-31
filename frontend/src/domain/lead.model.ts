export enum LeadStatus {
  NEW = 'NEW',
  QUALIFIED = 'QUALIFIED',
  DISQUALIFIED = 'DISQUALIFIED',
  ASSIGNED = 'ASSIGNED',
  FAILED = 'FAILED',
}

export interface LeadModel {
  id: string;
  tenantId: string;
  firstName: string;
  lastName: string;
  email: string;
  company: string;
  budget: number;
  industry: string;
  customAttributes: Record<string, unknown>;
  phone?: string;
  score: number;
  status: LeadStatus;
  assignedAgentId?: string;
  createdAt: string;
}

export function formatLeadStatusLabel(status: LeadStatus): string {
  const map: Record<LeadStatus, string> = {
    [LeadStatus.NEW]: 'Nuevo',
    [LeadStatus.QUALIFIED]: 'Calificado',
    [LeadStatus.DISQUALIFIED]: 'Descalificado',
    [LeadStatus.ASSIGNED]: 'Asignado',
    [LeadStatus.FAILED]: 'Fallido',
  };
  return map[status] || status;
}

export function isLeadQualified(lead: LeadModel): boolean {
  return lead.status === LeadStatus.QUALIFIED || lead.status === LeadStatus.ASSIGNED;
}
