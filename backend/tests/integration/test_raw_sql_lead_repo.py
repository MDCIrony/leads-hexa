import uuid
from datetime import datetime, timedelta, timezone
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import RawSqlAgentRepository
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_sales_group_repository import (
    RawSqlSalesGroupRepository,
)
from domain.entities.agent import Agent
from domain.entities.lead import Lead
from domain.entities.lead_source import LeadSource
from domain.entities.sales_group import SalesGroup
from domain.value_objects import LeadStatus
from domain.value_objects.enums import AgentRole, LeadSourceKind


def _seed_source(connection, tenant_id: uuid.UUID) -> uuid.UUID:
    """leads.tenant_id and leads.source_id are real foreign keys (migration
    005): an invented UUID is rejected, so every test needs a persisted
    organization and source of its own."""
    connection.execute(
        "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
        (tenant_id, "Acme", f"acme-{tenant_id}"),
    )
    source = RawSqlLeadSourceRepository(connection).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def test_raw_sql_lead_repository_lifecycle(test_db):
    with test_db.get_connection() as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        lead = Lead.create(
            tenant_id=tenant_id,
            source_id=source_id,
            first_name="Maria",
            last_name="Gomez",
            email="mgomez@techcorp.com",
            company="TechCorp Inc",
            budget=15000,
            industry="Technology",
            custom_attributes={"employee_count": 150},
            lead_id=lead_id,
        )
        lead.apply_score(45)
        lead.status = LeadStatus.QUALIFIED

        repo.save(lead)
        connection.commit()

        fetched = repo.get_by_id(lead_id)
        assert fetched is not None
        assert str(fetched.id) == str(lead_id)
        assert str(fetched.email) == "mgomez@techcorp.com"
        assert float(fetched.budget) == 15000.0
        assert int(fetched.score) == 45
        assert fetched.status == LeadStatus.QUALIFIED
        assert fetched.custom_attributes == {"employee_count": 150}

        tenant_leads = repo.list_by_tenant(tenant_id)
        assert len(tenant_leads) == 1


def test_a_lead_without_an_email_round_trips_as_none(test_db):
    """str(lead.email) used to turn a missing email into the literal string
    "None" on save; this guards the fix at the persistence boundary."""
    with test_db.get_connection() as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        lead = Lead.create(
            tenant_id=tenant_id,
            source_id=source_id,
            first_name="Luis",
            last_name="Nogales",
            email=None,
            company="Acme",
            budget=500,
            industry="Retail",
            lead_id=lead_id,
        )

        repo.save(lead)
        connection.commit()

        fetched = repo.get_by_id(lead_id)
        assert fetched is not None
        assert fetched.email is None


def _lead_for_load_test(tenant_id: uuid.UUID, source_id: uuid.UUID, email: str) -> Lead:
    # QUALIFIED, not the NEW default: assign_to below requires a lead that is
    # actually assignable, and every caller of this helper assigns it.
    return Lead.create(
        tenant_id=tenant_id,
        source_id=source_id,
        first_name="Laura",
        last_name="Diaz",
        email=email,
        company="Globex",
        budget=1000,
        industry="Tech",
        status=LeadStatus.QUALIFIED,
    )


