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
invocó fuera de la raíz de la colección. Para un informe navegable, `--reporter-html informe.html`.

## Qué hay dentro

```
bruno.json          Nombre, entorno por defecto, exclusiones
collection.bru      La puerta de entrada: cómo se parametriza y qué invariantes explican las respuestas
environments/       local.bru — las cuatro variables de las que cuelga todo lo demás
fixtures/           El CSV mixto que usa la carga por lotes
health/ auth/ tenants/ agents/ groups/ sources/ rules/ intake/ leads/ notifications/
                    Un request por endpoint, documentado al completo
flows/              Un flujo por diagrama de secuencia de la documentación
```

### Las carpetas de recurso

Un request por endpoint, con su bloque `docs` explicando qué hace, qué cuerpo admite, qué devuelve,
**qué escribe en la base de datos** y qué esperar después. Son para explorar y probar a mano.

No están pensadas para ejecutarse en bloque: buena parte necesita un `{{leadId}}` o un `{{recordId}}`
que sólo produce un flujo. Por eso llevan la etiqueta `reference` y los flujos la etiqueta `flow`,
que es lo que permite filtrar con `--tags`.

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
etiqueta `reference`, `auth: inherit` para heredar el token de la carpeta, y un bloque `docs` que se
sostenga solo.

**Un flujo nuevo** es una carpeta bajo `flows/` con su `folder.bru` —nombre, `seq` y unos `docs` que
digan qué demuestra— y sus peticiones. El patrón a copiar es `lead-processing`: es el más completo,
encadena con `vars:post-response`, sondea un trabajo asíncrono y comprueba resultados de negocio.

### Dos cosas del formato que cuesta descubrir solo

**La herencia de autenticación necesita dos bloques.** En un `folder.bru`, `auth:bearer` por sí solo
no basta: sin `auth { mode: bearer }` delante, el modo efectivo sigue siendo `none` y todas las
peticiones de la carpeta responden `401`.

**El contenido de un bloque de texto va indentado.** Una línea que sea exactamente `}` sin sangrar
cierra el bloque antes de tiempo. Importa al escribir ejemplos JSON dentro de `docs`.

Y una diferencia de versiones: la aplicación de escritorio es la 4.x y el ejecutor por línea de
comandos, la 3.1. Las anotaciones `@description(...)` que la aplicación sabe escribir **rompen el
parseo del ejecutor**, así que aquí no se usan: la documentación vive en los bloques `docs`.

## Relación con el resto del repositorio

Los flujos calcan los diagramas de secuencia de `docs/content/`, y cada `folder.bru` dice cuál.
Cuando un flujo y su diagrama discrepen, uno de los dos está mal y merece mirarse.

Esta colección **no está integrada** en `docker-compose.yml` ni en los comandos de validación del
repositorio: se ejecuta a mano, con el `bru` instalado en la máquina. `scripts/verify-e2e.sh` sigue
siendo el harness rápido de regresión.
