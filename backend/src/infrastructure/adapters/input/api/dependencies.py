from fastapi import Request
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from application.ports.output.rule_repository_port import RuleRepositoryPort
from application.ports.output.agent_repository_port import AgentRepositoryPort

def get_ingest_lead_use_case(request: Request) -> IngestLeadInputPort:
    return request.app.state.ingest_lead_use_case

def get_process_batch_use_case(request: Request) -> ProcessBatchInputPort:
    return request.app.state.process_batch_use_case

def get_lead_repo(request: Request) -> LeadRepositoryPort:
    return request.app.state.lead_repo

def get_rule_repo(request: Request) -> RuleRepositoryPort:
    return request.app.state.rule_repo

def get_agent_repo(request: Request) -> AgentRepositoryPort:
    return request.app.state.agent_repo
