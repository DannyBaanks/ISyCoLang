# Matriz de evidencia

Inventario de qué está sellado, dónde, y con qué árbol de código. Existe porque
`tests/test_evidence.py` puede verificar que un recibo no se tocó, pero **no puede**
verificar que una frase escrita en un `.md` tenga recibo: esa comprobación la hace esta
matriz a mano. Cuando una afirmación no tiene fila aquí, o tiene un comando que la
re-produce o es prosa.

**Reglas de lectura.**

- Un recibo `RELEASE_GATE` significa `arbol_sucio_codigo=false`: ni el engine, ni el
  corpus, ni las pruebas estaban modificados cuando corrió. `EVIDENCE_ONLY` es el mismo
  dato con el árbol de código sucio — sirve como referencia, no como gate.
- Las rutas de recibo son relativas al repo. Cada `evidence/<dir>/SHA256SUMS.txt` guarda
  nombres **sin carpeta**, así que se verifica **desde adentro** del directorio:
  `(cd evidence/c && sha256sum -c SHA256SUMS.txt)`. Desde la raíz falla con «No existe el
  archivo». Volver a verificarlo el 2026-11-03: hay **22** listas (16 en `evidence/`, `spec/`
  y los cinco `programs/conformance*/`), las 22 pasan desde adentro —615 archivos— y
  las 22 fallan desde la raíz. La única lista que sí corre desde la raíz es
  `docs/origin/SHA256SUMS.txt` (2/2). `programs/dogfood/` no tiene lista (no es corpus
  congelado) y `tests/test_evidence.py` resuelve las rutas él mismo, por eso no depende
  del `cwd`.
- `git_head` se abrevia a 7. Un recibo viejo sigue siendo válido para el árbol que fija.
- Los cuatro recibos de la población **213** (`a4f608c`, el commit que metió `443`) salen de
  **una sola corrida en lote**, en ese orden: `run_conformance`, `ir_gate`, `c_gate`,
  `backend_gate`. El stdout sellado de cada uno es la **sección verbatim** de ese log —
  incluye la línea `### herramienta ###` y su `EXIT_<herramienta>=N`, que son del lote y no
  de la herramienta, y son el registro del código de salida. El log completo vivió en `/tmp`
  y no es evidencia canónica; lo canónico son los cuatro `_stdout.txt` sellados.
- Lo mismo con los cuatro de la población **216**, en el mismo orden y los cuatro con
  `git_head=2499fae` (el sello de la sonda con la matriz de N1). Ojo con el campo **hasta ese
  lote**: `tools/c_gate.py` escribía el head al **final** de su corrida y `tools/backend_gate.py`
  al **inicio**, así que en 216 entraron commits *mientras* medía F5. Que los cuatro coincidan
  no era una cortesía del instrumento: se verificó por hash (hallazgo 8). Desde el arnés
  endurecido los cuatro gates calculan sello, `git_head` y `veredicto_arbol` **al inicio**
  (`tools/c_gate.py:84` y `:89`, `tools/backend_gate.py:299` y `:305`, por `tools/_gate.py:155`)
  y F4 añade `git_head_end` al terminar (`tools/c_gate.py:178`): un recibo dice dónde empezó y
  puede demostrar si el árbol se movió mientras medía.
- **F5 no quedó en ese lote.** Su corrida de `2499fae` salió `FAIL` por un `TIMEOUT` del
  arnés (`gate_2026-11-01T215718Z.json`), se preservó el recibo y se re-corrió sola: el
  `PASS` es `gate_2026-11-01T225011Z.json` con `git_head=6c00225`. En esa segunda corrida el
  árbol tenía modificaciones **solo en `docs/` y `spec/CORE_v0.5.md`** —que la herramienta no
  lee, lee `programs/**/*.isy` y sus `expect.json`— más el `README.md` del corpus v0.5, que
  tampoco es un programa. El `PASS` no comparte head con F2/F3/F4 y está dicho en la tabla.

## Gates

