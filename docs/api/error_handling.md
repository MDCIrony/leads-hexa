# Manejo Centralizado de Excepciones (RFC 7807)

El sistema implementa una jerarquía de excepciones de dominio con códigos de error de negocio (`error_code`) estables, que un adaptador traduce a respuestas JSON estructuradas.

**El dominio no conoce HTTP.** Una excepción de dominio lleva un `message` y un `error_code`, nunca un `status_code`: qué número devuelve el transporte es decisión del adaptador, y el guardián de arquitectura falla si el dominio importa algo que lo delate. La tabla de traducción vive en [`exception_handlers.py`](../../backend/src/infrastructure/adapters/input/api/exception_handlers.py), y lo que no figura en ella es un `400` por defecto.

---

## 🧬 Jerarquía de Excepciones de Dominio

Definida en [`src/domain/exceptions.py`](../../backend/src/domain/exceptions.py):

```python
class DomainException(Exception):
    """Base domain exception.

    Carries a stable error_code so that adapters can map it to whatever their
    transport requires. The domain itself knows nothing about HTTP."""

    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
```

### Excepciones Definidas y Traducción HTTP

El código de estado de la columna derecha **no vive en la excepción**: lo decide `STATUS_BY_ERROR_CODE` en el adaptador.

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
| `ForbiddenException` | `FORBIDDEN` | `403 Forbidden` | Rol o tenant insuficiente para realizar la acción solicitada. |
| `DomainException` | `SOURCE_NOT_FOUND` | `404 Not Found` | El origen no existe en la organización, o la organización no tiene uno activo para ese canal. |
| `DomainException` | `SOURCE_ALREADY_EXISTS` | `400 Bad Request` | Ya hay un origen con ese nombre en la organización. |
| `DomainException` | `SOURCE_IN_USE` | `400 Bad Request` | El origen tiene leads asociados y no puede borrarse. |
| `DomainException` | `INTAKE_RECORD_NOT_FOUND` | `404 Not Found` | El registro de la bandeja no existe en la organización. |
| `DomainException` | `INVALID_INTAKE_TRANSITION` | `400 Bad Request` | Promover o descartar un registro ya `PROMOTED` o `DISCARDED`. |
| `DomainException` | `INVALID_INTAKE_STATUS` | `400 Bad Request` | El filtro `status` de la bandeja no es un estado conocido. |
| `DomainException` | `REJECTION_WITHOUT_ERRORS` | `400 Bad Request` | Rechazar un registro exige al menos un error de campo. |
| `DomainException` | `INTAKE_JOB_NOT_FOUND` | `404 Not Found` | El trabajo de ingesta no existe en la organización. |
| `DomainException` | `INVALID_JOB_TRANSITION` | `400 Bad Request` | Reprocesar un trabajo ya `COMPLETED` o `FAILED`, o una transición interna inválida sobre `IntakeJob`. |
| `DomainException` | `INVALID_JOB_STATUS` | `400 Bad Request` | El filtro `status` de la lista de trabajos no es un estado conocido. |

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
