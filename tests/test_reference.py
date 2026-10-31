"""Tests del intérprete de referencia (F2).

Capas del estándar §10 que cubre este archivo: conformidad (A–E, G vía corpus),
determinismo (F), sabotaje (la suite detecta semánticas mutadas), oráculo
independiente para el redondeo decimal y el engine hace el trabajo (§9).
La capa H (cross-runtime) llega con el primer backend (F4).
"""
from __future__ import annotations

import decimal
import hashlib
import json
import random
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import isyco.interp as interp  # noqa: E402
from isyco import canonical_json, run  # noqa: E402
from isyco.conformance import load_all, run_corpus  # noqa: E402
from isyco.errors import LimitReached, RuntimeFault  # noqa: E402
from isyco.types import IntT, int_fit, round_scaled  # noqa: E402

CORPUS = load_all(ROOT)


def failing(executor=run) -> list[str]:
    return [row["name"] for row in run_corpus(CORPUS, executor) if row["verdict"] != "PASS"]


class Conformance(unittest.TestCase):
    def test_corpus_frozen(self):
        for corpus in ("conformance", "conformance_v0.2", "conformance_v0.3", "conformance_v0.4",
                       "conformance_v0.5"):
            sums = (ROOT / "programs" / corpus / "SHA256SUMS.txt").read_text().split("\n")
            for line in filter(None, sums):
                digest, name = line.split()
                data = (ROOT / "programs" / corpus / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest, f"{corpus}/{name}")

    def test_corpus_passes(self):
        self.assertGreaterEqual(len(CORPUS), 170)
        self.assertEqual(failing(), [])

    def test_superseded_cases_are_explicit(self):
        """Solo los casos listados en SUPERSEDED.json cambian de expected, y lo dicen."""
        superseded = {c["name"] for c in CORPUS if "superseded" in c}
        self.assertEqual(superseded, {"003_header_wrong_version", "119_header_v03",
                                      "264_header_v04", "322_header_v05"})

    def test_determinism(self):
        for case in CORPUS:
            first = run(case["program"], case["input"], case.get("limits"), trace="full")
            second = run(case["program"], case["input"], case.get("limits"), trace="full")
            self.assertEqual(canonical_json(first), canonical_json(second), case["name"])


class Sabotage(unittest.TestCase):
    """Cada mutación de la semántica debe romper al menos un caso del corpus."""

    def mutated(self, attr, owner, replacement):
        original = getattr(owner, attr)
        setattr(owner, attr, replacement)
        try:
            return failing()
        finally:
            setattr(owner, attr, original)

    def test_half_even_becomes_half_up(self):
        orig = interp.round_scaled
        fails = self.mutated("round_scaled", interp, lambda q, mode, at: orig(
            q, "half_up" if mode == "half_even" else mode, at))
        self.assertTrue(fails)

    def test_trunc_division_becomes_floor(self):
        self.assertTrue(self.mutated("int_trunc_div", interp, lambda a, b: a // b))

    def test_wrap_becomes_sat(self):
        orig = interp.int_fit
        fails = self.mutated("int_fit", interp, lambda t, v, at: orig(
            IntT(t.bits, t.signed, "sat" if t.ovf == "wrap" else t.ovf), v, at))
        self.assertTrue(fails)

    def test_step_limit_off_by_one(self):
        def tick_ge(self, at):
            self.steps += 1
            if self.steps >= self.limits["max_steps"]:
                raise LimitReached("max_steps", at)
        self.assertTrue(self.mutated("tick", interp.Interpreter, tick_ge))

    # --- CORE v0.3 -----------------------------------------------------------
    def test_structs_shared_instead_of_copied(self):
        """Aliasing: si asignar un struct no copiara, el corpus v0.3 debe notarlo."""
        orig = interp._copy
        fails = self.mutated("_copy", interp,
                             lambda v: v if isinstance(v, dict) else orig(v))
        self.assertIn("230_struct_copy", fails)

    def test_str_overflow_truncates(self):
        """S3: truncar en silencio en vez de OVERFLOW."""
        orig = interp.Interpreter.binary

        def truncating(self, e):
            if e.op == "+" and isinstance(e.ty, interp.StrT):
                return (self.eval(e.left) + self.eval(e.right))[:e.ty.n]
            return orig(self, e)
        self.assertIn("203_str_concat_overflow", self.mutated("binary", interp.Interpreter, truncating))


class RoundingOracle(unittest.TestCase):
    """round_scaled contra el módulo decimal de Python (implementación independiente)."""

    MODES = {"half_even": decimal.ROUND_HALF_EVEN, "half_up": decimal.ROUND_HALF_UP,
             "down": decimal.ROUND_DOWN}

    def test_matches_decimal_module(self):
        rng = random.Random(20261028)
        ctx = decimal.Context(prec=100)
        for _ in range(20000):
            num = rng.randint(-10**6, 10**6)
            den = rng.choice([1, 2, 3, 4, 5, 7, 8, 10, 20, 40, 1000, rng.randint(1, 999)])
            q = Fraction(num, den)
            exact = ctx.divide(decimal.Decimal(num), decimal.Decimal(den))
            for mode, dmode in self.MODES.items():
                want = int(exact.quantize(decimal.Decimal(1), rounding=dmode, context=ctx))
                self.assertEqual(round_scaled(q, mode, None), want, (num, den, mode))

    def test_exact_mode(self):
        self.assertEqual(round_scaled(Fraction(10, 2), "exact", None), 5)
        with self.assertRaises(RuntimeFault):
            round_scaled(Fraction(1, 3), "exact", None)

    def test_wrap_matches_twos_complement(self):
        rng = random.Random(7)
        for bits in (8, 16, 32, 64):
            t = IntT(bits, True, "wrap")
            for _ in range(2000):
                v = rng.randint(-(1 << (bits + 4)), 1 << (bits + 4))
                raw = (v & ((1 << bits) - 1)).to_bytes(bits // 8, "little")
                self.assertEqual(int_fit(t, v, None), int.from_bytes(raw, "little", signed=True))


class EngineDoesTheWork(unittest.TestCase):
    """Estándar §9: el resultado aparece solo al ejecutar y depende de la entrada."""

    def test_result_comes_from_execution(self):
        case = next(c for c in CORPUS if c["name"] == "027_interes")
        source = case["program"].decode()
        for value in case["expected"]["emits"]:
            self.assertNotIn(value, source)
        interp.load(case["program"])  # cargar y chequear no produce salida
        other, _ = run(case["program"], ["2000.00", "0.0525"])
        self.assertEqual(other["emits"], ["8.22", "16.44", "24.66"])


class Cli(unittest.TestCase):
    def test_cli_exit_code_and_json(self):
        program = ROOT / "programs" / "conformance" / "015_div_zero.isy"
        proc = subprocess.run([sys.executable, "-m", "isyco", "run", str(program)],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 3)
        result = json.loads(proc.stdout)
        self.assertEqual((result["status"], result["code"], result["emits"]),
                         ("ERROR", "DIV_ZERO", ["5"]))


if __name__ == "__main__":
    unittest.main()
