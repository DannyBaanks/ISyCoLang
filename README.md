# ISyCoLang

**Repo PRIVADO** (decisión de Danny, 2026-10-28): sin licencia ni remoto.

**Respaldo**: sin remoto no hay `push`; se usa un bundle verificable **fuera** del
repo: `git bundle create ../ISyCoLang-<fecha>.bundle --all` y `git bundle verify`
(historia completa; el SHA-256 del snapshot vigente se publica en el Tablero,
comentario de cierre de la lista de pulido).

**Estado: `EXECUTABLE`** (core v0.4 congelado más las decisiones v0.5 —V1, V2, V6,
V6-bis y V7 implementadas y selladas; `spec/CORE_v0.5.md` en `BORRADOR`—; fase F5,
olas 1 y 2 PASS, y el corpus v0.5 dentro del gate: 212 casos): intérprete de referencia
conforme a los corpus v0.1–v0.5, IR canónica (ISY-IR) y backends nativos C, Rust y Zig —
más los backends `pydecimal` y `cobol` de la ola 2, con sustratos `decimal` y GnuCOBOL —
verificados contra la referencia bajo el contrato `ISY_BACKEND/1` (`cobol` en el
núcleo numérico: `str` y `struct` responden UNSUPPORTED **por lo que el programa exige**,
no por su cabecera — CORE v0.5 V7).

## Respuestas rápidas (estándar §16)

| pregunta | respuesta hoy |
|---|---|
| ¿Qué es? | Un lenguaje pequeño con semántica propia y un compilador que usa muchos lenguajes como backends por contrato. |
| ¿Qué lo hace distinto? | La semántica es de ISyCoLang; C, Rust, COBOL, Prolog, esolangs… compiten por implementarla y la evidencia elige. Un carril aparte (3OPS Lab) investiga bases de tres operaciones. |
| ¿Formato? | `.isy`; spec congelada en `spec/CORE.md` (v0.1) + `spec/CORE_v0.2.md` + `spec/CORE_v0.3.md` (strings y structs) + `spec/CORE_v0.4.md` (módulos); la cabecera `isyco 0.1`/`0.2`/`0.3`/`0.4` elige. `isyco 0.5` ya corre en el engine (V1, V2, V6, V6-bis, V7) y su texto está en `spec/CORE_v0.5.md` como `BORRADOR`, sin congelar. |
| ¿Cómo ejecuto un programa? | `python3 -m isyco run programa.isy --input '["40","2"]'` (`--via c`, `--via rust`, `--via zig`, `--via pydecimal` o `--via cobol` para compilado). Guía para personas: `GUIA.md`. |
| ¿Dónde vive el engine? | `isyco/` (intérprete de referencia en Python, semántica normativa). |
| ¿Qué está demostrado? | Intérprete conforme a los corpus v0.1–v0.5 (212/212), IR que preserva la semántica (424/424 comparaciones iguales, 145 programas bajados a IR), backends C, Rust, Zig y pydecimal iguales a la referencia (212/212 y 8 484 corridas diferenciales sin diferencias cada uno, más 1 270 del diferencial de strings; C además con las cuatro combinaciones gcc/clang × plain/sanitized sobre los 212 — gate F4, `evidence/c/gate_2026-11-01T071619Z.json`); COBOL igual dentro de su dominio declarado (146/212, 66 UNSUPPORTED nombrando la capacidad que exige cada programa —`str`/`struct`/`emit_array`; las capacidades las exige el programa, no su cabecera: CORE v0.5 V7—, 8 484 corridas diferenciales sin diferencias). Ver claim table. |
| ¿Qué NO está demostrado? | Todo lo demás; ver la claim table en `ROADMAP.md` §6. |
| ¿Tests? | `python3 -m unittest discover -s tests -v` |
| ¿Evidencia? | `evidence/`, inventariada en `docs/EVIDENCE_MATRIX.md` |
| ¿Límites conocidos? | Ver `docs/FEASIBILITY_2026-10-28.md` §12 (riesgos). |

## Mapa

