# ROADMAP — ISyCoLang hacia un compilador

**Versión:** ROADMAP V1 · 2026-10-28
**Estado del proyecto:** `IDEA` (escalera de `ISYCO_LANGUAGE_ENGINE_STANDARD.md` §1)
**Origen:** `docs/origin/ROADMAP_V0_2026-09-03.md` (V0, preservado sin cambios) +
`docs/FEASIBILITY_2026-10-28.md` (estudio de viabilidad que justifica esta V1).
**Regla mayor:** `CLAIM_SCOPE ≤ EVIDENCE_SCOPE`.

---

## 0. Qué quiere ser ISyCoLang

Un lenguaje **pequeño de entender, formal de verificar y flexible de
especializar**, cuyo compilador pueda **aprovechar lo que cualquier lenguaje
que tengamos sabe hacer bien** (COBOL con decimales, Fortran con arreglos,
Prolog con búsqueda, z3 con restricciones, C/Rust/Zig con código nativo, los
esolangs como sustratos raros) sin que ninguno de ellos se vuelva la
semántica del lenguaje.

```text
la semántica es de ISyCoLang
los backends compiten por implementarla
la evidencia decide cuál gana
```

## 1. Decisión de arquitectura (de dónde sale esta V1)

El estudio de viabilidad comparó cuatro arquitecturas (detalle en
`docs/FEASIBILITY_2026-10-28.md`). La V1 adopta:

| pieza | rol | por qué |
|---|---|---|
| **Lenguaje fuente + IR canónica convencional** | camino de **ejecución** | una IR de 3 ops como camino de ejecución infla programas y pierde estructura para el backend nativo (INFERRED) |
| **Backends múltiples por contrato** | ejecución en C, Rust, Zig, COBOL, … y engines de `workspace/assembly` | patrón WISA / Code IR / E22: el contrato manda, el lenguaje del backend no |
| **3OPS Lab** (la hipótesis V0 de tres slots) | **carril de investigación** en paralelo, no ruta de ejecución | conserva la pregunta original sin obligar al compilador a cargarla |

```text
                ┌──────────── carril de ejecución ────────────┐
fuente .isy ─► AST ─► tipos/efectos ─► IR canónica ─► backend(s) ─► binario / resultado
                                         │
                                         └─► carril de análisis: lowering a pack 3-ops ─► 3OPS Lab
```

## 2. Reglas que aplican a todas las fases

1. **Semántica antes que backend.** Ningún backend define comportamiento; el
   intérprete de referencia es la semántica normativa.
2. **Engine ≠ Verifier.** Todo resultado de un backend se compara contra el
   intérprete de referencia **y** contra un `expected` obtenido por otro
   camino (tabla a mano, z3, implementación independiente).
3. **Backend saboteado obligatorio.** Cada suite diferencial incluye un
   backend con un bug inyectado; si la suite no lo detecta, la suite no sirve.
4. **Dominio declarado.** Equivalencia = `EQUIVALENT_WITHIN_DECLARED_DOMAIN`.
   Nunca "equivalente" a secas.
5. **Lo no soportado se rechaza** (`UNSUPPORTED`), nunca se aproxima.
6. **El host no hace el trabajo** (`test_engine_does_the_work`, estándar §9).
7. **Engines de `workspace/assembly` son copias** (fuente de verdad en
   `ISyCo Git/<Repo>`); este repo los **usa**, no los modifica.
8. **Nada destructivo** sobre el monorepo; todo acceso a él es de lectura salvo
   decisión explícita de Danny.

## 3. Fases

Cada fase tiene **gate**. Una fase no empieza hasta que su dependencia pasó su
gate. Sin estimaciones de tiempo: las fuentes de complejidad se nombran.

### F0 — Fundación  `[PASS 2026-10-28]`

- Repo, estándar y roadmap V0 preservados con SHA-256.
- Estudio de viabilidad.
- Inventario reproducible de `workspace/assembly` y de toolchains del host.

**Gate F0:** `sha256sum -c docs/origin/SHA256SUMS.txt` pasa; el inventario se
regenera con `python3 tools/inventory_assembly.py`.

### F1 — Semántica del core v0.1  `[PASS 2026-10-28: spec/CORE.md FROZEN v0.1]`

Definir en `spec/CORE.md`, antes de escribir el parser:

- valores y **contratos numéricos**: `int<N, wrap|trap|sat>`, `decimal<p,s,redondeo>`,
  `mod<M>`, `ieee754<32|64, estricto>` (precedentes: TRACE_MATH checked int64,
  Code IR `signed_fixed/32/trap`, E22 decimal);
- estado, variables, funciones, control (`if`, `while` acotable, `return`);
- **efectos declarados** (lectura/escritura/E/S) por función;
- errores canónicos y estados de terminación:
  `HALTED | LIMIT_REACHED | ERROR(code) | INVALID_PROGRAM | TIMEOUT`;
- formato de traza (estado antes → transición → estado después);
- formato canónico de archivo (`.isy`, UTF-8, gramática).

**Gate F1:** la spec responde las 10 preguntas del core del estudio (§C) sin
"TBD"; revisión de Danny.

### F2 — Intérprete de referencia + corpus de conformidad  `[PASS 2026-10-28: 58/58, 12 tests; erratas en spec/ERRATA_v0.1.md]`

- Parser + AST + chequeo de tipos/efectos.
- Intérprete de referencia (Python, legible antes que rápido) con trazas.
- `programs/conformance/`: un archivo por propiedad, `expected` escrito
  **antes** de correr.
- Tests por capas A–H del estándar §10.

**Gate F2:** corpus pasa; determinismo (mismo programa+entrada ⇒ misma traza,
byte a byte); casos adversariales (overflow, división por cero, límite de
pasos) dan el estado correcto, nunca `HALTED` por `LIMIT_REACHED`.

#### F2.1 — Core v0.2  `[PASS 2026-10-28: spec/CORE_v0.2.md; 20 casos nuevos, 78/78 en referencia, IR y C]`

