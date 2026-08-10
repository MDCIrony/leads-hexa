# Cómo se trabaja en el frontend

Interfaz web del enrutador de leads. React 19, TypeScript, Vite, Tailwind. Consume la API descrita en
[`docs/content/desarrollo/api-referencia.md`](../docs/content/desarrollo/api-referencia.md).

El alcance vive en [`docs/content/roadmap/frontend.md`](../docs/content/roadmap/frontend.md): qué
servicios existen, qué ve cada rol y qué tiene que hacer cada vista para considerarse terminada.

## Las cuatro capas, y la única dirección permitida

```
presentation  →  application  →  domain
                      ↓
                infrastructure  →  API
```

| Capa | Qué vive aquí | Qué NO |
|---|---|---|
| `domain/` | Modelos y tipos de negocio | Nada que sepa de HTTP, de React o del contrato del backend |
| `application/` | Servicios, hooks de caso de uso, mappers, sesión | JSX |
| `infrastructure/` | Cliente HTTP, tipos generados, almacenamiento | Reglas de negocio |
| `presentation/` | Páginas, componentes, rutas, guards | Llamadas a la API |

**Ninguna página llama a la API.** Siempre a través de su servicio en `application/services/`. Es lo
que hace que un cambio de contrato se arregle en un fichero y no en doce.

**`domain/` no importa nada de las otras tres.** Es la misma regla que el backend vigila con cuatro
tests de arquitectura, y aquí se sostiene a mano: si un modelo de dominio necesita un tipo del
contrato, es que ese tipo pertenece a `infrastructure` y hace falta un mapper.

## Tamaño y componetización

**Ningún fichero pasa de 150 líneas.** No es una métrica de estilo: un fichero que crece por encima de
eso casi siempre está haciendo dos cosas, y las dos se prueban peor juntas.

Cuando uno se acerque al límite, la salida **no** es partirlo por la mitad donde caiga. Es preguntar
qué dos responsabilidades tiene dentro y separarlas por ahí:

- Una página que carga datos, los filtra y los pinta → la carga a un hook, el pintado a un componente.
- Un formulario largo → sus campos agrupados en subcomponentes por bloque lógico.
- Un componente con muchas ramas de estado → un componente por estado, y el padre elige.

**Un componente hace una cosa.** Si su nombre necesita un «y» para describirlo, son dos.

## Reutilizar antes que crear

**Antes de escribir un componente, busca si ya existe.** Hay siete en `presentation/components/`
—`Header`, `Sidebar`, `Layout`, `DashboardTable`, `RuleBuilderForm`, `BulkUploader`,
`AgentSettings`— escritos sobre Tailwind y pensados para conectarse, no para reemplazarse.

Si uno no encaja, hay tres salidas y **sólo una es aceptable por defecto**:

1. **Adaptarlo** con props, si lo que falta es una variación → hazlo.
2. **Extraer** lo común y tener dos usos de una base → hazlo si la variación es grande.
3. **Escribir otro en paralelo** → sólo si los dos primeros no aplican, y **decláralo en la respuesta
   con el motivo**. Dos componentes que hacen casi lo mismo es cómo empieza una carpeta que nadie
   entiende en seis meses.

Lo mismo vale para los hooks y los ayudantes de test.

## Estilo

**Tailwind, en `className`, y nada más.** `index.css` es una sola línea —`@import "tailwindcss"`— y
así se queda: ni ficheros CSS por componente, ni estilos en línea, ni `clsx`, ni `cva`. Una clase
condicional se resuelve con una plantilla o con un `Record<Enum, string>` dentro del componente, como
hace `DashboardTable` con los estados del lead.

**El tema es oscuro y no tiene alternativa.** No hay modo claro y no se añade uno sobre la marcha.

| | |
|---|---|
| **Fondo y superficies** | Página `bg-slate-950` · tarjeta `bg-slate-900/40` · borde `border-slate-800` |
| **Texto** | `slate-100` títulos · `slate-200` cuerpo · `slate-400` secundario · `slate-500` apagado |
| **Acento** | `indigo`: `bg-indigo-600` en la acción principal, `text-indigo-400` en lo activo |
| **Semántica** | `emerald` bien · `rose` mal · `amber` aviso · `blue` neutro · `purple` asignado |
| **Distintivo de estado** | Siempre la misma tríada: `bg-X-500/10 text-X-400 border-X-500/20` |
| **Formas** | `rounded-lg` en controles · `rounded-xl` en tarjetas · `p-4` / `p-8` · `gap-3` |
| **Iconos** | `lucide-react`. `w-5 h-5` en cabecera, `w-4 h-4` en línea |

**Un color fuera de esta tabla es un defecto**, no una preferencia. Si un caso nuevo necesita uno, se
añade aquí primero.

### Las primitivas se usan, no se reescriben

`Button`, `Input` y `Field` viven en `presentation/components/ui/`. **Ningún formulario escribe sus
propias clases de `<input>` ni de `<button>`.** Son seis los formularios del MVP; seis juegos de
clases escritos a mano divergen a la tercera pantalla, y el día que cambie el foco o el estado
deshabilitado hay que tocarlos en seis sitios.

Si una primitiva no encaja, se le añade una variante **dentro de ella**. Escribir el control a mano
en la página es la salida que no está permitida.

### Accesibilidad, el mínimo que no se negocia

Todo campo lleva su `<label>` asociado —eso es lo que da `Field`—, todo botón sólo con icono lleva
`aria-label`, y el foco del teclado se ve. No es una fase posterior: cuesta cero escribirlo ahora y
caro añadirlo después.

