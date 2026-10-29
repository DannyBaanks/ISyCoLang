# ISyCoLang

**Repo PRIVADO** (decisión de Danny, 2026-10-28): sin licencia ni remoto público.

**Estado: `EXECUTABLE`** (fase F2): hay un intérprete de referencia que cumple el
corpus de conformidad v0.1. Todavía no hay compilador (F3–F4).

## Respuestas rápidas (estándar §16)

| pregunta | respuesta hoy |
|---|---|
| ¿Qué es? | Un lenguaje pequeño con semántica propia y un compilador que usa muchos lenguajes como backends por contrato. |
| ¿Qué lo hace distinto? | La semántica es de ISyCoLang; C, Rust, COBOL, Prolog, esolangs… compiten por implementarla y la evidencia elige. Un carril aparte (3OPS Lab) investiga bases de tres operaciones. |
| ¿Formato? | `.isy`, spec congelada en `spec/CORE.md` (v0.1). |
| ¿Cómo ejecuto un programa? | `python3 -m isyco run programa.isy --input '["40","2"]'` |
| ¿Dónde vive el engine? | `isyco/` (intérprete de referencia en Python, semántica normativa). |
| ¿Qué está demostrado? | Intérprete conforme al corpus (58/58), redondeo verificado contra `decimal`, inventario de backends. |
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
isyco/                             intérprete de referencia y CLI
programs/conformance/              corpus v0.1 (expected previos al intérprete)
tests/                             conformidad, determinismo, sabotaje, oráculo
tools/run_conformance.py           corre el corpus y guarda evidencia nueva
```

## Reproducir lo que existe

```bash
sha256sum -c docs/origin/SHA256SUMS.txt
python3 tools/inventory_assembly.py            # escribe un JSON nuevo con timestamp
python3 -m unittest discover -s tests -v       # 12 tests
python3 tools/run_conformance.py               # corpus + evidencia nueva
```

## Relación con el monorepo

Los backends candidatos viven en `~/Development/ISyCo/workspace/assembly`
(copias; fuente de verdad en `~/Development/ISyCo Git/<Repo>`). Este repo los
lee, no los modifica. Se rige por `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`.