Tres reglas de frontend aprobadas por Danny (índices literales `i64`, literales
negativos, `ARRAY_SIZE`), atadas a la cabecera `isyco 0.2`. El caso v0.1 `003` queda
superado de forma explícita en `programs/conformance/SUPERSEDED.json`.

#### F2.2 — Core v0.3: strings y structs  `[PASS 2026-10-29: referencia 64/64 (142/142 los tres corpus), IR isy-ir/0.2 284/284; C, Rust y Zig 142/142 (evidence/backends/gate_2026-10-29T143318Z.json)]`

Decisiones S1–S8 de Danny: `str<N>` acotado y ASCII, `OVERFLOW` al no caber,
ensanchamiento implícito `str<N>` → `str<M>` (N ≤ M), `len`/`s[i]`/`slice`/`chr`,
conversiones con `as` en forma canónica, structs por valor con `==`, E/S en JSON
canónico. Detalles **[P]** (P1–P7) aprobados por Danny el 2026-10-29.

**Gate F2.2:** spec congelada; referencia 64/64 en `programs/conformance_v0.3/`
sin cambiar ningún resultado de v0.1/v0.2; IR `isy-ir/0.2` validada; cada backend
nativo pasa el corpus v0.3 o declara `str`/`struct` como `UNSUPPORTED`.

#### F2.3 — Core v0.4: módulos  `[PASS 2026-10-29: referencia 28/28 (170/170 los cuatro corpus); IR 340/340; C, Rust y Zig 170/170]`

Decisiones M1–M4 de Danny: `import util;` con uso calificado `util.f()`, solo lo
`pub` se exporta, sin imports circulares, todos los módulos `isyco 0.4`. Se
resuelve en el frontend: la IR (`isy-ir/0.2`) no cambia. Detalles **[P]** (P1–P7)
aprobados por Danny el 2026-10-29.

**Gate F2.3:** spec congelada; referencia 28/28 en `programs/conformance_v0.4/`
sin cambiar ningún resultado anterior; IR y los tres backends nativos iguales a
la referencia en el corpus completo.

#### F2.4 — Core v0.5: `for`, `len` de arreglos, `str` sin capacidad  `[PROPUESTA 2026-10-30 — bloqueada por decisión de Danny, no por código]`

Nace del dogfood (`docs/DOGFOOD_2026-10-30.md`): los cinco programas reales midieron
qué no se puede escribir. `spec/CORE_v0.5_propuesta.md` convierte eso en siete
decisiones numeradas **V1–V7** con su corpus `programs/conformance_v0.5/` (401–410)
y los `expected` escritos a mano **antes** de implementar. A 2026-10-30 nada de v0.5 estaba
aprobado ni implementado; los bloques fechados debajo lo superan: **V1, V2, V6, V6-bis y V7 están
implementados y sellados; V3–V5 no tienen texto normativo nuevo todavía** (V3 ya era cierto en
el código y con V2 quedó medido). **Corrección 2026-11-01:** el directorio **sí entró**
en `CORPORA` (`isyco/conformance.py:13`) y el gate de backends pasó de 170 a **212**
casos; la referencia da 212/212 y los cuatro backends completos 212/212, con COBOL en
146/212 y 66 `UNSUPPORTED` nombrados. Dos medidas que sí entran hoy: el azúcar del `for`
con el incremento al final del cuerpo es **incorrecto** (`continue` no avanza →
`LIMIT_REACHED`, control negativo en el corpus) y añadir la cabecera `0.5` toca
**diez** sitios con la versión fijada en código (`evidence/v05_propuesta/`) — cifra
**corregida a doce** el 2026-10-31 al implementar V6/V7 y **a trece** el 2026-11-01 al entrar
V1/V2/V3: ver la nota de §7 en `spec/CORE_v0.5_propuesta.md` y el bloque de V7 más abajo.

**Gate F2.4:** los seis ítems de `spec/CORE_v0.5_propuesta.md` §5, incluida la
igualdad de `steps` contra los `while` gemelo (23 / 38 / 20) y la corrida COBOL
que falsifica V7.

> **Repriorizado 2026-10-30 por el objetivo real de Danny: una librería de texto.**
> `programs/dogfood/06_biblioteca_texto.isy` ya la escribe en `isyco 0.4` — `pad`,
> `empieza_con`, `cuenta_letra`, `mayus`, con los 11 `emits` predichos a mano antes de
> correr y `HALTED` en los cinco ejecutores; `07_texto_desborda.isy` fija que desbordar
> la capacidad declarada es `ERROR(OVERFLOW)` y nunca truncado
> (`evidence/textlib/run_2026-10-31T012545Z.json`). Con eso **V6 (y su ampliación
> V6-bis, `str` pelado en el retorno) pasa delante de V1/V2**, y la fila de §3 que
> pedía aritmética de capacidades queda refutada: `checker.py:377-379` ya la tiene.
> Corrección completa en `spec/CORE_v0.5_propuesta.md` §8.

> **V6 implementado y sellado 2026-10-31.** `str` pelado en parámetros, resuelto por el
> sitio de llamada con una copia por resolución (`isyco/specialize.py`): los 18 casos
> nuevos `411`–`428` coinciden en referencia, IR y cada backend —77 EQUIV, 13 UNSUPPORTED
> (todos COBOL, y por la etiqueta `ir0.2`, no por V6), cero DIVERGENT/BUILD_FAIL—;
> 22 clones en el corpus, máximo 2 por definición, sin tope fijado (base de P4) **— P4 se cerró el
> 2026-11-02 con 256 resoluciones por definición y `SPEC_LIMIT`; ver el bloque de P4 al final de
> esta sección—**.
> Decisión y controles: `docs/decisions/V6_CONTEXTUAL_STR.md`;
> `evidence/v05_v6/run_20261031T103514Z.json`. Quedan V6-bis, V7, revalidar V1–V5 y P1–P4;
> el directorio sigue fuera de `CORPORA` hasta que `401`–`410` pasen —**ocurrió el
> 2026-11-01**: entró con sus 42 casos y el gate pasó a 212, sin mover ningún resultado
> de los 170 anteriores. **Y subió otra vez el mismo día:** `443_m4_modulo_v04` (`a4f608c`)
> fija la diagonal `0.5` de M4 con su `expected` escrito antes de correr, y lleva la
> población del gate a **43 / 213** — los recibos más recientes de F2, F3, F4 y F5 son de esa
> población y están en `docs/EVIDENCE_MATRIX.md`; ninguno de los 170 de siempre se movió.

