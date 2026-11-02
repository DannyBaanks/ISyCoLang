"""Tests del backend C (F4). Se saltan si no hay gcc/clang.

Diferencial de tres vías: expected (a mano) ↔ referencia ↔ binario nativo.
Si falla expected ↔ referencia, el error es de semántica; si falla
referencia ↔ binario, es del backend. El gate completo con evidencia es
tools/c_gate.py; aquí va una muestra rápida.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends.c import emit_c, run_c  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.difftest import DEC_TYPES, compare, compare_str  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402
from isyco.backends.base import missing_features  # noqa: E402
from isyco.backends.c import BACKEND as C_BACKEND  # noqa: E402

CORPUS = load_all(ROOT)
KEYS = COMPARED + ("steps",)
HAS_CC = any(shutil.which(cc) for cc in ("gcc", "clang", "cc"))


def backend_failures(**kw) -> list[str]:
    """Casos donde C difiere de la referencia. Los que piden capacidades que C no
    declara (str/struct de v0.3) deben dar UNSUPPORTED y no cuentan como cubiertos."""
    bad = []
    for case in CORPUS:
        ref, _ = run(case["program"], case["input"], case.get("limits"))
        got, _ = run_c(case["program"], case["input"], case.get("limits"), **kw)
        missing = missing_features(C_BACKEND, case["program"])
        if missing and ref["status"] != "INVALID_PROGRAM":
            if got["status"] != "UNSUPPORTED" or got["code"] != ",".join(missing):
                bad.append(case["name"])
            continue
        if {k: ref[k] for k in KEYS} != {k: got.get(k) for k in KEYS} or got.get("backend_stderr"):
            bad.append(case["name"])
    return bad


@unittest.skipUnless(HAS_CC, "no hay compilador de C")
class ThreeWay(unittest.TestCase):
    def test_expected_vs_reference(self):
        for case in CORPUS:
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            self.assertEqual({k: ref[k] for k in COMPARED}, case["expected"], case["name"])

    def test_reference_vs_native(self):
        self.assertEqual(backend_failures(), [])

    def test_native_actually_ran(self):
        """Los programas válidos pasan por el binario: deben reportar pasos > 0."""
        case = next(c for c in CORPUS if c["name"] == "027_interes")
        got, _ = run_c(case["program"], case["input"])
        self.assertEqual(got["emits"], ["4.11", "8.22", "12.33"])
        self.assertGreater(got["steps"], 0)
        self.assertNotIn("4.11", emit_c(compile_ir(case["program"])))


@unittest.skipUnless(HAS_CC, "no hay compilador de C")
class Sabotage(unittest.TestCase):
    def test_half_even_tie_sabotage_detected(self):
        self.assertTrue(backend_failures(sabotage="half_even_as_half_up"))

    def test_floor_division_sabotage_detected(self):
        self.assertTrue(backend_failures(sabotage="div_floor"))

    def test_str_truncation_sabotage_detected(self):
        """CORE v0.3 S3: un C que corta en vez de OVERFLOW falla el corpus y el diferencial."""
        self.assertIn("203_str_concat_overflow", backend_failures(sabotage="str_concat_truncates"))
        report = compare_str(partial(run_c, sabotage="str_concat_truncates"), per_op=4)
        self.assertTrue(report["diffs"])

    def test_difftest_detects_sabotage(self):
        # El sabotaje es de redondeo half_even: solo los tipos decimales pueden mostrarlo.
        report = compare(partial(run_c, sabotage="half_even_as_half_up"), pairs=0, types=DEC_TYPES)
        self.assertTrue(report["diffs"])
        # Un sabotaje «detectado» sobre un tipo abortado no vale: la pierna debe estar limpia.
        self.assertEqual(report.get("harness", []), [])
        self.assertEqual(report.get("types_aborted", []), [])


@unittest.skipUnless(HAS_CC, "no hay compilador de C")
class Differential(unittest.TestCase):
    def test_boundary_values_all_numeric_types(self):
        report = compare(run_c, pairs=2)
        self.assertGreater(report["runs"], 2000)
        self.assertEqual(report["diffs"], [])
        # Igual que en F5: `diffs == []` con un tipo abortado por el toolchain era verde.
        self.assertEqual(report.get("harness", []), [])
        self.assertEqual(report.get("types_aborted", []), [])


@unittest.skipUnless(HAS_CC, "no hay compilador de C")
class Cli(unittest.TestCase):
    def test_run_via_c(self):
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        out = [json.loads(subprocess.run(
            [sys.executable, "-m", "isyco", "run", str(program), "--input", '["1000.00","0.0525"]', *via],
            cwd=ROOT, capture_output=True, text=True).stdout) for via in ([], ["--via", "c"])]
        self.assertEqual({k: out[0][k] for k in KEYS}, {k: out[1][k] for k in KEYS})


if __name__ == "__main__":
    unittest.main()
