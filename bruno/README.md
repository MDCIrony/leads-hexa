# Lead Router · colección de Bruno

Subproyecto autónomo: la superficie HTTP completa de la plataforma, documentada endpoint a endpoint,
más seis flujos de negocio ejecutables que la recorren de punta a punta.

Se abre con [Bruno](https://usebruno.com) —`Open Collection` sobre esta carpeta— o se ejecuta desde
la línea de comandos con `bru`. Los ficheros `.bru` son texto plano y versionable: un cambio en la
API se ve en el diff.

## Poner en marcha

La plataforma tiene que estar levantada. Desde la raíz del repositorio:

```bash
docker compose up -d
curl -s http://localhost:8001/health     # {"status":"ok"} cuando ha aplicado las migraciones
```

El ejecutor por línea de comandos se instala aparte, una sola vez:

```bash
npm install -g @usebruno/cli
```

Todos los comandos de este documento se ejecutan **desde esta carpeta**. Fuera de la raíz de la
colección, `bru` sale con código 4.

```bash
bru run flows --env local -r                  # los seis flujos, en orden
bru run flows/lead-processing -r --env local  # uno solo
bru run . -r --env local --tags flow          # sólo lo ejecutable, sin la referencia
```

Códigos de salida: `0` todo pasa, `1` falló alguna aserción, `3` un sondeo entró en bucle, `4` se
invocó fuera de la raíz de la colección. Para un informe navegable, `--reporter-html informe.html
--reporter-skip-all-headers`: sin la segunda opción, el informe guarda las cookies de sesión de cada
petición.

`bru run flows --env local -r` es uno de los comandos de validación del repositorio: los seis flujos
en verde demuestran que el contrato HTTP —sesión por cookie, roles, aislamiento, ingesta asíncrona
y avisos— sigue siendo el que documenta `docs/content/desarrollo/api-referencia.md`, hablando con el
gateway como lo haría cualquier cliente.

## Cómo se autentica

Cada login guarda la cookie `leads_session` de su respuesta en la variable de su rol
(`adminSession`, `managerSession`, `agentSession`, `otherAgentSession`, `managerSessionB`), y cada
petición la manda con `auth: none` y la cabecera `Cookie: leads_session={{managerSession}}`. No hay
token en `Authorization`: la API usa sesiones opacas (ADR-0029) y el gateway descarta ese
encabezado (ADR-0032).

Bruno guarda las cookies en un tarro por dominio y lo mezcla **por encima** de la cabecera `Cookie`
de la petición, así que con el tarro activo la última sesión que entró hablaría por todos los roles.
El `script:post-response` de `collection.bru` lo vacía tras cada respuesta; `--disable-cookies` haría
lo mismo desde fuera, pero no hace falta pasarlo.

## Qué hay dentro

```
bruno.json          Nombre, entorno por defecto, exclusiones
collection.bru      La puerta de entrada: cómo se parametriza y qué invariantes explican las respuestas
environments/       local.bru — las cuatro variables de las que cuelga todo lo demás
fixtures/           El CSV mixto que usa la carga por lotes
health/ auth/ tenants/ agents/ advisors/ groups/ sources/ rules/ intake/ leads/ notifications/
                    Un request por endpoint, documentado al completo
flows/              Un flujo por diagrama de secuencia de la documentación
```

### Las carpetas de recurso

Un request por endpoint, con su bloque `docs` explicando qué hace, qué cuerpo admite, qué devuelve,
**qué escribe en la base de datos** y qué esperar después. Son para explorar y probar a mano.

No están pensadas para ejecutarse en bloque: buena parte necesita un `{{leadId}}` o un `{{recordId}}`
que sólo produce un flujo. Por eso llevan la etiqueta `reference` y los flujos la etiqueta `flow`,
que es lo que permite filtrar con `--tags`.

#### Cómo se les da lo que necesitan

Las variables que escriben los flujos —las sesiones, los identificadores— **viven en la ejecución,
no en el disco**. Eso cambia lo que hay que hacer según desde dónde se lance:

**En la aplicación de escritorio**, basta con ejecutar antes el flujo que produzca lo que la carpeta
pide; las variables quedan cargadas en la sesión y las peticiones ya responden.

**Desde la línea de comandos**, cada `bru run` es un proceso nuevo y empieza sin nada. Hay que
encadenar el flujo y la carpeta **en la misma invocación**:

```bash
bru run flows/organization-onboarding agents groups advisors sources tenants --env local -r
bru run flows/lead-processing         leads  intake                 --env local -r
bru run flows/notifications           notifications                 --env local -r
```

| Carpeta | Qué la alimenta | Qué le deja |
|---|---|---|
| `tenants`, `agents`, `groups`, `advisors`, `sources` | `flows/organization-onboarding` | `adminSession`, `managerSession`, `tenantId`, `agentId` |
| `leads`, `intake` | `flows/lead-processing` | además `leadId`, `jobId`, `recordId` |
| `notifications` | `flows/notifications` | además `agentSession` y un aviso sin leer |
| `auth` | `flows/organization-onboarding` | `managerEmail` y `managerSession` |
| `health` | nada | es autónoma |

Un `bru run . --tags reference` sobre un entorno recién levantado falla casi entero, y es lo
esperado: son peticiones de exploración, no un harness.

Y hay cinco fallos que **no** son de configuración. Encadenando `flows/lead-processing leads intake`
pasan 29 de 34 peticiones; las cinco que responden `400` son las que **mutan** una entidad que el
flujo ya llevó a su estado final:

| Petición | Por qué `400` |
|---|---|
| `leads/Assign lead`, `leads/Discard lead` | El motor ya asignó ese lead; la transición es inválida |
| `intake/Promote intake record`, `intake/Discard intake record` | El registro ya está `PROMOTED` |
| `intake/Reprocess intake job` | El trabajo ya está `COMPLETED` |

No hay nada que arreglar: son peticiones de exploración que necesitan una entidad en el estado de
partida, y el flujo las deja pasadas de punto. Para probarlas a mano, ingiere un lead nuevo y usa su
identificador.

### Los flujos

| Flujo | Qué demuestra |
|---|---|
| `identity-and-access` | Cómo se entra, qué distingue un `403` de un `401`, y por qué desactivar a alguien le corta el acceso en el acto |
| `organization-onboarding` | Que dar de alta una organización crea cinco cosas en una transacción, comprobado provocando el fallo |
| `lead-reception` | Que nada de lo que entra se pierde, ni siquiera lo que no valida |
| `lead-processing` | Viabilidad, puntuación y reparto: las tres etapas, cada una por su comportamiento distintivo |
| `notifications` | Que cada aviso llega a quien tiene que actuar, y sólo a esa persona |
| `tenant-isolation` | Por qué unas veces es `404` y otras `403` |

Cada uno es **autónomo**: asegura el administrador de plataforma, crea su propia organización y
trabaja sólo dentro de ella. Se puede correr uno solo, en cualquier orden, sin haber corrido los
demás.

## Tres reglas para que esto siga funcionando dentro de un año

**Nada depende de una base de datos limpia.** El primer paso de cada flujo genera un `runId` con la
marca temporal y sufija con él todo lo que crea. Volver a correrlo no choca con la pasada anterior.

**Nada se afirma contra un absoluto.** Un contador se compara con la línea base capturada antes de
provocar el evento, no con cero. Un elemento se busca en una lista por lo que esta ejecución creó, no
por su posición. Es lo que separa una prueba que sigue siendo cierta de una que sólo pasó la primera
vez.

**Nada espera un tiempo fijo.** El procesamiento de un lead ocurre en segundo plano; el paso
`Await lead processing` de `lead-processing` sondea hasta un estado terminal con tope de intentos, y
es el patrón que hay que copiar. Un `sleep` de dos segundos alarga cada ejecución sin motivo y, el
día que la máquina va cargada, se queda corto.

## Cómo se extiende

**Un endpoint nuevo** es un `.bru` en la carpeta de su recurso, con su `seq` en el bloque `meta`, la
etiqueta `reference`, `auth: none` con la cabecera `Cookie: leads_session={{managerSession}}` —o la
sesión del rol que toque—, y un bloque `docs` que se sostenga solo. Un script que llame a
`bru.sendRequest` manda la misma cabecera.

**Un flujo nuevo** es una carpeta bajo `flows/` con su `folder.bru` —nombre, `seq` y unos `docs` que
digan qué demuestra— y sus peticiones. El patrón a copiar es `lead-processing`: es el más completo,
encadena con `vars:post-response`, sondea un trabajo asíncrono y comprueba resultados de negocio.

### Dos cosas del formato que cuesta descubrir solo

**La cookie no se hereda de la carpeta.** Una cabecera en `folder.bru` llegaría a todas sus
peticiones, también a las que no deben llevar ninguna: el arranque de `POST /agents`, donde el
gateway exige que una credencial presente sea válida, y `Reject a request with no session`. Por eso
cada petición nombra la suya.

**El contenido de un bloque de texto va indentado.** Una línea que sea exactamente `}` sin sangrar
cierra el bloque antes de tiempo. Importa al escribir ejemplos JSON dentro de `docs`.

Y una diferencia de versiones: la aplicación de escritorio es la 4.x y el ejecutor por línea de
comandos, la 3.1. Las anotaciones `@description(...)` que la aplicación sabe escribir **rompen el
parseo del ejecutor**, así que aquí no se usan: la documentación vive en los bloques `docs`.

## Relación con el resto del repositorio

Los flujos calcan los diagramas de secuencia de `docs/content/`, y cada `folder.bru` dice cuál.
Cuando un flujo y su diagrama discrepen, uno de los dos está mal y merece mirarse.

Esta colección **no está integrada** en `docker-compose.yml`: se ejecuta con el `bru` instalado en la
máquina. `bru run flows --env local -r` figura entre los comandos de validación de `CLAUDE.md` y de
`docs/content/desarrollo/validacion.md`, junto a `scripts/verify-e2e.sh`, que sigue siendo el
harness de regresión más amplio.
