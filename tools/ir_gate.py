"""Gate F3: intérprete de ISY-IR == intérprete de referencia, con evidencia.

Uso: python3 tools/ir_gate.py   (desde la raíz del repo)

Para cada caso del corpus y cada nivel de traza guarda el SHA-256 del resultado
y de la traza por las dos rutas, y el `semantic_hash` de la IR. Escribe
evidence/ir/gate_<UTC>.json (nunca sobrescribe). Exit 0 solo si todo coincide.

No hay toolchain aquí, así que no hace falta la guarda por caso: si la referencia o
el intérprete IR explotan, eso es un bug del idioma y tiene que subir con traceback.
Lo que sí se endurece es la escritura — el sello se toma al empezar, las filas entran
en el recibo a medida que se producen (una corrida abortada deja las ya medidas) y el
`finally` sella aunque la corrida reviente, con su stdout y los SHA256SUMS del
directorio.
"""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
from isyco import canonical_json, run  # noqa: E402
from isyco.conformance import load_all  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.harness import SCHEMA  # noqa: E402
from isyco.ir import semantic_hash  # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir  # noqa: E402


def sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def recuento(rows: list) -> dict:
    """Las tres cifras del recibo, calculadas sobre lo que se llegó a medir."""
    return {"comparisons": len(rows),
            "equal": sum(r["verdict"] == "EQUAL" for r in rows),
            "programs_lowered_to_ir": len({r["name"] for r in rows if r["ir_semantic_hash"]})}


def main() -> int:
    sello = _gate.stamp()
    destino = _gate.EVIDENCE / "ir"
    with _gate.captura_stdout() as transcripcion:
        rows = []
        report = {"schema": "isycolang.ir_gate/1", "generated_utc": sello,
                  "git_head": _gate.git_head(), **_gate.arbol(),
                  "harness": {"guarda": SCHEMA, "codigos": ["HARNESS_INTERNAL"],
                              "capas": ["corrida"]},
                  "rows": rows}
        ok = True
        try:
            for case in load_all(ROOT):
                try:
                    ir_sem = semantic_hash(compile_ir(case["program"]))
                except InvalidProgram:
                    ir_sem = None  # rechazado por el frontend: no hay IR
                for level in ("stmt", "full"):
                    ref = run(case["program"], case["input"], case.get("limits"), trace=level)
                    via = run_via_ir(case["program"], case["input"], case.get("limits"),
                                     trace=level)
                    rows.append({"name": case["name"], "trace_level": level,
                                 "ir_semantic_hash": ir_sem,
                                 "ref_result_sha256": sha(ref[0]),
                                 "ir_result_sha256": sha(via[0]),
                                 "ref_trace_sha256": sha(ref[1]),
                                 "ir_trace_sha256": sha(via[1]),
                                 "verdict": "EQUAL" if canonical_json(ref) == canonical_json(via)
                                 else "DIFF"})
        except Exception as exc:  # noqa: BLE001 — capa 3: el recibo se escribe igualmente
            report["abortado"] = {"exception": type(exc).__name__, "excerpt": str(exc)[:400],
                                  "traceback": traceback.format_exc()[-2000:]}
            ok = False
            print(f"ARNÉS ABORTADO: {type(exc).__name__}: {exc}", file=sys.stderr)
        report.update(recuento(rows))
        # Un corpus vacío no es conformidad: 0 == 0 no demuestra nada (como en F2).
        report["verdict"] = "PASS" if (ok and rows and report["equal"] ==
                                       report["comparisons"]) else "FAIL"
        try:
            sellado = _gate.sellar(report, transcripcion.texto, destino, f"gate_{sello}")
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({**sellado, "verdict": report["verdict"],
                          "comparisons": report["comparisons"], "equal": report["equal"],
                          "programs_lowered_to_ir": report["programs_lowered_to_ir"],
                          "abortado": "abortado" in report}, ensure_ascii=False))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
