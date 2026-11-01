# Decisión N1 — `for c in s` sobre un `str` es normativa (2026-11-01)

**Decisión:** el iterando del `for` puede ser un lugar de tipo `str`, no solo un arreglo. Todo
**lugar** `str` —local `str<N>`, campo calificado, parámetro `str` pelado (V6), entrada por
stdin— se recorre **`len(s)` veces** y la variable del bucle es **`u8`, copia**. La cota es la
**longitud del valor**, no la capacidad declarada. Era la única arista marcada `[D]` en
`spec/CORE_v0.5.md` §4.4 y la fila N1 de `docs/OPEN_QUESTIONS_P1_P4.md`; queda **adoptada, por
caso y por texto**.

Nace del objetivo real de esta etapa: una **librería de texto**. Los cuatro utilidades de
`programs/dogfood/06_biblioteca_texto.isy` (`pad`, `empieza_con`, `cuenta_letra`, `mayus`)
recorren cadenas, y hoy cada una repite `let i: i64 = 0; while i < len(s) { let c: u8 = s[i];
… i = i + 1; }`. Con N1 adoptada, `cuenta_letra` y `mayus` pasan a la forma corta.

## La regla, en sus sitios (ninguno se toca)

Lo importante de N1 es que **no añade regla nueva al engine**: el azúcar ya era agnóstico del
tipo del lugar.

| dónde | qué hace con un `str` |
|---|---|
| `parser.py:317` (`for_stmt`) | expande `let foridx#k: i64 = -1; while foridx#k + 1 < len(s) { foridx#k = foridx#k + 1; let c = s[foridx#k]; <cuerpo>; }` — sin saber que `s` es un `str` |
| `parser.py:334-337` | el iterando se lee como **lugar**: `A.Name` y luego cadenas de `A.Field`; no hay `expr()` ahí, así que `for c in s[0]` es `SYNTAX` (V2 §4.3) |
| `parser.py:341` y `:350` | la cota es `A.Len(lugar)` y el elemento es `A.Index(lugar, foridx#k)` con el `let` **sin tipo** — ninguna de las dos mira el tipo del lugar |
| `checker.py:204-209` | el `let` sintético llega **sin anotación** ⇒ su tipo es `typeof(s[foridx])`, que en `checker.py:348-352` es **`u8`** para un `Index` sobre `StrT` |
| `checker.py` (`Len` sobre `StrT`) | `len(s)` es i64 y **runtime** en cualquier versión: V1 pliega estático solo el `len` de un **arreglo**, y esa es la diferencia exacta que la cota mide |
| `interp.py:238-239` | `A.Len` ⇒ `len(self.eval(e.expr))` — longitud del valor; `interp.py:223-230` ⇒ `INDEX_OUT_OF_BOUNDS` si el índice se pasa |

Por qué no rechazarla: rechazar obligaría a etiquetar de tipo los nodos sintéticos que el
parser produce sin tipos, y el `while` gemelo escrito a mano seguiría siendo legal. O sea el
`for` dejaría de ser azúcar, que es justamente la invariantе que V2 fijó con pasos, traza e IR
iguales.

## Orden de la evidencia, dicho sin adornos

En las decisiones anteriores el `expected` se escribía a mano **antes** de correr nada porque
había código que cambiar. Aquí no: la conducta ya existía y ya estaba medida en la
investigación (los nueve bordes de §4.4 se midieron en vivo antes de decidir). Lo que se hace
es transcribir la **regla** —`len(s)` vueltas, variable `u8` copia— y verificar que el
`expected` de cada caso se sigue de la regla, no del stdout: `444` fija que la cota es
longitud y no capacidad (un `str<8>` con `"hola"` emite 4, no 8), `446` fija la copia, `445`
fija que el `str` pelado de V6 se recorre. Si el `expected` fuera una transcripción del
stdout, el caso no sería una predicción; por eso los tres se escribieron desde la regla y el
caso vacío (`str<1>` = `""`, 6 pasos) se quedó en los tests y en la sonda, no en el corpus.

## Corpus

Tres casos en `programs/conformance_v0.5/` con su `while` gemelo escrito a mano
(alta `00bc5a3`, corrección de cabecera del gemelo `0224002`):

