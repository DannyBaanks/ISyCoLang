"""Gate F4: backend C contra referencia y expected, con evidencia.

Uso: python3 tools/c_gate.py [--pairs N]   (desde la raíz del repo)

1. Corpus en tres vías: expected (a mano) ↔ referencia ↔ binario C,
   con gcc y clang, con y sin UBSan+ASan.
2. Diferencial por tipo numérico (isyco/difftest.py) con gcc, y una muestra con sanitizers.
3. Sabotajes: cada backend saboteado debe fallar el corpus y el diferencial.

Las llamadas al binario van con la guarda de `isyco/harness`: un `TOOLCHAIN_BUILD_FAIL` se
anota en la lista hermana `harness` y no en `failures`, que sigue midiendo solo desacuerdos
con la referencia. Una pierna que muere deja `not_run` y fuerza FAIL: `cases` cuenta solo lo
que se midió. El sello se calcula al inicio de la corrida (lo que fija F4 es dónde *empezó*),
y `git_head_end` sigue dejando constancia del árbol al terminar. Escribe
`evidence/c/gate_<UTC>.json` con su stdout y `SHA256SUMS.txt`, y nunca sobrescribe.
Exit 0 solo si todo pasa.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import _gate  # noqa: E402
from isyco import run  # noqa: E402
from isyco.backends import c as C  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.backends.base import missing_features  # noqa: E402
from isyco.difftest import compare  # noqa: E402
from isyco.harness import CODES, SCHEMA, intento  # noqa: E402

SANITIZE = ("-fsanitize=undefined,address", "-fno-sanitize-recover=all")
KEYS = COMPARED + ("steps",)


def version(cc: str) -> str:
    return subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.split("\n")[0]


def corpus_three_way(cases, **kw) -> dict:
    """Tres vías por caso. Un caso que revienta el compilador se anota y no se cuenta."""
    rows, unsupported, filas = [], [], []
    for case in cases:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        got, fr = intento(C.run_c, case["program"], case["input"], case.get("limits"),
                          fase="corpus", contexto={"leg": "corpus", "case": case["name"],
                                                   "kw": sorted(kw)}, **kw)
        if fr is not None:
            fr["cc"] = os.environ.get("ISYCO_CC")
            filas.append(fr)
            continue
        got = got[0]
        if got.get("status") == "UNSUPPORTED" and got["code"] == ",".join(
                missing_features(C.BACKEND, case["program"])):
            unsupported.append({"name": case["name"], "missing": got["code"]})   # no cubierto
            continue
        expected_ok = {k: ref[k] for k in COMPARED} == case["expected"]
        backend_ok = ({k: ref[k] for k in KEYS} == {k: got.get(k) for k in KEYS}
                      and not got.get("backend_stderr"))
        rows.append({"name": case["name"], "expected_vs_reference": expected_ok,
                     "reference_vs_backend": backend_ok})
    return {"intentados": len(cases), "cases": len(rows), "unsupported": unsupported,
            "expected_vs_reference_ok": sum(r["expected_vs_reference"] for r in rows),
            "reference_vs_backend_ok": sum(r["reference_vs_backend"] for r in rows),
            "failures": [r for r in rows if not (r["expected_vs_reference"]
                                                 and r["reference_vs_backend"])],
            "harness": filas, "no_medidos": len(filas)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=40)
    args = parser.parse_args()
    sello = _gate.stamp()
    destino = _gate.EVIDENCE / "c"

    with _gate.captura_stdout() as transcripcion:
        report = {"schema": "isycolang.c_gate/1", "generated_utc": sello,
                  "git_head": _gate.git_head(), **_gate.arbol(),
                  "harness": {"guarda": SCHEMA, "codigos": list(CODES),
                              "capas": ["caso", "pierna", "corrida"]},
                  "compilers": {}, "missing_compilers": [],
                  "cflags": C.CFLAGS, "sanitize_flags": list(SANITIZE), "corpus": {},
                  "difftest": {}, "sabotage": {}}
        ok = True
        try:
            cases = load_all(ROOT)
            compilers = [cc for cc in ("gcc", "clang") if shutil.which(cc)]
            report["compilers"] = {cc: version(cc) for cc in compilers}
            report["missing_compilers"] = [cc for cc in ("gcc", "clang") if cc not in compilers]
            # El gate promete gcc Y clang (docs/BACKEND_C.md): con uno solo no se puede afirmar.
            ok = not report["missing_compilers"]
            if report["missing_compilers"]:
                print(f"compiladores ausentes: {', '.join(report['missing_compilers'])}",
                      file=sys.stderr)

            def capa(legible, f, *a, **kw):
                """Capa 2: lo que la guarda por caso no atrapó deja la pierna como `not_run`."""
                res, fr = intento(f, *a, fase=f"pierna:{legible}", contexto={"leg": legible,
                                                                              **kw}, **kw)
                return {"not_run": True, "harness": [fr]} if fr is not None else res

            for cc in compilers:
                os.environ["ISYCO_CC"] = cc
                for label, flags in (("plain", ()), ("sanitized", SANITIZE)):
                    res = capa("corpus", corpus_three_way, cases, extra_flags=flags)
                    if res.get("not_run"):
                        ok = False
                    else:
                        # UNSUPPORTED no pertenece al denominador: fuera del dominio declarado
                        # el gate no puede afirmar nada, así que C (que declara todas las
                        # capacidades) lo trata como fallo en vez de encoger la cuenta.
                        ok &= (not res["failures"] and not res["unsupported"]
                               and not res["harness"])
                    report["corpus"][f"{cc}/{label}"] = res
                    print(f"corpus {cc}/{label}: {res.get('reference_vs_backend_ok', 0)}"
                          f"/{res.get('cases', 0)} (unsupported "
                          f"{len(res.get('unsupported', []))}, arnés "
                          f"{len(res.get('harness', []))})", flush=True)
            if compilers:
                os.environ["ISYCO_CC"] = compilers[0]
                for label, executor, pairs in (("gcc/plain", C.run_c, args.pairs),
                                               ("gcc/sanitized",
                                                partial(C.run_c, extra_flags=SANITIZE), 4)):
                    res = capa("difftest", compare, executor, pairs=pairs)
                    if res.get("not_run"):
                        ok = False
                        report["difftest"][label] = res
                    else:
                        omitted = sum(t["omitted"] for t in res["types"])
                        report["difftest"][label] = {"runs": res["runs"], "pairs_per_op": pairs,
                                                     "seed": res["seed"],
                                                     "types": len(res["types"]),
                                                     "diffs": res["diffs"][:50],
                                                     "diff_count": len(res["diffs"]),
                                                     "harness": res["harness"],
                                                     "types_aborted": res["types_aborted"],
                                                     "omitted": omitted}
                        ok &= not res["diffs"] and not res["harness"]
                    escrito = report["difftest"][label]
                    print(f"difftest {label}: {escrito.get('runs', 0)} corridas, "
                          f"{escrito.get('diff_count', 0)} diferencias, "
                          f"{len(escrito.get('harness', []))} filas del arnés", flush=True)
                for sabotage in ("half_even_as_half_up", "div_floor"):
                    corpus_res = capa("sabotage.corpus", corpus_three_way, cases,
                                      sabotage=sabotage)
                    diff_res = capa("sabotage.difftest", compare,
                                    partial(C.run_c, sabotage=sabotage), pairs=4)
                    filas = corpus_res.get("harness", []) + diff_res.get("harness", [])
                    medidas = not corpus_res.get("not_run") and not diff_res.get("not_run")
                    # None, no 0: una pierna muerta no midió y «0 fallos» diría «no detectó».
                    fallas = ([f["name"] for f in corpus_res.get("failures", [])]
                              if medidas else None)
                    diffs = len(diff_res["diffs"]) if medidas else None
                    # Un crash del arnés no puede blanquearse como «sabotaje detectado».
                    detected = bool(medidas and fallas and diffs and not filas)
                    report["sabotage"][sabotage] = {
                        "corpus_failures": fallas, "difftest_diffs": diffs,
                        "detected": detected, "harness": filas, "not_run": not medidas}
                    ok &= detected
                    print(f"sabotaje {sabotage}: detectado={detected} (corpus {fallas}, "
                          f"diferencial {diffs}, arnés {len(filas)})", flush=True)
        except Exception as exc:  # noqa: BLE001 — capa 3: el recibo se escribe igualmente
            report["abortado"] = {"exception": type(exc).__name__, "excerpt": str(exc)[:400],
                                  "traceback": traceback.format_exc()[-2000:]}
            ok = False
            print(f"ARNÉS ABORTADO: {type(exc).__name__}: {exc}", file=sys.stderr)
        report["git_head_end"] = _gate.git_head()
        report["verdict"] = "PASS" if ok else "FAIL"
        try:
            resumen = _gate.sellar(report, transcripcion.texto, destino, f"gate_{sello}")
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({**resumen, "verdict": report["verdict"]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
