# Visión

Para quién es Lead Router, qué problema resuelve y qué papel juega cada persona que lo usa.

## Para quién es

Lead Router sirve a cualquier organización comercial que recibe más contactos de los que un
reparto manual puede atender con criterio: inmobiliarias, concesionarios, academias, consultoras.
El requisito no es el sector, es la estructura: varias personas atendiendo leads, y una diferencia
real entre ellas —zona, idioma, especialidad, carga de trabajo— que justifica decidir a quién le
corresponde cada contacto en lugar de repartirlo por orden de llegada.

## Los tres roles

| Rol | Qué hace |
|---|---|
| **Administrador de plataforma** | Da de alta organizaciones y a su primer gestor |
| **Gestor** | Administra su organización: asesores, grupos, reglas, fuentes de leads |
| **Asesor** | Ve únicamente los leads que se le asignaron a él, con su detalle completo |

El administrador de plataforma no accede a ningún dato comercial: ni un lead, ni una regla, ni un
asesor. El gestor ve todos los leads de su organización y resuelve a mano los que el sistema no
supo procesar.

La separación entre el primer rol y los otros dos es deliberada: quien crea organizaciones no
puede leer sus leads. Un superadministrador con acceso a los datos comerciales de sus clientes
sería una propiedad indeseable, no una comodidad.

## El recorrido de un lead, sin tecnicismos

Alguien deja sus datos en un formulario, o llegan por un fichero que sube el gestor. A partir de
ahí, el sistema decide solo, en tres pasos:

1. **¿Se puede trabajar?** Si no hay ninguna forma de contactar a esa persona, se descarta con el
   motivo escrito. Nadie pierde tiempo detrás de un contacto inalcanzable.
2. **¿Cuánto vale?** El lead suma o resta puntos según reglas que el gestor definió de antemano.
3. **¿Quién lo atiende?** Se busca un asesor según esas mismas reglas, respetando su carga de
   trabajo actual.

Si todo encaja, el asesor recibe un aviso y el lead aparece en su panel. Si algo no encaja —el
dato no se pudo interpretar, o ningún asesor tenía hueco— el aviso lo recibe el gestor, que decide
a mano: corrige el dato, asigna manualmente o descarta con motivo.

Ningún lead se pierde en el camino. Lo que llega y no se puede interpretar queda guardado tal como
llegó, visible en una bandeja para que el gestor lo revise y lo corrija.

## Seguir leyendo

- [El problema](el-problema.md) — qué cuesta repartir leads a mano, y qué hace la plataforma al
  respecto.
- [El modelo de decisión](modelo-de-decision.md) — por qué son tres decisiones de naturaleza
  distinta, y qué pasa cuando se confunden en una sola.
- [Qué decide cada organización](dominio-y-organizacion.md) — qué es invariante del modelo y qué
  es configuración de cada cliente.
- [Glosario](glosario.md) — los términos del dominio en un mismo sitio.
