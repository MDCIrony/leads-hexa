import dataclasses
from uuid import uuid4

from application.dtos.commands import (
    CreateAgentCommand,
    CreateRoutingRuleCommand,
    CreateScoringRuleCommand,
)
from application.dtos.queries import GetAgentQuery, GetAgentsQuery, GetLeadsQuery, GetRulesQuery

_ALL_DTOS = (
    CreateAgentCommand,
    CreateScoringRuleCommand,
    CreateRoutingRuleCommand,
    GetLeadsQuery,
    GetAgentsQuery,
    GetAgentQuery,
    GetRulesQuery,
)


def test_every_dto_is_a_frozen_dataclass():
    for dto in _ALL_DTOS:
        assert dataclasses.is_dataclass(dto), f"{dto.__name__} is not a dataclass"
        assert dto.__dataclass_params__.frozen, f"{dto.__name__} is not frozen"


def test_create_agent_command_keeps_its_field_names_and_defaults():
    command = CreateAgentCommand(
        name="Carlos Lopez",
        email="clopez@sales.com",
        team="Sales",
        password="s3cret",
    )
    assert command.active_leads_count == 0
    assert command.is_active is True
    assert command.role == "AGENT"
    assert command.tenant_id is None


def test_queries_keep_their_pagination_defaults():
    query = GetLeadsQuery(tenant_id=uuid4())
    assert query.limit == 100
    assert query.offset == 0
