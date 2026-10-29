# Erratas e interpretaciones de CORE v0.1

`CORE.md` está congelada. Al construir el intérprete de referencia (F2)
aparecieron puntos donde la spec no era explícita. Este documento registra **qué
interpretación tomó la referencia** para que todos los backends hagan lo mismo.
No cambia la spec. Los marcados como **candidato v0.2** esperan la decisión de
Danny para entrar en `CORE_v0.2.md`.

| id | tema | la spec dice | interpretación de la referencia | tipo |
|---|---|---|---|---|
| E1 | invocar `main` | "+1 por llamada" (§8) | la invocación inicial de `main` también cuenta como llamada (+1 paso, profundidad 1). Caso 042 | aclaración |
| E2 | `else if` | "+1 por sentencia ejecutada" (§8) | el `if` que sigue a `else` es otra `if_stmt` de la gramática y cuenta su propio paso | aclaración |
| E3 | pasos de `while` | "+1 por sentencia y por evaluación de condición" (§8) | +1 al llegar a la sentencia y +1 antes de cada evaluación de la condición (la primera evaluación suma 2 en total) | aclaración |
| E4 | orden de errores estáticos | "el primero" (§9) no fija entre fases | lexer → parser (incluye `DEC_PARAMS`, `ARRAY_SIZE`, función duplicada) → `NO_MAIN` → tipo de retorno de `main` → cada función en orden de fuente | aclaración |
| E5 | tamaño de arreglo fuera de `1..65536` | no da código (§3.4) | `INVALID_PROGRAM(ARRAY_SIZE)` | **candidato v0.2** (código nuevo) |
| E6 | arreglo literal sin tipo esperado | no lo trata | `INVALID_PROGRAM(AMBIGUOUS_LITERAL)` | aclaración |
| E7 | `[e; N]` | no dice cuántas veces se evalúa `e` | se evalúa **una vez** y se replica | aclaración |
| E8 | `a[i] = e` | evaluar `i`, luego `e` (§7) | el chequeo de rango se hace después de evaluar `e`, al guardar | aclaración |
| E9 | `main` que retorna un arreglo | la forma canónica de arreglo es solo de entrada (§10.1) | `INVALID_PROGRAM(TYPE_MISMATCH)` | aclaración |
| E10 | índice literal `a[0]` | un literal sin contexto es ambiguo (§3.5) | `AMBIGUOUS_LITERAL`; hay que escribir `a[0 as i32]` | **candidato v0.2**: dar a los índices literales un tipo por defecto (p. ej. `i64`) |
| E11 | `-128` en `i8` | el literal `128` no cabe (§3.5) | `LITERAL_OUT_OF_RANGE`; hay que escribir `-127 - 1` | **candidato v0.2**: tratar `-LITERAL` como un solo literal negativo |
| E12 | literal entero en contexto decimal | no lo prohíbe | permitido: `5` en `dec<5,2>` vale `5.00` | aclaración |
| E13 | `==`/`!=` sobre `bool` | permitido (§3.1) | permitido; `<` y compañía sobre `bool` son `TYPE_MISMATCH` | aclaración |
| E14 | eventos de traza | lista de `kind` (§11) | `let` produce `assign`; `break`/`continue` no producen evento; `error`/`limit` es el último evento y lleva `code` | aclaración |
