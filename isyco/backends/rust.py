"""Backend Rust: ISY-IR v0.1 -> Rust (edición 2021) -> binario con rustc.

Implementación independiente del backend C (mismo protocolo ISY_BACKEND/1):
- la aritmética entera se calcula exacta en i128 y `fit` aplica trap/wrap/sat;
  u64*u64 usa `checked_mul`/`wrapping_mul`;
- se compila con `-C overflow-checks=on -C panic=abort`: si algún cálculo
  intermedio desbordara i128 (no debería), el binario aborta y el driver lo
  reporta como BACKEND_CRASH en vez de dar un número equivocado;
- los arreglos son `[T; N]`, que Rust copia por valor;
- el estado de pasos/límites/salida viaja como `c: &mut Ctx` en cada función.

isy-ir/0.2 (CORE v0.3), sin compartir código con el backend C:
- str<N> es `IsyStr<N>` (`Copy`, por valor); su igualdad compara solo `len` bytes;
- cada struct es un `struct` de Rust con `#[derive(Clone, Copy, PartialEq)]`, así
  que `==` entre structs y arreglos lo da el compilador;
- texto -> número con `u128` y operaciones `wrapping_*` explícitas.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..ir import ty_from_json
from ..pila import con_pila
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical
from .base import ALL_FEATURES, Backend, fn_ident, type_ident

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
    ISY_HALF_EVEN_TIE
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

// ---- isy-ir/0.2 (CORE v0.3): str<N> por valor, salida escapada, texto <-> número ----
#[derive(Clone, Copy)]
struct IsyStr<const N: usize> { len: u32, v: [u8; N] }
impl<const N: usize> IsyStr<N> {
    fn s(&self) -> &[u8] { &self.v[..self.len as usize] }
}
// Igualdad por contenido: los bytes después de `len` no cuentan.
impl<const N: usize> PartialEq for IsyStr<N> { fn eq(&self, o: &Self) -> bool { self.s() == o.s() } }
fn isy_str<const N: usize>(c: &mut Ctx, b: &[u8]) -> IsyStr<N> {
    if b.len() > N { isy_fail(c, "OVERFLOW") }
    let mut r = IsyStr::<N> { len: b.len() as u32, v: [0u8; N] };
    r.v[..b.len()].copy_from_slice(b);
    r
}
fn isy_cat<const N: usize>(c: &mut Ctx, a: &[u8], b: &[u8]) -> IsyStr<N> {
    if a.len() + b.len() > N { isy_fail(c, "OVERFLOW") }
    let mut r = IsyStr::<N> { len: (a.len() + b.len()) as u32, v: [0u8; N] };
    r.v[..a.len()].copy_from_slice(a);
    r.v[a.len()..a.len() + b.len()].copy_from_slice(b);
    r
}
// Sabotaje de prueba: corta en silencio en vez de OVERFLOW (viola S3).
fn isy_cat_trunc<const N: usize>(a: &[u8], b: &[u8]) -> IsyStr<N> {
    let mut joined = a.to_vec();
    joined.extend_from_slice(b);
    joined.truncate(N);
    let mut r = IsyStr::<N> { len: joined.len() as u32, v: [0u8; N] };
    r.v[..joined.len()].copy_from_slice(&joined);
    r
}
// Carga de una línea E/R: barra invertida y salto de línea escapados (BACKEND §3).
fn isy_out(c: &mut Ctx, b: u8) {
    match b { b'\\' => c.out.extend_from_slice(b"\\\\"), b'\n' => c.out.extend_from_slice(b"\\n"), _ => c.out.push(b) }
}
fn isy_put_text(c: &mut Ctx, s: &[u8]) { for &b in s { isy_out(c, b) } }
fn isy_put_json_text(c: &mut Ctx, s: &[u8]) {
    isy_out(c, b'"');
    for &b in s {
        match b {
            b'"' => { isy_out(c, b'\\'); isy_out(c, b'"') }
            b'\\' => { isy_out(c, b'\\'); isy_out(c, b'\\') }
            b'\n' => { isy_out(c, b'\\'); isy_out(c, b'n') }
            b'\t' => { isy_out(c, b'\\'); isy_out(c, b't') }
            _ => isy_out(c, b),
        }
    }
    isy_out(c, b'"');
}
fn isy_allowed(x: i128) -> bool { x == 9 || x == 10 || (32..=126).contains(&x) }
fn isy_fmt_dec(m: i128, s: usize) -> Vec<u8> {
    if s == 0 { return m.to_string().into_bytes(); }
    let mut digits = m.unsigned_abs().to_string();
    while digits.len() < s + 1 { digits.insert(0, '0'); }
    let (whole, frac) = digits.split_at(digits.len() - s);
    format!("{}{}.{}", if m < 0 { "-" } else { "" }, whole, frac).into_bytes()
}
// Magnitud de una tira de dígitos. big = el valor real es >= 2^123 (no cabe en ningún
// tipo); mag sigue siendo el valor exacto módulo 2^128, que es lo que wrap necesita.
fn isy_digits(d: &[u8]) -> (u128, bool) {
    let mut mag: u128 = 0;
    let mut big = false;
    for &b in d {
        if mag >= 1u128 << 123 { big = true; }
        mag = mag.wrapping_mul(10).wrapping_add((b - b'0') as u128);
    }
    if mag >= 1u128 << 123 { big = true; }
    (mag, big)
}
fn isy_sign(s: &[u8]) -> (bool, &[u8]) {
    if s.first() == Some(&b'-') { (true, &s[1..]) } else { (false, s) }
}
fn isy_parse_int(c: &mut Ctx, s: &[u8], lo: i128, hi: i128, bits: u32, ovf: u8) -> i128 {
    let (neg, d) = isy_sign(s);
    if d.is_empty() || !d.iter().all(|b| b.is_ascii_digit()) || (d[0] == b'0' && d.len() > 1)
        || (neg && d == b"0") { isy_fail(c, "BAD_FORMAT") }
    let (mag, big) = isy_digits(d);
    if !big { let v = mag as i128; return isy_fit(c, if neg { -v } else { v }, lo, hi, bits, ovf); }
    if ovf == 0 { isy_fail(c, "OVERFLOW") }
    if ovf == 2 { return if neg { lo } else { hi }; }
    let u = if neg { 0u128.wrapping_sub(mag) } else { mag };
    let w: u128 = 1u128 << bits;
    let r = (u & (w - 1)) as i128;
    if r > hi { r - w as i128 } else { r }
}
fn isy_parse_dec(c: &mut Ctx, s: &[u8], scale: usize, max: i128) -> i64 {
    let (neg, d) = isy_sign(s);
    let int_len = d.iter().take_while(|b| b.is_ascii_digit()).count();
    if int_len == 0 || (d[0] == b'0' && int_len > 1) { isy_fail(c, "BAD_FORMAT") }
    let frac: &[u8] = if scale == 0 {
        if int_len != d.len() { isy_fail(c, "BAD_FORMAT") }
        b""
    } else {
        if d.len() != int_len + 1 + scale || d[int_len] != b'.'
            || !d[int_len + 1..].iter().all(|b| b.is_ascii_digit()) { isy_fail(c, "BAD_FORMAT") }
        &d[int_len + 1..]
    };
    if neg && d.iter().all(|&b| b == b'0' || b == b'.') { isy_fail(c, "BAD_FORMAT") }
    let (whole, big) = isy_digits(&d[..int_len]);
    if big || whole > max as u128 { isy_fail(c, "OVERFLOW") }
    let (f, _) = isy_digits(frac);
    let mag = whole * 10u128.pow(scale as u32) + f;
    if mag > max as u128 { isy_fail(c, "OVERFLOW") }
    if neg { -(mag as i64) } else { mag as i64 }
}
fn isy_parse_bool(c: &mut Ctx, s: &[u8]) -> bool {
    if s == b"true" { return true; }
    if s == b"false" { return false; }
    isy_fail(c, "BAD_FORMAT")
}
"""


