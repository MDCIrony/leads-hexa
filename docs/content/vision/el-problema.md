# El problema

Qué es un lead, por qué repartirlos a mano deja de funcionar con volumen, y qué hace la plataforma
en su lugar.

## Qué es un lead

Un lead es un contacto que ha mostrado interés —dejó sus datos en un formulario, respondió a una
campaña, llegó por un fichero que envía un socio— y todavía no está calificado. Cada uno dispara
dos preguntas de naturaleza distinta:

1. **¿Merece la pena?** No todos los leads valen lo mismo. Uno llega sin teléfono ni correo; otro
   trae presupuesto declarado y es del sector al que se vende.
2. **¿Quién lo atiende?** El equipo comercial no es homogéneo: hay asesores senior y junior, quien
   lleva una zona o un idioma, y todos tienen una carga de trabajo que no debería desequilibrarse.

Por qué son preguntas distintas, y qué pasa cuando se tratan como si fueran una sola, es el
contenido de [El modelo de decisión](modelo-de-decision.md).

## Por qué falla el reparto manual

Sin un sistema, esas dos decisiones las toma una persona a mano, lead a lead. Con volumen, eso
produce tres problemas que se agravan cuanto más crece la organización:

| Problema | Qué cuesta |
|---|---|
| **Lentitud** | El lead espera en una hoja de cálculo mientras la competencia le contacta primero |
| **Reparto injusto** | Asesores saturados y ociosos a la vez; los buenos leads, para el más veloz |
| **Leads perdidos** | Nadie se hizo responsable, y no queda rastro de por qué |

## Qué hace la plataforma

Lead Router recibe el lead, lo evalúa contra reglas que el gestor escribe, y lo entrega
automáticamente al asesor que corresponde, dejando constancia de por qué. Cuando ninguna regla lo
cubre, no lo pierde: lo deja visible para que el gestor decida a mano.

## Vocabulario del sector

Son términos ya establecidos en la práctica comercial, y esta plataforma los implementa tal cual
se usan en el sector.

| Término | Qué significa |
|---|---|
| **Lead** | Contacto que ha mostrado interés, aún sin calificar |
| **Lead scoring** | Asignar puntos a un lead según sus atributos, para ordenar por calidad |
| **MQL** — *Marketing Qualified Lead* | Supera el umbral de calidad: marketing dice que vale |
| **SQL** — *Sales Qualified Lead* | Ventas lo acepta y se hace responsable |
| **Lead routing** | Decidir a qué persona o equipo se entrega |
| **SDR** — *Sales Development Rep* | Perfil que califica y enriquece el lead antes de pasarlo |
| **AE** — *Account Executive* | Perfil que cierra la venta. Su tiempo es el recurso caro |
| **Speed-to-lead** | Tiempo entre que el lead entra y alguien le contacta |

La frontera MQL → SQL equivale, en esta plataforma, a la banda más baja de las reglas de
asignación: por debajo de ella, ningún lead se entrega a un asesor.

## Qué no resuelve

Delimitarlo es parte de explicar la plataforma:

- **No es un CRM.** No sigue la venta después de la asignación: no hay estados de contactado,
  ganado o perdido.
- **No hace puntuación predictiva.** Las reglas las escribe el gestor; no hay modelo que aprenda
  del histórico.
- **No integra plataformas externas por su cuenta.** La entrada por webhook está prevista en el
  diseño, con parte del contrato ya construido, pero el adaptador todavía no existe — ver
  [Webhook entrante](../roadmap/webhook-entrante.md).
- **No envía correos ni gestiona campañas.** Reparte leads; lo que ocurre después es de otro
  sistema.
