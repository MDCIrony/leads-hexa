# F2c — Reglas componibles: diseño

**Estado:** propuesto. Sucede a F2b.

**Objetivo en una frase:** que ningún criterio comercial quede escrito en el código.

**Documento maestro:** [spec del MVP](2026-08-07-lead-router-mvp-design.md). Este desarrolla §7.0 y
la parte de §6.9 y §6.10 relativa a condiciones. La justificación de negocio está en
[`docs/product/02`](../product/02-el-modelo-de-decision.md) y el criterio que separa dominio de
organización en [`docs/product/03`](../product/03-dominio-y-organizacion.md).

---

## 1. El problema

La puntuación es hoy la **única** herramienta para tres decisiones de naturaleza distinta:

| Decisión | Naturaleza | Herramienta disponible hoy |
|---|---|---|
| ¿Se puede trabajar? | **Binaria** | Puntuación |
| ¿Cuánto vale? | **Continua** | Puntuación |
| ¿Quién lo atiende? | **Categórica** | Puntuación |

Forzar lo binario y lo categórico dentro de una escala continua obliga al gestor a trucos que se
rompen solos:

| Lo que quiere | El truco al que se ve forzado | Por qué falla |
|---|---|---|
| «Sin contacto, descartar siempre» | Restar 9999 puntos | Es una escala continua expresando un sí/no. Otra regla que sume puede rescatarlo por accidente |
| «Los de este canal, al equipo A» | Sumar 1000 y reservar un tramo alto | Dos canales necesitan tramos disjuntos, y cualquier regla de calidad desplaza el lead fuera del suyo |

**Un número enorme en una regla es siempre la señal de que al modelo le falta una etapa.**

A eso se suma un cuarto defecto, de otra clase: el corte de puntuación que decide si un lead entra al
reparto está escrito en el código y nadie puede verlo. Una regla de reparto para leads mediocres no
se dispara nunca, sin ningún mensaje de error.

## 2. Alcance

1. **`Criterion`** — extraer la unidad de condición como value object compartido
2. **Condiciones múltiples por regla**, con semántica Y
3. **Operadores `IS_EMPTY` / `IS_NOT_EMPTY`**
4. **`DisqualificationRule`** — la etapa de viabilidad (§7.0 del maestro)
5. **Condiciones por atributo en `AssignmentRule`** — el eje de canal y zona
6. **Retirada del umbral fijo** de calificación
7. Migración `006`

**No entra:** el constructor visual de reglas (§6), la biblioteca de reglas predefinidas, y el rango
acotado de puntuación (sin fase, ver `docs/product/03 §6`).

## 3. `Criterion` — una gramática para todo el sistema

```
Criterion(field: str, operator: Operator, value: Any)
    .matches(lead) -> bool
```

Es la pieza que hoy vive **dentro** de `ScoringRule` y que esta fase extrae. La consumen las tres
etapas: viabilidad, puntuación y asignación.

**Por qué extraerla es lo que da coherencia a la fase.** Sin ella, los seis puntos del alcance son
seis parches. Con ella, son *un* cambio —una gramática de condiciones— aplicado en tres sitios. El
gestor aprende a escribir una condición **una vez** y la reutiliza en las tres etapas, y la interfaz
usa el mismo componente en los tres formularios.

La lista blanca de campos evaluables se conserva y se comparte. No es una limitación de negocio sino
una **frontera de seguridad**: sin ella una regla podría condicionar sobre el identificador de
organización, convirtiendo un dato de sistema en criterio comercial.

## 4. Composición: Y dentro, O entre

**Una regla lleva varias condiciones y se cumple cuando se cumplen todas.**

| Lo que el gestor quiere expresar | Cómo lo escribe |
|---|---|
| Se cumplen **todas** (Y) | **Una regla** con varias condiciones |
| Basta con que se cumpla **alguna** (O) | **Varias reglas**, una por condición |

Con esas dos formas se expresa cualquier criterio en forma normal disyuntiva, que es todo lo que
necesita un constructor de reglas de este tipo.

### Por qué una condición por regla no basta

El caso de referencia —*descartar a quien no tenga ni teléfono ni correo*— escrito como dos reglas
sueltas produce lo contrario de lo buscado:

| Lead | Teléfono | Correo | Con dos reglas sueltas | ¿Correcto? |
|---|---|---|---|---|
| Ana | — | ana@empresa.com | Descalificada | ❌ Se le puede escribir |
| Beto | 600 123 456 | — | Descalificado | ❌ Se le puede llamar |
| Carla | — | — | Descalificada | ✅ |

Dos de cada tres mal, y no se arregla añadiendo reglas: reglas separadas **siempre** significan «basta
con alguna».

### Lo que se descarta explícitamente

**Un modo configurable por regla** (`se cumple con todas / con alguna`). Añade un concepto que el
gestor debe entender para cubrir un caso que ya cubren dos reglas. No paga.

**Anidamiento de grupos** (`(A y B) o (C y D)` dentro de una regla). La forma normal disyuntiva ya lo
expresa con dos reglas. El anidamiento sólo se justifica cuando existe una interfaz visual que lo
haga legible, y esa interfaz no está en el MVP.

### Por qué esta decisión se toma ahora

**No hay nada que migrar.** El sistema no está desplegado y los únicos datos existentes son de
prueba. Ningún paso de esta fase escribe código de traducción ni de backfill: el modelo cambia y las
migraciones se aplican sobre base vacía.

El argumento es **preventivo**, y por eso vale ahora y no después. Los cambios posteriores no cuestan
lo mismo:

