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

## 9. ISY-IR v0.2 (`isy-ir/0.2`, CORE v0.3)

Un programa `isyco 0.3` produce `isy-ir/0.2`; uno `isyco 0.1`/`0.2` sigue
produciendo `isy-ir/0.1` sin cambios (mismo `semantic_hash` que en F3,
comprobado sobre los 54 programas válidos de esos corpus). Todo lo de abajo es
inválido bajo `isy-ir/0.1`.

**Tipos nuevos** (los structs van completos en línea; no hay tabla aparte):

```json
{"t":"str","n":1..65536}
{"t":"struct","name":"P","fields":[{"name":"x","ty":<tipo>}, …]}
{"t":"arr","elem":<escalar | str | struct>,"n":…}
```

**Expresiones nuevas:**

| `k` | campos | regla |
|---|---|---|
| `const` | `v` | también `str`: `v` es el texto (≤ n bytes permitidos) |
| `index` | `base`, `index` | si `base` es `str`, `ty` = `u8` |
| `concat` | `a`, `b` | ambos `str` (capacidades libres); `ty` = `str<M>`; si no cabe ⇒ `ERROR(OVERFLOW)` |
| `widen` | `e` | `e` es `str<N>`, `ty` es `str<M>` con N ≤ M; el ensanchamiento implícito de la fuente queda explícito |
| `len` | `e` | `e` str; `ty` = `i64` |
| `slice` | `e`, `lo`, `hi` | `e` str, `lo`/`hi` enteros; `ty` = tipo de `e` |
| `chr` | `e` | `e` entero; `ty` = `str<1>` |
| `field` | `base`, `name` | `base` struct con ese campo; `ty` = tipo del campo |
| `struct` | `fields`: `[{"name","value"}]` | cada campo exactamente una vez, **en el orden escrito** (es el orden de evaluación) |
| `cast` | `e` | además: `str`↔`str`, escalar→`str`, `str`→escalar (CORE v0.3 §2.5) |
| `cmp` | `op`, `a`, `b` | `str` con cualquier capacidad y todos los `op`; `eq`/`ne` entre structs o arreglos iguales |

**Sentencia nueva:** `set_path` con `local`, `path` = `[{"index": expr} | {"field": nombre}]`
y `value`. Los índices se evalúan en orden, luego `value`, y los rangos se
revisan al guardar (E8 generalizado). Un paso `index` sobre `str` es inválido.

**Otros cambios bajo v0.2:** `emit` acepta cualquier tipo y `main` puede
retornar cualquier tipo (forma canónica de CORE v0.3 §6).

Capacidades de backend nuevas (ISY_BACKEND/1 §2): `ir0.2`, `str`, `struct`.
