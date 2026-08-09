# ADR-0012 · Y dentro, O entre

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-08-08 |
| **Ámbito** | Backend · Dominio |

## Contexto

Una regla con una sola condición no alcanza para expresar un criterio real. *«Descartar a quien no
tenga forma de contactarnos»* no es una condición: son dos que deben cumplirse **a la vez** —sin
teléfono y sin correo—. Escritas como dos reglas sueltas, el resultado es el contrario del buscado:

| Lead | Teléfono | Correo | Con dos reglas sueltas | ¿Correcto? |
|---|---|---|---|---|
| Ana | — | ana@empresa.com | Descalificada | No: se le puede escribir |
| Beto | 600 123 456 | — | Descalificado | No: se le puede llamar |
| Carla | — | — | Descalificada | Sí |

Dos de cada tres casos salen mal, y añadir más reglas no lo arregla: reglas separadas **siempre**
significan «basta con que se cumpla alguna».

## Decisión

Una regla lleva una lista de condiciones y se cumple cuando se cumplen **todas**. No existe un
operador `OR` dentro de una regla, ni un modo configurable, ni anidamiento de grupos. Para expresar
una alternativa, se escribe otra regla:

| Lo que el gestor quiere expresar | Cómo lo escribe |
|---|---|
| Se cumplen **todas** las condiciones (Y) | Una regla con varias condiciones |
| Basta con que se cumpla **alguna** (O) | Varias reglas, una por condición |

Con esas dos formas se expresa cualquier criterio en forma normal disyuntiva, que es todo lo que un
constructor de reglas de este alcance necesita. El gestor nunca ve las palabras «Y» ni «O»: lee
«esta regla se cumple cuando pasa todo esto», y si quiere una alternativa, escribe otra regla.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Un modo configurable por regla («se cumple con todas» / «con alguna») | Añade un concepto que el gestor tiene que aprender para cubrir un caso que las reglas separadas ya cubren sin él |
| Anidamiento de grupos, tipo `(A y B) o (C y D)` dentro de una regla | La forma normal disyuntiva ya lo expresa con dos reglas. El anidamiento sólo se justifica con una interfaz visual que lo haga legible, y esa interfaz no entra en este alcance |
| Una sola condición por regla (lo que había antes) | Es la causa medida del defecto: fuerza a modelar un Y real como dos reglas en O, que produce el resultado contrario en dos de cada tres casos del ejemplo de arriba |

## Consecuencias

**Fácil:** cualquier criterio comercial expresable en forma normal disyuntiva se escribe sin
aprender un concepto nuevo, y una regla con varias condiciones es exactamente la misma pieza que
consumen las tres etapas del recorrido de un lead.

**Difícil:** un criterio genuinamente complejo —con Y y O mezclados a varios niveles— no tiene una
forma compacta de escribirse; hay que descomponerlo en varias reglas planas, y el número de reglas
puede crecer más rápido que la complejidad real del criterio.

**Por qué se fija ahora y no más adelante.** No había datos que migrar: el sistema no estaba
desplegado con clientes cuando se tomó esta decisión, y eso importa porque los cambios futuros no
cuestan lo mismo. Añadir un operador o un campo opcional **añade** información y no cambia el
significado de lo ya guardado, pero pasar de una condición por regla a varias **reinterpreta** lo
existente —hay que decidir, por cada regla guardada, si dos condiciones antiguas eran un Y o un
O—, y esa reinterpretación no se puede verificar sin conocer la intención de quien la escribió. El
coste de acertar la forma del dato era cero antes del primer despliegue con clientes reales, y deja
de serlo en cuanto alguien empieza a depender de la forma anterior.

## Ver también

- [ADR-0011 · Una gramática de condiciones](0011-gramatica-de-condiciones.md)
- [ADR-0014 · Retirada del umbral fijo](0014-retirada-del-umbral-fijo.md)
- [Reglas](../modulos/reglas.md)
