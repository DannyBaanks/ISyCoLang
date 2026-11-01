# Decisión V2 — `for x in a` se expande en el parser (2026-10-31)

**Decisión:** `for x in a { … }` con `a: [T; N]` es **azúcar del frontend**: el parser lo
reemplaza por el `while` gemelo escrito a mano, con la cota `len(a)` que resuelve V1. No hay
nodo nuevo en la IR, no hay átomo nuevo en `features_of`, no hay backend que tocar. Es la fila
V2 de `spec/CORE_v0.5_propuesta.md` §2, en la forma que el propio borrador fijaba con la
desugaring literal de §2 V2.

Nace del mismo dogfood que V1: los cinco programas de `programs/dogfood/` recorre arreglos, y
hoy cada recorrido repite `let i: i64 = 0; while i < N { … i = i + 1; }`.

## La regla, en sus cinco sitios

| dónde | qué hace |
|---|---|
| `lexer.py:19` (`KEYWORDS_V05`) y `lexer.py:71-72` | `for` se reserva **solo** con cabecera `0.5`; `in` no entra en ninguna lista (V3) |
| `parser.py:267` | `if self.v05 and self.accept("for")` — con cabecera vieja `for` sigue siendo un IDENT legal |
| `parser.py:317` (`for_stmt`) | devuelve **dos sentencias**: `let i#k: i64 = -1` y el `while` con el avance, el `let x` del elemento y el cuerpo |
| `parser.py:245` (`block`) | aplana la lista: el `for` vive en el bloque contenedor, no como sentencia-bloque |
| `checker.py:205-208` | el `let x` sintético llega **sin anotación**: su tipo es el del elemento (`self.typeof(s.expr, None)`) y desde ahí es un `let` igual que el escrito a mano |

La expansión es exactamente la del borrador:

```text
{ let i#k: i64 = -1; while i#k + 1 < len(a) { i#k = i#k + 1; let x: T = a[i#k]; <cuerpo>; } }
```

Cinco decisiones están escondidas ahí dentro, y ninguna es estética:

- **El incremento va ANTES del cuerpo.** Con el incremento al final, `continue` salta el
  avance. `programs/conformance_v0.5/gemelos/404_while_incremento_abajo.isy` (cabecera `0.4`,
  corre hoy) lo demuestra: `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`.
- **`-1` es `IntLit`, no `Unary`.** CORE v0.2 C2 (`isyco/parser.py`, `unary()`) ya define un
  `-` seguido de un número como un solo literal negativo; construirlo con el operador restaba
  un `{"k": "neg"}` en la IR que el gemelo escrito a mano no tiene. Este error lo cazó
  únicamente el control de forma de la IR: los `steps` eran idénticos.
- **El iterando es un LUGAR (`xs`, `p.xs`), no una `expr()`.** `xs {` es la sintaxis de un
  literal de struct, y una llamada o un literal evaluados dos veces —cota e índice— cambiarían
  los efectos. Era el primer fallo real: `for x in xs {` parseaba como struct literal y
  devolvía `SYNTAX: se esperaba ':', llegó '='`.
- **Las llaves del `while` gemelo son notacionales.** El lenguaje no tiene sentencias-bloque,
  así que `for_stmt` devuelve una lista y `block()` la aplana. Eso es seguro porque
  `fresh_index` (`parser.py:353`) elige el nombre fuera del conjunto de identificadores del
  módulo (`parser.py:25`), y el contador avanza: dos `for` seguidos y un `for` anidado no
  chocan (tests `test_dos_for_seguidos_reutilizan_el_nombre`, `test_for_anidado`).
- **La variable del `for` es una COPIA**, porque el `let` sintético se comporta como cualquier
  `let` sobre `a[i]`: reasignarla no toca el arreglo (`405_for_copia`, que es la confluencia
  con V4).

## Corpus

`402_for_decimales`, `403_for_enteros`, `404_for_break_continue`, `405_for_copia`, con los
`expected` escritos a mano el **2026-10-30** (`dd561c6` y `0e9ca79`, commits que no tocan
`isyco/`). Antes de V2 los cuatro eran `SYNTAX` en el `for` mismo —`se esperaba '=', llegó
'it'` en `402` y `'x'` en los otros tres (`spec/CORE_v0.5_propuesta.md` §4).

## Medición

`tools/v05_revalida_probe.py --casos 401,402,403,404,405,406 --write`, recibo
`isyco.evidence/0.1`, sellado **dos veces con los mismos números**:
`evidence/v05_revalida/run_20261031T235253Z` con el árbol de trabajo sucio
(`veredicto_arbol=EVIDENCE_ONLY`, `git_head=f5e16b7`) y
`evidence/v05_revalida/run_20261101T001608Z` ya con `HEAD` en el commit de V2 y
`git status` vacío (`RELEASE_GATE`, `arbol_sucio_codigo=false`, `git_head=dcd6880`). Las dos
corridas dan el mismo conteo (29 EQUIV + 1 UNSUPPORTED), los mismos pasos y los mismos
SHA-256 de IR.

