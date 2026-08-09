# Hoja de ruta

Qué queda por construir, qué se decidió dejar fuera y por qué. Esta página es el punto de entrada:
cada fila enlaza a donde vive el detalle.

## Cómo se prioriza

Dos criterios deciden qué entra primero:

1. **Qué falta para que el sistema sea un producto usable**, no sólo un backend correcto. Es el
   caso de la interfaz web: el backend cubre el recorrido completo de un lead y no tiene interfaz
   que lo muestre.
2. **Qué está bloqueado por una decisión de producto, no de programación.** Varias capacidades se
   analizaron y se dejaron fuera a propósito porque una pregunta de negocio —no una de
   implementación— sigue sin respuesta. Cada una tiene su razón escrita en la página enlazada;
   antes de proponerla como si fuera un olvido, conviene leerla.

## Qué está pendiente

| Elemento | Estado | Dónde se explica |
|---|---|---|
| Interfaz web | Planificado | [Frontend](frontend.md) |
| Integración por webhook | Planificado | [Webhook entrante](webhook-entrante.md) |
| Identidad del contacto | Fuera de alcance por ahora | [Identidad del contacto](identidad-del-contacto.md) |
| Definición del lead por organización | Fuera de alcance por ahora | [La definición del lead](definicion-del-lead.md) |
| Constructor visual de reglas | Fuera de alcance por ahora | [El modelo de decisión](../vision/modelo-de-decision.md) |
| Rango acotado de puntuación | Fuera de alcance por ahora | [Qué decide cada organización](../vision/dominio-y-organizacion.md) |

Lo marcado **fuera de alcance por ahora** no quedó fuera por olvido. Las cuatro comparten el mismo
motivo de fondo: la respuesta correcta depende de decisiones de negocio que varían de una
organización a otra, y que todavía no se han tomado ni se le pueden imponer a un cliente sin
conocerlo.

## Otras extensiones ya previstas en el modelo

Estas piezas no tienen página propia porque su alcance es pequeño y su diseño está resuelto: lo
que falta es sólo el adaptador o la pantalla. El modelo de dominio ya las contempla, para que
añadirlas no obligue a tocar el núcleo.

| Elemento | Qué existe ya | Qué falta |
|---|---|---|
| Webhooks de salida configurables | El despachador con firma HMAC ya funciona en el código | Una entidad de configuración con CRUD, suscripción del manejador al bus de eventos, reintentos y cola de fallidos |
| Ciclo comercial del lead | El estado `ASIGNADO` cierra el recorrido de esta plataforma | Estados de contactado, ganado o perdido, y las acciones del asesor sobre ellos |
| Métricas e informes | El desglose de puntuación por lead | Agregados de conversión, tiempo de respuesta y rendimiento por asesor |
| Refresh token y cierre de sesión | Autenticación con expiración fija | Renovación y revocación antes de que el token expire |
| Colas y trabajadores externos | La carga masiva ya es asíncrona y un trabajo interrumpido se reprocesa sin duplicar leads | Reintento automático y un proceso separado del propio servidor web |

## Deuda técnica

Aparte de las capacidades pendientes, hay puntos ya construidos que funcionan pero cuestan
mantener o arriesgan un fallo si crece el uso. Están catalogados, con su coste y su riesgo, en
[Deuda técnica](deuda-tecnica.md).
