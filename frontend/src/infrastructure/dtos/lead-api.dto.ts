export interface LeadIngestRequestDto {
  first_name: string;
  last_name: string;
  email: string;
  company: string;
  budget: number;
  industry: string;
  custom_attributes?: Record<string, unknown>;
  phone?: string;
}

export interface LeadIngestResponseDto {
  lead_id: string;
  status: string;
  calculated_score: number;
  assigned_agent?: {
    id: string;
    name: string;
    email: string;
  };
  applied_rules_count: number;
  processed_at: string;
}

export interface LeadListItemDto {
  id: string;
  tenant_id: string;
  first_name: string;
  last_name: string;
  email: string;
  company: string;
  budget: number;
  industry: string;
  custom_attributes: Record<string, unknown>;
  phone?: string;
  score: number;
  status: string;
  assigned_agent_id?: string;
  created_at: string;
}