- **Tres vías:** 29 EQUIV (`expected` ↔ referencia ↔ backend) y 1 UNSUPPORTED. Los `steps` por
  caso: `401` 6, `402` 18, `403` 23, `404` 38, `405` 20, `406` 27.
- **Azúcar de verdad:** cada caso gasta **los mismos pasos que su `while` gemelo** escrito a
  mano —23, 38 y 20 son exactamente los números que exige el gate F2.4, ítem 2—. Seis IGUAL,
  cero PASOS_DIFIEREN, cero SALIDA_DIFIERE.
- **La IR es la del gemelo, no solo su conducta:** la sonda poda posiciones (`at`), el
  `source_sha256` y el nombre del local sintético, y compara el SHA-256 de la IR de azúcar con
  la del gemelo. Los seis coinciden: `401 ac64471411f4a3cd`, `402 671bc2b4781e4a39`,
  `403 8ca576e4d581ebdb`, `404 ef194bcb295b580b`, `405 f70c73fcc5544b3a`,
  `406 f7134aff33db4b14`. Y **cero** nodos `{"k": "len"}` en los seis, con el control positivo
  `len(s)` de v0.3 bajando **uno**.
- **Ninguna capacidad nueva:** `features_of` del `for` es idéntica a la de su gemelo; ningún
  átomo entra con V2. El único UNSUPPORTED del corpus medido (`402` en COBOL,
  `ir0.2,str,struct`) es la regla de contenido de V7 sobre un programa con `struct` y `str`,
  no un rechazo del `for`: `403`/`404`/`405` sí corren en COBOL. Está fijado como test
  (`test_cobol_rechaza_402_por_contenido_no_por_el_for`).
- **No regresión:** la misma fuente recabezada a `0.1`–`0.4` sigue siendo
  `INVALID_PROGRAM(SYNTAX)` en los cuatro casos, y con cabecera `0.4` `let for: i32 = 5;`
  compila —`for` no se reservó retroactivamente. Ningún programa existente cambia de
  significado.
- **El corpus completo:** los **42** casos de `programs/conformance_v0.5/` contra su
  `expected` a mano en la referencia: **42/42 IGUAL** (medido el 2026-10-31, con `408` y `440`
  leídos como `Bundle` a través de `load_corpus`, no como `main.isy` pelado).

## Control anti-fake

- **Brazo viejo, apagando la regla de verdad:** se parcha `has` en **los tres módulos** que lo
  importan (`lexer`, `parser`, `checker`), porque parchar solo el checker no puede desactivar
  un azúcar que vive en el parser — la sonda habría mentido sobre V2. Con la familia `v05`
  apagada, `402`–`405` vuelven a `INVALID_PROGRAM(SYNTAX)` y `401`/`406` a
  `INVALID_PROGRAM(TYPE_MISMATCH)`. Si hubieran ejecutado igual, el EQUIV de arriba sería
  vacuo: la sonda imprime `CONTROL FALSO` y **no sella** (exit 1).
- **El valor sale del tipo, no de la sonda:** cambiar la capacidad declarada mueve la salida, y
  la predicción estaba escrita a mano antes de correr — `402` a `[Item; 4]` da `8.85`, `403` a
  `[i32; 5]` da `26`, `404` con un elemento más emite `2 3 7 6` y retorna `4`, `405` a
  `[i32; 4]` emite `4 6` y retorna `5`. Los cuatro `coincide_con_lo_predicho=true` y
  `mueve_la_salida=true`.
- **`402` recibe su arreglo por stdin**, así que la sonda ahora pasa la entrada de cada caso a
  `referenciar`; comparar el azúcar con un gemelo corrido con entrada vacía habría sido un pase
  vacuo (`402` habría dado `0.00` en las dos vías).
- **Sabotaje en vivo (2026-10-31, medido de nuevo para este documento):** se movió el
  incremento de `for_stmt` al final del cuerpo — la forma que el control negativo del corpus ya
  declara incorrecta — se corrió la sonda con `--write` y se restauró el archivo (verificado
  por md5). Resultado: **12 `CONTROL FALSO`**, exit 1 y **cero archivos escritos** (el
  directorio `evidence/v05_revalida/` quedó con sus 7 entradas). El sabotaje se ve desde tres
  sitios distintos: `404` se vuelve `LIMIT_REACHED(max_steps)` en los cinco backends y su
  salida pasa a ser **exactamente la de `gemelos/404_while_incremento_abajo.isy`**
  (`emits=["2","3"]`); el `expected` a mano deja de coincidir; y la IR de los cuatro casos del
  `for` cambia de forma aunque los `steps` de `402`/`403`/`405` sigan siendo iguales — ese fue
  justo el error que el control de pasos no veía.
