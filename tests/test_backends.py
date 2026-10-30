"""Tests de ISY_BACKEND/1 (F5): capacidades, UNSUPPORTED y conformidad por backend.

Cada backend instalado se prueba contra los dos corpus y una muestra del
diferencial por tipo. El gate completo con evidencia es tools/backend_gate.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import run  # noqa: E402
from isyco.backends import available, registry  # noqa: E402
from isyco.backends.base import ALL_FEATURES, GNU_TIME, features_of, missing_features  # noqa: E402
from isyco.backends.c import CBackend  # noqa: E402
from isyco.conformance import COMPARED, load_all  # noqa: E402
from isyco.difftest import DEC_TYPES, INT_TYPES, compare, compare_str  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402

CORPUS = load_all(ROOT)
KEYS = COMPARED + ("steps",)
AVAILABLE = available()
# ISYCO_TEST_BACKENDS=c,rust limita qué backends nativos prueba esta suite (p. ej. para
# no esperar a Zig en frío). Sin la variable se prueban todos los instalados.
if os.environ.get("ISYCO_TEST_BACKENDS"):
    AVAILABLE = {k: v for k, v in AVAILABLE.items()
                 if k in os.environ["ISYCO_TEST_BACKENDS"].split(",")}
# Casos del corpus que hacen fallar cada sabotaje (medido con el barrido completo del
# gate, evidence/backends/). Cambiar el corpus puede exigir actualizar esta tabla.
SABOTAGE_WITNESSES = {
    "half_even_as_half_up": ("019_dec_half_even", "031_cast_dec_rescale"),
    "div_floor": ("014_div_trunc",),
    "str_concat_truncates": ("203_str_concat_overflow",),
}


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
        v03 = features_of(compile_ir(by_name("234_struct_nested")["program"]))
        self.assertTrue({"ir0.2", "str", "struct", "arrays", "int8", "unsigned"} <= v03)
        self.assertNotIn("ir0.2", features_of(compile_ir(by_name("027_interes")["program"])))

    def test_every_valid_program_needs_only_known_features(self):
        for case in CORPUS:
            try:
                module = compile_ir(case["program"])
            except InvalidProgram:
                continue
            self.assertLessEqual(features_of(module), ALL_FEATURES, case["name"])


class NoDecimalC(CBackend):
    """Backend de prueba que declara no saber decimales (además de lo que C no sabe)."""
    name = "c_nodec"
    features = CBackend.features - {"dec", "dec:half_even", "dec:half_up", "dec:down", "dec:exact"}


@unittest.skipUnless("c" in AVAILABLE, "no hay compilador de C")
class Unsupported(unittest.TestCase):
    def test_missing_feature_is_unsupported_never_approximated(self):
        backend = NoDecimalC()
        seen_unsupported = seen_pass = 0
        for case in CORPUS:
            ref, _ = run(case["program"], case["input"], case.get("limits"))
            got, _ = backend.run(case["program"], case["input"], case.get("limits"))
            missing = missing_features(backend, case["program"])
            if missing and ref["status"] == "INVALID_PROGRAM":
                # El frontend decide INVALID_PROGRAM/BAD_INPUT antes que el backend
                # (spec/BACKEND.md §1): la capacidad declarada no interviene.
                self.assertEqual({k: ref[k] for k in KEYS},
                                 {k: got.get(k) for k in KEYS}, case["name"])
            elif missing:
                self.assertEqual(got["status"], "UNSUPPORTED", case["name"])
                self.assertEqual(got["code"], ",".join(missing), case["name"])
                self.assertEqual(got["emits"], [])
                if "dec" in missing:
                    seen_unsupported += 1
            else:
                self.assertEqual({k: ref[k] for k in KEYS}, {k: got.get(k) for k in KEYS}, case["name"])
                seen_pass += 1
        self.assertGreater(seen_unsupported, 5)
        self.assertGreater(seen_pass, 20)


class Registry(unittest.TestCase):
    def test_every_sabotage_has_witnesses(self):
        for backend in registry().values():
            for sabotage in backend.sabotages:
                self.assertIn(sabotage, SABOTAGE_WITNESSES, f"{backend.name}: {sabotage}")

    def test_wave_one_registered(self):
        # Ola 1: C, Rust, Zig (F5). Ola 2: pydecimal (ROADMAP F5, "decimal de
        # punto fijo verificable"). El nombre del test es de la ola 1; el
        # registro hereda backends a medida que se cierra cada ola.
        self.assertEqual(set(registry()), {"c", "rust", "zig", "pydecimal"})


@unittest.skipUnless(AVAILABLE, "no hay toolchain nativo instalado")
class Cli(unittest.TestCase):
    def test_native_via_matches_reference(self):
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        ref, _ = run(program.read_bytes(), ["1000.00", "0.0525"])
        want = {k: ref[k] for k in KEYS}
        seen = []
        for via in AVAILABLE:
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
                missing = missing_features(self.backend, case["program"])
                if missing and ref["status"] != "INVALID_PROGRAM":
                    # Fuera de capacidades: UNSUPPORTED exacto, nunca una aproximación.
                    if got["status"] != "UNSUPPORTED" or got["code"] != ",".join(missing):
                        bad.append((case["name"], got.get("status"), got.get("code")))
                elif {k: ref[k] for k in KEYS} != {k: got.get(k) for k in KEYS} or got.get("backend_stderr"):
                    bad.append((case["name"], got.get("status"), got.get("backend_stderr")))
            self.assertEqual(bad, [])

        def test_difftest_sample(self):
            # Muestra: forzados + 1 aleatorio, en un subconjunto de tipos para que corra rápido.
            types = INT_TYPES[::5] + DEC_TYPES[::2]
            report = compare(self.backend.run, pairs=1, types=types)
            self.assertEqual(report["diffs"], [])
            if "str" in self.backend.features:
                self.assertEqual(compare_str(self.backend.run, per_op=2)["diffs"], [])

        def test_engine_does_the_work(self):
            case = by_name("027_interes")
            source = self.backend.emit(compile_ir(case["program"]))
            for value in case["expected"]["emits"]:
                self.assertNotIn(value, source)
            other, _ = self.backend.run(case["program"], ["2000.00", "0.0525"])
            self.assertEqual(other["emits"], ["8.22", "16.44", "24.66"])

        def test_sabotages_detected(self):
            # Cada sabotaje declarado debe hacer fallar sus casos testigo del corpus: si no,
            # la suite no distinguiría este backend de uno roto (spec/BACKEND.md §5). Solo
            # los testigos, para no recompilar el corpus entero saboteado en cada corrida;
            # el barrido completo (corpus + diferenciales) lo hace tools/backend_gate.py.
            self.assertLessEqual({"half_even_as_half_up", "div_floor"}, set(self.backend.sabotages))
            for sabotage in self.backend.sabotages:
                witnesses = [by_name(name) for name in SABOTAGE_WITNESSES[sabotage]]
                caught = [c["name"] for c in witnesses
                          if {k: run(c["program"], c["input"], c.get("limits"))[0][k] for k in KEYS}
                          != {k: self.backend.run(c["program"], c["input"], c.get("limits"),
                                                  sabotage=sabotage)[0].get(k) for k in KEYS}]
                self.assertTrue(caught, sabotage)

        def test_cost_is_measured_and_not_compared(self):
            case = by_name("027_interes")
            got, _ = self.backend.run(case["program"], case["input"])
            cost = got["cost"]
            self.assertEqual(set(cost), {"wall_ms", "user_ms", "sys_ms", "max_rss_kb", "compile_ms"})
            self.assertGreater(cost["wall_ms"], 0)
            if GNU_TIME:
                # Pico del binario, no del intérprete de Python que lo lanza
                # (~12 MB). pydecimal SÍ es un intérprete: su techo es propio.
                self.assertLess(cost["max_rss_kb"], self.backend.rss_ceiling_kb)
            else:
                self.assertIsNone(cost["max_rss_kb"])
            self.assertNotIn("cost", KEYS)

    Conformance.__name__ = Conformance.__qualname__ = f"Conformance_{name}"
    return Conformance


for _name in ("c", "rust", "zig", "pydecimal"):
    globals()[f"Conformance_{_name}"] = _make_conformance(_name)


if __name__ == "__main__":
    unittest.main()