| gate | recibo más reciente | head | veredicto | cifras |
|---|---|---|---|---|
| F2 — referencia contra el corpus | `evidence/conformance/run_2026-11-03T003813Z.json` | `026db0f` | `PASS` | 218/218 en los cinco corpus, en **0,318 s** medidos. Cotejo hoja por hoja contra el lote anterior (`run_2026-11-02T070428Z.json`, `14b19a9`): 3 045 hojas compartidas, **2** distintas —`generated_utc` y `git_head`, el sello—, **5 altas** (`arbol_sucio_codigo`, `veredicto_arbol` y las tres hojas de `harness`: `guarda`, `codigos=[HARNESS_INTERNAL]`, `capas=[corrida]`) y **0 bajas**: el arnés endurecido no mueve ni una cifra del corpus ni de sus 218 renglones. Del recibo que reemplaza queda lo que fijó: `447` alto como `INVALID_PROGRAM/SPEC_LIMIT` y `448` con 16 emisiones `HALTED`, sobre 2 727 hojas compartidas con `run_2026-11-01T210445Z.json` de las que solo diferían `total`, `passed` y el sello |
| F3 — ISY-IR vs referencia | `evidence/ir/gate_2026-11-03T003813Z.json` | `026db0f` | `PASS` | 436/436 comparaciones iguales sobre **149** programas bajados (`448` sí baja; `447` no: se compara su rechazo), en **0,685 s**. La celda del veredicto **deja de ser un guion**: `ir_gate` ahora declara `verdict`. Cotejo contra `gate_2026-11-02T070428Z.json`: 3 494 hojas compartidas, **2** distintas (el sello), **6 altas** (`verdict`, `arbol_sucio_codigo`, `veredicto_arbol` y las tres de `harness`) y **0 bajas**. Del recibo que reemplaza queda lo que fijó con el índice correcto —caso **y** nivel de traza, porque cada renglón ocupa dos líneas—: 3 462 hojas compartidas sobre 432 renglones con 5 distintas (los contadores `432→436` y `148→149` más el sello) y cero diferencias en los hashes de los 432 renglones previos; el número que estuvo escrito ahí antes, 1 734, era la mitad exacta de indexar solo por `name` —hallazgo 14 abajo— |
| F4 — backend C (tres vías + sanitizers) | `evidence/c/gate_2026-11-03T003814Z.json` | `026db0f` | `PASS` | 218 casos en las cuatro combinaciones (`gcc/plain`, `gcc/sanitized`, `clang/plain`, `clang/sanitized`), cada una con las tres vías expected ↔ referencia ↔ binario en 218/218, cero fallos y cero `UNSUPPORTED`; diferencial 24 612 corridas en `gcc/plain` (40 parejas por operación, semilla 20261028, 32 tipos, 0 diferencias) y 6 468 con sanitizers (4 parejas); los dos sabotajes detectados (12 y 53 diferencias); `missing_compilers: []`; **5 m 58 s** medidos. Primer lote con la guarda: `harness: []`, `no_medidos: 0` e `intentados: 218` en las cuatro combinaciones, `harness: []` con `omitted: 0` y `types_aborted: []` en los dos diferenciales, y `harness: []` con `not_run: false` en los dos sabotajes. Y primer lote con el **sello al inicio**: `git_head` y `git_head_end` valen `026db0f`, así que está medido que el árbol no se movió mientras medía —antes el head de F4 se escribía al final y no podía decir nada de la mitad de la corrida—. Cotejo contra `gate_2026-11-02T072103Z.json`: 53 hojas compartidas, **2** distintas (el sello), **31 altas** (12 del corpus: tres campos de arnés por combinación; 6 del difftest; 4 de los sabotajes; 6 del bloque `harness`; `git_head_end`; y las dos del árbol) y **0 bajas**. Poblaciones anteriores, todas `PASS`: 218 en `gate_2026-11-02T072103Z.json` (`14b19a9`), cuyo cotejo contra el recibo de 216 —F4 no guarda renglones por caso, solo contadores por combinación— dio 42 hojas compartidas y 14 distintas: doce contadores `216→218` y el sello, con los dos diferenciales, la semilla, los 32 tipos y los dos sabotajes idénticos; 216 en `gate_2026-11-01T211424Z.json` (`2499fae`) y las seis que se enumeran renglón a renglón en `docs/BACKEND_C.md` |
| F5 — contrato `ISY_BACKEND/1` | `evidence/backends/gate_2026-11-03T004412Z.json` | `026db0f` | `PASS` | c/rust/zig/pydecimal **218/218** con 0 `UNSUPPORTED`; cobol **148/218 con 70 `UNSUPPORTED`** nombrados y 0 fallas; 8 484 corridas diferenciales por backend y 1 270 de strings en los cuatro completos, todas sin diferencias; `does_the_work` en los cinco; los tres sabotajes detectados en cada uno de los cuatro (cobol solo dos: no tiene `str`); `missing_toolchains: []`; **42 m 25 s** medidos. Con la guarda puesta, la cifra que importa es la que no se ve: **cero hojas `harness` en las cuatro piernas y en los tres sabotajes de los cinco backends, `no_medidos: 0`, `completado: true` en los cinco y `abortado` ausente del recibo**, así que `not_run` no aparece ni una vez. stdout crudo sellado al lado: `gate_2026-11-03T004412Z_stdout.txt`. Cotejo contra `gate_2026-11-02T081912Z.json`: 424 hojas compartidas, **25** distintas —21 son `generated_utc`, `git_head` y 19 campos de costo (`wall_ms_total`, `user_ms_total`, `sys_ms_total`, `max_rss_kb_max`), que el propio arnés declara no semánticos; las otras 4 son un **renombrado** que quita ambigüedad: el sabotaje `str_concat_truncates` guardaba sus 15 diferencias de strings en `difftest_diffs`, y ahora ese campo es solo el diferencial **numérico** (0, que es lo cierto: truncar strings no toca la aritmética) mientras `difftest_str_diffs` lleva las 15 y `detected` sigue siendo `true`—, **86 altas** (33 de `harness` por pierna y sabotaje, 12 de `difftest_str_diffs`, 9 de `omitted`, 5 cada una de `completado`, `no_medidos`, `types_aborted` y `seleccionado`, 4 de `aborted`, 6 del bloque `harness` y 2 del árbol) y **0 bajas**. Ojo con el stdout: la línea de sabotaje resume `diferencial N` solo con el numérico, así que un sabotaje de `str` puede leerse como `diferencial 0` teniendo 15 diferencias de strings en el JSON. Anteriores en el mismo directorio: el **FAIL** de `gate_2026-11-02T235456Z.json` (`4bb9ab5`, 41 m 48 s) con el caso extra y su fila `TOOLCHAIN_BUILD_FAIL` —párrafo abajo—, luego `gate_2026-11-02T081912Z.json` (`14b19a9`, 218) cuyo cotejo contra `gate_2026-11-01T225011Z.json` dio 398 compartidas, 39 distintas —contadores, campos de costo y sello—, 2 altas que eran `448` entrando al `UNSUPPORTED` de cobol con `ir0.2,str` y 0 bajas; `gate_2026-11-01T225011Z.json` (`6c00225`, 216 casos, los tres de N1 entrando con `ir0.2,str` tal como estaba predicho), `gate_2026-11-01T082046Z.json` (`a4f608c`, 213) y antes `gate_2026-11-01T215718Z.json`, `FAIL` por `TIMEOUT` del arnés en el difftest de strings de pydecimal, preservado con su diagnóstico en `evidence/f5_flake/run_20261101T220854Z.json` y su reproduccion: 500 llamadas y dos pasadas de 1 270 con 0 diferencias. Que cobol pase de 147 a 148 **no** es una capacidad nueva: `447` es un rechazo del frontend y cuenta como `passed` en los cinco —hallazgo 12 abajo— |