```text
ROADMAP.md                         fases F0–F9 + carril 3OPS Lab, con gates
docs/FEASIBILITY_2026-10-28.md     estudio de viabilidad (por qué esta arquitectura)
docs/origin/                       roadmap V0 y estándar, preservados con SHA-256
tools/inventory_assembly.py        inventario de solo lectura de workspace/assembly
evidence/inventory/                salidas del inventario y de toolchains
spec/CORE.md                       semántica v0.1 congelada (+ ERRATA_v0.1.md)
spec/CORE_v0.2.md … CORE_v0.4.md   cambios congelados de v0.2, v0.3 (str<N>, structs) y v0.4 (módulos)
spec/CORE_v0.5_propuesta.md        propuesta V1–V7 (2026-10-30) con sus correcciones fechadas
spec/CORE_v0.5.md                  texto normativo de v0.5 — BORRADOR, sin congelar ni sellar
spec/IR.md                         forma de ISY-IR v0.1 y v0.2 (lo que reciben los backends)
GUIA.md                            guía para personas: escribir, correr y leer un resultado
spec/BACKEND.md                    contrato ISY_BACKEND/1 (capacidades, protocolo, conformidad, costo)
docs/decisions/                    decisiones registradas (p. ej. no reusar Code IR)
docs/OPEN_QUESTIONS_P1_P4.md       qué respondieron P1–P4 y qué dejó abierto la implementación
docs/EVIDENCE_MATRIX.md            qué está sellado, con qué árbol, y qué afirmación no tiene recibo
docs/BACKEND_C.md                  backend C: garantías, protocolo, límites
isyco/backends/base.py             driver común: validación, capacidades, caché, ejecución
isyco/backends/c.py                ISY-IR -> C -> binario nativo
isyco/backends/rust.py             ISY-IR -> Rust -> binario nativo
isyco/backends/zig.py              ISY-IR -> Zig -> binario nativo
isyco/backends/cobol.py            ISY-IR -> GnuCOBOL -> binario nativo (núcleo numérico)
isyco/backends/pydecimal.py        ISY-IR -> Python 3 con `decimal` (ola 2: otro sustrato, mismo contrato)
isyco/versions.py                  única fuente de la versión: SUPPORTED, INTRODUCED, has()
isyco/specialize.py                V6/V6-bis: las copias acotadas de una definición `str` pelado
isyco/modules.py                   enlazado de módulos (v0.4) y la regla «misma versión que la raíz»
isyco/difftest.py                  diferencial por tipo numérico en valores frontera
isyco/                             intérprete de referencia y CLI
programs/conformance/              corpus v0.1 (expected previos al intérprete; SUPERSEDED.json)
programs/conformance_v0.2/         corpus v0.2 (expected previos a implementar v0.2)
programs/conformance_v0.3/         corpus v0.3 (strings y structs)
programs/conformance_v0.4/         corpus v0.4 (módulos)
programs/conformance_v0.5/         corpus v0.5 (401–442, decisiones V1–V7) + gemelos escritos a mano
programs/dogfood/                  programas que Danny quiere escribir; fuera del gate, miden dolor real
tests/                             conformidad, determinismo, sabotaje, oráculo
tools/run_conformance.py           corre el corpus y guarda evidencia nueva
tools/ir_gate.py                   compara IR vs referencia y guarda evidencia
tools/c_gate.py                    gate F4 (tres vías, gcc/clang, sanitizers, sabotaje)
tools/c_sanitize_v03.py            backend C con UBSan+ASan sobre v0.3 (corpus + strings)
tools/backend_gate.py              gate F5 (corpus, capacidades, diferencial, stub) por backend
tools/warm_build_cache.py          precompila en paralelo los binarios del corpus y diferenciales
tools/v05_proposal_probe.py        qué dice el core HOY del corpus y los gemelos de la propuesta
tools/v05_revalida_probe.py        revalidación de V1 y V2: tres vías, gemelos, no regresión
tools/v05_v6_probe.py              diferencial de V6/V6-bis: referencia, IR ida y vuelta, backends
tools/v05_spec_probe.py            aristas que `spec/CORE_v0.5.md` afirma y ningún caso fija
tools/v05_p4_probe.py              censo de especializaciones (P4) y forma del crecimiento
tools/v7_capability_probe.py       V7: capacidades por contenido vs por etiqueta, con brazo viejo
tools/textlib_probe.py             ¿librería de texto hoy? tres vías sobre `programs/dogfood/`
tools/dogfood_wall_probe.py        el «muro de cabecera» del dogfood: víctimas de la etiqueta o del programa
```

## Reproducir lo que existe

```bash
sha256sum -c docs/origin/SHA256SUMS.txt
python3 tools/inventory_assembly.py            # escribe un JSON nuevo con timestamp
python3 -m unittest discover -s tests -v       # 166 tests (3,2-5,5 min con build/ llena; ver tests/README.md)
python3 -m isyco ir programa.isy               # ISY-IR canónica
python3 tools/ir_gate.py                       # gate F3 + evidencia nueva
python3 tools/c_gate.py                        # gate F4 + evidencia nueva (varios minutos)
python3 tools/backend_gate.py                  # gate F5: C, Rust, Zig, pydecimal y cobol + evidencia nueva
python3 tools/run_conformance.py               # corpus + evidencia nueva
python3 tools/v05_spec_probe.py                # aristas del borrador v0.5: mide y reporta
python3 tools/v05_spec_probe.py --write        # …y sella en evidence/v05_spec/ (árbol limpio = RELEASE_GATE)
python3 tools/v05_p4_probe.py                  # censo de especializaciones (P4): K, W2, W3 y costo
```

## Relación con el monorepo

Los backends candidatos viven en `~/Development/ISyCo/workspace/assembly`
(copias; fuente de verdad en `~/Development/ISyCo Git/<Repo>`). Este repo los
lee, no los modifica. Se rige por `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`.
