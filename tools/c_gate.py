"""Gate F4: backend C contra referencia y expected, con evidencia.

Uso: python3 tools/c_gate.py [--pairs N]   (desde la raíz del repo)

1. Corpus en tres vías: expected (a mano) ↔ referencia ↔ binario C,
   con gcc y clang, con y sin UBSan+ASan.
2. Diferencial por tipo numérico (isyco/difftest.py) con gcc, y una muestra con sanitizers.
3. Sabotajes: cada backend saboteado debe fallar el corpus y el diferencial.
Escribe evidence/c/gate_<UTC>.json (nunca sobrescribe). Exit 0 solo si todo pasa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import c as C  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.backends.base import missing_features  # noqa: E402
from isyco.difftest import compare  # noqa: E402

SANITIZE = ("-fsanitize=undefined,address", "-fno-sanitize-recover=all")
KEYS = COMPARED + ("steps",)


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def version(cc: str) -> str:
    return subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.split("\n")[0]


def corpus_three_way(cases, **kw) -> dict:
    rows, unsupported = [], []
    for case in cases:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        got, _ = C.run_c(case["program"], case["input"], case.get("limits"), **kw)
        if got.get("status") == "UNSUPPORTED" and got["code"] == ",".join(
                missing_features(C.BACKEND, case["program"])):
            unsupported.append({"name": case["name"], "missing": got["code"]})   # no cubierto
            continue
        expected_ok = {k: ref[k] for k in COMPARED} == case["expected"]
        backend_ok = ({k: ref[k] for k in KEYS} == {k: got.get(k) for k in KEYS}
                      and not got.get("backend_stderr"))
        rows.append({"name": case["name"], "expected_vs_reference": expected_ok,
                     "reference_vs_backend": backend_ok})
    return {"cases": len(rows), "unsupported": unsupported,
            "expected_vs_reference_ok": sum(r["expected_vs_reference"] for r in rows),
            "reference_vs_backend_ok": sum(r["reference_vs_backend"] for r in rows),
            "failures": [r for r in rows if not (r["expected_vs_reference"] and r["reference_vs_backend"])]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=40)
    args = parser.parse_args()
    cases = load_all(ROOT)
    compilers = [cc for cc in ("gcc", "clang") if shutil.which(cc)]
    missing_compilers = [cc for cc in ("gcc", "clang") if cc not in compilers]
    report = {"schema": "isycolang.c_gate/1", "compilers": {cc: version(cc) for cc in compilers},
              "missing_compilers": missing_compilers,
              "cflags": C.CFLAGS, "sanitize_flags": list(SANITIZE), "corpus": {}, "difftest": {},
              "sabotage": {}}
    # El gate promete gcc Y clang (docs/BACKEND_C.md): con uno solo no se puede afirmar.
    ok = not missing_compilers
    if missing_compilers:
        print(f"compiladores ausentes: {', '.join(missing_compilers)}", file=sys.stderr)
    for cc in compilers:
        os.environ["ISYCO_CC"] = cc
        for label, flags in (("plain", ()), ("sanitized", SANITIZE)):
            res = corpus_three_way(cases, extra_flags=flags)
            report["corpus"][f"{cc}/{label}"] = res
            # UNSUPPORTED no pertenece al denominador: fuera del dominio declarado
            # el gate no puede afirmar nada, así que C (que declara todas las
            # capacidades) lo trata como fallo en vez de encoger la cuenta.
            ok &= not res["failures"] and not res["unsupported"]
            print(f"corpus {cc}/{label}: {res['reference_vs_backend_ok']}/{res['cases']} "
                  f"(unsupported {len(res['unsupported'])})", flush=True)
    if compilers:
        os.environ["ISYCO_CC"] = compilers[0]
        for label, executor, pairs in (("gcc/plain", C.run_c, args.pairs),
                                       ("gcc/sanitized", partial(C.run_c, extra_flags=SANITIZE), 4)):
            res = compare(executor, pairs=pairs)
            report["difftest"][label] = {"runs": res["runs"], "pairs_per_op": pairs,
                                         "seed": res["seed"], "types": len(res["types"]),
                                         "diffs": res["diffs"][:50],
                                         "diff_count": len(res["diffs"])}
            ok &= not res["diffs"]
            print(f"difftest {label}: {res['runs']} corridas, "
                  f"{len(res['diffs'])} diferencias", flush=True)
        for sabotage in ("half_even_as_half_up", "div_floor"):
            corpus_res = corpus_three_way(cases, sabotage=sabotage)
            diff_res = compare(partial(C.run_c, sabotage=sabotage), pairs=4)
            detected = bool(corpus_res["failures"]) and bool(diff_res["diffs"])
            report["sabotage"][sabotage] = {
                "corpus_failures": [f["name"] for f in corpus_res["failures"]],
                "difftest_diffs": len(diff_res["diffs"]), "detected": detected}
            ok &= detected
            print(f"sabotaje {sabotage}: detectado={detected}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report["generated_utc"] = stamp
    report["git_head"] = git_head()
    report["verdict"] = "PASS" if ok else "FAIL"
    out = ROOT / "evidence" / "c" / f"gate_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out.write_text(payload, encoding="utf-8")
    print(json.dumps({"out": str(out.relative_to(ROOT)), "verdict": report["verdict"],
                      "sha256": hashlib.sha256(payload.encode()).hexdigest()}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
