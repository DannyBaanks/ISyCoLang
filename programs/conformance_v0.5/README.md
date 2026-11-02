# `programs/conformance_v0.5/` — corpus **activo**: 48/48 coinciden con su `expected`

Los `expected` de este directorio se escribieron a mano el **2026-10-30** (commits
`dd561c6` y `0e9ca79`, que no tocan ningún archivo de `isyco/`), antes de implementar
ninguna decisión V1–V7 de `spec/CORE_v0.5_propuesta.md`.

**Corrección 2026-10-31.** Cuando se escribió el README, ningún caso corría: los siete
sin strings los rechazaba la cabecera (`isyco/parser.py:12`, `SYNTAX at 1:1`) y los tres
con strings tropezaban antes, en el léxico (`isyco/lexer.py:64` solo encendía `"…"` para
`0.3`/`0.4`). Eso ya no es cierto. Con V6, V6-bis, V7, V1 y V2 implementados y sellados,
los **42** casos del directorio coinciden en `status`, `code`, `emits` y `return` con su
`expected` a mano, medido contra la referencia de este árbol:

    python3 - <<'PY'   # 42/42 IGUAL (2026-10-31)
    from isyco import run
    from isyco.conformance import COMPARED, load_corpus
    from pathlib import Path
    for c in load_corpus(Path("programs/conformance_v0.5")):
        got, _ = run(c["program"], c["input"], c.get("limits"))
        print(c["name"], {k: got[k] for k in COMPARED} == c["expected"])
    PY

**Alta del caso `443` (2026-11-01).** Con el `443_m4_modulo_v04/` el directorio tiene 43
casos y el mismo bucle de arriba da **43/43 IGUAL**. El `expected` se transcribió de la
regla (`isyco/modules.py:48-52`: la cabecera del módulo tiene que coincidir con la de la
raíz) antes de correrlo; los dos controles que lo rodean se corrieron en memoria con el
mismo par de archivos y solo la cabecera cambiada:

| raíz | módulo | observado |
|---|---|---|
| `0.5` | `0.4` | `INVALID_PROGRAM(VERSION_MISMATCH)` — el caso del corpus |
| `0.5` | `0.5` | `HALTED`, `return 2`, 4 pasos — lo único defectuoso era la cabecera |
| `0.4` | `0.5` | `INVALID_PROGRAM(VERSION_MISMATCH)` — la regla es simétrica |

Los cuatro casos con módulos —`408_qname_arreglo/`, `421_marca_entre_modulos/`,
`440_llamada_calificada_void/` y `443_m4_modulo_v04/`— tienen que leerse con
`load_corpus`, que arma el `Bundle` del directorio: tomar `main.isy` como bytes sueltos
devuelve un falso `UNKNOWN_MODULE`. La población del directorio es 44 programas a un
archivo + 4 carpetas = **48** (los 43 de `443`, los tres de N1 y los dos de P4); un
`glob("4*.isy")` sobre la raíz se queda en 44 y esa es la cuenta que el censo de P4 hizo
mal la primera vez (`docs/EVIDENCE_MATRIX.md`, hallazgo 2).

**Alta de los casos `444`–`446` (2026-11-01, N1).** `for` sobre un `str` pasa a ser
normativa con tres casos y sus gemelos (`docs/decisions/N1_FOR_SOBRE_STR.md`); con ellos el
directorio tiene 46 casos y el mismo bucle de arriba da **46/46 IGUAL**. El `expected` está
transcrito de la regla —«`len(s)` vueltas, la variable es `u8` copia»— y no del stdout: la
conducta ya existía en la referencia y se midió antes de escribir los casos.

| caso | qué fija | gemelo | pasos medidos |
|---|---|---|---|
| `444_for_sobre_str` | la cota es la **longitud del valor**, no la capacidad: `str<8>` con `"hola"` emite 4 bytes, no 8 | `gemelos/444_while.isy` (`0.4`) | 22 y 22 |
| `445_for_str_pelado_stdin` | N1 × V6: un `str` pelado recorre lo que le llega por stdin (`"mundo"` → 5 bytes, `len` 5) | `gemelos/445_while.isy` (`0.5`) | 27 y 27 |
| `446_for_copia_str` | la variable del `for` sobre `str` es copia: `65 65 65` y `s[0]` sigue dando `97` | `gemelos/446_while.isy` (`0.4`) | 22 y 22 |

El gemelo de `445` lleva cabecera `0.5` porque el `str` pelado en parámetro es V6 y en `0.4`
no existe; los otros dos se escriben en `0.4` porque `len` de un `str` y `s[i]` son de v0.3.
Trazas `stmt` e IR podada: idénticas caso por caso (21, 26 y 21 filas). En `445` la cadena
completa tiene que declarar `!emit` —si `main` no lo declara el checker tira
`UNDECLARED_EFFECT` nombrando a `main`— y eso ya era regla antes de N1.

