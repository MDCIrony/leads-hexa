"""The race the pre-check cannot see, made deterministic: the unique constraint answers it."""
import uuid

from application.dtos.admissions import AdmissionCandidate, AdmissionRequest
from application.use_cases.admissions.admit_lead import AdmitLeadUseCase
from domain.advisors.advisor import Advisor
from domain.leads.lead import Lead
from domain.rules.assignment_rule import AssignmentRule
from domain.groups.sales_group import SalesGroup
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import AgentRole, AssignmentStrategy
from domain.value_objects.tenant_id import TenantId
from infrastructure.adapters.output.persistence.advisors.raw_sql_advisor_repository import RawSqlAdvisorRepository
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import RawSqlSalesGroupRepository


def _seed_round_robin(conn, tenant_id) -> None:
    group = RawSqlSalesGroupRepository(conn).save(SalesGroup.create(
        tenant_id=tenant_id, name="Team", default_strategy=AssignmentStrategy.ROUND_ROBIN))
    advisors = RawSqlAdvisorRepository(conn)
    for name in ("Ana", "Bea"):
        advisor = Advisor(AgentId(), TenantId(tenant_id), name, AgentRole.AGENT, True, 1)
        advisors.upsert_identity(advisor)
        advisors.set_group(advisor.agent_id.value, tenant_id, group.id.value)
    RawSqlRuleRepository(conn).save_assignment_rule(tenant_id, AssignmentRule.create(
        tenant_id=tenant_id, name="All", min_score=0, target_group_id=group.id.value,
        strategy=AssignmentStrategy.ROUND_ROBIN))


def _counts(conn, tenant_id) -> tuple:
    outbox = conn.execute("SELECT COUNT(*) AS n FROM outbox_events").fetchone()["n"]
    leads = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE tenant_id = %s", (tenant_id,)).fetchone()["n"]
    cursors = [rule.rr_cursor for rule in RawSqlRuleRepository(conn).get_assignment_rules_by_tenant(tenant_id)]
    return outbox, leads, cursors


def test_the_loser_answers_with_the_winners_lead_and_leaves_no_trace(test_db, monkeypatch):
    tenant_id, record_id = uuid.uuid4(), uuid.uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        _seed_round_robin(conn, tenant_id)
        winner = RawSqlLeadRepository(conn).save(Lead.create(
            tenant_id=tenant_id, source_id=uuid.uuid4(), first_name="W", last_name="W", company="W",
            budget="10", industry="W", intake_record_id=record_id))
        before = _counts(conn, tenant_id)

    real = RawSqlLeadRepository.get_by_intake_record
    misses = iter([True])

    def missed_once(self, tenant, record):
        # The winner committed after the loser's pre-check: that read saw nothing.
        return None if next(misses, False) else real(self, tenant, record)

    monkeypatch.setattr(RawSqlLeadRepository, "get_by_intake_record", missed_once)
    candidate = AdmissionCandidate(first_name="L", last_name="L", email=None, phone=None, company="L",
                                   industry="L", budget="10", custom_attributes={})

    result = AdmitLeadUseCase(PostgresUnitOfWork(test_db)).execute(AdmissionRequest(
        tenant_id=tenant_id, intake_record_id=record_id, source_id=uuid.uuid4(), candidate=candidate))

    assert (result.outcome, result.lead_id) == ("ADMITTED", str(winner.id))
    with test_db.get_connection(autocommit=True) as conn:
        assert _counts(conn, tenant_id) == before

    # Proof the rule does rotate: a fresh record moves the cursor the loser's rollback kept still.
    AdmitLeadUseCase(PostgresUnitOfWork(test_db)).execute(AdmissionRequest(
        tenant_id=tenant_id, intake_record_id=uuid.uuid4(), source_id=uuid.uuid4(), candidate=candidate))
    with test_db.get_connection(autocommit=True) as conn:
        assert _counts(conn, tenant_id)[2] != before[2]