> **V6-bis implementado y sellado 2026-10-31.** `-> str` pelado resuelto por la capacidad
> **esperada en el sitio de llamada**: `429`–`438` (4 ejecutables, 6 rechazos) con los
> `expected` a mano antes de tocar `isyco/`; dos expectativas de la misma definición dan
> dos copias (`doble.4.r8`, `doble.2.r4`), ninguna expectativa es `TYPE_MISMATCH` (nunca
> `MAX_STR`), y desbordar la expectativa es `ERROR(OVERFLOW)` con cero `emits` (`430`) —
> nada de truncate and continue. Diferencial extendido a los 28 casos `411`–`438`:
> **123 EQUIV, 17 UNSUPPORTED (COBOL, otra vez por la etiqueta `ir0.2`), cero
> DIVERGENT/BUILD_FAIL**; el sabotaje `str_concat_truncates` ahora rompe dos casos
> (`418` y `430`). 28 clones en el corpus, máximo 4 por programa, sin tope fijado **— cerrado el
> 2026-11-02 con 256 resoluciones por definición; bloque de P4 al final de esta sección—**.
> Decisión: `docs/decisions/V6B_CONTEXTUAL_RETURN.md`;
> `evidence/v05_v6/run_20261031T183542Z.json`. Quedan V7, revalidar V1–V5 y P1–P4.

> **Censo de P4 corregido y sellado 2026-11-01.** Los «22 clones» y los «28 clones, máximo
> 2 por definición» de los dos bloques de arriba no estaban en ningún recibo: las sondas
> V6 guardan el resultado por backend, no el registro de clones. `tools/v05_p4_probe.py`
> lo recalcula desde `Checker.specs` sobre la población del gate y sella
> `evidence/v05_p4/run_20261101T062234Z.json` (`RELEASE_GATE` sobre `52f5564`): **32 clones**
> en 18 de 42 casos (26 de V6 + 6 de V6-bis), 4 por programa como máximo, 2 por definición
> **dentro de un programa** pero **7 de `doble` en todo el corpus**. La forma también está
> medida: K anchos en una ranura → K clones, dos ranuras → W², tres → W³, y 20 sitios con el
> mismo ancho → 1 clon. Ningún techo ni error nombrado hasta 2048 clones: **P4 sigue
> abierta**, con la base numérica en evidencia en lugar de en prosa. **Población del censo:**
> son los 42 casos que había al sellar; `443` entró el 2026-11-01 con `a4f608c` y el gate quedó
> en 43. El caso nuevo no tiene parámetros `str`, así que lo esperable es que los 32 clones no
> se muevan, pero **no se re-midió**: es predicción, no medición.
>
> **Re-medido el 2026-11-01** (`evidence/v05_p4/run_20261101T154040Z.json`, `RELEASE_GATE`
> sobre `2938c01`, 3,2 s de corrida): censo sobre los **43** casos y sus 4 directorios de
> módulos — los mismos **32 clones** en los mismos **18 programas**, mismos máximos (4 por
> programa, 2 por definición dentro de un programa, 7 de `doble` en el corpus), curvas
> K/W²/W³ y control negativo byte a byte iguales. `443` entra con 0 clones y su
> `VERSION_MISMATCH`: los casos que rechaza el frontend pasan de 11 a 12. La predicción de
> arriba se confirmó midiendo.
>
> **Re-medido de nuevo el 2026-11-01, con N1 dentro** (`evidence/v05_p4/run_20261101T234407Z.json`,
> sha `7d3bafba…`, `RELEASE_GATE` sobre `6ebb00d`): censo sobre los **46** casos — **33 clones en
> 19 programas**, 27 de V6 + 6 de V6-bis, 13 definiciones. El clon extra es `emite.16` de `445`, el
> `str` pelado recorrido por un `for`; `444` y `446` aportan **0**, o sea que el azúcar no
> especializa nada por sí solo. Máximos sin cambio (4 por programa, 2 por definición dentro de un
> programa, 7 de `doble` en el corpus), y las 43 filas compartidas con la corrida de las 15:40 dan
> idénticas en nombres y conteos, con curvas y control byte a byte iguales. **P4 sigue abierta.**
> (Cerrada el 2026-11-02 con el bloque de P4 al final de esta misma sección de F2, que además
> corrige la frase de «ningún techo hasta 2048 clones».)

> **V7 implementado 2026-10-31.** La capacidad la exige el **programa**, no su cabecera:
> `features_of` camina los tipos bajados y las sentencias, `ir0.2` solo aparece si hay `str` o
> `struct`, y el átomo nuevo `emit_array` nombra lo que la etiqueta tapaba — imprimir un arreglo.
> Medido sobre el corpus congelado: **60** módulos dicen `isy-ir/0.2`, **46** lo usan y **14**
> pedían `ir0.2` por pura etiqueta (**17** con los canarios `439`–`442`). El brazo viejo se
> reconstruye del commit previo (`git show f856d55:isyco/backends/base.py`, **FIEL en los 118
> módulos**, cero divergencias) en vez de caricaturizarse: 17 `UNSUPPORTED(ir0.2)` → **15 EQUIV**
> —status, code, emits, return **y pasos** iguales a la referencia— + 2 `UNSUPPORTED(emit_array)`.
> Solo le cambia a COBOL (63 → 48 en esa población) y su gate F5 sube **113 → 125/170** con
> UNSUPPORTED **57 → 45**, cero fallos, 8 484 corridas sin diferencias y los dos sabotajes
> detectados. Sale además un bug **previo** de COBOL: una llamada void en sentencia no declaraba
> el hueco `{prefijo}RET` que el proemio y el epílogo escriben (`isyco/backends/cobol.py:907`) — se
> arregla el emisor, no se inventa una capacidad para taparlo. Corrección a §7: son **12** los
> sitios con la versión fijada, no 10, y la fuente única que pedía ya existe (`isyco/versions.py`).
> Decisión: `docs/decisions/V7_CONTENT_CAPABILITIES.md`; gate de release
> `evidence/backends/gate_2026-10-31T200602Z.json` (sha `f24c8f0c…`) y sonda
> `evidence/v05_v7/run_20261031T200146Z.json` (`RELEASE_GATE`, mismo `corpus_hash` que la
> corrida `EVIDENCE_ONLY` `run_20261031T194109Z`). Quedan revalidar V1–V5 y P1–P4.