**El FAIL del caso extra convive con el PASS del lote.** `tools/backend_gate.py`
acepta `--extra-case <ruta.isy>`: un caso **fuera** del corpus congelado, sin
`expect.json` porque `corpus()` compara el backend contra la referencia y nunca
contra un `expected`. Lo que se corrió es la fuente que cierra P4 por el lado
del toolchain —256 clones de una definición de 4 ranuras × 4 anchos, 10 906
bytes, sha `52a2803975...`—, legal bajo el tope y mortal para el comptime de
Zig. El recibo es `evidence/backends/gate_2026-11-02T235456Z.json` (`4bb9ab5`,
`RELEASE_GATE`, 41 m 48 s) y sale `verdict=FAIL` con **una** razón:
`backends/zig/corpus/harness` de una fila `TOOLCHAIN_BUILD_FAIL` con `case:
extra_zig_4x4`, `build_key 7443b5e8e72fb777f63cba72`, `ms: 1131.5` y la línea
`error:` del compilador en `detail`, mientras `failures` queda `[]` y
`no_medidos: 1`. Los otros cuatro backends corren el mismo caso sin morir: c,
rust y pydecimal `219/219`, cobol `148/219` con `extra_zig_4x4` entre sus 71
`UNSUPPORTED`. Las otras tres filas del recibo (una por sabotaje de zig) son el
mismo fuente muerto: la caché negativa no alcanza cuando el sabotaje cambia las
banderas, porque la clave del artefacto incluye las banderas. Antes de este
arreglo la corrida no terminaba: abortaba en ese caso 219 y no había
`gate_*.json` ni para los 218 anteriores. Queda sellado tal cual —el gate se
niega a pisar un archivo que exista (`tools/_gate.py:164`) y reescribe los
`SHA256SUMS.txt` con nombres pelados— y su stamp es el **más viejo** de los dos
del arnés endurecido, así que `latest()` lee el `PASS` de arriba y este FAIL no
lo tapa. La fuente va copiada al lado (`gate_2026-11-02T235456Z_extra_case.isy`)
porque `build/` está en `gitignore` y sin copia el `program_sha256` del recibo
no apuntaría a nada comprobable.

**La sonda que demuestra la guarda, y no solo el gate.**
`evidence/f5_harness/run_2026-11-02T233718Z.json` (`8df68b8`, `RELEASE_GATE`,
`arbol_sucio_codigo: false`) es `tools/f5_harness_probe.py --write` sobre la
misma fuente, con **siete claims DEMONSTRADO** y su stdout crudo, la fuente
`.isy`, el `.zig` emitido (310 088 bytes, sha `7cdc036863...`, sellado por lo
mismo de `build/`) y el stderr del compilador al lado. No es un gate: es la
prueba de que el fallo es **dato** y de que el dato es reproducible. Los dos
que no se leen del JSON anterior: C1 recomponer la `build_key` a mano desde
nombre, versión y fuente y que coincida con la de la fila; C4 que el mismo
fuente muerto no vuelve a invocar el compilador —1 079,283 ms el primer intento
contra 0,905 ms el segundo, con el mismo stderr—, y C5 que el `zig build`
crudo, sin la guarda en medio, dice la misma línea y sale con `exit 1`, o sea
que la CLI no entrega `status` ni `code` del contrato cuando muere el
toolchain. C2 afirma que un rechazo del frontend **sube** como
`InvalidProgram` (la guarda no se lo traga), C3 que la referencia y los backends
instalados coinciden en esa fuente (`HALTED`, `return 0`, 770 pasos, 256 emits;
c/rust/pydecimal iguales, cobol `UNSUPPORTED`, zig con la fila), C6 que 16
clones de la misma definición **sí** compilan en Zig —la frontera es del
compilador, no del idioma— y C7 que una fila en cualquier pierna vuelve
no-conforme al backend aunque `failures` y `diffs` estén vacíos. El caso
**no entró al corpus** (decisión de Danny): la población del gate sigue siendo
218 y el raro deja recibo propio.

**Hueco de F4 — CERRADO el 2026-11-01.** Existió así: F4 no se había re-corrido desde que
`conformance_v0.5` entró en `CORPORA`, así que su recibo más reciente (`ec6b823`) fijaba 170
casos, no 212; los 42 nuevos estaban cubiertos por F5, que incluye a C sobre los 212, pero
la vía de F4 con sanitizers (`gcc/sanitized`) no había corrido sobre ellos. Se cerró con
`python3 tools/c_gate.py` sobre el commiteado `422719a`, árbol limpio: **212/212 en las
cuatro combinaciones**, 0 `UNSUPPORTED`, 0 diferencias en las 31 080 corridas diferenciales
y los dos sabotajes detectados. El recibo anterior sigue siendo válido para el árbol que
fija; lo que cambió es el más reciente.

## Decisiones de CORE v0.5