def test_active_load_by_agent_counts_only_currently_assigned_leads(test_db):
    """Derived on read: three leads land on Ana, one on Beto, and neither the
    unassigned lead nor the disqualified one (despite still carrying an
    assigned_agent_id) should count."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)
        ana, beto = uuid.uuid4(), uuid.uuid4()

        for i in range(3):
            lead = _lead_for_load_test(tenant_id, source_id, f"ana{i}@example.com")
            lead.assign_to(ana, lead.tenant_id)
            repo.save(lead)

        lead = _lead_for_load_test(tenant_id, source_id, "beto@example.com")
        lead.assign_to(beto, lead.tenant_id)
        repo.save(lead)

        unassigned = _lead_for_load_test(tenant_id, source_id, "unassigned@example.com")
        repo.save(unassigned)

        # Simulates a lead disqualified after assignment: assigned_agent_id
        # stays set while status moves away from ASSIGNED, which is exactly
        # the case active_load_by_agent must not be fooled by.
        disqualified = _lead_for_load_test(tenant_id, source_id, "disqualified@example.com")
        disqualified.assign_to(ana, disqualified.tenant_id)
        disqualified.status = LeadStatus.DISQUALIFIED
        repo.save(disqualified)

        loads = repo.active_load_by_agent(tenant_id)

        assert loads == {ana: 3, beto: 1}


_NO_DIGITS = str.maketrans("0123456789", "abcdefghij")


def _seed_lead(connection, tenant_id, source_id, **overrides) -> Lead:
    # Digits mapped out of the uuid4 hex: a raw hex email used to leak
    # digits into the haystack that a "%50%"-style search could collide
    # with by chance (~11% of the time), which is what made the search
    # tests flaky before the ILIKE escaping was added.
    defaults = dict(
        tenant_id=tenant_id,
        source_id=source_id,
        first_name="Maria",
        last_name="Gomez",
        email=f"lead-{uuid.uuid4().hex.translate(_NO_DIGITS)}@example.test",
        company="TechCorp",
        budget=1000,
        industry="Tech",
    )
    defaults.update(overrides)
    lead = Lead.create(**defaults)
    return RawSqlLeadRepository(connection).save(lead)


def test_status_filter_returns_only_matching_leads(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW)
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW)
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED)

        found = repo.list_by_tenant(tenant_id, status=LeadStatus.QUALIFIED)
        assert len(found) == 1
        assert found[0].status == LeadStatus.QUALIFIED
        assert repo.count_by_tenant(tenant_id, status=LeadStatus.QUALIFIED) == 1


def test_source_filter_returns_only_matching_leads(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_a = _seed_source(connection, tenant_id)
        source_b = RawSqlLeadSourceRepository(connection).save(
            LeadSource.create(tenant_id=tenant_id, name="Referido", kind=LeadSourceKind.MANUAL_FORM)
        ).id.value

        _seed_lead(connection, tenant_id, source_a)
        _seed_lead(connection, tenant_id, source_b)
        _seed_lead(connection, tenant_id, source_b)

        found = repo.list_by_tenant(tenant_id, source_id=source_b)
        assert len(found) == 2
        assert repo.count_by_tenant(tenant_id, source_id=source_b) == 2


def test_assigned_agent_id_filter(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)
        agent_one, agent_two = uuid.uuid4(), uuid.uuid4()

        lead_one = _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED)
        lead_one.assign_to(agent_one, lead_one.tenant_id)
        repo.save(lead_one)

        lead_two = _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED)
        lead_two.assign_to(agent_two, lead_two.tenant_id)
        repo.save(lead_two)

        found = repo.list_by_tenant(tenant_id, assigned_agent_id=agent_one)
        assert len(found) == 1
        assert repo.count_by_tenant(tenant_id, assigned_agent_id=agent_one) == 1


def test_group_id_filter_scopes_agents_to_the_tenant(test_db):
    """A group_id from another organization must not leak its agents' leads,
    even though the outer query already scopes by tenant_id."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        other_tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        group = RawSqlSalesGroupRepository(connection).save(
            SalesGroup.create(tenant_id=tenant_id, name="Sales")
        )
        agent = RawSqlAgentRepository(connection).save(
            Agent.create(
                "Ana", "ana@example.com", group.id.value, role=AgentRole.AGENT, tenant_id=tenant_id
            )
        )

        lead = _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED)
        lead.assign_to(agent.id.value, lead.tenant_id)
        repo.save(lead)

        found = repo.list_by_tenant(tenant_id, group_id=group.id.value)
        assert len(found) == 1

        _seed_source(connection, other_tenant_id)
        other_group = RawSqlSalesGroupRepository(connection).save(
            SalesGroup.create(tenant_id=other_tenant_id, name="Other Sales")
        )
        assert repo.list_by_tenant(tenant_id, group_id=other_group.id.value) == []


def test_two_filters_combine_with_and(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW, company="Acme")
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED, company="Acme")
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED, company="Globex")

        found = repo.list_by_tenant(tenant_id, status=LeadStatus.QUALIFIED, search="Acme")
        assert len(found) == 1
        assert found[0].company == "Acme"
        assert found[0].status == LeadStatus.QUALIFIED