| caso | qué fija | gemelo | pasos | traza `stmt` | sha-256 |
|---|---|---|---|---|---|
| `444_for_sobre_str` | la cota es la **longitud del valor**, no la capacidad: `str<8>` con `"hola"` emite 4 bytes y `len` devuelve `4` | `gemelos/444_while.isy` (`0.4`) | 22 y 22 | 21 y 21 | `87bdfa7daa76aa71` |
| `445_for_str_pelado_stdin` | N1 × V6: un `str` pelado recorre lo que le llega por stdin (`"mundo"` → sus 5 bytes, `len` 5) | `gemelos/445_while.isy` (`0.5`) | 27 y 27 | 26 y 26 | `1805ca9c1a58c579` |
| `446_for_copia_str` | la variable es **copia** `u8`: `c = 65` no muta el `str` (`65 65 65` y `s[0]` sigue `97`) | `gemelos/446_while.isy` (`0.4`) | 22 y 22 | 21 y 21 | `b2e804e37d30b048` |

La población pasa de **43 a 46** casos del corpus (42 programas a un archivo + 4 carpetas con
módulos) y de **213 a 216** en el gate. `gemelos/` no la cuenta
(`isyco/conformance.py:17-41`: `load_corpus` mira `*.expect.json` y las carpetas con
`expect.json`; `gemelos/` no tiene ninguno) — medido: `load_corpus` devuelve **46** y el
directorio tiene **7** gemelos.

Un detalle que la sonda no puede cubrir y el caso sí: en `445` la **cadena completa** tiene que
declarar `!emit`. Si `main` no lo declara aunque su callee emita, el checker tira
`UNDECLARED_EFFECT` nombrando a `main`. Es la regla de efectos que ya existía, no una nueva.

## Medición

`python3 tools/v05_spec_probe.py --write` selló la sección nueva **7) N1 (§4.4)** — doce filas
de formas con su predicho — en `evidence/v05_spec/run_20261101T210009Z.{txt,json}`
(`veredicto_arbol=RELEASE_GATE`, `arbol_sucio_codigo=false`, `git_head=c536858`; sha-256 del
json `9ff73257f62d4106…`, del txt `22695f85f0001d8d…`). Las secciones 1–6 del recibo son
**byte a byte idénticas** al sello anterior: control de no regresión sobre la propia sonda.

Cuatro vías de igualdad con el gemelo, medidas caso por caso:

- **Salida:** `status`/`code`/`emits`/`return` idénticos en los tres pares, y los tres
  coinciden con su `expected` escrito desde la regla (recibo F2
  `evidence/conformance/run_2026-11-01T210445Z.json`: **216/216 `PASS`**, con los 213
  anteriores byte a byte iguales —cero diferencias— y tres filas nuevas).
- **Pasos:** 22 / 27 / 22, exactamente los mismos que su `while` gemelo; pinneados en
  `PASOS_EXIGIDOS` de `tests/test_v05_core.py:105`, que es el gate F2.4.
- **Trazas `stmt`:** 21 / 26 / 21 líneas, idénticas tras renombrar el índice sintético
  (`foridx#k` → `i`).
- **IR:** el `for` baja a la **misma IR** que el gemelo — recibo F3
  `evidence/ir/gate_2026-11-01T210450Z.json`: **432/432** comparaciones iguales sobre **148**
  programas bajados (antes 426/145; el incremento es exactamente los tres casos nuevos), y en
  los tres pares el SHA-256 de la IR podada (`at`, `source_sha256`, nombre del local sintético)
  coincide: `444 afe157c0dfb11899`, `445 c5ef4d57e3c413ee`, `446 ae1d41a58d059ad7`.
- **Ninguna capacidad nueva:** `features_of` del `for` es **idéntica** a la de su gemelo en los
  tres casos. Lo que le echa COBOL en falta en los tres —y en los tres gemelos— es
  `['ir0.2','str']`: la regla de contenido de V7 sobre un programa con `str`, no un rechazo del
  azúcar (`test_cobol_rechaza_los_tres_por_contenido_no_por_el_for`).
- **Backends (F5):** `evidence/backends/gate_2026-11-01T225011Z.json` (`verdict=PASS`, sha
  `63d7a9b4954c468d…`): C, Rust, Zig y pydecimal **216/216**, cada uno con sus 8 484 corridas
  diferenciales y 1 270 del diferencial de strings en **0 diferencias**, y COBOL **147/216 con
  69 `UNSUPPORTED`** nombrados —los tres casos de N1 entran con `ir0.2,str`, exactamente la
  cifra predicha antes de correr (66 → 69)— y 0 fallas. F4, en el mismo lote que F2 y F3:
  `evidence/c/gate_2026-11-01T211424Z.json` (`PASS`), 216 casos en las cuatro combinaciones
  gcc/clang × plain/sanitized con las tres vías en 216/216.
