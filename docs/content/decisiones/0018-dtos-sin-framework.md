# ADR-0018 · DTOs sin framework

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend · Aplicación |

## Contexto

Los comandos y consultas de la capa de aplicación usaban Pydantic como tipo de dato. Pydantic es un
framework, y su presencia en `application/dtos/` era una de las violaciones medidas de la regla de
dependencias: el contrato interno de un caso de uso quedaba acoplado a la API de validación de un
paquete de terceros en vez de a un tipo del lenguaje.

## Decisión

Todo comando y toda consulta de `application/dtos/` es un `@dataclass(frozen=True)`. Pydantic queda
confinado a los esquemas del adaptador HTTP
(`infrastructure/adapters/input/api/schemas.py`), con mappers explícitos que traducen en ambos
sentidos entre el esquema de la API y el DTO de aplicación.

Un test dedicado recorre cada DTO y comprueba las dos propiedades por separado:
`backend/tests/unit/application/test_dtos_are_framework_free.py` afirma que cada uno es un
`dataclass` y que está `frozen`.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener Pydantic como DTO de la capa de aplicación (lo que había) | Es una de las violaciones medidas de la regla de dependencias: acopla el contrato interno de los casos de uso a la API de un framework de validación en vez de a un tipo del lenguaje |
| `@dataclass` mutable, sin `frozen=True` | Un comando o una consulta que un manejador pudiera mutar después de construirse reintroduce la clase de error que la inmutabilidad evita: un efecto de lado que cambia el DTO a medio camino entre el router y el caso de uso |

## Consecuencias

**Fácil:** los datos que cruzan la capa de aplicación no dependen de ningún framework, y eso está
verificado dos veces: el guardián general de dependencias impide importar Pydantic en cualquier
fichero de `application/`, y el test de DTOs comprueba además que cada uno es realmente un
`dataclass` inmutable, no sólo «no Pydantic». El mapeo entre el esquema HTTP y el DTO queda visible
y explícito en el borde, en vez de que un mismo objeto sirva para las dos cosas.

**Difícil:** cada campo que cruza el borde HTTP se traduce a mano entre el esquema Pydantic y el
DTO, sin generación automática. El test de DTOs enumera una lista cerrada de clases: un comando o
una consulta nuevo que no se añada a esa lista no queda cubierto por él, aunque el guardián general
de dependencias sí seguiría impidiéndole importar Pydantic.

## Ver también

- [ADR-0001 · Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [Arquitectura del sistema](../arquitectura/index.md)
