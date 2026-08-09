# ADR-0009 · Registrar antes de interpretar

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Aplicación |

## Contexto

Frente a una petición que no se puede interpretar hay dos estrategias razonables y opuestas:
rechazarla cuanto antes (*fail-fast*), o aceptarla, guardarla tal cual y decidir después (*tolerant
reader*). Las dos son prácticas documentadas, y no se pueden aplicar a la vez en el mismo punto,
porque una exige cortar pronto y la otra exige no cortar.

El sistema prometía por escrito que «todo payload que llega se persiste antes de intentar
interpretarlo», y el guardado se colocó dentro del servicio de ingesta. Comprobado contra el sistema
real: tres peticiones con credencial válida, cada una rota de una forma distinta —correo sin
arroba, presupuesto no numérico, campo obligatorio ausente— devolvían `422` y creaban **cero**
registros. El validador del esquema HTTP, en el borde, rechazaba antes de que el servicio —que era
quien tenía la instrucción de guardar— llegara a ejecutarse. La promesa de no perder nada estaba
escrita en el sitio equivocado.

## Decisión

Todo payload que llega a un canal de ingesta se persiste **antes** de intentar interpretarlo, en un
registro propio separado del lead que pueda resultar. La validación de formato que duplicaba, en el
borde HTTP, una comprobación que ya hace el dominio se retira: lo único que sigue cortando en el
borde es lo que el propio framework no puede evitar cortar —un campo del tipo equivocado o ausente
en el esquema declarado—. Interpretar, y decidir si el resultado es un lead válido o un rechazo con
detalle, ocurre **después** de guardar, nunca antes.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Fail-fast en el borde: validar todo el payload antes de guardar nada | Es la causa medida del defecto: lo que se rechaza en el borde no deja rastro, y el emisor rara vez reintenta porque no siempre sabe que falló |
| Guardar el payload ya interpretado o normalizado | Pierde la forma cruda, que es la que permite reinterpretar cuando cambie la configuración de la fuente en vez de tener que pedir el reenvío |
| Relajar los objetos de valor del lead para aceptar datos parcialmente inválidos | Destruye el argumento arquitectónico más defendible del dominio —que un lead nunca existe en estado incoherente— para resolver un problema que en realidad es de en qué momento se guarda, no de qué invariantes tiene el dominio |

## Consecuencias

**Fácil:** un dato que no se puede interpretar deja de perderse: queda en la bandeja de entrada con
el detalle de qué campo falló, y se puede corregir y reintentar sin pedir el reenvío. Guardar la
forma cruda, sin normalizar, es lo que hace posible reinterpretar después con una configuración
distinta.

**Difícil:** el registro de entrada introduce un estado intermedio —recibido pero no procesado— que
alguien tiene que revisar; ya no basta con mirar la tabla de leads para saber qué entró. Validar dos
veces el mismo concepto en capas distintas resultó ser peor que validar una sola vez: por eso la
duplicación en el esquema HTTP se retira en vez de mantenerse «por si acaso».

## Ver también

- [ADR-0008 · El correo del lead es opcional](0008-correo-opcional.md)
- [ADR-0010 · Recepción y procesamiento separados](0010-recepcion-y-procesamiento-separados.md)
- [Ingesta](../modulos/ingesta.md)
- [Recorrido de un lead](../arquitectura/recorrido-de-un-lead.md)