> **V1 implementado 2026-10-31 (revalidación de V1–V5).** `len(a)` con `a: [T; N]` devuelve
> `N` en `i64` y **el frontend lo sustituye en el AST** (`isyco/checker.py:37`), así que la IR
> no gana ningún nodo ni ninguna capacidad: 0 nodos `{"k": "len"}` en 401/406 frente al control
> `len(s)` de v0.3, que sigue bajando con el suyo. Medido: `401` y `406` pasan de
> `INVALID_PROGRAM(TYPE_MISMATCH)` a coincidir en `expected` ↔ referencia ↔ **los cinco**
> backends (10 EQUIV, pasos incluidos), con los mismos pasos que su gemelo con la capacidad
> escrita a mano (6 = 6 y 27 = 27) — es estático, no cuesta paso. No regresión: la misma fuente
> recabezada a 0.1/0.2 sigue en `UNKNOWN_NAME` (ahí `len` no es palabra clave) y a 0.3/0.4 en
> `TYPE_MISMATCH`. La sonda se auto-falsifica: apagando la familia `v05` en el checker los dos
> casos vuelven a rechazarse, y si no lo hicieran el EQUIV sería vacuo
> (`tools/v05_revalida_probe.py --casos 401,406`). Decisión:
> `docs/decisions/V1_LEN_ARREGLO.md`. Quedan V2 (`402`–`405`), V3–V5 y P1–P4.

> **V2 implementado 2026-10-31 (revalidación de V1–V5).** `for x in a { … }` se expande en el
> **parser** (`isyco/parser.py:317` `for_stmt`) exactamente en el `while` gemelo con la cota
> `len(a)` de V1: `let i#k: i64 = -1; while i#k + 1 < len(a) { i#k = i#k + 1; let x = a[i#k]; … }`.
> `for` se reserva solo desde `0.5` (`isyco/lexer.py:19`) y `in` **no** se reserva (V3, que así
> queda medido). Los cuatro casos `402`–`405` pasan de `SYNTAX` a coincidir en `expected` ↔
> referencia ↔ backends (**29 EQUIV + 1 UNSUPPORTED**, el único atribuido a la regla de
> contenido de V7 sobre un programa con `struct`/`str`, no al `for`). Cumple el ítem 2 del gate
> al paso: **23 / 38 / 20** pasos idénticos a sus gemelos, y la **IR también es idéntica** a la
> del gemelo tras podar posiciones y el nombre del local sintético (`402 671bc2b4781e4a39`,
> `403 8ca576e4d581ebdb`, `404 ef194bcb295b580b`, `405 f70c73fcc5544b3a`) — control que cazó un
> `{"k": "neg"}` de más que los pasos no veían. El iterando es un **lugar**, no una expresión:
> `for x in [1, 2, 3]` es `SYNTAX` (P2 respondido por medición, más estricto que la
> recomendación del borrador). No regresión: recabezados a 0.1–0.4 siguen `SYNTAX`, y con `0.4`
> `let for: i32 = 5;` compila. La sonda se apaga de verdad parchando `has` en **los tres**
> módulos (`lexer`, `parser`, `checker`) — parchar solo el checker habría mentido — y el
> sabotaje del incremento al final produce 12 `CONTROL FALSO`, exit 1 y cero evidencia sellada.
> **Los 42 casos del corpus coinciden con su `expected` a mano (42/42).** Decisión:
> `docs/decisions/V2_FOR_AZUCAR.md`; gate de release `evidence/v05_revalida/run_20261101T001608Z`
> (`RELEASE_GATE`, `arbol_sucio_codigo=false`, mismos números que la corrida `EVIDENCE_ONLY`
> `run_20261031T235253Z`). Quedan los textos normativos V3–V5 y P1–P4; **meter el corpus
> en `CORPORA` ocurrió el 2026-11-01** (commit `57f38bc`): los 42 casos entran al gate, que
> pasa de 170 a **212** — referencia `212/212`, C/Rust/Zig/pydecimal `212/212`, COBOL
> `146/212` con 66 `UNSUPPORTED` nombrados, cero fallos y cero diferencias en las 8 484
> corridas diferenciales; IR `424/424` con 145 programas bajados. Recibos
> `evidence/backends/gate_2026-11-01T015245Z.json` (`verdict=PASS`, `git_head=57f38bc`) y
> `evidence/ir/gate_2026-11-01T013721Z.json`.

