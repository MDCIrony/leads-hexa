# Mejoras futuras

Capacidades **fuera del alcance de este MVP**, descritas con suficiente detalle para poder
retomarlas sin reconstruir el razonamiento.

Esta entrega es un MVP con una finalidad docente acotada. Lo que hay aquí no son ideas sueltas: son
funcionalidades que se discutieron, se entendieron y se decidieron **conscientemente** para después.
Escribirlas evita dos errores opuestos —colarlas en el alcance por parecer pequeñas, y perderlas por
no haberlas escrito.

## Criterio de entrada

Una capacidad llega a esta carpeta cuando cumple las tres:

1. **Aporta valor real al producto**, no es un adorno técnico.
2. **No es necesaria para que el MVP demuestre lo que tiene que demostrar.**
3. **Está bloqueada por decisiones que no son de programación** —negocio, producto o cumplimiento
   normativo—, o su tamaño justifica una entrega propia.

Lo que no cumple las tres no vive aquí: si es alcance, va a [`specs/`](../../specs/); si es un
defecto conocido, va al catálogo de [`03 — Dominio y organización`](../03-dominio-y-organizacion.md).

## Índice

| Documento | De qué trata | Por qué no entra ahora |
|---|---|---|
| [01 — Identidad del contacto](01-identidad-del-contacto.md) | Reconocer que dos entradas son la misma persona: histórico de intentos, rescate de descartados, métrica real por canal | El identificador lo elige cada organización, así que exige una pantalla de configuración propia. Y arrastra dos decisiones abiertas, una de ellas de protección de datos |
| [02 — La definición del lead por organización](02-la-definicion-del-lead-por-organizacion.md) | Que cada organización decida qué campos tiene un lead suyo y qué se exige de cada uno, en vez de heredar una definición única | Exige decidir antes qué es un lead como mínimo, qué pasa con lo ya capturado cuando la definición cambia y qué se le promete a quien envía. Y con una definición configurable el MVP demostraría **peor** lo que tiene que demostrar |

## Cómo se escribe aquí

Igual que en el resto de [`product/`](../README.md): en español, sin jerga de implementación, y sin
nombrar una clase, un fichero ni un endpoint.

Con un añadido propio de esta carpeta: **cada documento dice explícitamente qué habría que decidir
antes de construirlo**. Un documento de mejora futura que no enumera sus bloqueos no sirve para
retomarlo — sirve sólo para recordar que la idea existió.
