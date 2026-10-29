"""Tests de ISY-IR v0.1 (F3).

Gate: el intérprete de la IR produce el mismo resultado y la misma traza que el
intérprete de referencia, byte a byte, en todo el corpus y en programas que
ejercitan lo que la IR cambia (tabla de locales, else-if, ida y vuelta JSON).
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import canonical_json, run  # noqa: E402
from isyco.conformance import load_all  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.ir import ir_hash, semantic_hash  # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir  # noqa: E402
from isyco.ir_validate import IRInvalid, validate  # noqa: E402

CORPUS = load_all(ROOT)

# Programas que tocan justo lo que la IR transforma.
EXTRA = {
    "sibling_scopes": ("""isyco 0.1
fn main(flag: bool) !emit {
    if flag { let x: i32 = 7; emit x; } else { let x: dec<4,2> = 1.25; emit x; }
    let i: i32 = 0;
    while i < 2 { let y: bool = i == 0; emit y; i = i + 1; }
    if not flag { let y: u8 = 255; emit y; }
}
""", [["true"], ["false"]]),
    "else_if_chain": ("""isyco 0.1
fn clase(n: i32) -> i32 {
    if n < 0 { return -1; } else if n == 0 { return 0; } else if n < 10 { return 1; } else { return 2; }
}
fn main(n: i32) -> i32 { return clase(n); }
""", [["-5"], ["0"], ["7"], ["99"]]),
    "nested_loops": ("""isyco 0.1
fn main() !emit {
    let i: i32 = 0;
    while i < 4 {
        i = i + 1;
        if i == 2 { continue; }
        let j: i32 = 0;
        while true { j = j + 1; if j > i { break; } if j % 2 == 0 { continue; } emit i * 10 + j; }
    }
}
""", [[]]),
    "arrays_and_recursion": ("""isyco 0.1
