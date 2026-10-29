# ISyCoLang

**Repo PRIVADO** (decisión de Danny, 2026-10-28): sin licencia ni remoto público.

**Estado: `IDEA`.** No hay engine, parser ni compilador todavía. Este repo
contiene el roadmap, el estudio de viabilidad y el inventario de backends
candidatos. Todo lo demás está marcado `NOT_DEMONSTRATED`.

## Respuestas rápidas (estándar §16)

| pregunta | respuesta hoy |
|---|---|
| ¿Qué es? | Un lenguaje pequeño con semántica propia y un compilador que usa muchos lenguajes como backends por contrato. |
| ¿Qué lo hace distinto? | La semántica es de ISyCoLang; C, Rust, COBOL, Prolog, esolangs… compiten por implementarla y la evidencia elige. Un carril aparte (3OPS Lab) investiga bases de tres operaciones. |
| ¿Formato? | `.isy` (propuesto, F1). |
| ¿Cómo ejecuto un programa? | Todavía no se puede. |
| ¿Dónde vive el engine? | No existe (F2). |
| ¿Qué está demostrado? | Solo el inventario de backends y toolchains (`evidence/inventory/`). |
| ¿Qué NO está demostrado? | Todo lo demás; ver la claim table en `ROADMAP.md` §6. |
| ¿Tests? | Aún no hay. |
| ¿Evidencia? | `evidence/` |
| ¿Límites conocidos? | Ver `docs/FEASIBILITY_2026-10-28.md` §12 (riesgos). |

## Mapa

```text
ROADMAP.md                         fases F0–F9 + carril 3OPS Lab, con gates
docs/FEASIBILITY_2026-10-28.md     estudio de viabilidad (por qué esta arquitectura)
docs/origin/                       roadmap V0 y estándar, preservados con SHA-256
tools/inventory_assembly.py        inventario de solo lectura de workspace/assembly
evidence/inventory/                salidas del inventario y de toolchains
spec/  programs/conformance/  tests/   vacíos hasta F1/F2
```

## Reproducir lo que existe

```bash
sha256sum -c docs/origin/SHA256SUMS.txt
python3 tools/inventory_assembly.py            # escribe un JSON nuevo con timestamp
```

## Relación con el monorepo

Los backends candidatos viven en `~/Development/ISyCo/workspace/assembly`
(copias; fuente de verdad en `~/Development/ISyCo Git/<Repo>`). Este repo los
lee, no los modifica. Se rige por `docs/origin/ISYCO_LANGUAGE_ENGINE_STANDARD.md`.
