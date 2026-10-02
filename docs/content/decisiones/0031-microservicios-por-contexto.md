# ADR-0031 · Microservicios por contexto, una base por servicio

| | |
|---|---|
| **Estado** | Aceptada — servicios extraídos: `notifications` (F2) e `identity` (F3). El resto, en F4–F5 del [plan de desacople](../microservices/06-plan-de-desacople.md) |
| **Fecha** | 2026-10-01 |
| **Ámbito** | Arquitectura · Backend · Infraestructura |

## Contexto

El backend es un monolito modular hexagonal ([ADR-0001](0001-arquitectura-hexagonal.md)) con una única
unidad de trabajo sobre una única base. Los contextos ya se reconocen en el código, pero cualquier
caso de uso puede leer cualquier tabla en la misma transacción, y nueve cruces concretos lo hacen
(inventario en [Punto de partida](../microservices/01-punto-de-partida.md)). El objetivo es que
identidad, ingesta, decisión de leads y notificaciones cambien, se desplieguen y fallen por separado,
con el menor número de cambios que no deje deuda.

## Decisión

- **Cuatro servicios y un gateway:** `identity` (tenants, agentes, sesiones, MFA, OAuth, credenciales
  de integración), `intake` (fuentes, jobs, registros, errores, ficheros), `lead-core` (reglas,
  motores, grupos, asesores, leads, canal de producto) y `notifications` (bandeja). Viabilidad,
  scoring y asignación se quedan juntos en lead-core.
- **Una base por servicio** en el mismo PostgreSQL, cada una con su rol y sin `CONNECT` para los
  demás. `leads_db` se queda como base de lead-core.
- **Nada de consultas entre bases.** Lo que un servicio necesita de otro llega por API, evento o
  proyección local (`advisors` en lead-core, `members` en notifications).
- **Monorepo con un esqueleto idéntico por servicio** (`services/<svc>/`), con dos procesos por
  servicio (`api` y `worker`) desde la misma imagen. Sólo cambian el dominio, los casos de uso y los
  adaptadores concretos.
- **`libs/chassis`, sólo técnico:** verificación del token interno, persistencia base, outbox,
  consumidor Kafka, correlación y helper del guardián. No contiene tipos de dominio y sólo puede
  importarse desde `infrastructure`.
- **Cada servicio es un proyecto `uv` independiente** con `chassis` como dependencia por ruta.
- **`backend/` es lead-core** desde el primer día y se renombra al final.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Separar sólo procesos y compartir la base | Es un monolito distribuido: los despliegues siguen acoplados por el esquema |
| Un servicio por router o por tabla | Reproduce la organización HTTP, no el dominio, y multiplica las llamadas dentro de cada lead |
| Scoring, viabilidad y asignación por separado | Convierte en distribuida una transacción local (bloqueo de `rr_cursor`, lead y outbox) sin un problema de escala que lo pida |
| Servicios de Delivery, Reporting y Organizaciones desde el inicio | Proyecciones y sagas que todavía no pagan su coste; quedan con su señal en [Evoluciones](../microservices/07-evoluciones-y-riesgos.md) |
| Copiar el código en cada servicio sin librería común | La verificación del token, que es crítica, podría divergir entre copias |
| `uv workspace` con un entorno compartido | Los cinco servicios tienen paquetes de primer nivel `domain`, `application` e `infrastructure`; colisionarían |
| Un servidor PostgreSQL por servicio | Propiedad lógica sin coste operativo extra; mover una base a otro servidor no exige tocar código |

## Consecuencias

**Fácil:** cada servicio se entiende, se prueba y se despliega solo, y el guardián 4/4 sigue vigilando
cada hexágono. Ninguna imagen contiene código de otro servicio, así que un import cruzado no compila.
Aprender un servicio enseña la forma de los cinco.

**Difícil:** las referencias entre contextos dejan de ser FK y pasan a ser UUID externos. Las
proyecciones son eventualmente consistentes: un asesor desactivado puede recibir un lead durante la
ventana de propagación, aunque su acceso se corta en la petición siguiente. Pasa de dos procesos de
aplicación a nueve. Cambiar `chassis` obliga a reconstruir las imágenes que lo usan.

## Ver también

- [Desacople en microservicios](../microservices/index.md)
- [Servicios y datos](../microservices/02-servicios-y-datos.md)
- [ADR-0001 · Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