fn suma(a: [dec<8,2>; 4], i: i32) -> dec<8,2> {
    if i == 4 { return 0.00; }
    return a[i] + suma(a, i + 1);
}
fn main(a: [dec<8,2>; 4]) -> dec<8,2> {
    let b: [dec<8,2>; 4] = a;
    b[0 as i32] = b[0 as i32] * 2.00;
    return suma(b, 0) - suma(a, 0);
}
""", [[["1.10", "2.20", "3.30", "4.40"]]]),
}


def both(data, inputs, limits=None, trace="full"):
    return (canonical_json(run(data, inputs, limits, trace=trace)),
            canonical_json(run_via_ir(data, inputs, limits, trace=trace)))


class Gate(unittest.TestCase):
    def test_corpus_equal_results_and_traces(self):
        for case in CORPUS:
            for level in ("stmt", "full"):
                ref, ir = both(case["program"], case["input"], case.get("limits"), level)
                self.assertEqual(ref, ir, f"{case['name']} trace={level}")

    def test_extra_programs(self):
        for name, (source, inputs_list) in EXTRA.items():
            data = source.encode()
            for inputs in inputs_list:
                ref, ir = both(data, inputs)
                self.assertEqual(ref, ir, f"{name} {inputs}")
                self.assertEqual(json.loads(ref)[0]["status"], "HALTED", name)

    def test_extra_programs_with_tight_limits(self):
        for name, (source, inputs_list) in EXTRA.items():
            for max_steps in (1, 5, 13, 29):
                ref, ir = both(source.encode(), inputs_list[0], {"max_steps": max_steps})
                self.assertEqual(ref, ir, f"{name} max_steps={max_steps}")


class Identity(unittest.TestCase):
    def test_lowering_is_deterministic(self):
        for case in CORPUS:
            try:
                first = compile_ir(case["program"])
            except InvalidProgram:
                continue
            self.assertEqual(ir_hash(first), ir_hash(compile_ir(case["program"])), case["name"])

    def test_semantic_hash_ignores_layout(self):
        source = EXTRA["else_if_chain"][0]
        moved = source.replace("fn main", "\n\n# comentario\nfn main")
        a, b = compile_ir(source.encode()), compile_ir(moved.encode())
        self.assertNotEqual(ir_hash(a), ir_hash(b))
        self.assertEqual(semantic_hash(a), semantic_hash(b))

    def test_semantic_hash_sees_semantics(self):
        source = EXTRA["else_if_chain"][0]
        a = compile_ir(source.encode())
        b = compile_ir(source.replace("n < 10", "n < 11").encode())
        self.assertNotEqual(semantic_hash(a), semantic_hash(b))


def _valid_module():
    return compile_ir(EXTRA["arrays_and_recursion"][0].encode())


def _find(node, pred):
    """Primer sub-nodo (dict) que cumple pred, recorriendo en orden."""
    if isinstance(node, dict):
        if pred(node):
            return node
        values = node.values()
    elif isinstance(node, list):
        values = node
    else:
        return None
    for value in values:
        hit = _find(value, pred)
        if hit is not None:
            return hit
    return None


class ValidatorRejects(unittest.TestCase):
    """Cada mutación de una IR válida debe ser rechazada con el código esperado."""

    def assertRejects(self, mutate, code):
        module = _valid_module()
        validate(module)
        broken = copy.deepcopy(module)
        mutate(broken)
        with self.assertRaises(IRInvalid) as ctx:
            validate(broken)
        self.assertIn(code, [d.code for d in ctx.exception.diagnostics])

    def test_wrong_schema(self):
        self.assertRejects(lambda m: m.update(schema="isy-ir/9"), "IR_SCHEMA")

    def test_unknown_expression_kind(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "bin").update(k="pow"), "IR_NODE")

    def test_extra_field(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "local").update(hint=1), "IR_NODE")

    def test_type_lie(self):
        def lie(m):
            node = _find(m, lambda n: n.get("k") == "bin")
            node["ty"] = {"t": "int", "bits": 32, "signed": True, "ovf": "trap"}
        self.assertRejects(lie, "IR_TYPE")

    def test_non_canonical_const(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "const"
                                           and n["v"] == "0.00").update(v="0.0"), "IR_TYPE")

    def test_local_out_of_range(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "local").update(id=99), "IR_LOCAL")

    def test_undeclared_effect(self):
        def add_emit(m):
            fn = m["functions"][0]
            fn["body"].insert(0, {"s": "emit", "at": "1:1",
                                  "value": {"k": "const", "at": "1:1", "ty": {"t": "bool"}, "v": "true"}})
        self.assertRejects(add_emit, "IR_EFFECT")

    def test_missing_return(self):
        def drop_return(m):
            fn = m["functions"][0]
            fn["body"] = [s for s in fn["body"] if s["s"] != "return"]
        self.assertRejects(drop_return, "IR_RETURN")

    def test_break_outside_loop(self):
        self.assertRejects(lambda m: m["functions"][1]["body"].insert(0, {"s": "break", "at": "1:1"}),
                           "IR_CONTROL")

    def test_unknown_function(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "call").update(fn="nada"), "IR_CALL")

    def test_bad_type_parameters(self):
        def bad(m):
            m["functions"][0]["locals"][0]["ty"]["n"] = 0
        self.assertRejects(bad, "IR_TYPE")


V2_PROGRAM = """isyco 0.3
struct P { n: str<8>, xs: [i32; 2] }
fn main(a: str<4>) -> str<16> !emit {
    let p: P = P { n: a, xs: [1, 2] };
    p.xs[1] = 5;
    emit p;
    return p.n + "!";
}
"""


class ValidatorRejectsV2(unittest.TestCase):
    """isy-ir/0.2 (CORE v0.3): mismas reglas de mundo cerrado para str y structs."""

    def module(self):
        module = compile_ir(V2_PROGRAM.encode())
        self.assertEqual(module["schema"], "isy-ir/0.2")
        validate(module)
        return module

    def assertRejects(self, mutate, code):
        broken = self.module()
        mutate(broken)
        with self.assertRaises(IRInvalid) as ctx:
            validate(broken)
        self.assertIn(code, [d.code for d in ctx.exception.diagnostics])

    def test_explicit_widen_node(self):
        widen = _find(self.module(), lambda n: n.get("k") == "widen")
        self.assertEqual((widen["e"]["ty"], widen["ty"]), ({"t": "str", "n": 4}, {"t": "str", "n": 8}))

    def test_v2_types_rejected_under_v01_schema(self):
        self.assertRejects(lambda m: m.update(schema="isy-ir/0.1"), "IR_TYPE")

    def test_widen_that_narrows(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "widen")["ty"].update(n=2), "IR_TYPE")

    def test_struct_literal_missing_field(self):
        def drop(m):
            node = _find(m, lambda n: n.get("k") == "struct")
            node["fields"] = node["fields"][:1]
        self.assertRejects(drop, "IR_TYPE")

    def test_unknown_field(self):
        self.assertRejects(lambda m: _find(m, lambda n: n.get("k") == "field").update(name="z"), "IR_TYPE")

    def test_set_path_index_on_struct(self):
        def bad(m):
            node = _find(m, lambda n: n.get("s") == "set_path")
            node["path"] = [node["path"][1]] + node["path"]   # [i] sobre P antes de .xs
        self.assertRejects(bad, "IR_TYPE")

    def test_concat_of_number(self):
        def bad(m):
            node = _find(m, lambda n: n.get("k") == "concat")
            node["b"] = {"k": "const", "at": "1:1", "ty": {"t": "int", "bits": 32, "signed": True,
                                                           "ovf": "trap"}, "v": "1"}
        self.assertRejects(bad, "IR_TYPE")


class Cli(unittest.TestCase):
    def test_ir_command_prints_canonical_ir(self):
        import subprocess
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        proc = subprocess.run([sys.executable, "-m", "isyco", "ir", str(program)],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        module = json.loads(proc.stdout)
        validate(module)
        self.assertEqual(module["source_sha256"], hashlib.sha256(program.read_bytes()).hexdigest())

    def test_run_via_ir_flag(self):
        import subprocess
        program = ROOT / "programs" / "conformance" / "027_interes.isy"
        args = ["run", str(program), "--input", '["1000.00","0.0525"]']
        out = [subprocess.run([sys.executable, "-m", "isyco", *args, *via], cwd=ROOT,
                              capture_output=True, text=True).stdout for via in ([], ["--via", "ir"])]
        self.assertEqual(out[0], out[1])
        self.assertEqual(json.loads(out[1])["emits"], ["4.11", "8.22", "12.33"])


if __name__ == "__main__":
    unittest.main()
