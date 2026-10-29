"""Backend Rust: ISY-IR v0.1 -> Rust (edición 2021) -> binario con rustc.

Implementación independiente del backend C (mismo protocolo ISY_BACKEND/1):
- la aritmética entera se calcula exacta en i128 y `fit` aplica trap/wrap/sat;
  u64*u64 usa `checked_mul`/`wrapping_mul`;
- se compila con `-C overflow-checks=on -C panic=abort`: si algún cálculo
  intermedio desbordara i128 (no debería), el binario aborta y el driver lo
  reporta como BACKEND_CRASH en vez de dar un número equivocado;
- los arreglos son `[T; N]`, que Rust copia por valor;
- el estado de pasos/límites/salida viaja como `c: &mut Ctx` en cada función.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..ir import ty_from_json
from ..types import ArrT, BoolT, DecT, IntT, parse_canonical
from .base import ALL_FEATURES, Backend

ROUND_CODE = {"half_even": 0, "half_up": 1, "down": 2, "exact": 3}
OVF_CODE = {"trap": 0, "wrap": 1, "sat": 2}
CMP = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
ARITH = {"add": "+", "sub": "-", "mul": "*"}

RUNTIME = r"""#![allow(unused_mut, unused_variables, unused_assignments, unreachable_code, unused_parens,
         non_snake_case, dead_code, unused_braces, non_camel_case_types)]
use std::io::Write;

struct Ctx { steps: u64, max_steps: u64, depth: u64, max_depth: u64, emits: u64, max_emits: u64, out: Vec<u8> }

