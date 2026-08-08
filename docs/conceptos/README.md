# Conceptos de arquitectura

Dilemas de diseño analizados **sobre casos reales de este repositorio**. Material para estudiar y
para discutir en clase, no para construir.

Lo que distingue esta carpeta de las demás:

| Carpeta | Responde a |
|---|---|
| [`specs/`](../specs/) | ¿Qué hay que construir? |
| [`plans/`](../plans/) | ¿En qué orden? |
| [`product/`](../product/) | ¿Qué problema de negocio resuelve? |
| **`conceptos/`** (esta) | **¿Por qué se decidió así, y qué alternativas había?** |

A diferencia de `product/`, aquí **sí se nombran capas, transacciones y códigos HTTP**: el lector es
alguien que estudia arquitectura, no quien opera la plataforma.

## Cómo se escribe aquí

- **Un dilema por documento**, con nombre propio y sus dos lados defendidos en serio. Un documento que
  sólo defiende la opción elegida es una justificación, no un análisis.
- **El caso tiene que ser real y estar medido.** Nada de ejemplos inventados: el valor está en que el
  fallo ocurrió aquí y se puede reproducir.
- **Se escribe después de resolverlo**, no durante. Antes de resolverlo sería una propuesta.

## Índice

| Documento | Dilema | Caso |
|---|---|---|
| [01 — Dónde se valida lo que entra](01-donde-se-valida-lo-que-entra.md) | Fail-fast en la frontera contra tolerant reader | Un `422` de validación que descartaba el dato sin dejar rastro |
