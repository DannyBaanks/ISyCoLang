"""¿Se puede escribir una librería de texto HOY? Sonda de tres vías.

Los `expected` están escritos a mano antes de correr nada (rito del repo: esperado
independiente + backends como testigos). La pregunta no es si el core sabe
manipular texto sino si un programa real de librería —que crece, que recorre
carácter a carácter— entra en el `str<N>` de v0.3 sin reglas nuevas.

    python3 tools/textlib_probe.py            # tabla
    python3 tools/textlib_probe.py --json     # documento para evidence/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.backends import available, registry                    # noqa: E402
from isyco.conformance import COMPARED                            # noqa: E402
from isyco.interp import DEFAULT_LIMITS, run                       # noqa: E402
from isyco.ir_interp import compile_ir                             # noqa: E402

CASES = [
    {"name": "06_biblioteca_texto", "inputs": [],
     "claim": "pad, empieza_con, cuenta_letra y mayus funcionan con capacidades fijas",
     "expected": {"status": "HALTED", "code": None, "return": None,
                  "emits": ["hola----", "abc...", "5", "true", "false", "false",
                            "3", "0", "0", "HOLA 123", "ID----"]}},
    {"name": "07_texto_desborda", "inputs": [],
     "claim": "rellenar más allá de la capacidad declarada es ERROR(OVERFLOW), nunca truncado",
     "expected": {"status": "ERROR", "code": "OVERFLOW", "return": None, "emits": []}},
]


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def shape(row: dict) -> str:
    return f"{row['status']}" + (f"({row['code']})" if row.get("code") else "")


def probe(case: dict) -> dict:
    data = (ROOT / "programs" / "dogfood" / f"{case['name']}.isy").read_bytes()
    ref, _ = run(data, case["inputs"], DEFAULT_LIMITS)
    out = {**case, "schema": compile_ir(data)["schema"], "steps": ref["steps"],
           "reference": {k: ref[k] for k in COMPARED}}
    out["reference_ok"] = {k: ref[k] for k in COMPARED} == case["expected"]
    backends = {}
    for name in sorted(registry()):
        backend = available().get(name)
        if backend is None or not backend.toolchain():
            backends[name] = {"status": "SIN_TOOLCHAIN"}
            continue
        got, _ = backend.run(data, case["inputs"], DEFAULT_LIMITS)
        observed = {k: got.get(k) for k in COMPARED}
        backends[name] = {"status": shape(got), "code": got.get("code"),
                          "emits": got.get("emits"), "return": got.get("return"),
                          "igual_a_referencia": observed == {k: ref[k] for k in COMPARED},
                          "igual_a_esperado": observed == case["expected"],
                          "stderr": bool(got.get("backend_stderr"))}
    out["backends"] = backends
    return out


def main(as_json: bool) -> int:
    results = [probe(case) for case in CASES]
    if as_json:
        print(json.dumps({"git_head": git_head(), "cases": results}, indent=2,
                         sort_keys=True, ensure_ascii=False))
        return 0
    print(f"git_head={git_head()}")
    print("UNSUPPORTED no es fallo: es el dominio declarado del backend "
          "(COBOL no cubre str ni isy-ir/0.2).")
    for res in results:
        print(f"\n{res['name']}  —  {res['claim']}")
        print(f"  esperado (a mano) {json.dumps(res['expected'], ensure_ascii=False)}")
        print(f"  referencia        {shape(res['reference'])} emits={res['reference']['emits']}"
              f" steps={res['steps']} schema={res['schema']}"
              f"  {'COINCIDE' if res['reference_ok'] else 'DIFIERE'}")
        for name, row in res["backends"].items():
            if row["status"] == "SIN_TOOLCHAIN":
                print(f"  {name:10s} sin toolchain")
                continue
            print(f"  {name:10s} {row['status']:22s} vs esperado="
                  f"{'IGUAL' if row['igual_a_esperado'] else 'distinto'} "
                  f"vs referencia={'IGUAL' if row['igual_a_referencia'] else 'distinto'}"
                  f"{'  STDERR' if row['stderr'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--json" in sys.argv[1:]))
