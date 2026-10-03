# La bandeja de Nordwind Solar

La otra mitad del contrato: lo que escribiría un cliente del enrutador de leads para recibirlos.

No importa nada de `services/lead-core/`, y esa es su razón de ser. Habla sólo lo que el producto publica —el
topic de Kafka y, para ponerse al día, `GET /leads` con una clave de máquina— y guarda lo suyo en su
propio SQLite. Si necesitara el código fuente del producto para funcionar, el contrato no se
sostendría solo.

## Levantarla

```bash
docker compose --profile demo up -d test-consumer   # desde la raíz del repositorio
```

Queda en <http://localhost:8003>. El perfil `demo` la mantiene fuera del `docker compose up` normal.

Su imagen se construye desde este directorio y de nada más: `services/`, `frontend/` y `docs/` tienen
sus propios contextos de construcción, así que nada de este subproyecto viaja en ellos ni al revés.

## Registrarla

En la pantalla inicial, el correo y la contraseña de la gestora de la organización. La aplicación
hace dos llamadas públicas —`POST /auth/login` y `POST /agents/integration-credential`— y guarda lo
que recibe. **La contraseña de la persona no se almacena**: sólo la credencial de máquina.

Con la semilla de `demo/seed.py`, eso es `gestor@nordwindsolar.test` / `Demo1234`.

`POST /agents/integration-credential` es un *upsert*: cada emisión rota el secreto y **invalida el
anterior**. Si se registra esta aplicación después de ejecutar `demo/seed.py`, el fichero
`demo/credenciales.local.json` queda obsoleto — vuelve a ejecutar el sembrado para refrescarlo.

## Las dos puertas de entrada

| | Cuándo | Qué trae |
|---|---|---|
| **Kafka** (`⚡`) | Siempre que esté escuchando | Cada lead en el momento en que se enruta |
| **HTTP** (`↻`) | Botón «Reconciliar» | Lo que haya cambiado desde el último corte |

No son redundantes. Kafka entrega en el momento y permite **releer** lo retenido —el botón «Releer
desde el origen» vuelve al principio del topic—, que es justo lo que una cola no ofrece. HTTP
responde a la otra pregunta: *qué me he perdido*, sin tener que releerlo todo.

Una diferencia que conviene tener presente: **el topic lleva sólo lo que el enrutador se queda**
—y anuncia lo filtrado como un evento distinto, `LeadDisqualified`—, mientras que `GET /leads`
devuelve el embudo entero. Esta aplicación lee el `status` de la respuesta HTTP para que las dos
puertas coincidan en qué bandeja va cada lead.

## Lo que hace con ellos

El CRUD es de esta oficina, no del enrutador: estado de trabajo (`PENDIENTE`, `CONTACTADO`,
`PROPUESTA`, `GANADO`, `PERDIDO`), responsable interno, notas y quitar de la bandeja. El enrutador no
se entera de nada de eso, ni tiene por qué.

**Una reentrega no pisa ese trabajo.** La entrega es *al menos una vez*: el mismo evento vuelve cada
vez que un consumidor reinicia antes de confirmar. La actualización nombra sólo los campos que son
del enrutador, y además hay una tabla de `event_id` ya vistos.

## Configuración

| Variable | Por defecto | Para qué |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9095` | El listener autenticado interno. La credencial reporta `localhost:9094`, que es la dirección para clientes en la máquina anfitriona |
| `LEADS_API_BASE` | `http://gateway:8080/api/v1` | Para el registro y la reconciliación |
| `INBOX_DB` | `/data/inbox.db` | El SQLite, en un volumen para que sobreviva a un reconstruido |

## Fuera de la aplicación

```bash
pip install -r requirements.txt
KAFKA_BOOTSTRAP_SERVERS=localhost:9094 LEADS_API_BASE=http://localhost:8001/api/v1 \
  INBOX_DB=./data/inbox.db uvicorn app:app --port 8003
```
