# Tarea 2 — El correo deja de ser obligatorio

> Lee antes el [README de esta carpeta](README.md): contiene los constraints globales, el harness y
> lo que la fase no hace. Vinculan a esta tarea.

**Estado: ✅ cerrada en `91f4807`.** Se conserva como registro de lo que se pidió.

**Ficheros:**
- Modificar: `src/domain/entities/lead.py`, `src/domain/events/lead_events.py`,
  `src/application/dtos/commands.py`,
  `src/infrastructure/adapters/output/persistence/raw_sql_lead_repository.py`,
  `src/infrastructure/adapters/output/parsers/pandas_file_parser.py`,
  `src/infrastructure/adapters/input/api/schemas.py`
- Test: `tests/unit/domain/test_entities.py`, `tests/integration/test_raw_sql_lead_repo.py`,
  `tests/integration/test_pandas_file_parser.py`

**Consume de T1:** `Lead.source_id` ya existe y es obligatorio.

## El razonamiento, para que no lo deshagas a mitad

*«Sin correo no vale la pena»* es una **regla de la organización**, no un invariante: hay quien
contacta por teléfono, por mensajería o por redes profesionales. Escrita como invariante produce el
peor resultado posible — el lead **se destruye** en vez de quedar marcado, y el gestor no puede
contar lo que pierde.

Lo que **no** cambia: si viene un correo, sigue teniendo que tener forma de correo. `EmailAddress`
no se toca.

**C8 es la trampa de esta tarea.** No añadas «al menos una vía de contacto» en sustitución. Un lead
sin ninguna vía tiene que poder existir; F2c escribirá la regla que lo descalifica. Si lo bloqueas
aquí, la bandeja de descalificados queda vacía justo en el caso que la justifica.

## Paso 1: dominio

En `lead.py`:

```python
email: Optional[EmailAddress] = None
```

Ojo con el orden de los campos del `dataclass`: al ganar valor por defecto, `email` tiene que
moverse por debajo del último campo sin defecto. Colócalo junto a `phone` (`lead.py:28`), que ya es
opcional — quedan los dos canales de contacto juntos, que es como se leen.

En `create`, la firma pasa a `email: Optional[Union[str, EmailAddress]] = None` y la conversión a:

```python
if email is None or email == "":
    email_vo = None
elif isinstance(email, EmailAddress):
    email_vo = email
else:
    email_vo = EmailAddress(email)
```

La cadena vacía se trata como ausencia: un CSV con la celda en blanco y un formulario con el campo
sin rellenar significan lo mismo, y distinguirlos produciría un `InvalidEmailException` por un dato
que nadie escribió.

## Paso 2: persistencia

`raw_sql_lead_repository.py:58` — `str(lead.email)` convierte `None` en la cadena `"None"`:

```python
str(lead.email) if lead.email else None,
```

`_row_to_lead` no necesita cambio: `create` ya acepta `None`. Confírmalo leyendo la línea, no lo
supongas.

## Paso 3: evento

`lead_events.py:13` → `email: Optional[str] = None`. Al ser `kw_only=True`, el orden no importa.

En `ingest_lead_use_case.py:96`, la construcción del evento:

```python
email=str(saved_lead.email) if saved_lead.email else None,
```

## Paso 4: API y comando

- `commands.py:17` → `email: Optional[str] = None`. Igual que con el dataclass del lead, vigila el
  orden de los campos sin defecto.
- `schemas.py:17` → `email: Optional[str] = None`, y el validador `validate_email` (`schemas.py:24`)
  devuelve `None` tal cual sin llamar a `_validate_email_format`:

```python
@field_validator("email")
@classmethod
def validate_email(cls, v: Optional[str]) -> Optional[str]:
    if v is None or not v.strip():
        return None
    return _validate_email_format(v)
```

- `LeadResponse.email` (`schemas.py:44`) → `Optional[str]`. Revisa el resto de `schemas.py` por si
  algún otro esquema expone el correo del lead; el del **asesor** no se toca, ahí es la credencial
  de acceso y sigue siendo obligatorio de verdad.

## Paso 5: parser

`pandas_file_parser.py` — hoy `str(row_dict.get("email", "")).strip()` convierte una celda vacía en
`""` y un `NaN` en la cadena `"nan"`. Aplica el mismo tratamiento que ya usa `phone`:

```python
email = str(row_dict["email"]).strip() if "email" in row_dict and pd.notna(row_dict["email"]) else None
if email == "":
    email = None
```

## Tests

| Test | Aserción |
|---|---|
| `test_entities.py` | `Lead.create(..., email=None)` construye y `lead.email is None` |
| `test_entities.py` | `Lead.create(..., email="")` deja `email is None` |
| `test_entities.py` | `Lead.create(..., email="no-es-correo")` sigue elevando `InvalidEmailException` |
| `test_raw_sql_lead_repo.py` | Un lead sin correo se guarda y se relee con `email is None`, no con la cadena `"None"` |
| `test_pandas_file_parser.py` | Una fila con la celda de correo vacía produce un comando con `email is None` |

## Validación y commit

```bash
docker compose --profile test run --rm backend-test
git commit -m "feat(domain): let a lead exist without an email address"
```

---

