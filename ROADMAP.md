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
y los `expected` escritos a mano **antes** de implementar. Nada de v0.5 está
aprobado ni implementado; el directorio está fuera de `CORPORA`, así que los 170
casos de F2.3 no se mueven. Dos medidas que sí entran hoy: el azúcar del `for`
con el incremento al final del cuerpo es **incorrecto** (`continue` no avanza →
`LIMIT_REACHED`, control negativo en el corpus) y añadir la cabecera `0.5` toca
**diez** sitios con la versión fijada en código (`evidence/v05_propuesta/`).

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
