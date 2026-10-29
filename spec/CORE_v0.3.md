# ISyCoLang — Semántica del core v0.3

**Estado:** `DRAFT v0.3` (2026-10-29). Decisiones S1–S8 tomadas por Danny el
2026-10-29; los detalles marcados **[P]** son propuestas pendientes de su
revisión antes de congelar.
**Base:** `CORE.md` (v0.1) + `CORE_v0.2.md`. Este documento solo lista lo que
cambia; todo lo demás es idéntico a v0.2.

## 0. Versionado

- Cabecera `isyco 0.3`. `isyco 0.1` y `isyco 0.2` conservan exactamente su
  significado: ningún programa existente cambia.
- Palabras reservadas nuevas (solo en v0.3): `str struct len slice chr`.
- La IR pasa a `isy-ir/0.2` (tipos `str` y `struct`, nodos nuevos). Un backend
  que no implemente algo lo declara con las capacidades nuevas `str` y
  `struct` y responde `UNSUPPORTED` (ISY_BACKEND/1 §2), nunca aproxima.

## 1. Decisiones de Danny (2026-10-29)

| id | decisión |
|---|---|
| S1 | strings **acotados** `str<N>`: capacidad máxima en el tipo, valor por copia, sin heap |
| S2 | solo **ASCII**: 1 carácter = 1 byte |
| S3 | si un resultado no cabe en su capacidad ⇒ `ERROR(OVERFLOW)`, nunca se trunca |
| S4 | **structs por valor** con `==`/`!=` campo por campo |
| S5 | `str<N>` se **ensancha implícitamente** a `str<M>` si `N ≤ M`; achicar exige `as` |
| S6 | operaciones: literal, `==` `!=` `<` `<=` `>` `>=`, `+`, `len`, `s[i]`, `slice`, `chr` |
| S7 | `as` entre números/bool y `str` usa la **forma canónica** (§10.1) en ambos sentidos |
| S8 | E/S en **JSON canónico**: `str` = string JSON, struct = objeto JSON; `emit` de un str emite su texto |

## 2. Strings `str<N>`

### 2.1 Tipo y valores

- Un valor es una secuencia de **0 a N bytes**. `1 ≤ N ≤ 65536`; si no ⇒
  `INVALID_PROGRAM(STR_SIZE)`.
- Bytes permitidos **[P]**: ASCII imprimible `0x20–0x7E`, más tab `0x09` y
  salto de línea `0x0A`. Cualquier otro byte en un literal ⇒
  `INVALID_PROGRAM(ENCODING)`; en la entrada ⇒ `INVALID_PROGRAM(BAD_INPUT)`;
  producido por `chr` en ejecución ⇒ `ERROR(BAD_CHAR)`.
- Los strings son **inmutables**: `s[i] = …` ⇒ `INVALID_PROGRAM(NOT_ASSIGNABLE)`.
  Se cambia un string asignando uno nuevo a la variable.

### 2.2 Literales

```ebnf
STR_LIT = '"' { STR_CHAR | ESCAPE } '"' ;
ESCAPE  = '\\' ( '"' | '\\' | 'n' | 't' ) ;      (* cualquier otro escape: SYNTAX *)
```

- Un salto de línea crudo dentro del literal ⇒ `INVALID_PROGRAM(SYNTAX)`.
- Un literal de longitud `L` tiene tipo `str<max(L,1)>` y se ensancha (S5).
  Si el contexto espera `str<M>` con `M < L` ⇒ `INVALID_PROGRAM(LITERAL_OUT_OF_RANGE)`.

### 2.3 Ensanchamiento (S5)

Una expresión de tipo `str<N>` se acepta donde se espera `str<M>` con `N ≤ M`:
inicializador de `let`, asignación, argumento, `return`, elemento de arreglo,
campo de struct. Nunca pierde datos. Es la **única** conversión implícita del
lenguaje; con `N > M` ⇒ `INVALID_PROGRAM(TYPE_MISMATCH)` (usar `as`). Las
capacidades de un arreglo o struct no se ensanchan: `[str<4>; 2]` y
`[str<8>; 2]` son tipos distintos.

### 2.4 Operaciones

Los operandos de tipo string pueden tener capacidades distintas.