> **N1 adoptada y sellada 2026-11-01 — `for` sobre un `str` es normativa.** El iterando del
> azúcar puede ser un **lugar** de tipo `str` (local `str<N>`, campo calificado, parámetro `str`
> pelado de V6, entrada por stdin): se recorre **`len(s)` veces** y la variable del bucle es
> **`u8`, copia**. La cota es la **longitud del valor**, no la capacidad declarada. **No hizo
> falta tocar `isyco/`** — `parser.py:334-350` construye un lugar sin saber su tipo,
> `checker.py:204-209` da al `let` sintético el tipo de `s[foridx]`, que sobre `StrT` es `u8`
> (`checker.py:348-352`), y `interp.py:238` resuelve `len` en tiempo de ejecución. Tres casos con
> su `while` gemelo escrito a mano: `444_for_sobre_str` (un `str<8>` con `"hola"` emite
> `104 111 108 97` y devuelve `4`), `445_for_str_pelado_stdin` (N1 × V6: `"mundo"` por stdin,
> cinco bytes y `return 5`) y `446_for_copia_str` (`c = 65` dentro del bucle emite `65 65 65` y
> `s[0]` sigue dando `97`). Población **43 → 46** casos y gate **213 → 216**, con los 213
> `expected` sin moverse (recibo-vs-recibo: cero diferencias). El azúcar no cuesta nada:
> **22 / 27 / 22** pasos idénticos a los de su gemelo, pinneados en `PASOS_EXIGIDOS`; la IR del
> `for` es la IR del gemelo (F3 **432/432** sobre **148** programas bajados) y `features_of` no
> cambia — a los tres y a sus gemelos les falta `ir0.2,str`, que es la regla de contenido de V7,
> no un rechazo del azúcar. Rechazarla habría dejado de ser azúcar: el `while` gemelo sigue
> siendo legal. Recibos: F2 `evidence/conformance/run_2026-11-01T210445Z.json`, F4
> `evidence/c/gate_2026-11-01T211424Z.json` (`PASS`, 216/216 en las cuatro combinaciones con
> sanitizers) y F5 `evidence/backends/gate_2026-11-01T225011Z.json` (`PASS`; COBOL **147/216 con
> 69 `UNSUPPORTED`**, la cifra predicha antes de correr). La primera corrida de F5 sobre este
> árbol salió **FAIL** por un `TIMEOUT` del arnés en el diferencial de strings de pydecimal y el
> recibo queda preservado (`gate_2026-11-01T215718Z.json`): con el host en carga de otros
> agentes; la reproduccion determinista (`evidence/f5_flake/run_20261101T220854Z.json`: 500
> llamadas aisladas y dos pasadas completas de 1 270 casos, 0 diferencias) y la re-corrida del
> gate dicen que no fue divergencia semántica. No se tocó el arnés dentro del alcance de N1.
> Falsificación: `tests/test_reference.py::Sabotage.test_len_de_str_se_hace_estatico` — plegar
> `len` de un `str` a su capacidad, que es lo que V1 hace con los arreglos, rompe `444`— y la
> sección nueva **§7** de `tools/v05_spec_probe.py` con sus doce formas (`evidence/v05_spec/`
> `run_20261101T210009Z.json`, `RELEASE_GATE`; seis `CONTROL FALSO` y cero sello cuando se
> parcheó el engine). Decisión: `docs/decisions/N1_FOR_SOBRE_STR.md`. §4.4 del spec pierde el
> `[D]`. **Queda P4** como única decisión abierta del borrador (se cerró el 2026-11-02, ver el
> bloque de P4 debajo de este).

> **P4 CERRADA 2026-11-02 — 256 resoluciones por definición dentro del programa, con
> `SPEC_LIMIT`.** Decisión de Danny sobre la base sellada del censo: **granularidad** por
> definición fuente (no por programa, no por módulo), **número** 256 y **error nombrado**, en
> lugar del crecimiento silencioso. `specialize.MAX_CLONES_PER_DEFINITION` es literal normativo
> del spec y el contador vive en `Checker.spec_counts`: 256 claves distintas son legales y la
> 257 se rechaza **antes** de bajar a la IR. Dos casos nuevos — `447_tope_de_especializaciones`
> (257 resoluciones de una sola definición por la orilla de retorno → `INVALID_PROGRAM/SPEC_LIMIT`)
> y `448_dieciseis_clones_por_definicion` (4×4 = 16 copias de una definición de dos ranuras,
> legal) — suben la población de **46 a 48** casos y el gate de **216 a 218**. El censo se partió,
> no se excluyó: la sonda reporta aparte `casos_de_tope` y el máximo **sin** ellos, que sigue en
> **2**, así que la base con la que se decidió el número sigue siendo comprobable.
>
> **Corrección a la frase «ningún techo ni error nombrado hasta 2048 clones», del bloque del censo
> sellado el 2026-11-01.** Era verdad para el lenguaje **sin cota** y solo para las dos vías que la
> sección `costo` medía —`ref_ms` y `c_ms`: la referencia y C—. Con la cota de P4 puesta, esa
> población dejó de ser construible: `512`/`1024`/`2048` resoluciones de una misma definición se
> cortan en el frontend con `SPEC_LIMIT`. Y Zig no estaba medido: ahí el techo **sí** existe y cae
> por debajo de la cota.
> Matriz `aridad × ancho` con el tope puesto —sección 6 de
> `evidence/v05_p4/run_20261102T081925Z.json` y su bisección con `--bisect-zig`—: **una**
> ranura con 256 copias compila en c, rust y zig; con **dos** ranuras 256 (W=16) revienta en Zig
> (`error: evaluation exceeded 1000 backwards branches`) mientras c y rust la compilan; con
> **tres**, 216 (W=6); con **cuatro**, 256 (W=4). Frontera biseccionada
> sobre forma parcial (ranuras primeras fijas en 2, paso de 2^(n-1) clones) y con los dos bordes
> compilados antes de recorrer: **250 OK / 252 FALLO** en aridad 2, **164 / 168** en 3, **120 / 128**
> en 4, y `SIN_FALLO_DENTRO_DEL_TOPE` en 1. O sea: hay programas legales bajo P4 que un backend
> concreto no puede construir, y la cota del idioma no protege de eso. Eso es **Z1**, pregunta nueva
> en `docs/OPEN_QUESTIONS_P1_P4.md`. Ninguna de las dos cosas se arregla moviendo el número.
>
> Nada del borde se dejó a la suerte: 255/256/257 los fijan los nueve tests de
> `tests/test_specialize.py::TopePorDefinicion`, la identidad por-definición-no-por-programa
> también, y la asimetría está declarada en `docs/decisions/P4_SPEC_LIMIT.md`, en
> `programs/conformance_v0.5/README.md` y aquí: **la mutación off-by-one (`>` por `>=`) no la
> detecta ningún sabotaje de corpus**, porque un programa con 256 clones no puede entrar al gate
> (Zig lo rompe), así que la muerde solo `test_256_es_el_ultimo_legal`. Los dos sabotajes de P4
> sí están en la referencia: apagar el tope (`10**9`) rompe **exactamente** `447`, y bajarlo a `1`
> rompe `411_pad_dos_anchos` y deja en verde `416_cast_mas_estrecho` — la cota muerde por encima
> de 1, no en 1. Gates del lote: F2 `evidence/conformance/run_2026-11-02T070428Z.json`
> (`218/218`), F3 `evidence/ir/gate_2026-11-02T070428Z.json` (`436/436` sobre **149**
> programas bajados), F4 `evidence/c/gate_2026-11-02T072103Z.json` (`218/218` en las
> cuatro combinaciones), F5 `evidence/backends/gate_2026-11-02T081912Z.json` (`PASS`;
> c/rust/zig/pydecimal 218/218 y COBOL 148/218 con 70 `UNSUPPORTED`) y la sonda
> `evidence/v05_p4/run_20261102T081925Z.json` —`EVIDENCE_ONLY`: la documentación de este lote
> estaba a medio editar mientras corría, con `isyco/` y `tools/` intactos—. Decisión:
> `docs/decisions/P4_SPEC_LIMIT.md`. Con esto **no queda ninguna decisión abierta** del
> borrador de CORE v0.5; lo que queda es Z1, que es de toolchain y no de semántica.

