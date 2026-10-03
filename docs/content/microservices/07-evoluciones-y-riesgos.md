# 07 · Evoluciones y riesgos

Lo que se dejó fuera del plan no se olvidó: cada pieza tiene aquí la señal concreta que justificaría
añadirla. Y lo que el plan introduce tiene un coste, que también se escribe.

## Mediciones

Línea base de F0, tomada el 2026-10-02 con el stack local de Compose: 200 llamadas secuenciales de un
único cliente por medida. Es la referencia contra la que se decide cualquier evolución de abajo; sin
ella, «añade latencia» es una opinión.

| Medida | p50 | p95 | Nota |
|---|---|---|---|
| `introspect`, dentro de la red y directo al backend | 4,7 ms | 8,4 ms | Sesión por cookie: SHA-256, dos lecturas y firma Ed25519 |
| `GET /api/v1/leads` directo al backend con bearer, dentro de la red | 7,3 ms | 12,7 ms | Referencia sin gateway |
| `GET /api/v1/leads` por el gateway, con cookie | 10,6 ms | 13,9 ms | Sobrecoste del borde ≈ 3,3 ms en p50, del orden de una introspección |
| `POST /api/v1/auth/login` por el gateway | 292 ms | 314 ms | Dominado por bcrypt |
| `GET /api/v1/leads` con `X-Api-Key` por el gateway | 289 ms | 310 ms | bcrypt en cada petición (en la introspección), como antes |
| Job de 1.000 registros, de `202` a `COMPLETED` (línea base de F0) | 14,5 s | — | Una ejecución; `completed_at − created_at` = 14,2 s. Admisión en proceso, dentro de una única transacción |
| Job de 1.000 registros, de `202` a `COMPLETED`, tras F4 | 12,9 s y 11,9 s | — | Dos ejecuciones, mismo método. La admisión es una llamada HTTP por registro a lead-core (≈ 1,5 ms de red por llamada); no domina el job, así que la señal de la admisión por lotes no se cumple |
| La misma medida antes de corregir el arranque en desarrollo | 59,8 s | — | ≈ 42 ms por llamada: `uvicorn --reload` entrega el socket al hijo por descriptor y asyncio deja `TCP_NODELAY` desactivado, así que cada respuesta en una conexión reutilizada esperaba el ACK retardado. Las APIs de desarrollo arrancan con `watchfiles`; en producción no hay recargador |

**Conclusión.** El gateway con introspección añade ≈ 3 ms por petición: nada de lo medido justifica una
caché de introspección. La ruta `X-Api-Key` está limitada por bcrypt (≈ 290 ms) y es la primera
optimización a considerar si las integraciones consultan con frecuencia; queda como evolución con su
señal, no hecha.

## Evoluciones, con su señal

| Evolución | Qué aporta | Señal que la justifica | Coste |
|---|---|---|---|
| **Admisión por lotes** (`POST /internal/v1/admissions:batch`, N registros por llamada) | Menos idas y vueltas en jobs grandes | Tras F4, la admisión domina la duración del job medido arriba | Respuesta parcial por registro; misma idempotencia |
| **gRPC interno** para `admissions` y `agents/{id}` | Contrato binario tipado, HTTP/2, *streaming* | La admisión por lotes no basta, hace falta *streaming*, o entran servicios en otros lenguajes | Segunda pila (`protoc`, código generado, otro puerto); `introspect` sigue en HTTP porque `auth_request` sólo hace HTTP; la API pública sigue en REST. El cambio es un adaptador detrás de `LeadAdmissionPort` y `AdvisorDirectory` |
| **Caché de introspección** en el gateway | Una consulta a identity menos por petición | p95 de `introspect` relevante frente al total, o carga real sobre identity. Con ≈ 3 ms medidos en F0 no se cumple | La revocación tarda lo que dure la caché; ADR-0029 deja de cumplirse al pie de la letra |
| **Caché de verificación de `X-Api-Key`** (por hash de la clave, TTL corto) | Quita el bcrypt de cada petición de integración (≈ 290 ms medidos) | Integraciones que consultan `GET /leads` con frecuencia, o p95 de esa ruta que afecte a la carga de identity | Una clave revocada sigue valiendo lo que dure el TTL; el TTL tiene que ser corto y la caché sólo guardar el hash |
| **Kubernetes** | Réplicas, autorreparación, despliegue progresivo, autoescalado, `NetworkPolicy`, multihost | Más de un host, alta disponibilidad o despliegues sin corte | Operación del clúster. **No reduce latencia**: la red entre pods es equivalente a la de Compose. Cada servicio son dos `Deployment` (`api`, `worker`) con los mismos nombres DNS; el gateway pasa a Ingress o a un `Deployment` de nginx |
| **mTLS** entre servicios | Cifrado y autenticación del transporte | Red no confiable: varios hosts, red compartida, requisito de cumplimiento | Emisión y rotación de certificados; en Kubernetes, normalmente vía service mesh |
| **Principales SASL por servicio** en Kafka | Cada servicio sólo publica y lee sus topics | Igual que mTLS, o un servicio de terceros en la red | Credenciales por servicio y ACL `PREFIXED` sobre `internal.<svc>.` |
| **Delivery / Integraciones** | Reintentos, estado y métricas por destino (webhooks, CRMs) | Varios destinos con políticas distintas, o un equipo responsable | Un servicio que consume `leads.{tenant_id}` o un topic interno y lleva su propio estado; el outbox no se mueve |
| **Reporting / proyección de consulta** | Paneles sin cargar las bases operativas | El panel compone más de dos fuentes o sus consultas afectan a la operación | Read models alimentados por eventos, con consistencia eventual |
| **Organizaciones fuera de identity** | Ciclo de vida del cliente independiente | Un equipo o un ciclo de cambio distinto del de autenticación | El alta de un tenant pasa a ser una saga entre dos servicios |
| **Separar scoring o asignación** | Escalado independiente de los motores | Perfiles de carga muy distintos, medidos | Coordinar por red el bloqueo de `rr_cursor` y la escritura del lead. Hoy es una transacción local; no se recomienda |

