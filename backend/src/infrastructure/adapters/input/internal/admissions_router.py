"""POST and GET /internal/v1/admissions (contracts/openapi/lead-core-internal.v1.yaml).

Only the Compose network reaches it: the gateway answers 404 to any /internal/
from outside. Intake calls it with a service token; nobody else may."""
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from uuid import UUID

from chassis.auth import KeysUnavailable, ServiceClaims, TokenError
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from application.dtos.admissions import AdmissionCandidate, AdmissionRequest, AdmissionResult
from application.ports.input.admissions.admission_ports import AdmitLeadInputPort, LookupAdmissionsInputPort
from application.use_cases.admissions.admit_lead import AdmitLeadUseCase
from application.use_cases.admissions.lookup_admissions import LookupAdmissionsUseCase
from domain.exceptions import DomainException, UnauthorizedException
from infrastructure.adapters.input.api.dependencies import _bearer_token, get_container
from infrastructure.di.container import Container

_CALLERS = frozenset({"intake"})


def require_service_caller(request: Request, container: Container = Depends(get_container)) -> ServiceClaims:
    """Missing, invalid or someone else's token are one 401: telling them apart
    would only tell a prober which callers exist."""
    token = _bearer_token(request)
    if token is None:
        raise UnauthorizedException("Authentication required")
    try:
        return container.service_token_verifier.verify(token, _CALLERS)
    except KeysUnavailable as error:  # before TokenError, its parent: an outage is not the caller's fault
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise UnauthorizedException("Authentication required") from error


router = APIRouter(include_in_schema=False, dependencies=[Depends(require_service_caller)])


class CandidateBody(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    # Text, judged by the domain: an unreadable budget is a REJECTED, never a 422.
    budget: Optional[str] = None
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)


class AdmissionBody(BaseModel):
    tenant_id: UUID
    intake_record_id: UUID
    source_id: UUID
    candidate: CandidateBody


def get_admit_lead_use_case(container: Container = Depends(get_container)) -> AdmitLeadInputPort:
    return AdmitLeadUseCase(container.unit_of_work(), container.assignment_engine)


def get_lookup_admissions_use_case(container: Container = Depends(get_container)) -> LookupAdmissionsInputPort:
    return LookupAdmissionsUseCase(container.unit_of_work())


@router.post("")
def admit(body: AdmissionBody, use_case: AdmitLeadInputPort = Depends(get_admit_lead_use_case)) -> dict:
    # The organization is the one intake persisted on the record, not a token's: a service token has none.
    result = use_case.execute(AdmissionRequest(
        tenant_id=body.tenant_id, intake_record_id=body.intake_record_id, source_id=body.source_id,
        candidate=AdmissionCandidate(**body.candidate.model_dump()),
    ))
    return _payload_of(result)


@router.get("")
def lookup(
    intake_record_ids: List[UUID] = Query(min_length=1, max_length=200),
    use_case: LookupAdmissionsInputPort = Depends(get_lookup_admissions_use_case),
) -> dict:
    return {"items": [asdict(item) for item in use_case.execute(intake_record_ids)]}


def _payload_of(result: AdmissionResult) -> dict:
    if result.outcome == "REJECTED":
        return {"outcome": "REJECTED", "errors": [asdict(error) for error in result.errors]}
    payload = asdict(result)
    del payload["errors"]
    return payload