### F3 — IR canónica  `[PASS 2026-10-28: spec/IR.md; 40 programas válidos bajados a IR, 116/116 comparaciones iguales (los 18 inválidos no producen IR)]`

- IR tipada, cerrada, serializada a JSON canónico con SHA-256 (patrón Code IR).
- Validador de mundo cerrado.
- Decisión registrada: **reusar código de Code IR** (`ISyCo/experiments0000/py_transpile_toy/code_semantics`)
  o reimplementar — se decide leyendo el código, no por nombre.

**Gate F3:** intérprete sobre IR == intérprete sobre AST en todo el corpus.

### F4 — Primer backend nativo: C  `[PASS 2026-10-28: docs/BACKEND_C.md; evidence/c/gate_2026-10-29T005211Z.json]`

- Lowering IR → C, compilado con `gcc`/`clang` (presentes en el host).
- Diferencial de tres vías: `expected` ↔ referencia ↔ binario.
- Backend saboteado detectado.

**Gate F4:** 100 % del corpus `EQUIVALENT_WITHIN_DECLARED_DOMAIN`; el sabotaje
falla la suite. Primera afirmación `DEMONSTRATED` del proyecto.

### F5 — Contrato de backend `ISY_BACKEND/1` y adapters  `[EN CURSO — ola 1 (C, Rust, Zig) PASS 2026-10-29 con sabotajes y costo medido: spec/BACKEND.md; evidence/backends/gate_2026-10-29T055122Z.json · ola 2 completa: `pydecimal` PASS 2026-10-30 (evidence/backends/gate_2026-10-30T074904Z.json) y COBOL PASS 2026-10-30 (evidence/backends/gate_2026-10-30T211143Z.json) · olas 3–6 pendientes]`

Los engines de `workspace/assembly` hoy implementan E=(I,X,O,S): **ejecutan su
propio bootstrap**, no programas externos. Para ser backends hace falta un
contrato nuevo:

```text
entrada:  IR (o código generado) + entradas + límites
salida:   status, salidas, traza opcional, costo medido
promesa:  qué subconjunto de la IR implementa (capabilities declaradas)
```

Inventario 2026-10-28 (`evidence/inventory/`): 165 carpetas →
**54 `INTERPRETER_PY`** (aceptan un archivo fuente arbitrario vía
`run_esolang.py`), **99 `BOOTSTRAP_ONLY`** (solo bootstrap fijo), 10 no-engine,
2 sin clasificar.

Orden propuesto de backends (por toolchain presente y valor distinto):

| ola | backends | qué aporta |
|---|---|---|
| 1 | C, Rust, Zig | nativo, enteros con ancho explícito |
| 2 | COBOL (`cobc`), Python `decimal` **← `pydecimal` PASS 2026-10-30 · `cobol` PASS 2026-10-30** | decimal de punto fijo verificable (E22) |
| 3 | Fortran (`gfortran`), Julia | arreglos y numérico científico |
| 4 | Prolog (`swipl`), z3 | búsqueda y restricciones como backend de funciones declarativas |
| 5 | Go, Java, .NET, Haskell, OCaml, Lisp (`sbcl`), Lua, Node | interoperabilidad con ecosistemas |
| 6 | esolangs `INTERPRETER_PY` (brainfuck, malbolge, jajaja, …) | sustratos raros; subconjuntos pequeños |

**Gate F5:** cada backend declara su subconjunto y pasa el corpus de ese
subconjunto; un backend que "pasa" sin ejecutar (stub) es detectado por
`test_engine_does_the_work`.

### F6 — Carrera de backends y selección por función

- Cada función puede pedir un contrato (`@numeric(decimal<18,2,half_even>)`,
  `@effects(pure)`) y el compilador elige entre backends que lo cumplen.
- Selección por medición (latencia, CPU, memoria, buen vecino), no por
  reputación: `ENGINE_IDENTITY != ENGINE_FIT`.
- Enlace polyglot **primero por proceso persistente** (evidencia de dataflow:
  worker persistente 112–3142× mejor que proceso-por-operación, nunca mejor que
  in-process), ABI/FFI nativo después.

**Gate F6:** al menos un programa mixto (p. ej. C + COBOL) da el mismo resultado
que el programa en un solo backend, y la selección es reproducible.

### F7 — Packs de capacidades (módulos de dominio)

- Librerías con efectos y costos declarados; sin primitivas ocultas.
- Un pack nunca agrega semántica al core; si la agrega, es una versión nueva
  del core.

**Gate F7:** dos dominios distintos sin cambiar el hash del core.

### F8 — Optimización y síntesis sobre la IR

- Reescrituras con e-graphs, superoptimización local, CEGIS con z3 (instalado).
- Toda reescritura queda registrada con su prueba (exhaustiva en dominio finito
  o SMT acotado); si solo se observó en un corpus:
  `DERIVABLE_IN_OBSERVED_DOMAIN`.

