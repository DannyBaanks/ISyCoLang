# ISY-IR v0.1 — Representación intermedia canónica

**Estado:** `v0.1` (F3, 2026-10-28). Normativa para todo backend: un backend
recibe ISY-IR validada, nunca fuente `.isy`. La semántica de cada nodo es la de
`spec/CORE.md` (más `spec/ERRATA_v0.1.md`); este documento solo define la forma.

## 1. Principios

| decisión | por qué |
|---|---|
| **Estructurada** (bloques, `if`, `while`), sin CFG ni SSA | mapea directo a C, Rust, Zig, COBOL…; mantiene el conteo de pasos de §8 sin traducción. SSA queda para la IR de optimización (F8) |
| **Todo tipado:** cada expresión lleva `ty` | un backend no infiere nada; el validador comprueba cada `ty` |
| **Sin literales polimórficos:** `const` con valor en forma canónica de §10.1 | el tipo de cada literal ya se resolvió; los strings evitan perder precisión en JSON |
| **Locales por índice** con tabla por función | dos bloques hermanos pueden reusar un nombre con otro tipo; en la IR son locales distintos |
| **Conversiones explícitas** (`cast`) | ninguna conversión escondida |
| **`at` en cada nodo** | errores y trazas idénticos a la referencia; no entra al hash semántico |
| **Mundo cerrado** | cualquier campo o tipo de nodo desconocido invalida el módulo |

## 2. Módulo

```json
{"schema": "isy-ir/0.1", "source_sha256": "<sha256 del .isy>", "functions": [ … ]}
```

Las funciones van en orden de fuente; el punto de entrada es la que se llama `main`.

## 3. Tipos

```json
{"t":"bool"}
{"t":"int","bits":8|16|32|64,"signed":true|false,"ovf":"trap"|"wrap"|"sat"}
{"t":"dec","p":1..18,"s":0..p,"rnd":"half_even"|"half_up"|"down"|"exact"}
{"t":"arr","elem":<tipo escalar>,"n":1..65536}
```

## 4. Función

```json
{"name":"suma","at":"2:1","params":[0,1],"ret":<tipo>|null,"emits":false,
 "locals":[{"name":"a","ty":<tipo>}, …],"body":[<sentencia>, …]}
```

- `params` son siempre los primeros locales, `[0, 1, …, k-1]`.
- Todo local que no es parámetro se declara con **exactamente un** `let`.
- Un local solo se usa dentro del bloque donde se declaró, después de su `let`.

## 5. Sentencias (campo `s`, todas con `at`)

| `s` | campos | semántica (CORE) |
|---|---|---|
| `let` | `local`, `value` | declara e inicializa (por copia) |
| `set` | `local`, `value` | asigna (por copia) |
| `set_index` | `local`, `index`, `value` | `a[i] = e`: evalúa `index`, luego `value`, luego chequea rango (E8) |
| `if` | `cond`, `then`, `else` (lista o `null`) | un `else if` es un `else` cuyo bloque contiene un único `if` (E2) |
| `while` | `cond`, `body` | +1 paso al llegar, +1 por cada evaluación de `cond` (E3) |
| `break`, `continue` | — | solo dentro de `while` |
| `return` | `value` (expresión o `null`) | |
| `emit` | `value` (escalar) | requiere `emits: true` en la función |
| `call` | `call_at`, `fn`, `args` | llamada como sentencia; descarta el valor |

## 6. Expresiones (campo `k`, todas con `at` y `ty`)

| `k` | campos | regla de tipo |
|---|---|---|
| `const` | `v` | `v` es forma canónica de `ty` (escalar) |
| `local` | `id` | `ty` = tipo del local |
| `call` | `fn`, `args` | `ty` = retorno de `fn` (no `null`) |
| `index` | `base`, `index` | `base` arreglo, `index` entero, `ty` = elemento |
| `cast` | `e` | `e` y `ty` numéricos (CORE §3.6) |
| `neg` | `e` | numérico; `ty` = tipo de `e` |
| `not` | `e` | bool |
| `and`, `or` | `a`, `b` | bool, cortocircuito |
| `bin` | `op` ∈ `add sub mul div rem`, `a`, `b` | `a`, `b`, `ty` iguales y numéricos; `rem` no aplica a `dec` |
| `cmp` | `op` ∈ `eq ne lt le gt ge`, `a`, `b` | `a` = `b`; nada de arreglos; el orden no aplica a `bool`; `ty` = bool |
| `array` | `elems` | exactamente `n` elementos del tipo del elemento |
| `repeat` | `elem` | `elem` se evalúa una vez (E7) |

## 7. Identidad

- `ir_hash` = SHA-256 del JSON canónico (claves ordenadas, sin espacios, UTF-8).
- `semantic_hash` = lo mismo sin `at`, `call_at` ni `source_sha256`: mover
  código o agregar comentarios no lo cambia; cambiar una constante sí.

## 8. Validador

`isyco/ir_validate.py` vuelve a comprobar todo sin confiar en el frontend.
Códigos: `IR_SCHEMA`, `IR_NODE`, `IR_TYPE`, `IR_LOCAL`, `IR_CALL`, `IR_EFFECT`,
`IR_CONTROL`, `IR_RETURN`, con la ruta JSON del nodo (`functions[1].body[3].value.a`).
