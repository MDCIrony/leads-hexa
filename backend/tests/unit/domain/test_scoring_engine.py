import uuid
from domain.entities import Lead, ScoringRule
from domain.value_objects import Operator
from domain.services import ScoringEngine

def test_scoring_engine_evaluation():
    lead = Lead.create(
        tenant_id=uuid.uuid4(),
        first_name="Maria",
        last_name="Gomez",
        email="mgomez@techcorp.com",
        company="TechCorp Inc",
        budget=15000,
        industry="Technology",
        custom_attributes={"employee_count": 150},
    )

    rules = [
        ScoringRule.create(
            name="High Budget",
            field="budget",
            operator=Operator.GREATER_THAN,
            value=10000,
            score_delta=25,
        ),
        ScoringRule.create(
            name="Tech Industry",
            field="industry",
            operator=Operator.EQUALS,
            value="Technology",
            score_delta=20,
        ),
        ScoringRule.create(
            name="Large Company Size",
            field="custom_attributes.employee_count",
            operator=Operator.GREATER_THAN,
            value=100,
            score_delta=15,
        ),
        ScoringRule.create(
            name="Gmail domain",
            field="email",
            operator=Operator.CONTAINS,
            value="@gmail.com",
            score_delta=-10,
        ),
    ]

    engine = ScoringEngine()
    total_delta = engine.evaluate(lead, rules)

    assert total_delta == 60
    assert int(lead.score) == 60