**Gate F8:** optimizaciones no cambian ninguna traza observable del corpus.

### F9 — Dataflow como estrategia de ejecución (opcional)

- Scheduler por dependencias sobre efectos declarados (RAW/WAR/WAW + token de
  E/S); grano grueso (bloques/funciones), no por operación.

**Gate F9:** mismo resultado que el backend secuencial y ganancia medida bajo
carga realista; si no gana, queda documentado y apagado.

## 4. Carril paralelo — 3OPS Lab (hipótesis V0)

Arranca después de F1 (necesita los contratos numéricos y de estado); no
bloquea al compilador ni es bloqueado por él. Core **reformulado** según el
estudio:

- COMPOSE solo en compilación (macro-expansión contada), nunca en runtime;
- E/S, ancho de operandos, direccionamiento y memoria fijados por el core;
- operaciones como **tablas acotadas** sobre una ventana local (hidden-VM
  imposible por construcción);
- **control de pack nulo**: lo que tres NOPs resuelven es capacidad del core.

| gate | prueba |
|---|---|
| L0 | spec del core 3-ops sin huecos (PC, halt, errores, E/S, operandos) |
| L1 | pack nulo resuelve 0 tareas rankeadas |
| L2 | una op "VM escondida" es rechazada automáticamente |
| L3 | dos packs, mismo hash de core |
| L4 | intérprete == compilado a C, sabotaje detectado |
| L5 | síntesis con poda reproducible bajo presupuesto declarado |
| L6 | dos packs con cobertura/costo distintos y estables |
| L7 | segundo dominio sin tocar el core |

Correcciones al V0 que este carril adopta:

- **TRACE_MATH** hoy calcula métricas sobre trazas; no compone comportamientos.
  La función de "derivación" del V0 §9 requiere herramienta nueva
  (comparación de trazas completas + registro de derivaciones).
- **WISA** en disco es un perfil de pipeline de registros, no un dominio
  matemático. El primer dominio del Lab se define en L0.
- Búsqueda exhaustiva de largo 8 solo es tratable con ≤ 2 combinaciones de
  operandos por op sin poda (cálculo en el estudio §7).

## 5. Fuera de alcance por ahora

- Self-hosting del compilador.
- LLVM directo (no hay `llc` en el host; C/Rust/Zig cubren el nativo inicial).
- Afirmaciones de Turing-completitud de cualquier pack.
- Publicación pública. **Decisión de Danny (2026-10-28): el repo es PRIVADO por
  ahora.** Sin licencia ni remoto público; si se publica más adelante, se
  revisa la separación público/privado (estándar §21).

## 6. Claim table

