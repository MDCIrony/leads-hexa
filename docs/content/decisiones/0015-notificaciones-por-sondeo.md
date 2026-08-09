# ADR-0015 · Notificaciones por sondeo

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-07 |
| **Ámbito** | Full-stack |

## Contexto

Quien tiene que actuar sobre un lead —el asesor al que se le asigna, el gestor cuando algo falla o
queda sin cubrir— necesita enterarse sin ir a buscarlo en pantalla. El acceso a datos del sistema es
síncrono y bloqueante de principio a fin, desde el endpoint hasta la consulta a base de datos.

## Decisión

Las notificaciones internas se entregan por **sondeo del cliente**: la interfaz pregunta
periódicamente al backend por avisos nuevos, en vez de que el servidor empuje un mensaje en cuanto
ocurre. No hay *Server-Sent Events* ni *WebSocket* en este alcance.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| *Server-Sent Events* o *WebSocket* | Exigiría convertir a asíncrono todo el acceso a datos del backend, que hoy es síncrono y bloqueante de punta a punta; es un cambio de arquitectura del transporte completo para una sola capacidad |
| Sondeo del cliente (elegida) | Cero infraestructura adicional, funciona sin tocar nada del proxy que sirve la aplicación, y con la concurrencia esperada de este sistema es indistinguible del tiempo real para quien lo usa |

## Consecuencias

**Fácil:** ningún componente nuevo de infraestructura —ni conexiones persistentes que gestionar, ni
reconexión que programar en el cliente—. El mismo modelo de petición-respuesta que ya usa el resto
de la API sirve también para las notificaciones.

**Difícil:** un aviso no llega en el instante en que ocurre, sino en la siguiente vez que el cliente
pregunta; la latencia percibida depende de la frecuencia de sondeo que elija el cliente, no de
cuándo ocurrió el evento. Si el volumen de organizaciones activas creciera mucho, el sondeo
constante tiene un coste de peticiones que un modelo empujado no tendría.

## Ver también

- [ADR-0016 · Sólo eventos con consumidor](0016-solo-eventos-con-consumidor.md)
- [Notificaciones](../modulos/notificaciones.md)