HALF_EVEN_TIE = {
    None: "if q % 2 == 0 { q } else { q + sign }",
    # Sabotaje deliberado: half_even se comporta como half_up en los empates.
    "half_even_as_half_up": "q + sign",
}
SABOTAGES = ("half_even_as_half_up", "div_floor", "str_concat_truncates")


class RustEmitter:
    def __init__(self, module: dict, sabotage: str | None = None):
        if sabotage is not None and sabotage not in SABOTAGES:
            raise ValueError(sabotage)
        self.module = module
        self.sabotage = sabotage
        self.lines: list[str] = []
        self.indent = 1
        self.tmp = 0
        self.local_types: list = []
        self.rets = {fn["name"]: ty_from_json(fn["ret"]) for fn in module["functions"]}
        self.structs: dict[str, str] = {}      # repr(StructT) -> nombre del struct de Rust
        self.struct_defs: list[str] = []

    # --- tipos ----------------------------------------------------------------
    def rtype(self, t) -> str:
        if isinstance(t, BoolT):
            return "bool"
        if isinstance(t, IntT):
            return f"{'i' if t.signed else 'u'}{t.bits}"
        if isinstance(t, DecT):
            return "i64"
        if isinstance(t, StrT):
            return f"IsyStr<{t.n}>"
        if isinstance(t, StructT):
            key = repr(t)
            if key not in self.structs:
                name = f"S{len(self.structs)}_{type_ident(t.name)}"
                self.structs[key] = name
                fields = ", ".join(f"f_{fn}: {self.rtype(ft)}" for fn, ft in t.fields)
                self.struct_defs.append(f"#[derive(Clone, Copy, PartialEq)]\nstruct {name} {{ {fields} }}")
            return self.structs[key]
        return f"[{self.rtype(t.elem)}; {t.n}]"

    def zero(self, t) -> str:
        if isinstance(t, BoolT):
            return "false"
        if isinstance(t, ArrT):
            return f"[{self.zero(t.elem)}; {t.n}]"
        if isinstance(t, StrT):
            return f"IsyStr::<{t.n}> {{ len: 0, v: [0u8; {t.n}] }}"
        if isinstance(t, StructT):
            fields = ", ".join(f"f_{fn}: {self.zero(ft)}" for fn, ft in t.fields)
            return f"{self.rtype(t)} {{ {fields} }}"
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
        main_src = self.rust_main(main)
        return "\n".join([f"// generado por isyco.backends.rust desde ISY-IR {self.module['source_sha256']}",
                          RUNTIME.replace("ISY_HALF_EVEN_TIE", HALF_EVEN_TIE.get(self.sabotage, HALF_EVEN_TIE[None])),
                          *self.struct_defs, *bodies, main_src, ""])

    def signature(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        params = "".join(f", mut l{p}: {self.rtype(types[p])}" for p in fn["params"])
        ret = ty_from_json(fn["ret"])
        return f"fn {fn_ident(fn['name'])}(c: &mut Ctx{params}){'' if ret is None else ' -> ' + self.rtype(ret)}"

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
        count = sum(self.leaf_count(types[p]) for p in fn["params"])
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
            lines.append(f"    let mut a{p}: {self.rtype(t)} = {self.zero(t)};")
            argi = self.read_args(t, f"a{p}", argi, lines)
        call = f"f_main(c{''.join(', ' + n for n in names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    let r: {self.rtype(ret)} = {call};")
            lines.append('    c.out.extend_from_slice(b"R ");')
            lines += ["    " + x for x in self.put_top(ret, "r")]
            lines.append("    c.out.push(b'\\n');")
        lines += ['    isy_end(c, "HALTED", "-");', "}"]
        return "\n".join(lines)

    def leaf_count(self, t) -> int:
        if isinstance(t, ArrT):
            return t.n * self.leaf_count(t.elem)
        if isinstance(t, StructT):
            return sum(self.leaf_count(ft) for _, ft in t.fields)
        return 1

    def read_args(self, t, target: str, argi: int, lines: list) -> int:
        """Argumentos aplanados (ISY_BACKEND/1 §3) -> target; devuelve el siguiente índice."""
        if isinstance(t, ArrT):
            for k in range(t.n):
                argi = self.read_args(t.elem, f"{target}[{k}]", argi, lines)
            return argi
        if isinstance(t, StructT):
            for fname, ft in t.fields:
                argi = self.read_args(ft, f"{target}.f_{fname}", argi, lines)
            return argi
        if isinstance(t, StrT):
            lines.append(f"    {target} = isy_str::<{t.n}>(c, a[{argi}].as_bytes());")
        else:
            lines.append(f"    {target} = {self.arg(t, argi)};")
        return argi + 1

    def put_top(self, t, value: str) -> list[str]:
        """Carga de E/R: escalar canónico, str tal cual, arreglo/struct como JSON."""
        if isinstance(t, StrT):
            return [f"isy_put_text(c, {value}.s());"]
        if isinstance(t, (ArrT, StructT)):
            return self.json(t, value, 0)
        return [f"{self.put_call(t, value)};"]

    def json(self, t, x: str, depth: int) -> list[str]:
        """Sentencias que escriben x como JSON canónico (escalares entre comillas)."""
        if isinstance(t, StrT):
            return [f"isy_put_json_text(c, {x}.s());"]
        if isinstance(t, ArrT):
            i = f"i{depth}"
            return ["c.out.push(b'[');", f"for {i} in 0..{t.n}usize {{",
                    f"    if {i} > 0 {{ c.out.push(b','); }}",
                    *["    " + line for line in self.json(t.elem, f"{x}[{i}]", depth + 1)],
                    "}", "c.out.push(b']');"]
        if isinstance(t, StructT):
            out = ["c.out.push(b'{');"]
            for k, (fname, ft) in enumerate(t.fields):
                out.append(f'c.out.extend_from_slice(b"{"," if k else ""}\\"{fname}\\":");')
                out += self.json(ft, f"{x}.f_{fname}", depth)
            return out + ["c.out.push(b'}');"]
        return ["c.out.push(b'\"');", f"{self.put_call(t, x)};", "c.out.push(b'\"');"]

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
        elif kind == "set_path":
            keys = [self.expr(step["index"]) if "index" in step else None for step in s["path"]]
            value = self.expr(s["value"])
            target, t = f"l{s['local']}", self.local_types[s["local"]]
            for step, key in zip(s["path"], keys):     # rangos al guardar, en orden (E8)
                if "index" in step:
                    self.index_check(key, t.n)
                    target, t = f"{target}[{key} as usize]", t.elem
                else:
                    target, t = f"{target}.f_{step['field']}", t.field(step["field"])
            self.put(f"{target} = {value};")
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
            for line in self.put_top(t, value):
                self.put(line)
            self.put("c.out.push(b'\\n');")
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            self.put(f"{fn_ident(s['fn'])}(c{''.join(', ' + a for a in args)});")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, StrT):
                return self.temp(t, f"isy_str::<{t.n}>(c, {rust_bytes(value)})")
            if isinstance(t, BoolT):
                return "true" if value else "false"
            return f"({value}i128 as {self.rtype(t)})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"{fn_ident(e['fn'])}(c{''.join(', ' + a for a in args)})")
        if kind == "index" and isinstance(ty_from_json(e["base"]["ty"]), StrT):
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            self.put(f"if ({index} as i128) < 0 || ({index} as i128) >= ({base}.len as i128) "
                     f"{{ isy_fail(c, \"INDEX_OUT_OF_BOUNDS\") }}")
            return self.temp(t, f"{base}.v[{index} as usize]")
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
            if isinstance(ty_from_json(e["a"]["ty"]), StrT):
                return f"({a}.s() {CMP[e['op']]} {b}.s())"   # orden de slices = orden de bytes
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
        return self.expr_v2(kind, e, t)

    def expr_v2(self, kind: str, e: dict, t) -> str:
        """Nodos de isy-ir/0.2 (CORE v0.3)."""
        if kind == "concat":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            if self.sabotage == "str_concat_truncates":
                return self.temp(t, f"isy_cat_trunc::<{t.n}>({a}.s(), {b}.s())")
            return self.temp(t, f"isy_cat::<{t.n}>(c, {a}.s(), {b}.s())")
        if kind == "widen":
            return self.temp(t, f"isy_str::<{t.n}>(c, {self.expr(e['e'])}.s())")
        if kind == "len":
            return f"({self.expr(e['e'])}.len as i64)"
        if kind == "slice":
            x = self.expr(e["e"])
            lo = self.expr(e["lo"])
            hi = self.expr(e["hi"])
            self.put(f"if ({lo} as i128) < 0 || ({lo} as i128) > ({hi} as i128) || ({hi} as i128) > ({x}.len as i128) "
                     f"{{ isy_fail(c, \"INDEX_OUT_OF_BOUNDS\") }}")
            return self.temp(t, f"isy_str::<{t.n}>(c, &{x}.v[{lo} as usize..{hi} as usize])")
        if kind == "chr":
            code = self.expr(e["e"])
            self.put(f"if !isy_allowed({code} as i128) {{ isy_fail(c, \"BAD_CHAR\") }}")
            return self.temp(t, f"isy_str::<1>(c, &[{code} as u8])")
        if kind == "field":
            return f"{self.expr(e['base'])}.f_{e['name']}"
        if kind == "struct":
            self.tmp += 1
            name = f"t{self.tmp}"
            self.put(f"let mut {name}: {self.rtype(t)} = {self.zero(t)};")
            for item in e["fields"]:          # en el orden escrito: es el orden de evaluación
                value = self.expr(item["value"])
                self.put(f"{name}.f_{item['name']} = {value};")
            return name
        raise AssertionError(kind)

    def binary(self, e: dict, t) -> str:
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            if op in ("div", "rem"):
                self.put(f"if {b} == ({0} as {self.rtype(t)}) {{ isy_fail(c, \"DIV_ZERO\") }}")
                if op == "div" and self.sabotage == "div_floor":
                    # Sabotaje deliberado: división piso en vez de truncada.
                    exact = (f"{{ let (x, y) = ({a} as i128, {b} as i128); "
                             f"if x % y != 0 && ((x < 0) != (y < 0)) {{ x / y - 1 }} else {{ x / y }} }}")
                else:
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
        if isinstance(dst, StrT):
            if isinstance(src, StrT):
                text = f"{x}.s()"
            elif isinstance(src, BoolT):
                text = f'(if {x} {{ &b"true"[..] }} else {{ &b"false"[..] }})'
            elif isinstance(src, IntT):
                text = f"({x} as i128).to_string().as_bytes()"
            else:
                text = f"&isy_fmt_dec({x} as i128, {src.s})"
            return self.temp(dst, f"isy_str::<{dst.n}>(c, {text})")
        if isinstance(src, StrT):
            if isinstance(dst, BoolT):
                return self.temp(dst, f"isy_parse_bool(c, {x}.s())")
            if isinstance(dst, IntT):
                return self.temp(dst, f"(isy_parse_int(c, {x}.s(), {self.fit_args(dst)}) as {self.rtype(dst)})")
            return self.temp(dst, f"isy_parse_dec(c, {x}.s(), {dst.s}, {dst.max_m}i128)")
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, f"(isy_fit(c, {x} as i128, {self.fit_args(dst)}) as {self.rtype(dst)})")
        if isinstance(src, IntT):
            return self.temp(dst, f"(isy_dec_fit(c, ({x} as i128) * {10 ** dst.s}i128, {dst.max_m}i128) as i64)")
        if isinstance(dst, IntT):
            return self.temp(dst, f"(isy_fit(c, ({x} as i128) / {10 ** src.s}i128, {self.fit_args(dst)}) as {self.rtype(dst)})")
        q = self.rdiv(f"({x} as i128) * {10 ** dst.s}i128", f"{10 ** src.s}i128", ROUND_CODE[dst.rnd])
        return self.temp(dst, f"(isy_dec_fit(c, {q}, {dst.max_m}i128) as i64)")


def rust_bytes(text: str) -> str:
    """Literal de bytes de Rust con exactamente esos bytes (ASCII permitido, P1)."""
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}
    return 'b"' + "".join(escapes.get(ch, ch) for ch in text) + '"'


class RustBackend(Backend):
    name = "rust"
    extension = ".rs"
    features = ALL_FEATURES
    sabotages = SABOTAGES

    def toolchain(self) -> str | None:
        if not shutil.which("rustc"):
            return None
        return subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()

    @con_pila
    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return RustEmitter(module, sabotage).emit()

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return ["rustc", "--edition", "2021", "-O", "-C", "overflow-checks=on", "-C", "panic=abort",
                "--cap-lints", "allow", *extra_flags, "-o", str(binary), str(source)]


BACKEND = RustBackend()