| Claim | Status | Evidence |
|---|---|---|
| Existe un engine de ISyCoLang (intérprete de referencia) | DEMONSTRATED (2026-10-28) | `evidence/conformance/`, `tests/test_reference.py` |
| El intérprete cumple el corpus v0.1 (58 casos, expected previos al intérprete) | DEMONSTRATED | `evidence/conformance/` |
| El redondeo decimal coincide con una implementación independiente (`decimal` de Python) | VERIFIED (20 000 casos aleatorios × 3 modos) | `tests/test_reference.py::RoundingOracle` |
| El corpus detecta semánticas saboteadas | DEMONSTRATED (4 mutaciones) | `tests/test_reference.py::Sabotage` |
| ISY-IR preserva la semántica: resultado y traza idénticos a la referencia | DEMONSTRATED (corpus × trazas stmt/full + 4 programas de IR con límites ajustados) | `evidence/ir/`, `tests/test_ir.py` |
| Backend C: binario nativo == referencia en el corpus (status, code, emits, return, steps) | DEMONSTRATED con gcc 13.3 y clang 18.1, con y sin UBSan+ASan (58/58 en las 4 configuraciones) | `evidence/c/` |
| Backend C: diferencial por tipo numérico (24 enteros + 8 decimales × 15 operaciones, fronteras y empates) | DEMONSTRATED: 24 612 corridas sin diferencias (+6 468 con sanitizers) | `evidence/c/`, `isyco/difftest.py` |
| Contrato `ISY_BACKEND/1` con driver común (validación, capacidades, caché, límites, protocolo E/R/X) | DEMONSTRATED (2026-10-29) | `spec/BACKEND.md`, `isyco/backends/base.py`, `tests/test_backends.py` |
| Backends Rust y Zig: binario nativo == referencia en ambos corpus y en el diferencial por tipo | DEMONSTRATED: 78/78 y 8 484 corridas sin diferencias cada uno | `evidence/backends/gate_2026-10-29T022957Z.json` |
| Un backend que no declara una capacidad responde `UNSUPPORTED` y no ejecuta el programa | DEMONSTRATED (backend de prueba sin decimales) | `tests/test_backends.py::Unsupported` |
| Core v0.3 (str<N>, structs): la referencia cumple 64 casos con expected escritos a mano antes de implementar | DEMONSTRATED (2026-10-29), 142/142 sumando v0.1/v0.2 | `evidence/conformance/run_2026-10-29T081147Z.json` |
| v0.3 no cambia ningún programa v0.1/v0.2 | DEMONSTRATED: 78/78 y mismo `semantic_hash` de IR en los 54 programas válidos (salvo el caso 119, superado explícitamente) | `programs/conformance_v0.2/SUPERSEDED.json`, `evidence/ir/` |
| ISY-IR v0.2 preserva la semántica de v0.3 (resultado y traza) | DEMONSTRATED: 284/284 comparaciones, 99 programas | `evidence/ir/gate_2026-10-29T081148Z.json` |
| El corpus v0.3 detecta semánticas saboteadas (structs por referencia, str que trunca) | DEMONSTRATED (2 mutaciones) | `tests/test_reference.py::Sabotage` |
| Backend C ejecuta str y structs (isy-ir/0.2) igual que la referencia | DEMONSTRATED (2026-10-29): 142/142, diferencial de strings 1 214 corridas sin diferencias (concatenación, comparación, len/índice/slice/chr, casts con dígitos gigantes) | `evidence/backends/gate_2026-10-29T100103Z.json` |
| Backend C v0.3 sin comportamiento indefinido | DEMONSTRATED con UBSan+ASan en gcc 13.3 y clang 18.1: 64/64 y 974 corridas de strings sin diferencias | `evidence/c/sanitize_v03_2026-10-29T100117Z.txt` |
| La suite detecta un backend (C, Rust o Zig) que trunca strings en vez de OVERFLOW | DEMONSTRATED (sabotaje `str_concat_truncates`: 1 caso del corpus y 15 diferencias del diferencial de strings en cada backend) | `evidence/backends/gate_2026-10-29T172039Z.json` |
| Backends Rust y Zig ejecutan str y structs igual que la referencia | DEMONSTRATED (2026-10-29), implementaciones independientes de C: 142/142 y 1 214 corridas de strings sin diferencias cada uno; los 3 sabotajes detectados | `evidence/backends/gate_2026-10-29T143318Z.json` |
| Core v0.4 (módulos): la referencia cumple 28 casos con expected escritos a mano antes de implementar | DEMONSTRATED (2026-10-29), 170/170 con v0.1–v0.3 | `evidence/conformance/run_2026-10-29T202242Z.json`; re-run con `git_head` amarrado: `evidence/conformance/run_2026-10-30T003307Z.json` (`git_head=6468507`, 170/170, mismo `spec_sha256`) |
| v0.4 no cambia ningún programa anterior | DEMONSTRATED: 142/142 (salvo v0.3/264, superado explícitamente); los nombres simples generan el mismo código nativo | `programs/conformance_v0.3/SUPERSEDED.json`, `tests/test_modules.py` |
| Los módulos se resuelven en el frontend: la IR no cambia y los backends solo codifican nombres calificados | DEMONSTRATED: IR 340/340 (resultado y traza); C, Rust y Zig 170/170 con el mismo `modules` | `evidence/ir/gate_2026-10-29T202243Z.json`, `evidence/backends/gate_2026-10-29T203306Z.json`; re-runs con `git_head=1ba6b15`: `evidence/ir/gate_2026-10-30T005224Z.json` (340/340), `evidence/backends/gate_2026-10-30T010458Z.json` (PASS, 170/170 y 8 484+1 270 corridas por backend) |
| El corpus detecta un enlazador que ignora `pub` | DEMONSTRATED (mutación: 304 y 305 fallan) | `tests/test_modules.py::Sabotage` |
| La suite detecta un backend C saboteado | DEMONSTRATED (2 sabotajes, corpus y diferencial) | `evidence/c/` |
| La suite detecta un backend Rust o Zig saboteado | DEMONSTRATED (2026-10-29): los mismos 2 sabotajes que C; cada uno falla corpus (3 y 2 casos) y diferencial (12 y 53 diferencias), igual en los tres backends | `evidence/backends/gate_2026-10-29T055122Z.json`, `tests/test_backends.py` |
| Backends de las olas 2–6 de F5 (Fortran, Prolog/z3, Go/Java/…, esolangs; `pydecimal` y COBOL ya están PASS) | Fortran, Prolog/z3, Go/Java/…, esolangs: NOT_DEMONSTRATED (no implementados) | — |
| El contrato acepta un backend cuyo sustrato NO es nativo (Python 3 + `decimal`) con el mismo resultado que la referencia | DEMONSTRATED (2026-10-30): 170/170, 8 484 corridas del diferencial y 1 270 de strings sin diferencias; los 3 sabotajes detectados; todos los redondeos decididos por la división y `quantize` de CPython (la referencia usa enteros escalados), coste medido aparte (RSS de intérprete, ~14 MB) | `evidence/backends/gate_2026-10-30T074904Z.json`, `isyco/backends/pydecimal.py` |
| El contrato acepta GnuCOBOL 3.1.2 (sin argv, zoned decimal nativo) con el mismo resultado que la referencia | DEMONSTRATED (2026-10-30): 113/170 con 57 UNSUPPORTED declarados (str/struct), 8 484 corridas del diferencial sin diferencias, 2 sabotajes detectados; hallazgos del sustrato: un punto cierra todos los ámbitos abiertos, una etiqueta de párrafo no puede ir dentro de un IF, ORD/CHAR son 1-based, el argumento de llamada debe ser ítem (lvalue) y una FUNCTION-ID recursiva no propaga su valor (las funciones IR se compilan como subprogramas `IS RECURSIVE` invocados con CALL y resultado por referencia) | `evidence/backends/gate_2026-10-30T211143Z.json`, `isyco/backends/cobol.py` |
| El contrato de backend reporta costo medido (pared, CPU, pico de memoria del binario, compilación) | DEMONSTRATED (2026-10-29), informativo y no comparado; pico de memoria por GNU time (el rusage de un hijo de Python mide al intérprete) | `spec/BACKEND.md` §3.1, `evidence/backends/gate_2026-10-29T055122Z.json` |
| Un backend es más rápido o más ligero que otro | NOT_DEMONSTRATED (una corrida por caso en el gate, sin repeticiones ni control de carga; eso es F6) | — |
| Aritmética de ISyCoLang implementada dos veces de forma independiente (Python exacto y C con `__int128`) con el mismo resultado | VERIFIED dentro del dominio probado | `evidence/c/` |
| El validador de IR rechaza IR malformada | DEMONSTRATED (11 mutaciones, cada una con su código) | `tests/test_ir.py::ValidatorRejects` |
| Inventario de candidatos a backend en `workspace/assembly` | DEMONSTRATED (2026-10-28) | `evidence/inventory/` |
| Toolchains del host para olas 1–5 presentes | DEMONSTRATED (2026-10-28) | `evidence/inventory/toolchains_2026-10-28.txt` |
| La arquitectura V1 es viable | INFERRED | `docs/FEASIBILITY_2026-10-28.md` |
| Un core de 3 slots es buena ruta de ejecución | INFERRED NO | estudio §B |
| Algún pack de 3 ops es Turing-completo | NOT_DEMONSTRATED | — |
