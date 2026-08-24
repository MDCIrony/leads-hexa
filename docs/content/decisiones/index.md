# Decisiones de arquitectura

Esta página cataloga los ADR (*Architecture Decision Records*) de Lead Router: qué se decidió, qué
alternativas se descartaron y por qué. Es la respuesta a «¿por qué está hecho así?» — el resto del
sitio describe el sistema tal como es hoy; aquí vive el historial que lo explica.

## Qué es un ADR

Un ADR es un documento corto que registra **una** decisión de arquitectura: el contexto que la
forzó, la decisión tomada, las alternativas descartadas y sus consecuencias, buenas y malas. No es
un acta de reunión ni una guía de uso: un ADR no cambia cuando cambia el código que describe, sólo
cuando la propia decisión se revisa.

La pregunta que responde un ADR no es «¿qué hace el sistema?» —eso lo cubren los módulos y la
arquitectura— sino «¿por qué se construyó así y no de otra forma?».

## Numeración

Los ADR se numeran de forma secuencial con cuatro dígitos: `0001`, `0002`... El número no se
reutiliza ni se renumera aunque una decisión quede sustituida por otra posterior; el hueco que deja
en la secuencia es información, no un error que corregir.

## Cómo se propone un ADR nuevo

1. Se crea un fichero `NNNN-titulo-en-minusculas.md` en `content/decisiones/`, con el siguiente
   número disponible.
2. Se redacta siguiendo el formato de la siguiente sección, con **Estado: Propuesta**.
3. Se añade una fila a la tabla de abajo.
4. Al aceptarse, el estado pasa a **Aceptada**. Si una decisión posterior la reemplaza, el estado
   pasa a **Sustituida por ADR-XXXX** y el ADR nuevo enlaza al que sustituye — el fichero antiguo no
   se borra: perder el historial repetiría el problema que los ADR existen para evitar.

## Formato

Todo ADR sigue el mismo esqueleto, para que sean comparables entre sí:

```markdown
# ADR-NNNN · Título

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | AAAA-MM-DD |
| **Ámbito** | Backend · ... |

## Contexto
## Decisión
## Alternativas consideradas
## Consecuencias
## Ver también
```

La sección **Alternativas consideradas** es obligatoria: un ADR sin alternativas documenta un
hecho, no una decisión.

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-arquitectura-hexagonal.md) | Arquitectura hexagonal | Aceptada |
| [0002](0002-sql-crudo-sin-orm.md) | SQL crudo sin ORM | Aceptada |
| [0003](0003-dos-planos-disjuntos.md) | Dos planos disjuntos | Aceptada |
| [0004](0004-organizacion-desde-el-token.md) | La organización sale del token | Aceptada |
| [0005](0005-404-en-vez-de-403.md) | 404 en vez de 403 | Aceptada |
| [0006](0006-migraciones-idempotentes.md) | Migraciones idempotentes | Aceptada |
| [0007](0007-tipos-nativos-de-sql.md) | Tipos nativos de SQL | Aceptada |
| [0008](0008-correo-opcional.md) | El correo del lead es opcional | Aceptada |
| [0009](0009-registrar-antes-de-interpretar.md) | Registrar antes de interpretar | Aceptada |
| [0010](0010-recepcion-y-procesamiento-separados.md) | Recepción y procesamiento separados | Aceptada |
| [0011](0011-gramatica-de-condiciones.md) | Una gramática de condiciones | Aceptada |
| [0012](0012-y-dentro-o-entre.md) | Y dentro, O entre | Aceptada |
| [0013](0013-condiciones-en-jsonb.md) | Condiciones en JSONB | Aceptada |
| [0014](0014-retirada-del-umbral-fijo.md) | Retirada del umbral fijo | Aceptada |
| [0015](0015-notificaciones-por-sondeo.md) | Notificaciones por sondeo | Aceptada |
| [0016](0016-solo-eventos-con-consumidor.md) | Sólo eventos con consumidor | Sustituida por [0023](0023-eventos-del-canal-de-salida.md) |
| [0017](0017-retirada-de-webhook-dispatched.md) | Retirada de `webhook_dispatched` | Aceptada |
| [0018](0018-dtos-sin-framework.md) | DTOs sin framework | Aceptada |
| [0019](0019-trabajo-de-fondo-en-proceso.md) | Trabajo de fondo en el mismo proceso | Aceptada |
| [0020](0020-eventos-desde-la-aplicacion.md) | Los eventos se construyen en la aplicación | Aceptada |
| [0021](0021-texto-explicativo-compuesto-al-escribir.md) | El texto explicativo se guarda compuesto | Aceptada |
| [0022](0022-agregados-del-panel.md) | Agregados del panel | Aceptada |
| [0023](0023-eventos-del-canal-de-salida.md) | Los eventos del canal de salida | Aceptada |
