"""Inventario de solo lectura de workspace/assembly como candidatos a backend.

No ejecuta ningún engine. Solo mira qué archivos existen en cada carpeta y
clasifica cómo podría recibir un programa externo:

- INTERPRETER_PY: tiene <slug>_interpreter.py; run_esolang.py le pasa un
  archivo fuente arbitrario (candidato directo a backend).
- BOOTSTRAP_ONLY: tiene entry del contrato E=(I,X,O,S) (run_host.py/.js o
  bootstrap ELF) pero ese entry ejecuta su propio bootstrap fijo, no
  programas externos. Para ser backend necesita un adapter nuevo.
- NON_ENGINE: clasificado en TAXONOMY.json (SCAFFOLD, WEAK_INTERPRETER, TOOL).
- UNCLASSIFIED: nada de lo anterior.

Uso:
    python3 tools/inventory_assembly.py [ruta/a/workspace/assembly] [--out DIR]

La raíz del monorepo, si no se pasa como argumento, sale de `ISYCO_ASSEMBLY` o
de `~/Development/ISyCo/workspace/assembly`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ASSEMBLY = Path(os.environ.get(
    "ISYCO_ASSEMBLY",
    str(Path.home() / "Development" / "ISyCo" / "workspace" / "assembly")))


def classify(engine_dir: Path, taxonomy: dict) -> dict:
    slug = engine_dir.name
    has_interpreter = (engine_dir / f"{slug}_interpreter.py").is_file()
    has_entry = ((engine_dir / "run_host.py").is_file()
                 or (engine_dir / "run_host.js").is_file()
                 or any(engine_dir.glob("bootstrap*.exe")))
    if has_interpreter:
        kind = "INTERPRETER_PY"
    elif has_entry:
        kind = "BOOTSTRAP_ONLY"
    elif slug in taxonomy:
        kind = "NON_ENGINE:" + taxonomy[slug].get("kind", "?")
    else:
        kind = "UNCLASSIFIED"
    return {
        "slug": slug,
        "kind": kind,
        "has_entry": has_entry,
        "has_interpreter_py": has_interpreter,
        "has_source_json": (engine_dir / "SOURCE.json").is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("assembly", nargs="?", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--out", type=Path, default=Path("evidence/inventory"))
    args = parser.parse_args()

    taxonomy_path = args.assembly / "TAXONOMY.json"
    taxonomy = {}
    if taxonomy_path.is_file():
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8")).get("entries", {})

    rows = [classify(d, taxonomy) for d in sorted(args.assembly.iterdir())
            if d.is_dir() and not d.name.startswith(("_", "."))]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report = {
        "schema": "isycolang.assembly_inventory/1",
        "generated_utc": stamp,
        "assembly_root": str(args.assembly),
        "excluded": "carpetas que empiezan con '_' o '.' (p. ej. _quarantine)",
        "dirs": len(rows),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"assembly_inventory_{stamp}.json"
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out_file.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(json.dumps({"out": str(out_file), "sha256": digest,
                      "dirs": len(rows), "counts": report["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
