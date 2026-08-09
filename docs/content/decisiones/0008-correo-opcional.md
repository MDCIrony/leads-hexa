# ADR-0008 · El correo del lead es opcional

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Dominio |

## Contexto

El correo era un campo obligatorio del lead. Un payload que llegaba sin correo, o con uno mal
formado, no se guardaba en ninguna parte: la petición fallaba y el lead desaparecía sin dejar
rastro. El gestor no tenía forma de saber cuántos leads estaba perdiendo por ese motivo.

*«Sin correo no vale la pena»* suena a validación, pero no lo es para toda organización: hay
negocios que contactan por teléfono, por mensajería o por redes profesionales. Aplicando la prueba
que separa invariante de regla —¿existe una organización razonable a la que esta afirmación no le
aplique?—, la obligatoriedad del correo cae del lado de la regla, no del invariante.

## Decisión

El correo del lead pasa a ser opcional. Lo que se mantiene como invariante del dominio es el
**formato**: si un lead trae correo, tiene forma de correo. Lo que se suelta es la
**obligatoriedad**: un lead sin ninguna vía de contacto se crea igual, y es una regla de
descalificación de la organización la que decide si es contactable, no el modelo.

No se sustituye la exigencia por otra equivalente: no se exige «al menos un teléfono o un correo».
Eso reproduciría el mismo problema con otro nombre, y dejaría sin datos al caso de uso que justifica
el cambio —un lead sin ninguna vía de contacto, descalificado por una regla visible en vez de
destruido en el borde—.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Mantener el correo obligatorio | Es la causa medida de la pérdida de leads: se pierden sin traza y sin bandeja donde revisarlos |
| Exigir «al menos una vía de contacto» (correo o teléfono) | Reproduce el mismo defecto con otro nombre: un lead sin ninguna vía seguiría sin poder crearse, y la regla de descalificación de referencia se quedaría sin casos sobre los que actuar |
| Relajar el objeto de valor del correo para aceptar valores no válidos | Destruye la garantía de que un correo, si existe, tiene forma de correo — el invariante más defendible del dominio |

## Consecuencias

**Fácil:** ningún lead se pierde por falta de correo. El campo es opcional tanto en el dominio como
en la columna correspondiente; lo que antes era una pérdida silenciosa ahora es un lead visible que
una regla puede descalificar con motivo explícito.

**Difícil:** un campo que puede faltar no puede ser la identidad del contacto. Cuando el sistema
necesite reconocer que dos entradas son la misma persona, no puede apoyarse sólo en el correo —esa
capacidad queda fuera de este MVP precisamente por esta razón—.

## Ver también

- [ADR-0009 · Registrar antes de interpretar](0009-registrar-antes-de-interpretar.md)
- [Reglas](../modulos/reglas.md)
- [Recorrido de un lead](../arquitectura/recorrido-de-un-lead.md)