fn isy_end(c: &mut Ctx, status: &str, code: &str) -> ! {
    let line = format!("X {} {} {}\n", status, code, c.steps);
    c.out.extend_from_slice(line.as_bytes());
    let mut so = std::io::stdout().lock();
    let _ = so.write_all(&c.out);
    let _ = so.flush();
    std::process::exit(0)
}
fn isy_fail(c: &mut Ctx, code: &str) -> ! { isy_end(c, "ERROR", code) }
fn isy_limit(c: &mut Ctx, code: &str) -> ! { isy_end(c, "LIMIT_REACHED", code) }
fn isy_tick(c: &mut Ctx) { c.steps += 1; if c.steps > c.max_steps { isy_limit(c, "max_steps") } }
fn isy_enter(c: &mut Ctx) {
    isy_tick(c);
    if c.depth + 1 > c.max_depth { isy_limit(c, "max_call_depth") }
    c.depth += 1;
}
fn isy_emit_check(c: &mut Ctx) {
    if c.emits >= c.max_emits { isy_limit(c, "max_emits") }
    c.emits += 1;
}
fn isy_fit(c: &mut Ctx, v: i128, lo: i128, hi: i128, bits: u32, ovf: u8) -> i128 {
    if v >= lo && v <= hi { return v; }
    if ovf == 0 { isy_fail(c, "OVERFLOW") }
    if ovf == 2 { return if v > hi { hi } else { lo }; }
    let w: i128 = 1i128 << bits;
    (v - lo).rem_euclid(w) + lo
}
fn isy_mul_u64(c: &mut Ctx, a: u64, b: u64, ovf: u8) -> u64 {
    match a.checked_mul(b) {
        Some(r) => r,
        None => if ovf == 0 { isy_fail(c, "OVERFLOW") } else if ovf == 1 { a.wrapping_mul(b) } else { u64::MAX },
    }
}
fn isy_rdiv(c: &mut Ctx, num: i128, den: i128, mode: u8) -> i128 {
    let q = num / den;
    let r = num % den;
    if r == 0 { return q; }
    if mode == 3 { isy_fail(c, "INEXACT") }
    if mode == 2 { return q; }
    let sign: i128 = if (num < 0) != (den < 0) { -1 } else { 1 };
    let (ar, ad) = (r.abs(), den.abs());
    if 2 * ar > ad { return q + sign; }
    if 2 * ar < ad { return q; }
    if mode == 1 { return q + sign; }
    if q % 2 == 0 { q } else { q + sign }
}
fn isy_dec_fit(c: &mut Ctx, m: i128, max: i128) -> i128 {
    if m > max || m < -max { isy_fail(c, "OVERFLOW") }
    m
}
fn isy_put_i128(c: &mut Ctx, v: i128) { let s = v.to_string(); c.out.extend_from_slice(s.as_bytes()); }
fn isy_put_dec(c: &mut Ctx, m: i128, s: usize) {
    if s == 0 { isy_put_i128(c, m); return; }
    let mut digits = m.unsigned_abs().to_string();
    while digits.len() < s + 1 { digits.insert(0, '0'); }
    let (whole, frac) = digits.split_at(digits.len() - s);
    let text = format!("{}{}.{}", if m < 0 { "-" } else { "" }, whole, frac);
    c.out.extend_from_slice(text.as_bytes());
}
fn isy_put_bool(c: &mut Ctx, b: bool) { c.out.extend_from_slice(if b { b"true" } else { b"false" }); }
fn isy_arg(a: &[String], i: usize) -> i128 { a[i].parse::<i128>().unwrap() }
"""


class RustEmitter:
    def __init__(self, module: dict):
        self.module = module
        self.lines: list[str] = []
        self.indent = 1
        self.tmp = 0
        self.local_types: list = []
        self.rets = {fn["name"]: ty_from_json(fn["ret"]) for fn in module["functions"]}

    # --- tipos ----------------------------------------------------------------
    def rtype(self, t) -> str:
        if isinstance(t, BoolT):
            return "bool"
        if isinstance(t, IntT):
            return f"{'i' if t.signed else 'u'}{t.bits}"
        if isinstance(t, DecT):
            return "i64"
        return f"[{self.rtype(t.elem)}; {t.n}]"

    def zero(self, t) -> str:
        if isinstance(t, BoolT):
            return "false"
        if isinstance(t, ArrT):
            return f"[{self.zero(t.elem)}; {t.n}]"
        return f"(0 as {self.rtype(t)})"

    @staticmethod
    def fit_args(t: IntT) -> str:
        return f"{t.lo}i128, {t.hi}i128, {t.bits}, {OVF_CODE[t.ovf]}"

    # --- utilidades -----------------------------------------------------------
    def put(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def temp(self, t, value: str) -> str:
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"let {name}: {self.rtype(t)} = {value};")
        return name

    def rdiv(self, num: str, den: str, rnd: int) -> str:
        """isy_rdiv en su propia temporal: Rust no permite `c` prestado dos veces anidado."""
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"let {name}: i128 = isy_rdiv(c, {num}, {den}, {rnd});")
        return name

    # --- módulo ---------------------------------------------------------------
    def emit(self) -> str:
        bodies = [self.function(fn) for fn in self.module["functions"]]
        main = next(f for f in self.module["functions"] if f["name"] == "main")
        return "\n".join([f"// generado por isyco.backends.rust desde ISY-IR {self.module['source_sha256']}",
                          RUNTIME, *bodies, self.rust_main(main), ""])

    def signature(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        params = "".join(f", mut l{p}: {self.rtype(types[p])}" for p in fn["params"])
        ret = ty_from_json(fn["ret"])
        return f"fn f_{fn['name']}(c: &mut Ctx{params}){'' if ret is None else ' -> ' + self.rtype(ret)}"

    def function(self, fn: dict) -> str:
        self.lines, self.indent, self.tmp = [], 1, 0
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        for i, t in enumerate(self.local_types):
            if i not in fn["params"]:
                self.put(f"let mut l{i}: {self.rtype(t)} = {self.zero(t)};")
        self.put("isy_enter(c);")
        self.block(fn["body"])
        if fn["ret"] is None:
            self.put("c.depth -= 1;")
        else:
            self.put("std::process::abort() // inalcanzable: el validador exige retorno en todo camino")
        return f"{self.signature(fn)} {{\n" + "\n".join(self.lines) + "\n}\n"

    def rust_main(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        count = sum(types[p].n if isinstance(types[p], ArrT) else 1 for p in fn["params"])
        lines = ["fn main() {",
                 "    let a: Vec<String> = std::env::args().collect();",
                 f"    if a.len() != {4 + count} {{ std::process::exit(2); }}",
                 "    let mut ctx = Ctx { steps: 0, max_steps: a[1].parse().unwrap(), depth: 0,",
                 "        max_depth: a[2].parse().unwrap(), emits: 0, max_emits: a[3].parse().unwrap(),",
                 "        out: Vec::with_capacity(1 << 16) };",
                 "    let c = &mut ctx;"]
        argi = 4
        names = []
        for p in fn["params"]:
            t = types[p]
            names.append(f"a{p}")
            if isinstance(t, ArrT):
                lines.append(f"    let mut a{p}: {self.rtype(t)} = {self.zero(t)};")
                for k in range(t.n):
                    lines.append(f"    a{p}[{k}] = {self.arg(t.elem, argi)};")
                    argi += 1
            else:
                lines.append(f"    let a{p}: {self.rtype(t)} = {self.arg(t, argi)};")
                argi += 1
        call = f"f_main(c{''.join(', ' + n for n in names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    let r: {self.rtype(ret)} = {call};")
            lines.append('    c.out.extend_from_slice(b"R ");')
            lines.append(f"    {self.put_call(ret, 'r')};")
            lines.append("    c.out.push(b'\\n');")
        lines += ['    isy_end(c, "HALTED", "-");', "}"]
        return "\n".join(lines)

    def arg(self, t, i: int) -> str:
        if isinstance(t, BoolT):
            return f"(isy_arg(&a, {i}) != 0)"
        return f"(isy_arg(&a, {i}) as {self.rtype(t)})"

    def put_call(self, t, value: str) -> str:
        if isinstance(t, BoolT):
            return f"isy_put_bool(c, {value})"
        if isinstance(t, IntT):
            return f"isy_put_i128(c, {value} as i128)"
        return f"isy_put_dec(c, {value} as i128, {t.s})"

    # --- sentencias -----------------------------------------------------------
    def block(self, stmts: list) -> None:
        for s in stmts:
            self.stmt(s)

    def nested(self, header: str, stmts: list) -> None:
        self.put(header)
        self.indent += 1
        self.block(stmts)
        self.indent -= 1
        self.put("}")

    def index_check(self, index: str, n: int) -> None:
        self.put(f"if ({index} as i128) < 0 || ({index} as i128) >= {n} {{ isy_fail(c, \"INDEX_OUT_OF_BOUNDS\") }}")

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        self.put(f"isy_tick(c); // {kind} {s['at']}")
        if kind in ("let", "set"):
            value = self.expr(s["value"])
            self.put(f"l{s['local']} = {value};")
        elif kind == "set_index":
            index = self.expr(s["index"])
            value = self.expr(s["value"])
            self.index_check(index, self.local_types[s["local"]].n)
            self.put(f"l{s['local']}[{index} as usize] = {value};")
        elif kind == "if":
            cond = self.expr(s["cond"])
            self.nested(f"if {cond} {{", s["then"])
            if s["else"] is not None:
                self.nested("else {", s["else"])
        elif kind == "while":
            self.put("loop {")
            self.indent += 1
            self.put("isy_tick(c);")
            cond = self.expr(s["cond"])
            self.put(f"if !{cond} {{ break; }}")
            self.nested("{", s["body"])
            self.indent -= 1
            self.put("}")
        elif kind == "break":
            self.put("break;")
        elif kind == "continue":
            self.put("continue;")
        elif kind == "return":
            if s["value"] is None:
                self.put("c.depth -= 1;")
                self.put("return;")
            else:
                value = self.expr(s["value"])
                self.put("c.depth -= 1;")
                self.put(f"return {value};")
        elif kind == "emit":
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            self.put("isy_emit_check(c);")
            self.put('c.out.extend_from_slice(b"E ");')
            self.put(f"{self.put_call(t, value)};")
            self.put("c.out.push(b'\\n');")
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            self.put(f"f_{s['fn']}(c{''.join(', ' + a for a in args)});")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, BoolT):
                return "true" if value else "false"
            return f"({value}i128 as {self.rtype(t)})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"f_{e['fn']}(c{''.join(', ' + a for a in args)})")
        if kind == "index":
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            self.index_check(index, ty_from_json(e["base"]["ty"]).n)
            return self.temp(t, f"{base}[{index} as usize]")
        if kind == "cast":
            return self.cast(e, t)
        if kind == "not":
            return f"(!{self.expr(e['e'])})"
        if kind == "neg":
            x = self.expr(e["e"])
            if isinstance(t, IntT):
                return self.temp(t, f"(isy_fit(c, -({x} as i128), {self.fit_args(t)}) as {self.rtype(t)})")
            return self.temp(t, f"(isy_dec_fit(c, -({x} as i128), {t.max_m}i128) as i64)")
        if kind in ("and", "or"):
            first = self.expr(e["a"])
            self.tmp += 1
            name = f"t{self.tmp}"
            self.put(f"let mut {name}: bool = {first};")
            self.put(f"if {'' if kind == 'and' else '!'}{name} {{")
            self.indent += 1
            self.put(f"{name} = {self.expr(e['b'])};")
            self.indent -= 1
            self.put("}")
            return name
        if kind == "cmp":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            return f"({a} {CMP[e['op']]} {b})"
        if kind == "bin":
            return self.binary(e, t)
        if kind == "array":
            self.tmp += 1
            name = f"t{self.tmp}"
            self.put(f"let mut {name}: {self.rtype(t)} = {self.zero(t)};")
            for k, item in enumerate(e["elems"]):
                self.put(f"{name}[{k}] = {self.expr(item)};")
            return name
        if kind == "repeat":
            value = self.expr(e["elem"])
            return self.temp(t, f"[{value}; {t.n}]")
        raise AssertionError(kind)

    def binary(self, e: dict, t) -> str:
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            if op in ("div", "rem"):
                self.put(f"if {b} == ({0} as {self.rtype(t)}) {{ isy_fail(c, \"DIV_ZERO\") }}")
                exact = f"(({a} as i128) {'/' if op == 'div' else '%'} ({b} as i128))"
            elif op == "mul" and t.bits == 64 and not t.signed:
                return self.temp(t, f"isy_mul_u64(c, {a}, {b}, {OVF_CODE[t.ovf]})")
            else:
                exact = f"(({a} as i128) {ARITH[op]} ({b} as i128))"
            return self.temp(t, f"(isy_fit(c, {exact}, {self.fit_args(t)}) as {self.rtype(t)})")
        rnd = ROUND_CODE[t.rnd]
        scale = f"{10 ** t.s}i128"
        mx = f"{t.max_m}i128"
        if op in ("add", "sub"):
            return self.temp(t, f"(isy_dec_fit(c, ({a} as i128) {ARITH[op]} ({b} as i128), {mx}) as i64)")
        if op == "mul":
            q = self.rdiv(f"({a} as i128) * ({b} as i128)", scale, rnd)
            return self.temp(t, f"(isy_dec_fit(c, {q}, {mx}) as i64)")
        self.put(f"if {b} == 0 {{ isy_fail(c, \"DIV_ZERO\") }}")
        q = self.rdiv(f"({a} as i128) * {scale}", f"{b} as i128", rnd)
        return self.temp(t, f"(isy_dec_fit(c, {q}, {mx}) as i64)")

    def cast(self, e: dict, dst) -> str:
        x = self.expr(e["e"])
        src = ty_from_json(e["e"]["ty"])
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, f"(isy_fit(c, {x} as i128, {self.fit_args(dst)}) as {self.rtype(dst)})")
        if isinstance(src, IntT):
            return self.temp(dst, f"(isy_dec_fit(c, ({x} as i128) * {10 ** dst.s}i128, {dst.max_m}i128) as i64)")
        if isinstance(dst, IntT):
            return self.temp(dst, f"(isy_fit(c, ({x} as i128) / {10 ** src.s}i128, {self.fit_args(dst)}) as {self.rtype(dst)})")
        q = self.rdiv(f"({x} as i128) * {10 ** dst.s}i128", f"{10 ** src.s}i128", ROUND_CODE[dst.rnd])
        return self.temp(dst, f"(isy_dec_fit(c, {q}, {dst.max_m}i128) as i64)")


class RustBackend(Backend):
    name = "rust"
    extension = ".rs"
    features = ALL_FEATURES

    def toolchain(self) -> str | None:
        if not shutil.which("rustc"):
            return None
        return subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        if sabotage is not None:
            raise ValueError(f"rust no define sabotajes ({sabotage})")
        return RustEmitter(module).emit()

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return ["rustc", "--edition", "2021", "-O", "-C", "overflow-checks=on", "-C", "panic=abort",
                "--cap-lints", "allow", *extra_flags, "-o", str(binary), str(source)]


BACKEND = RustBackend()