- **El `FAIL` intermedio de F5, dicho:** la primera corrida de F5 sobre el árbol de N1
  (`gate_2026-11-01T215718Z.json`, sha `e1fc1c82…`) salió `FAIL` por un `TIMEOUT` del arnés en
  el diferencial de strings de pydecimal, con el host en carga de otros agentes (load 9,8). Se
  preservó el recibo y se midió la reproducibilidad
  (`evidence/f5_flake/run_20261101T220854Z.json`): 500 llamadas aisladas y dos pasadas
  completas de 1 270 casos dan **0 `TIMEOUT` y 0 diferencias**, a ~40 ms por caso frente al
  temporizador de 60 000 ms. La re-corrida del gate (el `PASS` de arriba) pasó esa misma
  pasada limpia. No se tocó `isyco/backends/base.py`: cambiar el temporizador del arnés para
  que un gate pase no es una decisión de N1, y queda dicho en su lugar (hallazgo 10 de
  `docs/EVIDENCE_MATRIX.md`).

## Los bordes que fija la sonda, no el corpus

| forma | observado |
|---|---|
| `str<4>`, `str<8>`, `str<16>` con `"hola"` | **los mismos 4 bytes y 22 pasos** — la capacidad declarada no mueve la cota |
| `let s: str<1> = ""; for c in s` | 0 vueltas, `HALTED`, **6 pasos** |
| `for c in l.texto` (campo calificado) | funciona, 18 pasos |
| `for s in ss { for c in s { … } }` | los dos azúcares anidados, 38 pasos |
| `str` pelado en parámetro (V6) | recorre lo que le llega, 24 pasos |
| `n + c` con `n: i64`, `c` de un `str` | `TYPE_MISMATCH` — `c` es `u8`, hace falta `c as i64` |
| `c` después del bucle | `UNKNOWN_NAME` — la variable no escapa |
| `for c in s[0]` | `SYNTAX` — la regla de lugar (§4.3) manda también sobre `str` |
| la misma fuente con cabecera `0.4` | `SYNTAX` — `for` es reservada solo desde `0.5` (V3) |
| `emit s[7]` en un `str<8>` con `"hola"` | `ERROR(INDEX_OUT_OF_BOUNDS)` a los **3 pasos** |
| `while` gemelo con la **capacidad** en la cota | `ERROR(INDEX_OUT_OF_BOUNDS)`, emite `104 111 108 97` y revienta a los **23 pasos** |

Las dos últimas filas son el corazón del control: poner la capacidad como cota **rompe**, así
que "la cota es la longitud" no es una forma de hablar.

## Hallazgo y corrección: los "24 pasos" mal atribuidos

El §4.4 del borrador afirmaba que el `for` sobre `str<4> = "hola"` y su gemelo gastaban **24
pasos**. Medido hoy: **22 y 22** (`str<4>`, `str<8>` y `str<16>` dan el mismo número). El 24
existe y no es un error de medición — es de otra **forma** de programa: la matriz de
*forma constante* de la sonda (§5) recorre dentro de una **función** (`fn recorre(s: str<4>)`
llamada desde `main`, con su marco y su `return len(s)`), y ese par cuesta 24. Corridas las dos
formas el mismo día: **24 con llamada, 22 sin ella**, misma salida en cada par. O sea la cifra
mal atribuida no era falsa, era de otro programa, que es la forma en que estos errores sobreviven.
La corrección quedó escrita en §4.4 y §7 de `spec/CORE_v0.5.md`, no silenciosa: el patrón es
enmendar encima del texto, no reescribir la historia.

## Control anti-fake

- **Sabotaje del engine, fijado como test** (`tests/test_reference.py::Sabotage`):
  `test_len_de_str_se_hace_estatico` pliega `len` de un `str` a su capacidad declarada — justo
  lo que V1 hace con los arreglos. Muerde `444_for_sobre_str`: con cota 8 sobre 4 bytes el
  recorrido se sale de rango. El test afirma `assertIn("444_for_sobre_str", fails)`, así que
  si la mutación dejara de romperse el test falla, no pasa en silencio.
- **Sabotaje en vivo de la sonda (2026-11-01):** se parcheó `Interpreter.eval` en el mismo
  proceso con esa mutación y se corrió `tools/v05_spec_probe.py --write`. Resultado:
  **6 `CONTROL FALSO`** en la sección 7, exit **1** y **cero archivos escritos**. Sin tocar
  nada del corpus.
