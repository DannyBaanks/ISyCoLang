"""Regresiones propias del backend Go; el corpus y diferenciales usan el gate común."""
import shutil
import unittest

from isyco import run
from isyco.backends import registry
from isyco.conformance import COMPARED, load_all
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = COMPARED + ("steps",)

@unittest.skipUnless(shutil.which("go"), "no hay Go")
class GoBackendTests(unittest.TestCase):
    def test_registered_backend_executes_corpus_against_expected_and_reference(self):
        self.assertIn("go", registry(), "falta el backend Go")
        backend = registry()["go"]
        for case in load_all(ROOT):
            with self.subTest(case=case["name"]):
                ref, _ = run(case["program"], case["input"], case.get("limits"))
                got, _ = backend.run(case["program"], case["input"], case.get("limits"))
                self.assertEqual({k: got.get(k) for k in KEYS}, {k: ref[k] for k in KEYS})
                for k in COMPARED:
                    self.assertEqual(got.get(k), case["expected"][k])

    def test_numeric_leaves_and_nested_aggregates_copy_by_value(self):
        # Mutating big.Int receivers or using slice aliases corrupts a and p.
        source = b'''isyco 0.3
struct P { z: [i64; 2], a: str<8> }
fn change(p: P) -> P {
    p.z[0] = p.z[0] + 5;
    p.a = "new";
    return p;
}
fn main() !emit {
    let a: [i64; 2] = [7, 8];
    let b: [i64; 2] = a;
    b[0] = b[0] + 10;
    emit a; emit b;
    let p: P = P { z: a, a: "<&>\\\\\\\"\\n\\t" };
    let q: P = change(p);
    emit p; emit q; emit p == q;
}
'''
        ref, _ = run(source, [])
        self.assertEqual(ref["status"], "HALTED", ref)
        self.assertEqual(ref["emits"][:2], ['["7","8"]', '["17","8"]'])
        got, _ = registry()["go"].run(source, [])
        self.assertEqual({k: got[k] for k in KEYS}, {k: ref[k] for k in KEYS})

    def test_left_operand_error_precedes_later_call(self):
        source = b'''isyco 0.3
fn later() -> i32 !emit { emit 99 as i32; return 0; }
fn main() !emit {
    let a: [i32; 1] = [1];
    emit a[5 as i32] + later();
}
'''
        ref, _ = run(source, [])
        self.assertEqual(ref["status"], "ERROR", ref)
        self.assertEqual(ref["code"], "INDEX_OUT_OF_BOUNDS")
        self.assertEqual(ref["emits"], [])
        got, _ = registry()["go"].run(source, [])
        self.assertEqual({k: got[k] for k in KEYS}, {k: ref[k] for k in KEYS})

    def test_large_unsigned_index_is_checked_before_machine_conversion(self):
        source = b'''isyco 0.3
fn main(i: u64) !emit { let a: [i32; 1] = [42]; emit a[i]; }
'''
        ref, _ = run(source, ["18446744073709551615"])
        self.assertEqual(ref["status"], "ERROR", ref)
        self.assertEqual(ref["code"], "INDEX_OUT_OF_BOUNDS")
        got, _ = registry()["go"].run(source, ["18446744073709551615"])
        self.assertEqual({k: got[k] for k in KEYS}, {k: ref[k] for k in KEYS})

if __name__ == "__main__":
    unittest.main()