| decisión | recibo | head | veredicto | qué fija |
|---|---|---|---|---|
| V1 (`len` en posición de i) | `evidence/v05_revalida/run_20261101T001608Z.json` | `dcd6880` | `RELEASE_GATE` | `401`–`406` contra `expected`, IR igual al gemelo, brazos viejo y nuevo |
| V2 (azúcar `for`) | el mismo recibo (`gemelos`, `no_regresion`) | `dcd6880` | `RELEASE_GATE` | traza `stmt` del `for` igual a la del `while` gemelo salvos `at`, y `pasos.azucar == pasos.gemelo` caso por caso; los valores **exigidos** (23/38/20) viven en `tests/test_v05_core.py:105` |
| V3, V4, V5 (léxico, parámetro reasignable, forma del `elem_type`) | `evidence/v05_spec/run_20261101T043007Z.json` | `a9a17bc` | `RELEASE_GATE` | 4 cabeceras del léxico; 11 formas del iterando; 4 programas a forma constante (24 pasos) con su control de forma (20) |
| V6 y V6-bis (`str` contextual) | `evidence/v05_v6/run_20261031T184709Z.json` | `f856d55` | `RELEASE_GATE` | 28 casos `411`–`438` diferenciales: 123 EQUIV, 17 `UNSUPPORTED` (COBOL por etiqueta), cero DIVERGENT |
| V7 (capacidades por contenido) | `evidence/v05_v7/run_20261031T200146Z.json` | `a66689c` | `RELEASE_GATE` | 118 módulos del corpus congelado en dos brazos, brazo viejo FIEL, conteos 113→125 en COBOL, canario `439` |
| Borrador normativo v0.5 | `evidence/v05_spec/run_20261101T153344Z.json` | `a4ef362` | `RELEASE_GATE` | las 6 matrices de aristas que el corpus no fija — las 5 de `run_20261101T043007Z.json` (`a9a17bc`, siguen válidas para su corrida) más la nueva del `let` sin anotación (§3, N3) |
| N1 (`for` sobre un `str`) | `evidence/v05_spec/run_20261101T210009Z.json` (sección 7) y el lote de gates `216` | `c536858` (sonda) / `2499fae` (gates) | `RELEASE_GATE` | la cota es `len(s)` del **valor** y no la capacidad (`444`: `str<8>` con `"hola"` emite 4 bytes), la variable es `u8` **copia** (`446`: `65 65 65 97`), el `str` pelado de V6 se recorre (`445` por stdin, 5 bytes); pasos e IR idénticos a su `while` gemelo (22/27/22, F3 432/432) y ninguna capacidad nueva (`features_of` igual al gemelo) |
| Censo y forma de P4 | `evidence/v05_p4/run_20261101T234407Z.json` | `6ebb00d` | `RELEASE_GATE` | 33 clones en 19/46 casos (27 V6 + 6 V6-bis, 13 definiciones); curvas K, W², W³; control de 20 sitios → 1 clon; sin techo hasta 2048 **en las dos vías que la sección `costo` medía: referencia y C**. Zig sí tenía techo por debajo de esa cota y se midió al cerrar P4 — ver la fila siguiente—. Las dos corridas anteriores siguen válidas para su población: `run_20261101T154040Z.json` (`2938c01`, 32 en 18/43) y `run_20261101T062234Z.json` (`52f5564`, sobre 42) |
| P4 (tope de especializaciones) | `evidence/v05_p4/run_20261102T085025Z.json` (R2) + lote de gates `218` | `d363e7c` | `RELEASE_GATE` — árbol limpio; **R1** (`run_20261102T081925Z.json`, `203f579`) salió `EVIDENCE_ONLY` con `arbol_sucio_codigo=true` por la documentación de este lote a medio editar mientras corría, con `isyco/` y `tools/` intactos; se conservó sin retocar (`5965bd2`) y se re-selló limpia la R2, que **repite R1 hoja por hoja**: 1 135 hojas compartidas, 118 distintas —114 campos de tiempo y las 4 del propio sello—, cero diferencias estructurales | 256 resoluciones por definición dentro del programa, la 257 es `SPEC_LIMIT` estático y no baja a IR; censo re-medido con la decisión dentro: **49 clones en 20/48 casos**, 14 definiciones, máximo 16 (el caso `448`) y **2** sin los casos de tope — esa sigue siendo la base del número —; `512`/`1024`/`2048` ya no son construibles (`chequeo=SPEC_LIMIT`, `resoluciones_max=257`, `clones=0`); matriz `aridad × ancho` contra c/rust/zig y su bisección; librería real sintetizada en tres módulos: 58 clones con ocho anchos por pool y ninguna definición pasa de 6 |

## Preguntas y puntos nuevos

| id | estado | recibo o falta |
|---|---|---|
| P1 (`at` del azúcar) | cerrada | `evidence/v05_revalida/run_20261101T001608Z.json` + test `ForAzucar` |
| P2 (`for` sobre literal de arreglo) | cerrada: no | `evidence/v05_spec/run_20261101T153344Z.json` §4 |
| P3 (nombres e identidad) | cerrada | el mismo recibo §6 (`411`/`417`/`420`) + `tests/test_specialize.py` |
| P4 (cota de especializaciones) | **cerrada el 2026-11-02 — regla, número y error nombrado** | `docs/decisions/P4_SPEC_LIMIT.md`; `447`/`448` en el gate de 218; `tests/test_specialize.py::TopePorDefinicion` (9 tests) y los dos sabotajes de P4 en `tests/test_reference.py`; base sellada `evidence/v05_p4/run_20261101T234407Z.json` (46 casos) y re-medida con la decisión dentro en `evidence/v05_p4/run_20261102T085025Z.json` (R2, `RELEASE_GATE`: 48 casos, 49 clones), cuya corrida del lote es `run_20261102T081925Z.json` (R1, `EVIDENCE_ONLY`) |
| Z1 (¿el techo de un toolchain es del idioma?) | **abierta desde 2026-11-02 — medición hecha, decisión no** | sección 6 y su bisección (`--bisect-zig`) en `evidence/v05_p4/run_20261102T085025Z.json` (R2; R1 da los mismos valores no temporales): 256 copias de una definición de dos ranuras compilan en C y Rust y revientan en Zig; frontera medida 250/252 (aridad 2), 164/168 (3), 120/128 (4). No tiene respuesta en el corpus ni en el checker: es de Danny |
| N1 (`for` sobre `str`) | **cerrada el 2026-11-01 — adoptada, por caso y por texto** | `programs/conformance_v0.5/444`–`446` con sus gemelos (`87bdfa7d…`, `1805ca9c…`, `b2e804e3…`); la regla escrita en `spec/CORE_v0.5.md` §4.4 y §7 sin el `[D]`; doce filas de formas en `evidence/v05_spec/run_20261101T210009Z.json` (`RELEASE_GATE` sobre `c536858`) |
| N2 (diagonal `0.5` de M4) | **cerrada por caso el 2026-11-01** | `programs/conformance_v0.5/443_m4_modulo_v04/` (`a4f608c`) con sus dos controles medidos; la matriz de 8 combinaciones sigue en `evidence/v05_spec/…` §1 |
| N3 (`let` sin anotación) | cerrada: por texto y por sonda | la regla estaba en `checker.py:205-209` y en el docstring; ya está en `spec/CORE_v0.5.md` §4.1 y medida en `evidence/v05_spec/run_20261101T153344Z.json` §3 (cuatro formas, tres sabotajes) |

