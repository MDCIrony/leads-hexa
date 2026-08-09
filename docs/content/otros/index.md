# Otros

Análisis conceptuales nacidos de problemas reales de este proyecto, escritos como material de
clase.

No son documentación de referencia: no describen un módulo ni un endpoint, y no hace falta leerlos
para programar contra el sistema. Son análisis en profundidad de una tensión de diseño concreta,
ilustrada con un caso medido sobre el propio Lead Router, pensados para leerse y discutirse aparte.

Por eso viven en su propia sección en lugar de en [Arquitectura](../arquitectura/index.md) o en
[Decisiones](../decisiones/index.md): esas dos responden "cómo está construido" y "por qué se
eligió así"; esta responde "qué principio general enseña este caso".

## Contenido

- [Dónde se valida lo que entra](donde-se-valida-lo-que-entra.md) — fail-fast en la frontera
  contra tolerant reader, con un caso real de esta plataforma y las preguntas que deja abiertas.
