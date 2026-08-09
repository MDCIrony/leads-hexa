# ADR-0001 · Arquitectura hexagonal

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Backend |

## Contexto

El proyecto de partida ya tenía carpetas `domain/`, `application/` e `infrastructure/`, pero la
regla de dependencias no se cumplía: la capa de aplicación importaba directamente
`infrastructure.security` para verificar contraseñas y emitir tokens, los DTO usaban Pydantic
—un framework— dentro de `application/`, un router accedía al repositorio sin pasar por un caso de
uso, y las excepciones de dominio llevaban un `status_code` HTTP. La separación en capas existía en
el nombre de las carpetas, no en el grafo real de imports.

Nada de esto se detectaba solo. Sin una comprobación automática, la regla depende de que cada
persona que toca el código la recuerde y la revise a mano en cada cambio.

## Decisión

Arquitectura hexagonal estricta: `domain/` no depende de nada fuera de la biblioteca estándar,
`application/` sólo depende de `domain/`, e `infrastructure/` es la única capa que conoce
frameworks, drivers y protocolos. La regla se hace cumplir con un **guardián automático** —cuatro
tests en `backend/tests/architecture/test_dependency_rule.py`— que recorre el árbol de sintaxis de
cada fichero de `domain/` y `application/` y falla si aparece un import prohibido.

El guardián analiza el **árbol de sintaxis**, no importa el módulo: así detecta la violación aunque
el fichero infractor no pudiera importarse de forma aislada por faltarle una dependencia.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Confiar en la revisión de código | La regla se erosiona en cuanto hay prisa; ya se había erosionado una vez antes de escribirse el guardián |
| Verificarlo en tiempo de importación (un *import hook*) | Exige que el módulo sea importable para comprobarlo, justo lo que un módulo infractor puede no ser |
| Un *linter* de terceros para reglas de capas | Añade una dependencia y una configuración propia para resolver algo que un test de pocas líneas ya resuelve con lo que el proyecto ya tiene |

## Consecuencias

**Fácil:** el dominio y la aplicación se prueban sin base de datos ni framework web —es la base de
la suite unitaria, que corre sin ninguna variable de entorno—. Cambiar el motor de persistencia o el
framework HTTP no debería tocar una sola línea de `domain/` o `application/`. Una violación se
detecta al ejecutar la suite, no en una revisión días después.

**Difícil:** cada capacidad que el dominio necesita del mundo exterior —la hora, un identificador
nuevo— exige su propio puerto (`ClockPort`, `IdGeneratorPort`) en vez de llamar directamente a
`datetime.now()` o `uuid4()`. Es ceremonia adicional para un MVP, y es el precio de que la pureza
sea real y no una convención.

## Ver también

- [Arquitectura del sistema](../arquitectura/index.md)