## Evidencia de contexto (no es gate)

| directorio | qué | cuándo |
|---|---|---|
| `evidence/v05_propuesta/` | las mediciones que reordenaron v0.5 (diez → doce sitios de versión) | 2026-10-31, head `4688517` |
| `evidence/dogfood/` | `programs/dogfood/` contra los cinco backends y su pared de tiempo | 2026-10-30, head `b0daac5` |
| `evidence/textlib/` | la librería de texto que motivó V6/V6-bis (`pad`, `mayus`, desbordamiento) | 2026-10-31, head `e94bb84` |
| `evidence/human_guide/` | transcripción de una persona operando `GUIA.md` sin ayuda | 2026-10-30 |
| `evidence/inventory/` | inventario de `workspace/assembly` (solo lectura) y toolchains | 2026-10-28/29 |

## Afirmaciones que no son evidencia

Viven en `README.md`, `GUIA.md` y `tests/README.md`, y se re-producen con un comando — no
tienen recibo porque un recibo de ellas sería una foto de un día:

| afirmación | comando |
|---|---|
| «194 tests OK» y el tiempo de la suite | `python3 -m unittest discover -s tests` |
| «sha256sum -c de `docs/origin/` coincide» | `sha256sum -c docs/origin/SHA256SUMS.txt` desde la raíz del repo |
| conteos de `SUPPORTED`, llamadas a `has()` y sitios de versión | `grep -n` de `spec/CORE_v0.5.md` §0, fijados como test en `tests/test_versions.py` |

## Auditoría 2026-11-01

Qué encontró esta matriz al cotejar prose contra recibos:

1. **El censo de P4 no estaba en ningún recibo.** `V6_CONTEXTUAL_STR.md` y
   `V6B_CONTEXTUAL_RETURN.md` atribuían «22 clones» y «28 clones, máximo 2 por definición»
   a `evidence/v05_v6/run_*`, y esos recibos solo guardan el resultado de cada backend
   por caso. Medido desde el instrumento (`Checker.specs`): **32** clones en 18 de los 42
   casos (hoy 43, y la re-medición sobre los 43 da los mismos 32 clones en los mismos 18:
   `run_20261101T154040Z.json`), 26 V6 + 6 V6-bis, máximo 4 por programa, 2 por definición **dentro de un
   programa** pero **7 de `doble` en todo el corpus**. Las dos secciones y `ROADMAP.md`
   llevan la corrección fechada; el dato nuevo está sellado arriba.
   **Tercera re-medición, el mismo día con N1 dentro** (`run_20261101T234407Z.json`, sha
   `7d3bafba…`, `RELEASE_GATE` sobre `6ebb00d`, `load_corpus: 46 casos`): **33 clones en 19 de
   los 46**, 27 V6 + 6 V6-bis. El clon extra es `emite.16` de `445_for_str_pelado_stdin` —el
   `str` pelado que recorre—; `444` y `446` aportan **0**, así que el azúcar del `for` no clona
   nada por sí solo. Cotejo recibo-vs-recibo de las 43 filas compartidas: **idénticas en nombres
   y conteos**, y las secciones `curva_una_ranura`, `curva_dos_ranuras`, `curva_tres_ranuras` y
   `control_mismo_ancho` salen **byte a byte iguales** entre los dos recibos. Lo único que
   cambia son las dos columnas de tiempo de `costo`, fila por fila; para `K=2048` el recibo de
   las 15:40 mide `ref_ms 458,9` / `c_ms 986,1` y el de las 23:44 `ref_ms 470,8` / `c_ms 989,8`.
   Las columnas estructurales de esas mismas siete filas —`clones`, `fuente_bytes`, `ir_bytes`,
   `ir_funciones`, `pasos`, `c_equiv`, `control`, `chequeo`, `status`— son idénticas en las dos.
2. **Contar la población equivocada.** El primer censo usaba `glob("4*.isy")` y perdía los
   tres casos con módulos (`408`, `421`, `440`) — `421` es justo el de `util.marca.3` y
   `util.marca.4`; hoy son cuatro, con `443`. La sonda ahora itera `load_corpus`, la misma
   población del gate. Es el
   mismo clase de bug de deriva de población que V7 ya había cazado con el «corpus
   congelado» de 118.
3. **F4 con 170 mientras F5 tiene 212.** No era un error: era un gate que no se re-corré.
   Quedó escrito arriba en vez de suponerse, y **se cerró el mismo día** con 212/212 en las
   cuatro combinaciones (arriba, «Hueco de F4»). Lo que sí quedaba abierto —que este gate no
   tenía cifra atada a la suite— **se cerró el 2026-11-01**: `DocsMatchLatestEvidence` ya no
   se detiene en `conformance/`, `ir/` y `backends/`; `test_c_gate_figure`
   (`tests/test_evidence.py`) lee `latest("c", "gate_")`, exige `verdict=PASS`, cero fallos,
   cero `UNSUPPORTED` y las tres vías completas en cada combinación presente, exige cero
   diferencias en el diferencial y que los dos sabotajes se detecten, y reclama que el README
   cite la **población** del recibo más nuevo. Su primera mordida fue real y documentada: con
   `443` en el corpus el README seguía diciendo «sobre los 212» y el gate decía 213, así que
   la prueba enrojeció sola — es el control negativo, sin tocar ninguna evidencia.
4. **La segunda pasada encontró su propio fallo.** La fila «techo encontrado» de
   `docs/OPEN_QUESTIONS_P1_P4.md` decía «474 ms de referencia, 3,7 s de `c_ms`» citando el
   recibo `v05_p4`, y el recibo dice `ref_ms=508,7` y `c_ms=1037,0`: lo escribí de memoria
   tras la corrida sin re-leer el JSON. Corregido allí mismo con nota fechada. Es el
   hallazgo 1 reproduciéndose a sí mismo, y por eso el cotejo es un paso de la matriz, no
   una confianza: la fila nueva cita bytes y milisegundos exactos del `costo`.