| operación | tipo | semántica |
|---|---|---|
| `a + b` | ver abajo | concatenación |
| `a == b`, `a != b` | `bool` | igualdad byte a byte (la capacidad no cuenta) |
| `a < b` … `a >= b` | `bool` | orden lexicográfico por bytes; un prefijo es menor |
| `len(s)` | `i64` | número de bytes |
| `s[i]` | `u8` | byte `i`; `i` de cualquier tipo entero (literal ⇒ `i64`, como C1); fuera de `[0, len-1]` ⇒ `ERROR(INDEX_OUT_OF_BOUNDS)` |
| `slice(s, a, b)` | igual que `s` | bytes `[a, b)`; `a`, `b` de cualquier tipo entero (literal ⇒ `i64`); si no `0 ≤ a ≤ b ≤ len(s)` ⇒ `ERROR(INDEX_OUT_OF_BOUNDS)` |
| `chr(b)` | `str<1>` | `b` de cualquier tipo entero (literal ⇒ `i64`); si `b` no es un byte permitido (§2.1) ⇒ `ERROR(BAD_CHAR)` |

**Capacidad de `a + b` [P]:** si hay un tipo esperado `str<M>` (anotación del
`let`, destino de asignación, parámetro, `return`, destino de `as`, campo), el
resultado es `str<M>`; si no hay contexto (`emit a + b`, `len(a + b)`, operando
de una comparación), es `str<min(N_a + N_b, 65536)>`. Si la longitud real no
cabe ⇒ `ERROR(OVERFLOW)` (S3). Así `let s: str<64> = "Hola, " + nombre;`
comprueba contra 64.

`len`, `slice` y `chr` son operaciones del core, no llamadas: no cuentan pasos
ni profundidad. Son palabras reservadas: `fn len(…)` ⇒ `INVALID_PROGRAM(SYNTAX)`.
Un literal entero donde se espera un `str` (o al revés) ⇒ `TYPE_MISMATCH`.

### 2.5 Conversiones con `as` (S7)

| de → a | regla |
|---|---|
| `str<N>` → `str<M>` | mismo contenido; si `len > M` ⇒ `ERROR(OVERFLOW)` |
| bool / entero / decimal → `str<M>` | forma canónica de §10.1; si no cabe ⇒ `ERROR(OVERFLOW)` |
| `str` → bool | `"true"` / `"false"`; otra cosa ⇒ `ERROR(BAD_FORMAT)` |
| `str` → entero | el texto debe ser un entero en forma canónica; si no ⇒ `ERROR(BAD_FORMAT)`; el valor exacto pasa por la regla `ovf` del destino (como int → int) |
| `str` → `dec<p,s,r>` **[P]** | el texto debe estar en la forma canónica **de ese tipo** (exactamente `s` decimales); si no ⇒ `ERROR(BAD_FORMAT)`; más de `p` dígitos ⇒ `ERROR(OVERFLOW)` |
| con arreglos o structs | `INVALID_PROGRAM(BAD_CAST)` |

## 3. Structs

### 3.1 Declaración

```ebnf
file        = header { fn_decl | struct_decl } ;
struct_decl = "struct" IDENT "{" field { "," field } [ "," ] "}" ;
field       = IDENT ":" type ;
type        = "bool" | int_type | dec_type | str_type | arr_type | IDENT ;
str_type    = "str" "<" NAT ">" ;
arr_type    = "[" elem_type ";" NAT "]" ;
elem_type   = "bool" | int_type | dec_type | str_type | IDENT ;   (* sin arreglos de arreglos *)
```

- Al menos un campo. Campo repetido, struct repetido o struct con el nombre
  de una función ⇒ `INVALID_PROGRAM(DUPLICATE_NAME)`. Tipo desconocido ⇒
  `UNKNOWN_NAME`.
- El orden de declaración de structs y funciones es libre.
- Un struct que se contiene a sí mismo, directa o indirectamente (también vía
  arreglo) ⇒ `INVALID_PROGRAM(RECURSIVE_TYPE)`.

### 3.2 Valores y operaciones

- Literal: `Punto { x: e1, y: e2 }`. Cada campo **exactamente una vez**, en
  cualquier orden; faltante, sobrante o repetido ⇒ `INVALID_PROGRAM(BAD_FIELDS)`.
  Los campos se evalúan **en el orden escrito** (§7). Cada `ei` tiene como
  tipo esperado el del campo (los literales y el ensanchamiento aplican).
- **[P]** En la condición de `if`/`while`, un literal de struct va entre
  paréntesis (`if p == (Punto { x: 1, y: 2 }) { … }`); sin paréntesis,
  `IDENT {` abre el bloque. Es la misma regla que Rust.
- Acceso `e.campo` (postfix); campo inexistente ⇒ `UNKNOWN_NAME`.
- Asignación, paso de parámetros y `return` **por copia**, como los arreglos.
- `==` / `!=`: campo por campo, en orden de declaración (S4). `<` etc. ⇒
  `TYPE_MISMATCH`.

