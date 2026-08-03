from typing import Generator
from fastapi import Request, Depends
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.output.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, GetAgentsInputPort, GetAgentInputPort
)
from application.ports.input.rule_use_case_ports import (
    CreateScoringRuleInputPort, GetScoringRulesInputPort,
    CreateRoutingRuleInputPort, GetRoutingRulesInputPort
)
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.get_leads_use_case import GetLeadsUseCase
from application.use_cases.agent_use_cases import CreateAgentUseCase, GetAgentsUseCase, GetAgentUseCase
from application.use_cases.rule_use_cases import CreateScoringRuleUseCase, GetScoringRulesUseCase, CreateRoutingRuleUseCase, GetRoutingRulesUseCase

def get_db(request: Request) -> RawSqlDatabase:
    return request.app.state.db

def get_uow(db: RawSqlDatabase = Depends(get_db)) -> Generator[UnitOfWorkPort, None, None]:
    uow = SqliteUnitOfWork(db)
    yield uow

def get_ingest_lead_use_case(request: Request, uow: UnitOfWorkPort = Depends(get_uow)) -> IngestLeadInputPort:
    return IngestLeadUseCase(uow=uow, event_publisher=getattr(request.app.state, "event_publisher", None))

def get_process_batch_use_case(request: Request, uow: UnitOfWorkPort = Depends(get_uow)) -> ProcessBatchInputPort:
    ingest_lead_use_case = IngestLeadUseCase(uow=uow, event_publisher=getattr(request.app.state, "event_publisher", None))
    return ProcessBatchUseCase(file_parser=request.app.state.file_parser, ingest_lead_use_case=ingest_lead_use_case)

def get_get_leads_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetLeadsInputPort:
    return GetLeadsUseCase(uow=uow)

def get_create_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateAgentInputPort:
    return CreateAgentUseCase(uow=uow)

def get_get_agents_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentsInputPort:
    return GetAgentsUseCase(uow=uow)

def get_get_agent_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetAgentInputPort:
    return GetAgentUseCase(uow=uow)

def get_create_scoring_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateScoringRuleInputPort:
    return CreateScoringRuleUseCase(uow=uow)

def get_get_scoring_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetScoringRulesInputPort:
    return GetScoringRulesUseCase(uow=uow)

def get_create_routing_rule_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> CreateRoutingRuleInputPort:
    return CreateRoutingRuleUseCase(uow=uow)

def get_get_routing_rules_use_case(uow: UnitOfWorkPort = Depends(get_uow)) -> GetRoutingRulesInputPort:
    return GetRoutingRulesUseCase(uow=uow)