- **El control que *no* cazó la mutación, dicho:** la fila `por_capacidad` de la sonda no
  detecta esa mutación (las dos filas marcadas fallan por igual, y `str<4>` está deliberadamente
  sin marcar). Su papel es otro — impedir que el control se vuelva vacío o se angoste a una
  sola fila—. Lo que detecta la mutación es la **predicción por fila**, no el control de forma.
  Dejarlo escrito es el punto: un control que no hace lo que parece no debe venderse como si lo
  hiciera.
- **Controles de vacuidad:** la sección 7 **no sella** si hay menos de dos filas con
  `control_capacidad` (sería un control vacío), si esas filas discrepan entre sí, o si alguna
  fila se desvía de su predicho.
- **Brazo viejo:** la misma fuente con cabecera `0.4` es `SYNTAX`
  (`test_con_cabecera_04_el_for_sobre_str_se_rechaza`), así que los tres casos ejercitan
  realmente el azúcar de 0.5 y no un camino lateral.

Suite: **179** tests OK, medido **188,336 s** (`python3 -m unittest discover -s tests` sobre el
árbol con el lote de conmutadores ya conmutados, 2026-11-01 23:30 UTC; `real 188,57`). La clase
`ForSobreStr` aporta **11** tests; el piso de población de `tests/test_reference.py` sube de 213
a **216**. Dicho sin adornos: una corrida anterior de la misma suite, a media tarde, dio **6
fallas** y ninguna era de N1 — cuatro leyeron el `README.md` mientras se editaba (la suite y la
edición corrieron a la vez) y dos eran un defecto propio del lote de evidencia: regenerar los
`SHA256SUMS.txt` con `./` en la columna de ruta rompe
`test_every_dir_has_sums_and_lists_every_file` aunque ningún digest cambie. Está escrito como
hallazgo 11 de `docs/EVIDENCE_MATRIX.md` y el número de arriba es de la corrida limpia, con
`sha256sum -c` verificado desde adentro de los cinco directorios tocados.

## Lo que N1 NO hace

No añade un átomo de capacidad, no toca la IR ni `ir_validate`, no toca ningún backend y no
define semántica en un backend (la referencia sigue siendo normativa). No permite `for` sobre
una **expresión** (`for c in s[0]`, `for x in f()` siguen siendo `SYNTAX`) ni sobre un rango de
enteros. No convierte la variable del `for` en alias del byte (§4.5 sigue valiendo: es copia).
No toca `isyco/`: si esta decisión hubiera requerido tocar el engine, algo estaría mal.

## Claims

| claim | estado | dónde |
|---|---|---|
| `for` sobre un lugar `str` coincide con su `expected` en la referencia y en los cinco backends | **DEMONSTRATED** (RELEASE_GATE) | F2 216/216 (`run_2026-11-01T210445Z.json`) + F5 216/216 en los cuatro completos y COBOL 147/216 con 69 `UNSUPPORTED` (`gate_2026-11-01T225011Z.json`) + F4 216/216 en cuatro combinaciones (`gate_2026-11-01T211424Z.json`) |
| La cota es la longitud del valor, no la capacidad | **DEMONSTRATED** | `444` + tres capacidades dando 22 pasos + el `while` con capacidad revienta |
| La variable del `for` sobre `str` es `u8` copia | **DEMONSTRATED** | `446` (`65 65 65 97`), `TYPE_MISMATCH` sin cast |
| El azúcar no cuesta pasos: 22 / 27 / 22 como su gemelo | **DEMONSTRATED** | `PASOS_EXIGIDOS`, medido |
| La IR del `for` sobre `str` es la IR del gemelo | **DEMONSTRATED** | F3 432/432; IR podada idéntica en los tres pares |
| Ninguna capacidad nueva | **DEMONSTRATED** | `features_of` iguales al gemelo; COBOL pierde `ir0.2,str` en azúcar y gemelo |
| El `str` pelado de V6 se recorre con `for` | **DEMONSTRATED** | `445` con stdin, 27/27 pasos |
| Ningún programa `0.1`–`0.4` cambia de significado | **DEMONSTRATED** | recabezado a `0.4` ⇒ `SYNTAX`; los 213 anteriores byte a byte iguales |
| Sabotear `len` de un `str` se detecta | **DEMONSTRATED** | test de mutación + 6 `CONTROL FALSO` y `--write` sin sellar (medido y revertido) |
| §4.4 deja de ser `[D]` y tiene la regla escrita | **DEMONSTRATED** | `spec/CORE_v0.5.md` §4.3/§4.4/§11/§12 |
