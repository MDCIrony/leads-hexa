# Validación

Tres comandos, cada uno demuestra algo que los otros dos no. Ninguno necesita `--build` ni
`restart` para reflejar un cambio.

```bash
docker compose --profile test run --rm backend-test    # suite completa     ~45 s
cd backend && uv run pytest -m unit -q                 # dominio aislado    ~1 s
./scripts/verify-e2e.sh                                # negocio sobre HTTP ~3 s
```

## Por qué no hace falta reconstruir

El código de `backend/src`, sus tests y las migraciones están montados como volúmenes de sólo
lectura en los contenedores `backend` y `backend-test` (ver `docker-compose.yml`). La API además
corre con recarga en caliente (`uvicorn --reload --reload-dir /app/src`, en `backend/Dockerfile`),
así que un cambio guardado se refleja sin reiniciar nada.

Sólo hace falta reconstruir la imagen cuando cambia algo que se instala en tiempo de build:
`pyproject.toml`, `uv.lock` o el propio `Dockerfile`.

```bash
docker compose build backend backend-test
```

## Qué demuestra cada uno

### La suite completa

`docker compose --profile test run --rm backend-test` corre contra una base PostgreSQL real
(`leads_test`, un contenedor aparte de la de desarrollo), no contra un doble en memoria. Es la
única de las tres que ejercita de verdad `backend/src/infrastructure/adapters/output/persistence`.
Cubre los cuatro marcadores de `pyproject.toml`: `unit`, `integration`, `e2e` (vía `TestClient`, sin
un servidor HTTP real) y `architecture`.

!!! warning
    `docker compose run` reemplaza el `CMD` de la imagen, no lo extiende. Para correr sólo una
    parte de la suite: `docker compose --profile test run --rm backend-test pytest -q <ruta>`.
    Invocar `backend-test` sin argumentos vuelve a ejecutar `pytest -q`, la suite entera.

### El dominio aislado

`cd backend && uv run pytest -m unit -q` corre sin PostgreSQL —ni falta el contenedor de base de
datos, ni falta Docker— y sin que quien lo ejecuta tenga que exportar ninguna variable de entorno.
`backend/tests/conftest.py` fija `DATABASE_URL` y `JWT_SECRET` una única vez, con
`os.environ.setdefault(...)`, antes de que se importe cualquier módulo de test.

Si `pytest -m unit` empieza a fallar fuera de Docker, es la señal de que se infiltró una
dependencia de infraestructura en el dominio: el marcador existe precisamente para detectar eso.

!!! warning
    Ningún fichero de test debe fijar `DATABASE_URL` o `JWT_SECRET` por su cuenta. Copiar un
    preámbulo `os.environ.setdefault(...)` de otro fichero reintroduce un fallo que depende del
    orden en que pytest importa los módulos: sólo pasa si `conftest.py` ya corrió antes.

### El negocio sobre HTTP real

`./scripts/verify-e2e.sh` no sustituye a pytest: los tests pueden estar en verde con el producto
roto —un router mal cableado en el módulo de dependencias, un contrato que cambió sin que ningún
test lo notara— y este script no. Lanza peticiones HTTP reales contra `http://localhost:8001`
(configurable con la variable de entorno `API`), construye su propio escenario —un administrador de
plataforma, dos organizaciones, varios agentes— y cada entidad lleva un sufijo por ejecución, así
que no necesita una base limpia para dar una respuesta correcta.

```bash
./scripts/verify-e2e.sh            # contra la base actual
./scripts/verify-e2e.sh --reset    # recrea el volumen de PostgreSQL primero
```

`--reset` sólo hace falta cuando una migración lo exige; el día a día no lo necesita. Requiere la
plataforma levantada — ver [Puesta en marcha](puesta-en-marcha.md).

El script se amplía, nunca se reescribe: cada fase de trabajo añade su propia función `verify_fN` y
la llama desde `main`, de modo que las comprobaciones anteriores siguen corriendo y probando que lo
que ya funcionaba sigue funcionando.

## Los cuatro tests de arquitectura

Dentro de la suite completa, `backend/tests/architecture/test_dependency_rule.py` analiza el árbol
de imports de cada módulo (AST, sin ejecutar el código) y falla si alguna capa cruza una frontera
que no le corresponde:

- `test_domain_does_not_import_outer_layers` — el dominio no importa `application` ni
  `infrastructure`.
- `test_application_does_not_import_infrastructure` — la aplicación no importa `infrastructure`.
- `test_domain_does_not_import_third_party_frameworks` — el dominio no importa nada fuera de la
  biblioteca estándar.
- `test_application_does_not_import_infrastructure_libraries` — la aplicación no importa ningún framework
  web, ni psycopg, ni un cliente de mensajería: llega a todos por un puerto.

Deben estar siempre 4/4. Si uno falla, algo cruzó una frontera que la arquitectura hexagonal existe
para impedir — ver [Arquitectura](../arquitectura/index.md) y
[ADR-0001](../decisiones/0001-arquitectura-hexagonal.md).

## El test de contrato de serialización

`backend/tests/e2e/test_response_contract.py` vigila un defecto que la suite dejó pasar cuatro
veces: **un campo nuevo llega hasta el borde de la API y el adaptador de salida lo descarta**. El
correo del lead se serializó como la cadena `"None"`; el identificador del origen, el del registro
de entrada y el motivo de descalificación se quedaron fuera de su respuesta. Ninguno lo detectó una
prueba: el primero apareció en el harness de negocio y el último, escribiendo otro test.

El resto de pruebas afirma sobre los campos que le interesan, así que sigue en verde aunque el
adaptador tire otros ocho. Ésta afirma sobre todos a la vez, con dos comprobaciones por entidad:

- **Nada de lo enviado vuelve vacío.** Se crea el recurso con valor en cada campo opcional, se
  relee, y se compara campo a campo.
- **Ningún campo del esquema queda sin rellenar.** Se recorren los campos declarados en el modelo
  Pydantic y se exige que ninguno vuelva `None`.

Añade además una garantía transversal: ningún cuerpo de respuesta contiene `hashed_password`,
`secret_hash` ni `password`.

!!! warning "Cuando este test falle, el arreglo está en el router"
    Los campos que legítimamente pueden volver vacíos viven en `NULLABLE_BY_DESIGN`, **cada uno con
    su razón escrita al lado**: estados del ciclo de vida que son mutuamente excluyentes, un
    `lead_id` que sólo existe si el registro llegó a promoverse. Cada uno de ésos se ejercita
    aparte, en un test que provoca su transición, para que la exención no se convierta en un hueco
    de cobertura.

    Si un campo empieza a volver `None` y no está en esa tabla, el test falla a propósito. **La
    corrección es rellenarlo en el router, no añadir una línea a `NULLABLE_BY_DESIGN`.** Ampliar la
    tabla para silenciar el fallo reintroduce exactamente el defecto que este test existe para
    impedir, y es tanto más tentador cuanto que el frontend genera sus tipos desde este contrato:
    un campo declarado en el esquema y nunca rellenado compila en TypeScript y llega `undefined` al
    navegador.

## La limpieza entre pruebas

Cada test de integración o end-to-end trunca las tablas antes de correr. La lista de tablas no está
escrita a mano: se lee de `pg_tables` en el momento de la ejecución, así que una tabla nueva se
limpia sola y no hace falta acordarse de añadirla a ningún sitio.

## Ver también

- [Convenciones](convenciones.md)
- [Cómo contribuir](contribuir.md) — cuándo correr cada comando antes de proponer un cambio.