5. **Renumerar la sonda rompe las citas a los recibos sellados.** Al meter la matriz del
   `let` como sección 3, las secciones viejas 3/4/5 pasaron a 4/5/6, y varias filas del docs
   citaban «`run_20261101T043007Z.json` §4» con la numeración nueva: apuntaban al recibo
   viejo, donde §4 es *pasos a forma constante* y no *el iterando*. Arreglado moviendo la
   cita al recibo que sí tiene esa numeración (`run_20261101T153344Z.json`). De paso la
   re-sello sirve de control de no-regresión sobre la propia sonda: comparando los dos
   `.txt` sección por sección, las cinco matrices viejas salen
   **byte a byte iguales** sobre los cabezales `a9a17bc` → `a4ef362`, y la sexta es la nueva.
   La comparación la hizo un script de un solo uso que no está versionado; se puede rehacer
   porque los dos `.txt` están sellados (trocear por las cabeceras `^\d) ` y cotejar los
   cuerpos con la numeración mapeada 1→1, 2→2, 3→4, 4→5, 5→6). Lo mismo vale para el cotejo
   del censo de P4 entre `run_20261101T062234Z.json` y `run_20261101T154040Z.json`, que se
   hizo campo por campo sobre los dos JSON.
   Un sello no es una foto inmóvil: re-correr la sonda y obtener lo mismo es parte del
   control.

6. **«24 pasos» no eran los del programa citado: eran los de un programa con llamada.**
   `spec/CORE_v0.5.md` §4.4 afirmaba que el `for` y su gemelo `while` gastaban 24 pasos y
   citaba el recorrido de `str<4> = "hola"`. Medido con ese programa en la forma de `444`
   —todo dentro de `main`— son **22**; los 24 son de la matriz de forma constante de la sonda
   (**§5**, no §4 como citaba el docs), cuyo recorrido vive **dentro de una función**: la
   diferencia no es el azúcar sino el marco de llamada, y el control Z de esa misma matriz ya
   estaba mostrando que cambiar la forma del cuerpo cambia los pasos. Es el hallazgo 1
   reproduciéndose dentro del spec. La corrección quedó en §4.4 con la razón medible, y el
   número **se volvió ejecutable**: `tests/test_v05_core.py:PASOS_EXIGIDOS` pinea 444 → 22,
   445 → 27, 446 → 22 y el test del gemelo los compara, así que la próxima deriva enrojece la
   suite en vez de quedar escrita en prosa. La sección nueva de la sonda entra como **§7**,
   appending, exactamente por el hallazgo 5: renumerar hubiera roto las citas a los cinco
   recibos sellados.
7. **El `unsupported` del gate no es el `missing_features` del frontend.** Al pre-validar los
   tres casos de N1 di con 71 programas COBOL sin soporte contando `missing_features` y el
   recibo decía 66: la diferencia son los casos que **rechaza el frontend antes de llegar al
   backend** (`244_input_str_too_long`, `245_input_struct_missing` = `INVALID_PROGRAM
   (BAD_INPUT)`). Esos cuentan como acuerdo, no como `UNSUPPORTED`, y no se les puede exigir
   un número de dominio. La pre-validación de una cifra de gate tiene que leerla del instrumento
   del gate, no de una función que parece la misma. Con N1 el conteo del gate pasa de 66 a 69
   porque entran tres programas con `str`.
8. **Un lote puede dejar commits dentro de la ventana de medición y hay que cerrarlo por
   hash.** Los cuatro recibos de la población 216 llevan `git_head=2499fae`, pero durante la
   corrida de F5 entraron `0224002`, `a3c344a`, `fcf925d` y `010e7c9` — o sea commits *después*
   de que el gate empezara a medir (`tools/backend_gate.py:107` fija el head al inicio;
   `tools/c_gate.py:118` lo fija al final). No se harmonizó el campo a mano. Se cerró con dos
   cotejos: (a) los **216** `program_sha256` del recibo de F2 están todos como blobs `.isy`
   commiteados en HEAD —medido con `git ls-tree -r HEAD programs/` + `cat-file`, cero
   ausencias—, y (b) `git diff --name-only 2499fae HEAD -- isyco/ programs/ tools/ spec/`
   devuelve exactamente cuatro archivos, y ninguno lo comen los gates:
   `gemelos/444_while.isy` (`load_corpus` no cuenta `gemelos/`), `programs/conformance_v0.5/SHA256SUMS.txt`,
   `spec/CORE_v0.5.md` y `tools/v05_p4_probe.py`. Mientras lo que el gate lee no se mueva, un
   commit de docs no altera lo medido — pero la prueba de eso es el hash y el `diff`, no la
   intención.
9. **Un gemelo cuya cabecera contradecía su propio comentario.** `gemelos/444_while.isy` decía
   en su comentario «cabecera 0.4: no necesita nada de 0.5» y tenía `isyco 0.5` en la primera
   línea. Medido en las tres cabeceras: `0.3`, `0.4` y `0.5` dan 22 pasos y la misma traza `stmt`
   (el `len` de un `str` es de v0.3), así que la promesa del comentario era la correcta y la
   línea, el error; se restauró `0.4` en `0224002`. No mueve la población del gate: `gemelos/`
   no lo cuenta `load_corpus` (`isyco/conformance.py:17-41`) — verificado antes de tocar, porque
   el punto de un gemelo es que *no* entre en el conteo.