def test_search_matches_name_email_and_company_but_not_unrelated_leads(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, first_name="Valentina", last_name="Rios")
        _seed_lead(connection, tenant_id, source_id, first_name="Pedro", last_name="Valentin")
        _seed_lead(connection, tenant_id, source_id, email="valentin@example.com")
        _seed_lead(connection, tenant_id, source_id, company="Valentino SRL")
        _seed_lead(connection, tenant_id, source_id, first_name="Nobody", last_name="Unrelated")

        found = repo.list_by_tenant(tenant_id, search="valentin")
        assert len(found) == 4
        assert repo.count_by_tenant(tenant_id, search="valentin") == 4


def test_search_with_a_literal_percent_is_not_treated_as_a_wildcard(test_db):
    """"50%" must match the literal text "50%", not "anything containing
    50" — ILIKE treats an unescaped % in the value itself as a wildcard."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, company="50% Off Corp")
        _seed_lead(connection, tenant_id, source_id, company="Regular Corp 501")

        found = repo.list_by_tenant(tenant_id, search="50%")
        assert len(found) == 1
        assert found[0].company == "50% Off Corp"


def test_search_with_a_literal_underscore_is_not_treated_as_a_wildcard(test_db):
    """"_" is ILIKE's single-character wildcard: "a_b" unescaped would also
    match "axb"."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, company="a_b Corp")
        _seed_lead(connection, tenant_id, source_id, company="axb Corp")

        found = repo.list_by_tenant(tenant_id, search="a_b")
        assert len(found) == 1
        assert found[0].company == "a_b Corp"


def test_pagination_with_a_filter_reports_the_full_total(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        for _ in range(3):
            _seed_lead(connection, tenant_id, source_id, status=LeadStatus.QUALIFIED)

        page = repo.list_by_tenant(tenant_id, status=LeadStatus.QUALIFIED, limit=1, offset=0)
        total = repo.count_by_tenant(tenant_id, status=LeadStatus.QUALIFIED)

        assert len(page) == 1
        assert total == 3


def test_count_by_status_fills_all_six_statuses_with_zero(test_db):
    """The database only returns rows for statuses that actually have leads;
    a panel needs the complete set, or ADR-0022 lies about what it returns."""
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW)
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW)
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.ASSIGNED)

        counts = repo.count_by_status(tenant_id)

        assert counts == {
            "NEW": 2,
            "QUALIFIED": 0,
            "DISQUALIFIED": 0,
            "UNASSIGNED": 0,
            "ASSIGNED": 1,
            "DISCARDED": 0,
        }


def test_count_by_status_respects_the_date_range(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        now = datetime.now(timezone.utc)
        _seed_lead(connection, tenant_id, source_id, status=LeadStatus.NEW, created_at=now)
        _seed_lead(
            connection, tenant_id, source_id, status=LeadStatus.NEW,
            created_at=now - timedelta(days=30),
        )

        counts = repo.count_by_status(tenant_id, date_from=now - timedelta(days=1))

        assert counts["NEW"] == 1


def test_active_load_by_agent_with_names_only_counts_assigned_and_orders_by_load(test_db):
    with test_db.get_connection(autocommit=True) as connection:
        repo = RawSqlLeadRepository(connection)
        tenant_id = uuid.uuid4()
        source_id = _seed_source(connection, tenant_id)

        group = RawSqlSalesGroupRepository(connection).save(
            SalesGroup.create(tenant_id=tenant_id, name="Sales")
        )
        ana = RawSqlAgentRepository(connection).save(
            Agent.create("Ana Ruiz", "ana@example.com", group.id.value, role=AgentRole.AGENT, tenant_id=tenant_id)
        )
        beto = RawSqlAgentRepository(connection).save(
            Agent.create("Beto Cruz", "beto@example.com", group.id.value, role=AgentRole.AGENT, tenant_id=tenant_id)
        )

        for i in range(2):
            lead = _lead_for_load_test(tenant_id, source_id, f"ana{i}@example.com")
            lead.assign_to(ana.id.value, lead.tenant_id)
            repo.save(lead)

        lead = _lead_for_load_test(tenant_id, source_id, "beto@example.com")
        lead.assign_to(beto.id.value, lead.tenant_id)
        repo.save(lead)

        unqualified = _lead_for_load_test(tenant_id, source_id, "unassigned@example.com")
        repo.save(unqualified)

        rows = repo.active_load_by_agent_with_names(tenant_id)

        assert rows == [(ana.id.value, "Ana Ruiz", 2), (beto.id.value, "Beto Cruz", 1)]