| Cambio posterior | Coste | Por qué |
|---|---|---|
| Añadir un operador nuevo | Bajo | **Añade** información. Lo guardado sigue significando lo mismo |
| Añadir un campo opcional a la regla | Bajo | Ídem: valor por defecto y las reglas existentes no cambian de comportamiento |
| **Pasar de una condición a N condiciones** | Alto | **Reinterpreta** lo guardado. Hay que decidir por el gestor si dos reglas suyas eran un Y o un O |
| Cambiar la unidad de agrupación | Muy alto | Cambia el objeto que el gestor manipula, no sólo cómo se almacena |

La línea que separa los dos primeros de los dos últimos: **añadir información nueva es barato;
reinterpretar la existente no lo es**, porque no se puede verificar sin conocer la intención de quien
la escribió. Una regla mal reinterpretada no falla: cambia a quién se asignan los leads, en silencio.

Hoy esa reinterpretación no tiene víctimas porque no hay configuración real. Ése es exactamente el
motivo de fijar la forma ahora: **el coste de acertar es cero, y sólo lo es hasta el primer
despliegue con clientes**.

Esto no contradice el principio de no construir de más: no se construye el constructor visual, ni el
anidamiento, ni la biblioteca de reglas. Se elige **la forma del dato que va a persistir**, que es
una decisión distinta de añadir funcionalidad especulativa.

## 5. Los operadores de vacío

| Operador | Semántica |
|---|---|
| `IS_EMPTY` | El campo falta, es nulo, es cadena vacía **o sólo espacios** |
| `IS_NOT_EMPTY` | Negación de la anterior |

**Se evalúan antes del cortocircuito de campo ausente.** Hoy un campo nulo sale por una rama previa
en la que sólo `NOT_EQUALS` resulta verdadero; sin ese cambio, `IS_EMPTY` devolvería falso justo en
el caso que quiere detectar.

Contar `"   "` como vacío es una **decisión de producto**, no un detalle: un fichero con una columna
en blanco produce espacios, y una regla que a ojo debería cumplirse y no se cumple es indistinguible
de una regla rota.

## 6. `DisqualificationRule` — la etapa de viabilidad

Modelo completo en §7.0 del documento maestro. Lo relevante aquí:

- Se evalúa **antes** de puntuar, y **corta el flujo**: no tiene sentido puntuar ni repartir lo que
  nadie puede trabajar.
- El lead queda `DISQUALIFIED` **con el motivo de la regla**: «Sin vía de contacto», no «puntuó 12».
- Una lista de condiciones vacía se rechaza: una regla que siempre se cumple descalificaría todo.
- `priority` determina qué motivo se registra si varias reglas se cumplen.

### La bandeja de rechazados

`DISQUALIFIED` y `DISCARDED` comparten vista, con una columna que distingue **máquina** de
**persona**. No es un archivo muerto: es donde el gestor comprueba si sus reglas descartan lo que
deben. Una regla mal escrita se detecta ahí, no en los leads que sí pasaron.

## 7. Condiciones en `AssignmentRule`

`conditions: list[Criterion]`, misma semántica Y. El motor pasa de filtrar sólo por banda a filtrar
por banda **y** condiciones.

Habilita el eje que hoy no existe: *«origen es esta campaña y presupuesto supera 10.000 → equipo
Enterprise»*. Lista vacía significa que la regla sólo discrimina por banda, así que las reglas
existentes siguen siendo válidas sin tocarlas.

## 8. Retirada del umbral fijo

`qualify()` deja de recibir dos umbrales fijados en el código.

**La banda más baja de las reglas de asignación pasa a ser el único corte de puntuación**, y lo
escribe el gestor.

Esto elimina la franja sin veredicto: hoy `qualify()` tiene dos ramas para tres tramos, así que un
lead entre ambos umbrales **no cambia de estado** y se queda `NEW`, indistinguible de uno recién
llegado y sin entrar nunca al reparto.

`QUALIFIED` sobrevive como estado transitorio entre el scoring y el reparto, sin umbral propio.

**Por qué el umbral no desaparece sin más, sino que se traslada:** hay que seguir distinguiendo dos
situaciones que el gestor trata de forma distinta.

| Estado | Significa | Qué hace el gestor |
|---|---|---|
| `DISQUALIFIED` | No se puede trabajar | Nada. Revisa la regla si sospecha |
| `UNASSIGNED` | Vale la pena, **pero nadie lo cubre** | Lo asigna a mano |

Si todo lead sin banda cayera en `UNASSIGNED`, la bandeja de revisión manual se llenaría de basura
mezclada con leads buenos y el gestor dejaría de mirarla.

## 9. Migración 006

- Tabla `disqualification_rules` y su tabla de condiciones
- Condiciones de `scoring_rules` y `assignment_rules` migradas a la nueva forma
- Retirada de las columnas de umbral, si las hubiera

Sin datos que preservar.

## 10. Criterio de aceptación

1. El gestor escribe «sin teléfono **y** sin correo → descartar», y un lead con sólo teléfono **no**
   se descarta
2. El lead descartado por regla muestra el **motivo de la regla**, no una puntuación
3. El gestor escribe «los de este canal, a este equipo» y se cumple sin tocar puntuaciones
4. Ningún corte de puntuación queda fuera de la interfaz
5. No existe ningún lead procesado en estado `NEW`
6. Las reglas escritas antes de esta fase siguen funcionando sin intervención
7. La suite completa en verde sin banderas, guardián de arquitectura 4/4, `pytest -m unit` sin
   variables de entorno
