from typing import List

from application.dtos.leads import LeadStatsResult
from domain.leads.lead import Lead
from infrastructure.adapters.input.api.leads.schemas import (
    AgentLoadResponse, AppliedRuleResponse, LeadDetailResponse, LeadResponse, LeadStatsResponse, PaginatedLeadsResponse,
)


def to_lead_response(lead: Lead) -> LeadResponse:
    return LeadResponse(
        id=str(lead.id),
        tenant_id=str(lead.tenant_id),
        source_id=str(lead.source_id),
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=str(lead.email) if lead.email else None,
        company=lead.company,
        budget=float(lead.budget),
        industry=lead.industry,
        custom_attributes=lead.custom_attributes,
        phone=lead.phone,
        score=int(lead.score),
        status=lead.status.value,
        assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
        created_at=lead.created_at.isoformat(),
        updated_at=lead.updated_at.isoformat(),
    )


def to_detail_response(lead: Lead) -> LeadDetailResponse:
    return LeadDetailResponse(
        id=str(lead.id),
        tenant_id=str(lead.tenant_id),
        source_id=str(lead.source_id),
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=str(lead.email) if lead.email else None,
        company=lead.company,
        budget=float(lead.budget),
        industry=lead.industry,
        custom_attributes=lead.custom_attributes,
        phone=lead.phone,
        score=int(lead.score),
        score_breakdown=[
            AppliedRuleResponse(rule_id=str(rule.rule_id), name=rule.name, score_delta=rule.score_delta)
            for rule in lead.score_breakdown
        ],
        status=lead.status.value,
        assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
        assigned_at=lead.assigned_at.isoformat() if lead.assigned_at else None,
        discard_reason=lead.discard_reason,
        disqualification_reason=lead.disqualification_reason,
        created_at=lead.created_at.isoformat(),
    )


def paginate(items: List[Lead], total: int, limit: int, offset: int) -> PaginatedLeadsResponse:
    responses = [to_lead_response(lead) for lead in items]
    return PaginatedLeadsResponse(
        items=responses,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(responses)) < total,
    )


def to_stats_response(result: LeadStatsResult) -> LeadStatsResponse:
    return LeadStatsResponse(
        total=result.total,
        by_status=result.by_status,
        unassigned=result.unassigned,
        load_by_agent=[
            AgentLoadResponse(agent_id=str(a.agent_id), name=a.name, active_leads=a.active_leads)
            for a in result.load_by_agent
        ],
    )
