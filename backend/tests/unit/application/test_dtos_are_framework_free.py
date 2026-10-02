import dataclasses
from uuid import uuid4

from application.dtos.commands import (
    CreateAssignmentRuleCommand,
    CreateSalesGroupCommand,
    CreateScoringRuleCommand,
    UpdateAssignmentRuleCommand,
    UpdateSalesGroupCommand,
)
from application.dtos.queries import (
    GetAssignmentRulesQuery,
    GetLeadsQuery,
    GetRulesQuery,
    GetSalesGroupsQuery,
)

_ALL_DTOS = (
    CreateScoringRuleCommand,
    CreateAssignmentRuleCommand,
    CreateSalesGroupCommand,
    UpdateAssignmentRuleCommand,
    UpdateSalesGroupCommand,
    GetLeadsQuery,
    GetRulesQuery,
    GetAssignmentRulesQuery,
    GetSalesGroupsQuery,
)


def test_every_dto_is_a_frozen_dataclass():
    for dto in _ALL_DTOS:
        assert dataclasses.is_dataclass(dto), f"{dto.__name__} is not a dataclass"
        assert dto.__dataclass_params__.frozen, f"{dto.__name__} is not frozen"


def test_queries_keep_their_pagination_defaults():
    query = GetLeadsQuery(tenant_id=uuid4())
    assert query.limit == 100
    assert query.offset == 0
