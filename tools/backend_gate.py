"""Gate F5: conformidad ISY_BACKEND/1 de cada backend instalado, con evidencia.

Uso: python3 tools/backend_gate.py [--pairs N] [--only c,rust,zig]

Por backend (spec/BACKEND.md §5):
1. corpus v0.1 + v0.2: mismo status/code/emits/return/steps que la referencia;
2. casos fuera de capacidades -> UNSUPPORTED (se cuentan aparte);
3. diferencial por tipo numérico (isyco/difftest.py) contra la referencia;
4. el engine hace el trabajo: el fuente generado no contiene las salidas
   esperadas y otra entrada da otra salida;
5. cada sabotaje declarado por el backend es detectado (corpus o diferencial);
6. costo medido (spec/BACKEND.md §3.1): resumen por backend, informativo.
Escribe evidence/backends/gate_<UTC>.json (nunca sobrescribe).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import available, registry  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.difftest import compare  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

KEYS = COMPARED + ("steps",)


def corpus(backend, cases, sabotage=None) -> dict:
    passed, unsupported, failures, costs = 0, [], [], []
    for case in cases:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        got, _ = backend.run(case["program"], case["input"], case.get("limits"), sabotage=sabotage)
        if got.get("cost"):
            costs.append(got["cost"])
        if got.get("status") == "UNSUPPORTED":
            unsupported.append({"name": case["name"], "missing": got["code"]})
        elif {k: ref[k] for k in KEYS} == {k: got.get(k) for k in KEYS} and not got.get("backend_stderr"):
            passed += 1
        else:
            failures.append({"name": case["name"], "reference": {k: ref[k] for k in KEYS},
                             "backend": {k: got.get(k) for k in KEYS},
                             "stderr": got.get("backend_stderr")})
    return {"cases": len(cases), "passed": passed, "unsupported": unsupported, "failures": failures,
            "cost": cost_summary(costs)}


def cost_summary(costs: list) -> dict:
    """Resumen del costo medido en las corridas del corpus (no semántico)."""
    rss = [c["max_rss_kb"] for c in costs if c.get("max_rss_kb") is not None]
    return {"runs_measured": len(costs),
            "wall_ms_total": round(sum(c["wall_ms"] for c in costs), 3),
            "user_ms_total": round(sum(c["user_ms"] for c in costs), 3),
            "sys_ms_total": round(sum(c["sys_ms"] for c in costs), 3),
            "max_rss_kb_max": max(rss) if rss else None,
            "rss_measured_runs": len(rss)}


def sabotages(backend, cases, pairs: int) -> dict:
    out = {}
    for sabotage in backend.sabotages:
        res = corpus(backend, cases, sabotage=sabotage)
        diff = compare(partial(backend.run, sabotage=sabotage), pairs=pairs)
        out[sabotage] = {"corpus_failures": len(res["failures"]), "difftest_diffs": len(diff["diffs"]),
                         "detected": bool(res["failures"]) and bool(diff["diffs"])}
    return out


def does_the_work(backend, cases) -> dict:
    case = next(c for c in cases if c["name"] == "027_interes")
    source = backend.emit(compile_ir(case["program"]))
    leaked = [v for v in case["expected"]["emits"] if v in source]
    other, _ = backend.run(case["program"], ["2000.00", "0.0525"])
    ok = not leaked and other.get("emits") == ["8.22", "16.44", "24.66"]
    return {"leaked_outputs": leaked, "other_input_emits": other.get("emits"), "ok": ok}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    only = set(filter(None, args.only.split(",")))
    cases = load_all(ROOT)
    report = {"schema": "isycolang.backend_gate/1", "pairs_per_op": args.pairs,
              "registered": sorted(registry()), "backends": {}}
    ok = True
    for name, backend in available().items():
        if only and name not in only:
            continue
        print(f"[{name}] {backend.toolchain()}", flush=True)
        entry = {"toolchain": backend.toolchain(), "features": sorted(backend.features)}
        entry["corpus"] = corpus(backend, cases)
        print(f"  corpus: {entry['corpus']['passed']}/{entry['corpus']['cases']} "
              f"(unsupported {len(entry['corpus']['unsupported'])}, fallas {len(entry['corpus']['failures'])})", flush=True)
        diff = compare(backend.run, pairs=args.pairs)
        entry["difftest"] = {"runs": diff["runs"], "seed": diff["seed"], "diff_count": len(diff["diffs"]),
                             "diffs": diff["diffs"][:30]}
        print(f"  difftest: {diff['runs']} corridas, {len(diff['diffs'])} diferencias", flush=True)
        entry["does_the_work"] = does_the_work(backend, cases)
        print(f"  engine hace el trabajo: {entry['does_the_work']['ok']}", flush=True)
        entry["sabotage"] = sabotages(backend, cases, pairs=min(args.pairs, 4))
        for sab, res in entry["sabotage"].items():
            print(f"  sabotaje {sab}: detectado={res['detected']} "
                  f"(corpus {res['corpus_failures']}, diferencial {res['difftest_diffs']})", flush=True)
        entry["conformant"] = (not entry["corpus"]["failures"] and not diff["diffs"]
                               and entry["does_the_work"]["ok"]
                               and all(r["detected"] for r in entry["sabotage"].values()))
        ok &= entry["conformant"]
        report["backends"][name] = entry
    report["missing_toolchains"] = sorted(set(registry()) - set(available()))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report["generated_utc"] = stamp
    report["verdict"] = "PASS" if ok and report["backends"] else "FAIL"
    out = ROOT / "evidence" / "backends" / f"gate_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    out.write_text(payload, encoding="utf-8")
    print(json.dumps({"out": str(out.relative_to(ROOT)), "verdict": report["verdict"],
                      "sha256": hashlib.sha256(payload.encode()).hexdigest()}))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
