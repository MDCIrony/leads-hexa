import abc
from typing import List, Optional
from uuid import UUID

from domain.rules.disqualification_rule import DisqualificationRule


class DisqualificationRuleRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, rule: DisqualificationRule) -> DisqualificationRule: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, rule_id: UUID, tenant_id: UUID) -> Optional[DisqualificationRule]: ...

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[DisqualificationRule]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID) -> int: ...

    @abc.abstractmethod
    def delete(self, rule_id: UUID, tenant_id: UUID) -> bool: ...