10. **Un `TIMEOUT` del arnés se cuenta como diferencia y no es divergencia semántica.**
    F5 sobre la población 216 salió `verdict=FAIL` (`evidence/backends/gate_2026-11-01T215718Z.json`,
    sha `e1fc1c82…`, `exit=1`) por una sola marca: `pydecimal`, diferencial de strings,
    **1 de 1 270**. El registro `diffs[0]` dice `op="a + b"`, entrada `"x"×12` + `"y"×8`,
    referencia `HALTED` en 3 pasos, backend `status=TIMEOUT`, `stderr: null`. Reproducido en
    aislado (`evidence/f5_flake/run_20261101T220854Z.json`): 500 llamadas a ese caso dan
    **0 TIMEOUT** con `wall_ms` p50 38,4 / p99 50,0 / máximo 51,6, y el diferencial completo
    da **0 diferencias en dos pasadas** de 1 270 cada una (59,7 s y 48,0 s). Un caso de ~40 ms
    consumió los 60 000 ms del temporizador (`base.py:322-329`): tres órdenes de magnitud, o
    sea el fallo está en el camino de ejecución del arnés, no en la semántica de `str`. Dos
    mecanismos candidatos y **no se pudo discriminar**: estrella por contención —el host
    marcaba `load average` 9,8 con otros agentes corriendo (`agy`, dos `qodercli`)—, o el
    hazard documentado de `subprocess.Popen(preexec_fn=...)` en proceso multi-hilo
    (`base.py:309-330` lanza además dos hilos `drain` y un `Timer` por corrida), que puede
    colgar el `fork` antes del `exec`. Qué se hizo: el recibo `FAIL` se conserva y se commitea
    con su stdout verbatim, la sonda de diagnóstico queda hasheada al lado, se re-corré el gate
    y las dos corridas conviven en `evidence/backends/`, y **no se toca `isyco/backends/base.py`
    en este lote** — endurecer el arnés (timeout más largo, reintento, o quitar `preexec_fn`)
    es decisión aparte con su propia evidencia, y meterla de contrabando taparía que un gate
    puede enrojecer por starvation del host en vez de por el lenguaje. La re-corrida dio
    `PASS` (`gate_2026-11-01T225011Z.json`, sha `63d7a9b4…`; pydecimal 216/216 y sus 1 270 de
    strings en 0 diferencias, COBOL 147/216 con 69 `UNSUPPORTED`).
11. **Regenerar los `SHA256SUMS.txt` con `sha256sum ./*` cambia la convención de rutas y
    rompe un test que no mira el contenido.** El commit `010e7c9` (los tres recibos del lote
    216) reescribió `evidence/conformance`, `evidence/ir` y `evidence/c` con entradas `./x`
    donde antes había `x`. Los 32 digest son **los mismos byte a byte**; lo que cambió es el
    texto de la ruta, y `tests/test_evidence.py:55-63` compara el conjunto listádo contra
    `p.name` de disco — `./x` ≠ `x` —, así que `test_every_dir_has_sums_and_lists_every_file`
    enrojeció para tres directorios. Se detectó con la suite completa después del lote (6
    fallas: esta, `test_corpus_frozen` por el `README.md` del corpus sin re-hashear, y cuatro
    del `DocsMatchLatestEvidence` que leyeron el README a medio editar porque la suite corrió
    *mientras* se editaba). Arreglo: los tres archivos vuelven a nombres sin `./` y el corpus
    regenerado con `find`; verificado `sha256sum -c` **desde adentro** de cada directorio
    (11/11, 11/11, 10/10, 23/23 y 104/104 `OK`, cero `FAILED`) y `git diff` sobre los tres
    recibos = solo la columna de ruta. Lo que enseña: un test de integridad que compara
    *nombres* es sensible a cómo se invocó `sha256sum`, y correr la suite encima de una edición
    de docs produce falsos negativos que parecen hallazgos del cambio.
12. **Un rechazo del frontend cuenta como `passed` en los cinco backends, y eso es un punto
    ciego que hay que nombrar.** Al cerrar P4 con `SPEC_LIMIT` (`isyco/errors.py`, `IsyError` →
    `interp.run:381-385` lo convierte en `{status: INVALID_PROGRAM, code: …, emits: []}`) no hizo
    falta tocar ningún arnés: `tools/ir_gate.py:44` ya capturaba `InvalidProgram` para comparar el
    rechazo en vez de la IR, y `tools/warm_build_cache.py:34-36` ya saltaba esos programas. Pero
    `tools/backend_gate.py:47-61` **no distingue** quién rechazó: si los cinco devuelven el mismo
    documento, `passed += 1`, así que `447` entra como pasado también en COBOL —no porque COBOL lo
    soporte sino porque el frontend compartido lo mató antes de que existiera pregunta de
    capacidad—. El número del gate no afirma nada sobre ese renglón; lo que lo fija es
    `tests/test_backends.py::TopeFrontend` (los cinco `status`/`code` idénticos y **cero** líneas de
    `backend_stderr`, más la salida de la CLI). Lo que enseña: cuando un error nuevo es de
    frontend, la cobertura que hay que exigir está en el test que compara backends entre sí, no en
    el conteo del gate.
