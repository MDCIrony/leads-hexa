# Manejo Centralizado de Excepciones (RFC 7807)

El sistema implementa una jerarquía de excepciones de dominio con códigos de error de negocio (`error_code`) y códigos de estado HTTP estandarizados (`status_code`), mapeados automáticamente a respuestas JSON estructuradas por el manejador global.

---

## 🧬 Jerarquía de Excepciones de Dominio

Definida en [`src/domain/exceptions.py`](../../backend/src/domain/exceptions.py):

```python
class DomainException(Exception):
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
```

### Excepciones Definidas y Mapeo HTTP

| Excepción | `error_code` | Status Code HTTP | Descripción |
| :--- | :--- | :--- | :--- |
| `DomainException` | `DOMAIN_ERROR` | `400 Bad Request` | Clase base para errores del dominio. |
| `InvalidEmailException` | `INVALID_EMAIL` | `400 Bad Request` | Formato de correo electrónico inválido. |
| `InvalidBudgetException` | `INVALID_BUDGET` | `400 Bad Request` | Valor de presupuesto inválido (< 0). |
| `InvalidUUIDException` | `INVALID_UUID` | `400 Bad Request` | Formato de UUID v4 inválido. |
| `InvalidRuleException` | `INVALID_RULE` | `400 Bad Request` | Regla de scoring/routing o su operador es inválido. |
| `LeadRoutingException` | `ROUTING_FAILED` | `400 Bad Request` | Fallo en la asignación o enrutamiento del lead. |
| `AgentNotFoundException` | `AGENT_NOT_FOUND` | `404 Not Found` | El agente solicitado no existe en la base de datos. |
| `InvalidCredentialsException` | `INVALID_CREDENTIALS` | `401 Unauthorized` | Intento de login con credenciales incorrectas. |
| `UnauthorizedException` | `UNAUTHORIZED` | `401 Unauthorized` | Token JWT ausente, expirado, inválido o agente inactivo. |
| `ForbiddenException` | `FORBIDDEN` | `401 Unauthorized` / `403 Forbidden` | Rol o tenant insuficiente para realizar la acción solicitada. |

---

## 🌐 Manejador Global HTTP (`exception_handlers.py`)

En la capa de infraestructura ([`src/infrastructure/adapters/input/api/exception_handlers.py`](../../backend/src/infrastructure/adapters/input/api/exception_handlers.py)), un *handler* global intercepta cualquier `DomainException` no controlada y genera una respuesta JSON HTTP con la estructura estándar del sistema:

```json
{
  "error": true,
  "error_code": "INVALID_EMAIL",
  "message": "Formato de correo electrónico inválido"
}
```

---

## 📋 DTOs y Schemas con Manejo de Errores

Tanto en la capa de aplicación ([`commands.py`](../../backend/src/application/dtos/commands.py)) como en la capa API ([`schemas.py`](../../backend/src/infrastructure/adapters/input/api/schemas.py)), las respuestas que comunican parcialidades o estados de error incluyen los campos `error` y `error_code`:

- **[`LeadProcessedResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)**: Transporta los detalles de ingesta individual.
```python
class LeadProcessedResponse(BaseModel):
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    webhook_dispatched: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
```

- **[`FailedRowResponse`](../../backend/src/infrastructure/adapters/input/api/schemas.py)**: Transporta los errores por fila en cargas masivas batch.
```python
class FailedRowResponse(BaseModel):
    row_number: int
    email: str
    error: str
    error_code: Optional[str] = None
```
