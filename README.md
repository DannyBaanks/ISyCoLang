# ISyCoLang

**Repo PRIVADO** (decisión de Danny, 2026-10-28): sin licencia ni remoto.

**Estado: `EXECUTABLE`** (core v0.3 con strings y structs; fase F5, ola 1 de 6): intérprete de referencia conforme al corpus
v0.1, IR canónica (ISY-IR) y backends nativos C, Rust y Zig verificados contra
la referencia bajo el contrato `ISY_BACKEND/1`.

## Respuestas rápidas (estándar §16)

| pregunta | respuesta hoy |
|---|---|
| ¿Qué es? | Un lenguaje pequeño con semántica propia y un compilador que usa muchos lenguajes como backends por contrato. |
| ¿Qué lo hace distinto? | La semántica es de ISyCoLang; C, Rust, COBOL, Prolog, esolangs… compiten por implementarla y la evidencia elige. Un carril aparte (3OPS Lab) investiga bases de tres operaciones. |
| ¿Formato? | `.isy`; spec congelada en `spec/CORE.md` (v0.1) + `spec/CORE_v0.2.md` + `spec/CORE_v0.3.md` (strings y structs); la cabecera `isyco 0.1`/`0.2`/`0.3` elige. |
| ¿Cómo ejecuto un programa? | `python3 -m isyco run programa.isy --input '["40","2"]'` (`--via c`, `--via rust` o `--via zig` para nativo). Guía para personas: `GUIA.md`. |
| ¿Dónde vive el engine? | `isyco/` (intérprete de referencia en Python, semántica normativa). |
| ¿Qué está demostrado? | Intérprete conforme a los corpus v0.1 y v0.2 (78/78), IR que preserva la semántica, backends C, Rust y Zig iguales a la referencia (78/78 y 8 484 corridas diferenciales cada uno; C además con gcc/clang y sanitizers). Ver claim table. |
| ¿Qué NO está demostrado? | Todo lo demás; ver la claim table en `ROADMAP.md` §6. |
| ¿Tests? | `python3 -m unittest discover -s tests -v` |
| ¿Evidencia? | `evidence/` |
| ¿Límites conocidos? | Ver `docs/FEASIBILITY_2026-10-28.md` §12 (riesgos). |

## Mapa

```text
ROADMAP.md                         fases F0–F9 + carril 3OPS Lab, con gates
docs/FEASIBILITY_2026-10-28.md     estudio de viabilidad (por qué esta arquitectura)
docs/origin/                       roadmap V0 y estándar, preservados con SHA-256
tools/inventory_assembly.py        inventario de solo lectura de workspace/assembly
evidence/inventory/                salidas del inventario y de toolchains
spec/CORE.md                       semántica v0.1 congelada (+ ERRATA_v0.1.md)
spec/CORE_v0.2.md, CORE_v0.3.md    cambios congelados de v0.2 y v0.3 (str<N>, structs)
spec/IR.md                         forma de ISY-IR v0.1 (lo que reciben los backends)
GUIA.md                            guía para personas: escribir, correr y leer un resultado
spec/BACKEND.md                    contrato ISY_BACKEND/1 (capacidades, protocolo, conformidad, costo)
docs/decisions/                    decisiones registradas (p. ej. no reusar Code IR)
docs/BACKEND_C.md                  backend C: garantías, protocolo, límites
isyco/backends/base.py             driver común: validación, capacidades, caché, ejecución
isyco/backends/c.py                ISY-IR -> C -> binario nativo
isyco/backends/rust.py             ISY-IR -> Rust -> binario nativo
isyco/backends/zig.py              ISY-IR -> Zig -> binario nativo
isyco/difftest.py                  diferencial por tipo numérico en valores frontera
isyco/                             intérprete de referencia y CLI
programs/conformance/              corpus v0.1 (expected previos al intérprete; SUPERSEDED.json)
programs/conformance_v0.2/         corpus v0.2 (expected previos a implementar v0.2)
tests/                             conformidad, determinismo, sabotaje, oráculo
tools/run_conformance.py           corre el corpus y guarda evidencia nueva
tools/ir_gate.py                   compara IR vs referencia y guarda evidencia
tools/c_gate.py                    gate F4 (tres vías, gcc/clang, sanitizers, sabotaje)
tools/c_sanitize_v03.py            backend C con UBSan+ASan sobre v0.3 (corpus + strings)
tools/backend_gate.py              gate F5 (corpus, capacidades, diferencial, stub) por backend
```

## Reproducir lo que existe

```bash
sha256sum -c docs/origin/SHA256SUMS.txt
python3 tools/inventory_assembly.py            # escribe un JSON nuevo con timestamp
python3 -m unittest discover -s tests -v       # 70 tests
python3 -m isyco ir programa.isy               # ISY-IR canónica
python3 tools/ir_gate.py                       # gate F3 + evidencia nueva
python3 tools/c_gate.py                        # gate F4 + evidencia nueva (varios minutos)
python3 tools/backend_gate.py                  # gate F5: C, Rust y Zig + evidencia nueva
python3 tools/run_conformance.py               # corpus + evidencia nueva
```

## Relación con el monorepo

Los backends candidatos viven en `~/Development/ISyCo/workspace/assembly`
(copias; fuente de verdad en `~/Development/ISyCo Git/<Repo>`). Este repo los
lee, no los modifica. Se rige por `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`.