13. **Un fallo del compilador de un toolchain abortaba F5 y no dejaba recibo. CERRADO el
    2026-11-03.** Cerrar P4 obligó a construir un programa que el idioma acepta y Zig no compila:
    256 clones de una definición de cuatro ranuras es legal bajo el tope, y el compilador de Zig
    revienta su propio límite de comptime con `error: evaluation exceeded 1000 backwards
    branches`. De ahí que `448` lleve 16 clones y no 256, y de ahí que la sonda sí registre el
    fallo como dato (`tools/v05_p4_probe.py:538`, «el fallo es el dato») mientras el gate lo
    propagaba. Lo que no estaba en ningún recibo era el arnés. Medido sobre el árbol de aquel
    lote —`backend_gate.corpus(zig, [4 ranuras × 4 anchos])`—: `tools/backend_gate.py:51` llamaba
    a `backend.run(...)` dentro del bucle de `corpus()` sin `try`, `main()` (`:115`) tampoco lo
    envolvía, la única captura del archivo era la de `git_head()` (`:40-43`) y el JSON se escribía
    solo al final (`:146`), así que si el caso *k* rompía un compilador no había gate ni para los
    *k−1* anteriores: lanzaba `builtins.RuntimeError` («zig: el compilador falló: …») a los
    2 197 ms subiendo por `base.py:272` (`run`) ← `:238` (`_binary`) ← `:195` (`build`), y **no**
    era `InvalidProgram`, o sea que ningún `except` del arnés lo veía. `tools/warm_build_cache.py`
    capturaba solo `InvalidProgram` y solo alrededor del lowering (`:34-36`); la compilación real
    estaba en `:62`, sin guarda. **Arreglado en este lote, en tres capas**, cada una con su prueba:
    el **caso** (`isyco/harness.py:61`, `intento` devuelve resultado o fila y no lanza), la
    **pierna** (`tools/backend_gate.py:210`, `capa()` marca `not_run` cuando una fila cayó en
    medio) y la **corrida** (`tools/backend_gate.py:334`, `except Exception` guarda
    `report["abortado"]` y el `finally` sella igual). `base.py:216` lanza ahora
    `ToolchainBuildFailure` (`:37`, subclase de `RuntimeError`; nada en el repo hacía
    `except RuntimeError`, así que cambiar el tipo no le quitaba el manejo a nadie) y conoce la
    clave del artefacto, que la fila publica como `build_key` —recomponible a mano desde nombre,
    versión, banderas y fuente—; la caché negativa (`:197`) no vuelve a invocar un compilador que
    ya murió. El registro es una lista **hermana** `harness`, no una mezcla: `failures` y `diffs`
    siguen siendo solo divergencia semántica, y `tools/_gate.py:118` (`es_conforme`) pliega la
    hermana —una fila en cualquier pierna vuelve no-conforme al backend aunque los dos contadores
    estén vacíos, que es justo lo que `tests/test_harness.py` muerde—. Dos códigos
    (`TOOLCHAIN_BUILD_FAIL` y `HARNESS_INTERNAL`, `isyco/harness.py:25`) y un sello en el recibo
    (`harness.guarda = isyco.harness/1`): un recibo anterior al arreglo no lo tiene, así que
    ninguna afirmación posterior puede respaldarse en él por error. Recibos: la sonda con sus
    siete claims `DEMONSTRADO` (`evidence/f5_harness/run_2026-11-02T233718Z.json`, `8df68b8`,
    `RELEASE_GATE`), el gate con el caso extra (`evidence/backends/gate_2026-11-02T235456Z.json`,
    `4bb9ab5`, `verdict=FAIL` con **una** fila y `failures: []`) y el lote verde que lo reemplaza
    (`evidence/backends/gate_2026-11-03T004412Z.json`, `026db0f`). Lo que enseña sigue valiendo: un
    gate puede enrojecer por starvation del host (hallazgo 10) o **morirse sin enrojecer** por el
    toolchain, y antes, en el segundo caso, no había `gate_*.json` que discutir —solo stdout sin
    hashear—. Hoy el renglón existe; lo que queda afuera es el modo «se cuelga», que ningún
    `timeout=` del compilador ampara y está escrito como `NOT_DEMONSTRATED` en
    `docs/OPEN_QUESTIONS_P1_P4.md` (Z1).
14. **Cotejar recibos hoja por hoja tiene dos trampas de clave, y las dos dan números falsos.** La
    no-regresión de este lote se midió primero alineando los JSON **por posición**: F2 devolvió 35
    hojas distintas y F3 53, con `emits`, `code`, `claim` y `program_sha256` entre ellas. De esas,
    solo 4 en F2 y 5 en F3 son diferencias reales: al entrar `447` y `448` ordenados por nombre
    dentro del corpus, los renglones de después se desplazan y cada hoja se compara con la vecina
    equivocada. Y encima el desplazamiento pierde cobertura —dejan de casar 4 hojas del recibo
    viejo, 2 723 compartidas en vez de 2 727— mientras inventa diferencias. El segundo intento fue
    indexar cada lista por `name`, que está bien en F2 (un renglón por caso) y mal en F3, donde
    cada caso ocupa **dos** renglones (`trace_level` `stmt` y `full`): la clave se repite, el `dict`
    se queda con el último y el conteo sale justo a la mitad. De ahí el **1 734** que salió primero
    en el mensaje de `203f579` y pasó a tres docs con `d363e7c`, cuando con la clave del renglón
    (`name` + `trace_level`) son **3 462** hojas compartidas. Las conclusiones no se mueven: las 5
    distintas siguen siendo los tres contadores y el sello, y cero hashes de los 432 renglones
    previos tocados. Lo que enseña: un cotejo entre dos recibos es una afirmación **por renglón**,
    así que la clave tiene que ser la identidad del renglón, y antes de citar cualquier cifra hay
    que comprobar que esa clave es única —contar las hojas antes y después de indexar, o comparar
    `len(claves)` contra `len(renglones)`—. Ninguna de las dos trampas se ve en el resultado: ambas
    devuelven un número que parece una medición.

Nada de lo anterior (1–9) cambia un `expected`, un hash congelado ni un resultado de gate: son
correcciones de *atribución* (una cifra que no tenía recibo) y una re-medición. El 10 sí cambió
un veredicto — F5 `PASS` → `FAIL` en una corrida — y se documenta con la corrida y el
diagnóstico, no corrigiendo el recibo; la re-corrida lo dejó en `PASS` con el `FAIL` preservado.
El 11 es un defecto **propio** del lote de evidencia (`010e7c9`), no del lenguaje: no mueve
ningún digest y se arregla en la convención de rutas. El 12 tampoco cambia ninguna cifra: nombra
lo que el conteo del gate **no** dice sobre un renglón, para que nadie lea un `218/218` de F5 como
si COBOL ejecutara el programa que el frontend rechaza. El 13 tampoco mueve una cifra ni un
veredicto: nombra una forma de perderse el recibo que este lote **no** atravesó —en
`gate_2026-11-02T081912Z.json` los cinco backends salen con `fallas=0`, o sea ningún programa de
los 218 rompió un toolchain—, y queda como defecto del instrumento con su arreglo pendiente. El 14
sí corrige una cifra de este lote de evidencia —el 1 734 de F3 era la mitad exacta de los 3 462
hojas compartidas que da el cotejo con la identidad del renglón—: se corrige aquí y en los tres
docs que la citaban, sin reescribir `203f579` ni `d363e7c` ni sus mensajes, y sin tocar ningún
`expected`, ningún digest y ningún veredicto, porque las cinco hojas distintas siguen siendo los
contadores y el sello.
