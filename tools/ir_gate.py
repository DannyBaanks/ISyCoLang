"""Gate F3: intérprete de ISY-IR == intérprete de referencia, con evidencia.

Uso: python3 tools/ir_gate.py   (desde la raíz del repo)
Para cada caso del corpus y cada nivel de traza guarda el SHA-256 del resultado
y de la traza por las dos rutas, y el `semantic_hash` de la IR. Escribe
evidence/ir/gate_<UTC>.json (nunca sobrescribe). Exit 0 solo si todo coincide.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import canonical_json, run  # noqa: E402
from isyco.conformance import load_all  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir import semantic_hash  # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir  # noqa: E402


def sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    rows = []
    for case in load_all(ROOT):
        try:
            ir_sem = semantic_hash(compile_ir(case["program"]))
        except InvalidProgram:
            ir_sem = None  # rechazado por el frontend: no hay IR
        for level in ("stmt", "full"):
            ref = run(case["program"], case["input"], case.get("limits"), trace=level)
            via = run_via_ir(case["program"], case["input"], case.get("limits"), trace=level)
            rows.append({"name": case["name"], "trace_level": level, "ir_semantic_hash": ir_sem,
                         "ref_result_sha256": sha(ref[0]), "ir_result_sha256": sha(via[0]),
                         "ref_trace_sha256": sha(ref[1]), "ir_trace_sha256": sha(via[1]),
                         "verdict": "EQUAL" if canonical_json(ref) == canonical_json(via) else "DIFF"})
    equal = sum(r["verdict"] == "EQUAL" for r in rows)
    with_ir = len({r["name"] for r in rows if r["ir_semantic_hash"]})
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report = {"schema": "isycolang.ir_gate/1", "generated_utc": stamp,
              "git_head": git_head(),
              "comparisons": len(rows), "equal": equal, "programs_lowered_to_ir": with_ir,
              "rows": rows}
    out = ROOT / "evidence" / "ir" / f"gate_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2) + "\n"
    out.write_text(payload, encoding="utf-8")
    print(json.dumps({"out": str(out.relative_to(ROOT)),
                      "sha256": hashlib.sha256(payload.encode()).hexdigest(),
                      "comparisons": len(rows), "equal": equal,
                      "programs_lowered_to_ir": with_ir}))
    return 0 if equal == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
