"""Mide qué dice el core HOY del corpus y los gemelos de la propuesta v0.5.

Dos preguntas separadas, porque la cabecera `isyco 0.5` tapa todo lo demás:

  cuerpo     — el programa tal como está en programs/conformance_v0.5/ (cabecera 0.5).
  a 0.4      — la MISMA línea de código con la cabecera reetiquetada a `isyco 0.4`:
               así el rechazo que se registra es el de la regla nueva, no el de la versión.
  gemelo     — los while equivalentes del azúcar V2 (ya corren en 0.4): fijan el
               `steps` que el gate F2.4 ítem 2 va a exigir y demuestran que los
               `expected` de 403/404/405 no son un número inventado.

Uso:
    python3 tools/v05_proposal_probe.py > evidence/v05_propuesta/run_<UTC>.txt
    python3 tools/v05_proposal_probe.py --json > evidence/v05_propuesta/run_<UTC>.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.conformance import COMPARED, load_corpus                      # noqa: E402
from isyco.errors import InvalidProgram                                   # noqa: E402
from isyco.interp import DEFAULT_LIMITS, run                              # noqa: E402
from isyco.ir_interp import compile_ir                                    # noqa: E402
from isyco.source import Bundle                                           # noqa: E402

CORPUS = ROOT / "programs" / "conformance_v0.5"
GEMELOS = CORPUS / "gemelos"
# El bucle infinito de la variante ingenua se corta por límite, no por reloj.
SPIN_LIMITS = {**DEFAULT_LIMITS, "max_steps": 20_000}


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def rehead(data: bytes, version: str) -> bytes:
    """Reescribe solo la línea 1: el cuerpo queda byte a byte igual."""
    head, _, rest = data.partition(b"\n")
    return f"isyco {version}".encode() + b"\n" + rest


def source_of(case: dict) -> bytes | Bundle:
    program = case["program"]
    if isinstance(program, Bundle):
        return Bundle(tuple((rel, rehead(data, "0.4")) for rel, data in program.files),
                      program.main)
    return rehead(program, "0.4")


def frontend_message(data) -> str | None:
    """El mensaje del frontend con posición: run() solo devuelve el código."""
    try:
        compile_ir(data)
    except InvalidProgram as err:
        return f"{err.code} at {err.at}: {err.detail}"
    return None


def observed(data, inputs, limits=None) -> dict:
    result, _ = run(data, inputs, limits)
    row = {k: result[k] for k in COMPARED}
    row["steps"] = result["steps"]
    return row


def shape(row: dict) -> str:
    return (f"{row['status']}"
            + (f"({row['code']})" if row.get("code") else "")
            + f" emits={row['emits']} return={row['return']!r} steps={row['steps']}")


def corpus_rows() -> list[dict]:
    rows = []
    for case in load_corpus(CORPUS):
        hoy = observed(case["program"], case["input"])
        body = observed(source_of(case), case["input"])
        rows.append({"case": case["name"], "claim": case["claim"], "expected": case["expected"],
                     "input": case["input"],
                     "hoy_0.5": {**hoy, "frontend": frontend_message(case["program"])},
                     "a_0.4": {**body, "frontend": frontend_message(source_of(case))},
                     "coincide": all(hoy[k] == case["expected"][k] for k in COMPARED)})
    return rows


def gemelo_rows() -> list[dict]:
    """Cada gemelo se compara contra el expected del caso `for` que representa."""
    expected = {c["name"]: c["expected"] for c in load_corpus(CORPUS)}
    linked = {"403_while": "403_for_enteros", "405_while": "405_for_copia",
              "404_while_incremento_arriba": "404_for_break_continue",
              "404_while_incremento_abajo": "404_for_break_continue"}
    rows = []
    for path in sorted(GEMELOS.glob("*.isy")):
        # El único que no termina usa un tope explícito: se corta por max_steps, no por reloj.
        limits = SPIN_LIMITS if path.stem.endswith("_abajo") else None
        row = observed(path.read_bytes(), [], limits)
        exp = expected.get(linked[path.stem], {})
        rows.append({"gemelo": path.stem, "version": path.read_text().splitlines()[0],
                     "limits": limits and "max_steps=20000" or "defaults",
                     "observed": row, "expected_de": linked.get(path.stem),
                     "coincide_con_expected": bool(exp)
                     and {k: row[k] for k in COMPARED} == {k: exp[k] for k in COMPARED},
                     "prediccion_steps": row["steps"]})
    return rows


def main(as_json: bool) -> int:
    corpus, gemelos = corpus_rows(), gemelo_rows()
    report = {"git_head": git_head(), "corpus": corpus, "gemelos": gemelos}
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    print(f"git_head={report['git_head']}  corpus={CORPUS.relative_to(ROOT)}")
    print("\n== casos 401-410: el expected NO se copió del resultado ==")
    for row in corpus:
        print(f"\n{row['case']}  —  {row['claim']}")
        print(f"  esperado     {json.dumps(row['expected'], ensure_ascii=False, sort_keys=True)}")
        print(f"  hoy (0.5)    {shape(row['hoy_0.5'])}")
        print(f"               frontend: {row['hoy_0.5']['frontend']}")
        print(f"  cuerpo a 0.4 {shape(row['a_0.4'])}")
        print(f"               frontend: {row['a_0.4']['frontend']}")
    print("\n== gemelos V2 (cabecera 0.4, corren hoy) ==")
    for row in gemelos:
        print(f"{row['gemelo']:34s} {shape(row['observed'])}")
        print(f"{'':34s} vs expected de {row['expected_de']}: "
              f"{'COINCIDE' if row['coincide_con_expected'] else 'DIFIERE'}"
              f"  pasos predichos={row['prediccion_steps']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--json" in sys.argv[1:]))
