# Consumidor de prueba

Script mínimo y sin dependencias del backend que se suscribe al topic de una organización y
muestra por pantalla lo que Kafka le entrega. Es la comprobación manual de que el contrato descrito
en [ADR-0026](../../docs/content/decisiones/0026-kafka-como-canal-del-producto.md) se sostiene
solo: si necesitara importar algo de `backend/`, sería señal de que no lo hace. Es exactamente lo
que un cliente externo escribiría para integrarse.

## Requisitos

```bash
pip install confluent-kafka
```

## Uso

Con `docker compose up -d kafka` levantado en este repo (bróker accesible en el host por el
puerto **9094**):

```bash
python consume.py --tenant <uuid>                   # sólo lo que llegue a partir de ahora
python consume.py --tenant <uuid> --from-beginning   # reobtención: todo lo retenido en el topic
```

Cada ejecución usa un grupo de consumidores nuevo, así que repetir `--from-beginning` siempre
vuelve a traer el historial completo del topic en vez de continuar donde se quedó una ejecución
anterior. Es la prueba a mano de la promesa del producto: el cliente puede volver a por los leads
que ya recibió.

`Ctrl+C` cierra el consumidor de forma ordenada.
