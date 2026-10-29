"""Tests de ISY_BACKEND/1 (F5): capacidades, UNSUPPORTED y conformidad por backend.

Cada backend instalado se prueba contra los dos corpus y una muestra del
diferencial por tipo. El gate completo con evidencia es tools/backend_gate.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import available, registry  # noqa: E402
from isyco.backends.base import ALL_FEATURES, features_of  # noqa: E402
from isyco.backends.c import CBackend  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.difftest import DEC_TYPES, INT_TYPES, compare  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

CORPUS = load_all(ROOT)
KEYS = COMPARED + ("steps",)
AVAILABLE = available()


def by_name(name):
    return next(c for c in CORPUS if c["name"] == name)


class Features(unittest.TestCase):
    def test_features_of_examples(self):
        f = features_of(compile_ir(by_name("027_interes")["program"]))
        self.assertTrue({"dec", "dec:half_even", "int32", "ovf:trap", "calls", "while", "emit"} <= f)
        self.assertNotIn("recursion", f)
        self.assertIn("recursion", features_of(compile_ir(by_name("036_recursion_fact")["program"])))
        self.assertIn("arrays", features_of(compile_ir(by_name("033_array_copy")["program"])))
        self.assertIn("unsigned", features_of(compile_ir(by_name("012_u8_wrap_neg")["program"])))

    def test_every_valid_program_needs_only_known_features(self):
        for case in CORPUS:
            try:
                module = compile_ir(case["program"])
            except InvalidProgram:
                continue
            self.assertLessEqual(features_of(module), ALL_FEATURES, case["name"])


class NoDecimalC(CBackend):
    """Backend de prueba que declara no saber decimales."""
    name = "c_nodec"
    features = ALL_FEATURES - {"dec", "dec:half_even", "dec:half_up", "dec:down", "dec:exact"}


@unittest.skipUnless("c" in AVAILABLE, "no hay compilador de C")
class Unsupported(unittest.TestCase):
    def test_missing_feature_is_unsupported_never_approximated(self):
        backend = NoDecimalC()
        seen_unsupported = seen_pass = 0
        for case in CORPUS:
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            try:
                needs_dec = "dec" in features_of(compile_ir(case["program"]))
            except InvalidProgram:
                needs_dec = False
            if needs_dec and ref["status"] == "INVALID_PROGRAM":
                # El frontend decide INVALID_PROGRAM/BAD_INPUT antes que el backend
                # (spec/BACKEND.md §1): la capacidad declarada no interviene.
                self.assertEqual({k: ref[k] for k in KEYS},
                                 {k: got.get(k) for k in KEYS}, case["name"])
            elif needs_dec:
                self.assertEqual(got["status"], "UNSUPPORTED", case["name"])
                self.assertIn("dec", got["code"])
                self.assertEqual(got["emits"], [])
                seen_unsupported += 1
            else:
                self.assertEqual({k: ref[k] for k in KEYS}, {k: got.get(k) for k in KEYS}, case["name"])
                seen_pass += 1
        self.assertGreater(seen_unsupported, 5)
        self.assertGreater(seen_pass, 20)


class Registry(unittest.TestCase):
    def test_wave_one_registered(self):
        self.assertEqual(set(registry()), {"c", "rust", "zig"})


@unittest.skipUnless(AVAILABLE, "no hay toolchain nativo instalado")
class Cli(unittest.TestCase):
    def test_native_via_matches_reference(self):
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        ref, _ = run(program.read_bytes(), ["1000.00", "0.0525"])
        want = {k: ref[k] for k in KEYS}
        seen = []
        for via in ("c", "rust", "zig"):
            if via not in AVAILABLE:
                continue
            proc = subprocess.run(
                [sys.executable, "-m", "isyco", "run", str(program),
                 "--input", '["1000.00","0.0525"]', "--via", via],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual({k: json.loads(proc.stdout)[k] for k in KEYS}, want, via)
            seen.append(via)
        self.assertTrue(seen)


def _make_conformance(name):
    @unittest.skipUnless(name in AVAILABLE, f"toolchain de {name} no instalado")
    class Conformance(unittest.TestCase):
        backend = AVAILABLE.get(name)

        def test_corpus(self):
            bad = []
            for case in CORPUS:
                ref, _ = run(case["program"], case["input"], case.get("limits"))
                got, _ = self.backend.run(case["program"], case["input"], case.get("limits"))
                if {k: ref[k] for k in KEYS} != {k: got.get(k) for k in KEYS} or got.get("backend_stderr"):
                    bad.append((case["name"], got.get("status"), got.get("backend_stderr")))
            self.assertEqual(bad, [])

        def test_difftest_sample(self):
            # Muestra: forzados + 1 aleatorio, en un subconjunto de tipos para que corra rápido.
            types = INT_TYPES[::5] + DEC_TYPES[::2]
            report = compare(self.backend.run, pairs=1, types=types)
            self.assertEqual(report["diffs"], [])

        def test_engine_does_the_work(self):
            case = by_name("027_interes")
            source = self.backend.emit(compile_ir(case["program"]))
            for value in case["expected"]["emits"]:
                self.assertNotIn(value, source)
            other, _ = self.backend.run(case["program"], ["2000.00", "0.0525"])
            self.assertEqual(other["emits"], ["8.22", "16.44", "24.66"])

    Conformance.__name__ = Conformance.__qualname__ = f"Conformance_{name}"
    return Conformance


for _name in ("c", "rust", "zig"):
    globals()[f"Conformance_{_name}"] = _make_conformance(_name)


if __name__ == "__main__":
    unittest.main()
