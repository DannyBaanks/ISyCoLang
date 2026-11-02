"""Corre el corpus con el intérprete de referencia y guarda evidencia nueva.

Uso: python3 tools/run_conformance.py   (desde la raíz del repo)
Escribe evidence/conformance/run_<UTC>.json (nunca sobrescribe) e imprime el
resumen y su SHA-256. Exit 0 solo si todo el corpus pasa.

Aquí tampoco hay toolchain: la referencia ES el instrumento, así que una excepción
suya es un bug del idioma y se propaga con traceback. Lo endurecido es la escritura —
sello al empezar, veredicto del árbol como campo, y el recibo con su stdout y los
SHA256SUMS del directorio aunque la corrida reviente a mitad. Como `run_corpus`
produce las filas de una sola vez, un abortado queda con `rows` vacío: el recibo
igual dice qué corría y por qué cayó.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
from isyco.conformance import load_all, run_corpus  # noqa: E402
from isyco.harness import SCHEMA  # noqa: E402


def main() -> int:
    sello = _gate.stamp()
    destino = _gate.EVIDENCE / "conformance"
    with _gate.captura_stdout() as transcripcion:
        rows: list[dict] = []
        report = {"schema": "isycolang.conformance_run/1", "generated_utc": sello,
                  "engine": "isyco reference interpreter (Python)",
                  "git_head": _gate.git_head(), **_gate.arbol(),
                  "harness": {"guarda": SCHEMA, "codigos": ["HARNESS_INTERNAL"],
                              "capas": ["corrida"]},
                  "python": platform.python_version(),
                  "spec_sha256": hashlib.sha256((ROOT / "spec" / "CORE.md").read_bytes())
                  .hexdigest(),
                  "total": 0, "passed": 0, "verdict": "FAIL", "rows": rows}
        ok = True
        try:
            rows += run_corpus(load_all(ROOT))
            report["total"] = len(rows)
            report["passed"] = sum(row["verdict"] == "PASS" for row in rows)
        except Exception as exc:  # noqa: BLE001 — capa 3: el recibo se escribe igualmente
            report["abortado"] = {"exception": type(exc).__name__, "excerpt": str(exc)[:400],
                                  "traceback": traceback.format_exc()[-2000:]}
            ok = False
            print(f"ARNÉS ABORTADO: {type(exc).__name__}: {exc}", file=sys.stderr)
        # Un corpus vacío no es un corpus conforme: sin filas, 0 == 0 no demuestra nada.
        report["verdict"] = "PASS" if (ok and rows and report["passed"] ==
                                       report["total"]) else "FAIL"
        try:
            sellado = _gate.sellar(report, transcripcion.texto, destino, f"run_{sello}")
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({**sellado, "verdict": report["verdict"], "total": report["total"],
                          "passed": report["passed"],
                          "abortado": "abortado" in report}, ensure_ascii=False))
        if not rows:
            print("corpus vacío: no hay nada que verificar", file=sys.stderr)
        for row in report["rows"]:
            if row["verdict"] != "PASS":
                print("FAIL", row["name"], row["observed"], file=sys.stderr)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