**Alta de los casos `447`–`448` (2026-11-02, P4).** El tope de especializaciones por
definición (CORE v0.5 §7, `docs/decisions/P4_SPEC_LIMIT.md`) entra con dos casos y el mismo
bucle de arriba da **48/48 IGUAL**. El `expected` de `447` se escribió desde la regla —«256
por definición como máximo»— antes de correr nada; lo único medido antes es una propiedad de
`spec_name` que ya fijaron `414`/`415`: que 257 `let` con capacidades distintas son 257
resoluciones, no una. Medidos después, ambos coinciden.

| caso | qué fija | gemelo | observado (referencia) |
|---|---|---|---|
| `447_tope_de_especializaciones` | 257 resoluciones de **una** definición son `INVALID_PROGRAM(SPEC_LIMIT)`: 0 emits, 0 pasos, y no baja a la IR ni llega a ningún backend | no lo tiene: no hay forma equivalente sin `str` pelado | 9 106 bytes, rechazado al contar la resolución 257, 14,0 ms en la referencia |
| `448_dieciseis_clones_por_definicion` | el piso legal, en la forma que justifica la granularidad: dos ranuras peladas × 4 anchos = **16 copias de una sola definición** (el máximo del censo era 2) | no lo tiene: un `while` escrito a mano no crea especializaciones | `HALTED`, `105…408`, 859 bytes, **49 pasos** |

Los dos `expect.json` no nombran `at` (`conformance.py:9 COMPARED` no lo compara): al `447`
no le importa cuál llamada es la 257, solo que existan 257. El **borde exacto 255/256/257 no
vive aquí** sino en `tests/test_specialize.py::TopePorDefinicion` y en la sonda, porque un
caso de corpus con 256 clones es legal bajo el tope y **Zig no lo compila** (`evaluation
exceeded 1000 backwards branches`, medido con 4 ranuras): el corpus fija el exceso y un piso,
la cifra la fijan el checker y la sonda. Lo que pasaría si ese caso entrara aquí está medido y
nombrado en `docs/EVIDENCE_MATRIX.md` (hallazgo 13): `tools/backend_gate.py:51` no captura el
`RuntimeError` del backend, así que no enrojecería F5 — lo abortaría sin dejar `gate_*.json`.
Las cuatro altas anteriores siguen valiendo caso por caso —ningún `expected` ni hash congelado
se reescribió.

| archivo | qué fija | decisión | hoy (referencia) |
|---|---|---|---|
| `401_len_arreglo` | `len([T; N])` → `N` | V1 | `HALTED`, `5`, 6 pasos |
| `402_for_decimales` | `for` sobre arreglo de structs | V2 | `HALTED`, `3.85`, 18 pasos — COBOL dice `UNSUPPORTED(ir0.2,str,struct)` |
| `403_for_enteros` | `for` sobre arreglo de enteros | V2 | `HALTED`, `17`, 23 pasos |
| `404_for_break_continue` | `break`/`continue` dentro de `for` | V2 | `HALTED`, `2 3 7 → 3`, 38 pasos |
| `405_for_copia` | la variable del `for` es copia, no alias | V2 + V4 | `HALTED`, `1 3 → 2`, 20 pasos |
| `406_len_parametro` | `len(a)` como cota del `while` gemelo | V1 | `HALTED`, `21`, 27 pasos |
| `407_parametro_reasignable` | asignar a un parámetro no muta al llamador | V4 | `HALTED`, `41 → 42`, 8 pasos |
| `408_qname_arreglo/` | `[modulo.Tipo; N]` | V5 | `HALTED`, `9.00`, 7 pasos |
| `409_str_cualquier_capacidad` | `str` sin capacidad en un parámetro | V6 | `HALTED`, `104 97 → 4`, 8 pasos |
| `410_str_vacia_reutilizable` | la misma utilidad sirve con la cadena vacía | V6 | `HALTED`, `true false → false`, 10 pasos |

`411`–`428` (V6), `429`–`438` (V6-bis), `439`–`442` (V7) y `443` (M4 generalizada, N2 en
`docs/OPEN_QUESTIONS_P1_P4.md`) se agregaron con sus propias
decisiones: `docs/decisions/V6_CONTEXTUAL_STR.md`, `docs/decisions/V6B_CONTEXTUAL_RETURN.md`
y `docs/decisions/V7_CONTENT_CAPABILITIES.md`. `444`–`446` son N1 (`for` sobre `str`),
decidida y sellada el 2026-11-01 en `docs/decisions/N1_FOR_SOBRE_STR.md`; `447`–`448` son P4
(tope de especializaciones por definición), decidida y sellada el 2026-11-02 en
`docs/decisions/P4_SPEC_LIMIT.md`.

## `gemelos/`

`403_while.isy`, `404_while_incremento_arriba.isy`, `404_while_incremento_abajo.isy`
y `405_while.isy` están escritos con la cabecera `isyco 0.4` y **corren hoy**. A ellos se
les sumaron el 2026-11-01 `444_while.isy` y `446_while.isy` (también `0.4`) y
`445_while.isy`, que es el único gemelo con cabecera `0.5`. Sirven
a dos cosas:

