"""Corre el corpus de conformidad contra un ejecutor y compara con los expected."""
from __future__ import annotations

import json
from pathlib import Path

from .interp import run
from .source import Bundle

COMPARED = ("status", "code", "emits", "return")


CORPORA = ("conformance", "conformance_v0.2", "conformance_v0.3", "conformance_v0.4",
           "conformance_v0.5")


def load_corpus(directory: Path) -> list[dict]:
    """Carga un corpus. Los archivos congelados no se editan nunca: si un cambio de
    spec aprobado vuelve obsoleto un expected, SUPERSEDED.json lo reemplaza de forma
    explícita y el caso queda marcado como `superseded`."""
    superseded_path = directory / "SUPERSEDED.json"
    superseded = (json.loads(superseded_path.read_text(encoding="utf-8"))
                  if superseded_path.exists() else {})
    cases = []
    for expect_path in sorted(directory.glob("*.expect.json")):
        name = expect_path.name[: -len(".expect.json")]
        spec = json.loads(expect_path.read_text(encoding="utf-8"))
        case = {"name": name, "program": (directory / f"{name}.isy").read_bytes(), **spec}
        if name in superseded:
            case["expected"] = superseded[name]["expected"]
            case["superseded"] = superseded[name]["superseded_by"]
        cases.append(case)
    # CORE v0.4: un caso con módulos es una carpeta con main.isy, sus módulos y expect.json.
    for case_dir in sorted(d for d in directory.iterdir() if (d / "expect.json").is_file()):
        spec = json.loads((case_dir / "expect.json").read_text(encoding="utf-8"))
        case = {"name": case_dir.name, "program": Bundle.from_path(case_dir / "main.isy"), **spec}
        if case_dir.name in superseded:
            case["expected"] = superseded[case_dir.name]["expected"]
            case["superseded"] = superseded[case_dir.name]["superseded_by"]
        cases.append(case)
    return cases


def load_all(root: Path) -> list[dict]:
    """Todos los corpus de programs/ (v0.1 a v0.5)."""
    return [case for name in CORPORA for case in load_corpus(root / "programs" / name)]


def run_corpus(cases: list[dict], executor=run) -> list[dict]:
    """executor(programa_bytes, input, limits) -> (resultado, traza)."""
    rows = []
    for case in cases:
        result, _ = executor(case["program"], case["input"], case.get("limits"))
        observed = {key: result[key] for key in COMPARED}
        rows.append({
            "name": case["name"],
            "claim": case["claim"],
            "program_sha256": result["program_sha256"],
            "expected": case["expected"],
            "observed": observed,
            "steps": result["steps"],
            "verdict": "PASS" if observed == case["expected"] else "FAIL",
            **({"superseded_by": case["superseded"]} if "superseded" in case else {}),
        })
    return rows
