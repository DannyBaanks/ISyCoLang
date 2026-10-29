"""Corre el corpus de conformidad contra un ejecutor y compara con los expected."""
from __future__ import annotations

import json
from pathlib import Path

from .interp import run

COMPARED = ("status", "code", "emits", "return")


def load_corpus(directory: Path) -> list[dict]:
    cases = []
    for expect_path in sorted(directory.glob("*.expect.json")):
        name = expect_path.name[: -len(".expect.json")]
        spec = json.loads(expect_path.read_text(encoding="utf-8"))
        cases.append({"name": name, "program": (directory / f"{name}.isy").read_bytes(), **spec})
    return cases


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
        })
    return rows