1. son la prueba ejecutable de que los esperados `17`, `2 3 7 → 3` y `1 3 → 2` no se
   copiaron de ningún resultado nuevo, y
2. fijan los `steps` que el azúcar V2 reproduce: medidos el 2026-10-31, el `for` gasta
   **23, 38 y 20** — los mismos que su gemelo — y su IR es idéntica a la del gemelo tras
   podar posiciones y el nombre del índice sintético. Lo mismo, medido el 2026-11-01 sobre
   los tres gemelos de N1: **22, 27 y 22** pasos, trazas e IR podada iguales.

`404_while_incremento_abajo.isy` es el **control negativo**: es el azúcar V2 escrito
como «`while` con el incremento al final del cuerpo», y su `continue` salta el avance.
Termina en `LIMIT_REACHED(max_steps)` con `emits=["2","3"]`. Por eso la desugaring de
V2 pone el incremento **antes** del cuerpo. Sabotear `for_stmt` con esa forma produce
hoy 12 `CONTROL FALSO` en la sonda y ninguna evidencia sellada.

## Dónde se mide

- Propuesta (las diez columnas «hoy» de 2026-10-30 y los cuatro gemelos):
  `python3 tools/v05_proposal_probe.py` →
  `evidence/v05_propuesta/run_2026-10-31T001600Z.txt`   # sha256 3b7285a5…
- Revalidación V1/V2 (tres vías, gemelos, no regresión, auto-falsación, forma de la IR):
  `python3 tools/v05_revalida_probe.py --casos 401,402,403,404,405,406 --write` →
  `evidence/v05_revalida/`
- El directorio **está dentro de `CORPORA`** (`isyco/conformance.py:13`) desde `57f38bc`
  (2026-11-01): los 42 casos forman parte del gate de backends, que pasó de 170 a **212**.
  Referencia `212/212`; C, Rust, Zig y pydecimal `212/212`; COBOL `146/212` con 66
  `UNSUPPORTED` que nombran la capacidad que exige cada programa. Los 170 de siempre no se
  movieron: de esos 66, **21** son casos ≥`401` y **45** son exactamente los que declaraba
  COBOL con el corpus de 170 (`gate_2026-10-31T200602Z.json`: 125/170, 45 `UNSUPPORTED`).
  Recibo `evidence/backends/gate_2026-11-01T015245Z.json`.
- **Segunda corrida el mismo día (`443`, commit `a4f608c`):** con el caso nuevo la población
  es **43 / 213** y los cuatro gates se re-corrieron sobre el árbol commiteado, en un solo
  lote y todos `PASS`: referencia `213/213` (`evidence/conformance/run_2026-11-01T074055Z.json`),
  IR `426/426` sobre 145 programas bajados (`evidence/ir/gate_2026-11-01T074055Z.json`),
  F4 `213/213` en las cuatro combinaciones con sanitizers (`evidence/c/gate_2026-11-01T074655Z.json`)
  y F5 con c/rust/zig/pydecimal `213/213` y COBOL `147/213` con los mismos 66 `UNSUPPORTED`
  nombrados (`evidence/backends/gate_2026-11-01T082046Z.json`): `443` se rechaza en el
  frontend, así que no suma capacidad ni resta ninguna y COBOL lo cuenta como pasado. Ninguno
  de los 170 anteriores se movió.
- **Tercera corrida el mismo día (N1, commits `00bc5a3`/`0224002`):** con `444`–`446` la
  población es **46 / 216** y los cuatro gates se corrieron sobre el árbol commiteado `2499fae`
  (el sello de la sonda con la matriz de N1) en un solo lote: referencia `216/216`
  (`evidence/conformance/run_2026-11-01T210445Z.json`), IR `432/432` sobre **148** programas
  bajados —los tres nuevos sí bajan; su IR es la de su gemelo—
  (`evidence/ir/gate_2026-11-01T210450Z.json`), F4 `216/216` en las cuatro combinaciones con
  sanitizers (`evidence/c/gate_2026-11-01T211424Z.json`) y F5 `PASS` con c/rust/zig/pydecimal
  `216/216` y COBOL `147/216` con **69** `UNSUPPORTED` (`evidence/backends/gate_2026-11-01T225011Z.json`,
  sha `63d7a9b4…`, `git_head=6c00225`): los tres casos entran en la lista de COBOL con
  `ir0.2,str` —la regla de contenido de V7 sobre un programa con `str`, no un rechazo del
  azúcar— y suben el conteo de 66 a 69 tal como estaba predicho. Los 213 anteriores no se
  movieron: las filas del recibo de referencia salen byte a byte iguales.
  F5 es el único que no comparte head con el resto del lote: su corrida en `2499fae` dio
  `FAIL` por un `TIMEOUT` del arnés en el diferencial de strings de pydecimal, el recibo se
  preservó (`gate_2026-11-01T215718Z.json`) y el `PASS` de arriba es la re-corrida sola, con
  la misma pasada de 1 270 casos en 0 diferencias.