## El contrato del backend no se escribe a mano

`src/infrastructure/api/schema.d.ts` se **genera** desde `/openapi.json` con `npm run gen:api` y
**nunca se edita**. Está commiteado para que el proyecto compile sin el backend levantado.

Un tipo escrito a mano que duplique una respuesta de la API es un defecto, no un atajo: es la copia
que se desincroniza. Si el contrato cambia, el proyecto tiene que **dejar de compilar** — ése es todo
el propósito.

Los modelos de `domain/` sí se escriben a mano, porque son del frontend, y los mappers traducen entre
unos y otros.

## Cinco reglas del contrato que la interfaz no puede olvidar

Están razonadas en el roadmap; aquí en corto:

| | |
|---|---|
| **Un solo sobre paginado** | `{items, total, limit, offset, has_more}` en los dieciséis listados |
| **Todo lo temporal llega de lo más nuevo a lo más viejo** | Ninguna vista reordena |
| **El login no es JSON** | `form-urlencoded`, y el correo va en el campo `username` |
| **La organización sale del token** | Nunca se envía `tenant_id` en ninguna petición |
| **La ingesta responde `202`** | El lead no existe todavía: hay que sondear el trabajo |

## Errores: se traducen una vez

Cada código HTTP se traduce a lo que ve el usuario **en un solo sitio**. Si cada página lo resuelve,
cada página lo hará distinto.

| | |
|---|---|
| `401` | Sesión caducada → al login. **Sin culpar a nadie** |
| `403` | El rol no alcanza. **No** cierra la sesión |
| `404` | «No existe». Nunca insinuar que existe en otro sitio |
| `422` | Señalar el campo: el cuerpo trae `details[].field` |
| `400` | Error de negocio: mostrar su `message`, y distinguir por `error_code` cuando importe |
| `5xx` | Genérico y con reintentar |

El sobre de error del backend es siempre `{error, error_code, message}`. **Un solo lector** lo
interpreta; ninguna página lo destripa.

**El `404` que parece un `403` es deliberado.** Un lead de otro asesor responde `404` a propósito: un
`403` confirmaría que existe. La interfaz tiene que respetarlo, no «mejorarlo».

## Estado

- **De servidor**: el hook de datos. No se copia a estado local «para tenerlo a mano».
- **De sesión**: un contexto. Es el único global que hay.
- **De formulario**: del propio formulario.
- **De interfaz** (un desplegable abierto): del componente.

**No hay gestor de estado global**, y añadir uno es una decisión de arquitectura, no un detalle de
implementación: se discute antes.

## TypeScript

- **`any` está prohibido.** Si no sabes el tipo, es `unknown` y se estrecha. Un `any` en una respuesta
  de la API anula la única red que tenemos contra un cambio de contrato.
- Sin `@ts-ignore` sin una línea al lado explicando por qué.
- Los tipos de retorno de las funciones exportadas se declaran.

## Comentarios y nombres

- **Los comentarios explican el porqué, nunca el qué.** Uno que narra la línea siguiente sobra.
- El caso que merece comentario es el contraintuitivo: por qué el `404` se trata como «no existe», por
  qué el login manda `username`, por qué no se reordena una lista que parece desordenada.
- **Código, comentarios y nombres en inglés. Los textos que ve el usuario, en español.**

## Tests

- **Junto al fichero que prueban**, no en un árbol paralelo.
- Se prueba **comportamiento, no implementación**: lo que el usuario ve y lo que se envía a la API. Un
  test que afirma sobre el estado interno de un componente se rompe cada vez que alguien lo refactoriza
  sin cambiar nada observable.
- Las respuestas simuladas salen de las fixtures **capturadas del backend real**, tipadas con los
  tipos generados. Una fixture escrita a mano es una suposición.
- **Cada bug arreglado deja un test** que falla sin el arreglo. Si no, vuelve.

## Depurar sin sufrir

Es lo que más se agradece dentro de seis meses, y lo que menos cuesta ahora:

- **Un fallo se ve donde ocurre.** Nada de `catch` que se traga un error y sigue: si no se puede
  manejar, que suba.
- **Los estados de carga y de error son explícitos en cada vista**, nunca una pantalla en blanco. Una
  pantalla vacía puede significar «cargando», «no hay nada» o «falló», y son tres cosas distintas para
  quien la mira.
- **Nada de esperas fijas.** La ingesta se sondea hasta estado terminal, con tope de intentos. Un
  `sleep` de dos segundos se queda corto el día que la máquina va cargada.
- **`console.log` no se commitea.**

## Validación antes de dar algo por hecho

```bash
npm run build      # tsc + vite: un contrato roto no compila
npm run test       # vitest, y corre SIN el backend levantado
npm run gen:api    # regenera los tipos (necesita el backend en :8001)
```

El backend se levanta desde la raíz con `docker compose up -d` y queda en `http://localhost:8001`.

**Compilar no es funcionar.** Antes de decir que una vista está terminada, recórrela en el navegador
contra el backend real. Los tests con la API simulada prueban el cableado; que la aplicación hable de
verdad con el backend sólo lo prueba el navegador.

## El backend no se toca desde aquí

Si una vista necesita algo que la API no da, **es un hallazgo que se reporta**, no un endpoint que se
añade sobre la marcha. La API está cerrada, documentada y con su propia suite detrás. Un cambio ahí
tiene su propio circuito.

## Commits

`type(scope): description` en inglés, sin `Co-authored-by`. El cuerpo sólo si aporta: la motivación en
una o dos líneas, en imperativo, sin narrar el estado anterior en pasado.