- **El control negativo sigue negativo:** `404_while_incremento_abajo` da
  `LIMIT_REACHED(max_steps)` con `emits=["2","3"]` también después de V2
  (`test_el_control_negativo_sigue_siendo_negativo`).

Fuera de la sonda, la clase `ForAzucar` de `tests/test_v05_core.py` (17 tests) fija lo que la
sonda no puede: `break`/`continue` dentro del `for` valen lo mismo que en el `while`
(`BAD_LOOP_CONTROL` si `break` queda fuera), `return` dentro del `for` sigue exigiendo el
retorno del camino (`MISSING_RETURN`), la variable del `for` no sale del bucle
(`UNKNOWN_NAME`), `for` sobre un campo (`for n in c.cosas`) funciona, y **P2 queda respondida
por medición**: `for x in [1, 2, 3]` y `for x in f()` son `SYNTAX`. La recomendación del
borrador era `AMBIGUOUS_LITERAL`; la realidad es más estricta — el iterando se rechaza en la
gramática, así que un literal sin contexto nunca llega a la regla de tipos.

## Lo que V2 NO hace

No añade un átomo de capacidad, no toca la IR ni `ir_validate`, no toca ningún backend y no
define semántica en un backend (la referencia sigue siendo normativa, `AGENTS.md` §4). No
define `for` sobre `str`, sobre slices ni sobre rangos de enteros: el iterando es un lugar de
tipo `[T; N]`. No reserva `in` (eso es V3, y ya era cierto: `test_in_sigue_siendo_contextual`
escribe `let in: i32 = 7` dentro de un módulo con `for`). No convierte la variable del `for`
en alias del elemento (V4).

Suite: **165** tests OK (148 + 17 de `ForAzucar`). Con los 42 casos del corpus pasando, el
directorio entra en `CORPORA` (`isyco/conformance.py:13`) en el commit siguiente, y el gate de
backends pasa de 170 a 212 casos.

**Corrección 2026-11-01:** ese commit siguiente es `57f38bc`. La suite es hoy **166** tests y el
gate de backends corre los **212** casos con el corpus v0.5 dentro: referencia `212/212` y C,
Rust, Zig y pydecimal `212/212`, COBOL `146/212` con 66 `UNSUPPORTED` nombrados, cero diferencias
en las 8 484 corridas diferenciales. Recibo `evidence/backends/gate_2026-11-01T015245Z.json`
(`verdict=PASS`, árbol de código limpio).

## Claims

| claim | estado | dónde |
|---|---|---|
| `for x in a` coincide con su `expected` en la referencia y en los cinco backends | **DEMONSTRATED** (RELEASE_GATE) | 29 EQUIV + 1 UNSUPPORTED atribuido a V7, recibo limpio `run_20261101T001608Z` sobre `dcd6880` |
| El azúcar no cuesta pasos: 23 / 38 / 20 como el `while` gemelo | **DEMONSTRATED** | seis gemelos IGUAL, medidos |
| La IR del `for` es la IR del gemelo (ninguna forma nueva) | **DEMONSTRATED** | SHA-256 de IR idéntico tras podar posiciones y el nombre sintético |
| Ningún programa `0.1`–`0.4` cambia de significado | **DEMONSTRATED** | recabezados: `SYNTAX` en 402–405; `for` sigue siendo IDENT en `0.4` |
| `in` queda contextual (V3) | **DEMONSTRATED** | `test_in_sigue_siendo_contextual`, y `for` reservado solo desde `0.5` |
| La variable del `for` es copia (V4, caso 405) | **DEMONSTRATED** | `405_for_copia` emite `1 3` y retorna `2` |
| P2: `for` sobre una expresión no se permite | **DEMONSTRATED** | literal y llamada → `SYNTAX` (más estricto que la recomendación) |
| Los canarios ejercitan el azúcar (no pasan por otro lado) | **DEMONSTRATED** | brazo viejo sobre `lexer`+`parser`+`checker` → `INVALID_PROGRAM(SYNTAX)` |
| El azúcar sabotiado se detecta | **DEMONSTRATED** | incremento abajo ⇒ 12 `CONTROL FALSO`, `--write` no sella (medido y revertido) |
| V2 está dentro del gate de release de backends | **DEMONSTRATED** desde 2026-11-01 (antes **PENDIENTE**) | el corpus entró en `CORPORA` con `57f38bc`; gate `212/212` con los 42 casos incluidos, recibo `gate_2026-11-01T015245Z.json` |