## Riesgos que el plan introduce

| Riesgo | Por qué existe | Mitigación |
|---|---|---|
| **Identity en el camino de cada petición** | El *phantom token* introspecciona siempre | Falla cerrado (503, nunca deja pasar); timeouts de 1 s y 2 s; `keepalive`; réplicas de `identity` si la medición lo pide; la caché es una palanca documentada |
| **El gateway como punto único** | Es la única entrada | Es nginx sin estado: se replica sin coordinación. Healthcheck propio |
| **Proyecciones atrasadas** | `advisors` y `members` son eventualmente consistentes | `upsert` por `version`; hidratación de `advisors` cuando falta la fila; reconstrucción completa desde topics compactados |
| **Un asesor desactivado puede recibir un lead en la ventana de propagación** | La asignación lee `advisors`, no identity | La ventana es la latencia del relay y el consumidor (del orden de segundos). El acceso del asesor sí se corta en la siguiente petición, porque la introspección es síncrona. Se acepta y se documenta en ADR-0031 |
| **`chassis` acopla despliegues** | Cambiarlo obliga a reconstruir varias imágenes | Sólo contiene código técnico estable; entra lo que necesitan dos servicios y no contiene reglas de negocio |
| **Duplicados** | Todo es al menos una vez | `processed_events` en cada consumidor; `event_id` estable; admisión idempotente por `intake_record_id` |
| **Ventanas de migración** | Las extracciones copian datos con escrituras congeladas | Scripts que se pueden repetir, verificación por recuentos y md5, vuelta atrás sólo hasta el corte y escrita así |
| **Observabilidad mínima** | Hoy no hay métricas, trazas ni alertas | `X-Request-Id` de punta a punta y logs correlacionados desde F0; las DLQ se ven en las consolas. Métricas, trazado distribuido y alertas sobre DLQ, *lag* de consumidores y edad del outbox quedan como siguiente paso fuera de este plan |
| **Más piezas que operar** | De 2 procesos de aplicación (`backend`, `intake-worker`) a 9: `identity`, `identity-worker`, `intake`, `intake-worker`, `lead-core`, `lead-core-worker`, `notifications`, `notifications-worker` y el `gateway` | Un patrón idéntico por servicio: quien opera uno sabe operar todos |
| **Un error permanente de base se reintenta para siempre** | Los consumidores esperan a que la base vuelva (`psycopg.OperationalError` es reintentable) y no distinguen una caída de una contraseña mala: con credenciales erróneas el carril no avanza ni acaba en la DLQ. Vive en el bucle de `libs/chassis`, común a los cuatro servicios | Compose fija las contraseñas y `verify_ms_f5` comprueba que cada rol entra en su base, así que un desajuste se ve al arrancar. No se corrige en F5: cambia `chassis` y no es de lead-core. Se aborda cuando un tercero rote credenciales o un orquestador reinicie por salud |

## Lo que no se reabre sin una razón nueva

- **JWT en el navegador.** ADR-0029 lo retiró por motivos que siguen vigentes (revocación inmediata,
  ningún token en almacenamiento web). El *phantom token* da a los servicios un JWT sin dárselo al
  navegador.
- **Unificar brokers.** RabbitMQ reparte trabajo con un ejecutor; Kafka conserva hechos que se releen.
  Son respuestas a dos preguntas distintas (ADR-0026, ADR-0027).
- **Cabeceras de identidad sin firmar** (`X-Tenant-Id`, `X-User-Id`). Cualquier proceso de la red
  podría escribirlas; el token firmado cuesta una verificación local.
