# ADR-0019 · Trabajo de fondo en el mismo proceso

| | |
|---|---|
| **Estado** | Sustituida por [ADR-0027](0027-cola-para-el-trabajo-de-fondo.md) |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Aplicación |

## Contexto

La fase de procesamiento del recorrido de ingesta corre después de responder al cliente
([ADR-0010](0010-recepcion-y-procesamiento-separados.md)). Correr ese trabajo en segundo plano
exige decidir dónde vive: dentro del mismo proceso que atiende peticiones HTTP, o en un servicio
aparte que lo consuma de una cola.

## Decisión

El trabajo de fondo corre en el mismo proceso que la API, con el mecanismo de tareas en segundo
plano del propio framework web. No hay cola externa —ni bróker, ni un proceso trabajador
independiente— en este alcance.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Celery o RQ, con un bróker dedicado | Añade infraestructura —un bróker, un proceso trabajador que desplegar y mantener aparte— que este MVP no necesita para su volumen y su alcance |
| Un proceso trabajador propio, sin bróker de terceros, leyendo la tabla de trabajos directamente | Resuelve el mismo problema con más código propio que mantener, y sigue sin cubrir el fallo real —el contenedor puede caer igualmente—; el reproceso manual cubre ese caso sin necesitar un segundo proceso |

## Consecuencias

**Fácil:** cero infraestructura adicional que operar. El trabajo de fondo se despliega, escala y
reinicia exactamente igual que la API, sin un componente nuevo que monitorizar por separado.

**Difícil:** si el contenedor cae entre la respuesta `202` y el final del trabajo, éste queda
registrado como en curso para siempre — no hay ningún proceso externo que lo detecte ni lo retome.
Se asume ese riesgo y se mitiga haciendo el trabajo **visible y reprocesable a mano**, en vez de
detectarlo por antigüedad —exigiría un umbral arbitrario— o ignorarlo. Reprocesar es,
deliberadamente, la misma operación que ejecutaría una cola futura si se añadiera: construirla ahora
no es trabajo perdido.

## Ver también

- [ADR-0027 · Una cola para el trabajo de fondo](0027-cola-para-el-trabajo-de-fondo.md)
- [ADR-0010 · Recepción y procesamiento separados](0010-recepcion-y-procesamiento-separados.md)
- [Ingesta](../modulos/ingesta.md)
