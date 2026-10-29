"""Corre el corpus con el intérprete de referencia y guarda evidencia nueva.

Uso: python3 tools/run_conformance.py   (desde la raíz del repo)
Escribe evidence/conformance/run_<UTC>.json (nunca sobrescribe) e imprime el
resumen y su SHA-256. Exit 0 solo si todo el corpus pasa.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.conformance import load_all, run_corpus  # noqa: E402


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    rows = run_corpus(load_all(ROOT))
    passed = sum(row["verdict"] == "PASS" for row in rows)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report = {
        "schema": "isycolang.conformance_run/1",
        "generated_utc": stamp,
        "engine": "isyco reference interpreter (Python)",
        "git_head": git_head(),
        "python": platform.python_version(),
        "spec_sha256": hashlib.sha256((ROOT / "spec" / "CORE.md").read_bytes()).hexdigest(),
        "total": len(rows),
        "passed": passed,
        "rows": rows,
    }
    out_dir = ROOT / "evidence" / "conformance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"run_{stamp}.json"
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out_file.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(json.dumps({"out": str(out_file.relative_to(ROOT)), "sha256": digest,
                      "total": len(rows), "passed": passed}))
    for row in rows:
        if row["verdict"] != "PASS":
            print("FAIL", row["name"], row["observed"], file=sys.stderr)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