### 3.3 Lvalues

```ebnf
lvalue = IDENT { "[" expr "]" | "." IDENT } ;
```

`p.x = e`, `a[i].x = e`, `p.pts[i] = e`, `p.q.x = e`. Los índices del lvalue
se evalúan de izquierda a derecha y **después** `e` (generaliza §7); los
chequeos de rango se hacen al guardar, después de evaluar `e`, de izquierda a
derecha (generaliza E8). Un índice sobre un `str` en un lvalue ⇒
`NOT_ASSIGNABLE`.

## 4. Arreglos (cambios)

- Los elementos pueden ser `str<N>` y structs (`elem_type`), además de los
  escalares. Siguen sin existir arreglos de arreglos (se usan structs).
- **[P]** `==` / `!=` entre arreglos del mismo tipo, elemento por elemento:
  hace falta para que un struct con un campo arreglo sea comparable (S4).

## 5. Tamaño de un valor **[P]**

El tamaño de un tipo es: escalar = 1, `str<N>` = N, `[T; N]` = N × tamaño(T),
struct = suma de sus campos. Un tipo con tamaño > 1 048 576 ⇒
`INVALID_PROGRAM(TYPE_TOO_LARGE)`. Evita que `[str<65536>; 65536]` (4 GiB) sea
un tipo válido; los límites son semántica.

## 6. Entrada, salida y forma canónica (S8)

| tipo | en la entrada (JSON) | forma canónica (`emit`, `return`, traza) |
|---|---|---|
| bool, entero, decimal | string canónico (sin cambios) | sin cambios |
| `str<N>` | string JSON; bytes permitidos y `len ≤ N`, si no `BAD_INPUT` | el texto mismo |
| `[T; N]` | arreglo JSON de N valores en su forma de entrada | JSON canónico de un arreglo |
| struct | objeto JSON con exactamente sus campos (cualquier orden de claves) | JSON canónico de un objeto, campos en **orden de declaración** |

- **JSON canónico** aquí: sin espacios, escalares como strings canónicos,
  strings con los escapes mínimos de JSON (`\"`, `\\`, `\n`, `\t`).
  Ejemplo: `emit p;` con `p = Punto { x: 1, y: -2 }` emite `{"x":"1","y":"-2"}`.
- `emit` acepta ahora strings, arreglos y structs (antes solo escalares), y
  `main` puede retornar cualquier tipo (en v0.3 no aplica E9).
- Nota: `emit "5"` y `emit 5` producen la misma línea de salida `5`. La salida
  no lleva tipos; el tipo lo fija el programa.

## 7. Errores nuevos

| status | códigos nuevos |
|---|---|
| `INVALID_PROGRAM` | `STR_SIZE`, `NOT_ASSIGNABLE`, `BAD_FIELDS`, `RECURSIVE_TYPE`, `TYPE_TOO_LARGE` |
| `ERROR` | `BAD_FORMAT`, `BAD_CHAR` |

### 7.1 Orden de los errores estáticos (extiende E4)

lexer (incluye `ENCODING` y escapes) → parser (incluye `STR_SIZE` junto a
`ARRAY_SIZE`/`DEC_PARAMS`, y los `DUPLICATE_NAME` de funciones, structs y
campos) → structs en orden de fuente (`UNKNOWN_NAME` de tipos, luego
`RECURSIVE_TYPE`, luego `TYPE_TOO_LARGE`) → `NO_MAIN` → lo demás como E4.
`TYPE_TOO_LARGE` también se revisa en cada tipo escrito en una función.

## 8. Pasos y límites

Sin cambios: los structs, strings y las operaciones `len`/`slice`/`chr` no
agregan pasos. `max_steps`, `max_call_depth` y `max_emits` cuentan igual.

## 8.1 Caso superado al congelar

`programs/conformance_v0.2/119_header_v03` afirma que `isyco 0.3` es `SYNTAX`.
Al congelar v0.3 se supera de forma explícita en
`programs/conformance_v0.2/SUPERSEDED.json` (pasa a `HALTED`, sin salida), como
se hizo con el caso v0.1 `003`; la afirmación vigente la toma `264_header_v04`.

## 9. Lo que v0.3 NO incluye

Strings dinámicos, UTF-8, formato con plantillas, arreglos de arreglos,
métodos, genéricos, módulos/imports y lectura de archivos. Cada uno es una
versión futura con su propia decisión.

## 10. Corpus

`programs/conformance_v0.3/` (64 casos, 201–264) con `expected` escritos a
mano **antes** de implementar. Los corpus v0.1 y v0.2 no se modifican.
