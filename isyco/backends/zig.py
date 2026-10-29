"""Backend Zig: ISY-IR v0.1 -> Zig 0.16 -> binario con `zig build-exe -O ReleaseSafe`.

Implementación independiente de C y Rust (mismo protocolo ISY_BACKEND/1):
- la aritmética entera se calcula exacta en i128 (`@divTrunc`, `@rem`) y
  `isy_fit` aplica trap/wrap/sat; u64*u64 usa `@mulWithOverflow`;
- ReleaseSafe deja activos los chequeos de seguridad: un desborde de i128 o un
  `@intCast` fuera de rango aborta (BACKEND_CRASH) en vez de dar un valor malo;
- Zig rechaza variables sin usar y `var` que nunca cambian: los parámetros se
  copian a `var` locales y cada local se marca con `_ = &lN;`;
- la salida va a un búfer global que se vacía con la syscall write de Linux
  (la API de E/S de la stdlib cambió en 0.15/0.16; la syscall no).
Solo Linux: usa `std.os.linux.write`.
"""
from __future__ import annotations

import platform
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

RUNTIME = r"""const std = @import("std");

var isy_steps: u64 = 0;
var isy_max_steps: u64 = 0;
var isy_depth: u64 = 0;
var isy_max_depth: u64 = 0;
var isy_emits: u64 = 0;
var isy_max_emits: u64 = 0;
var isy_buf: [1 << 16]u8 = undefined;
var isy_len: usize = 0;

fn isy_flush() void {
    var off: usize = 0;
    while (off < isy_len) {
        const n = std.os.linux.write(1, isy_buf[off..].ptr, isy_len - off);
        if (@as(isize, @bitCast(n)) <= 0) break;
        off += n;
    }
    isy_len = 0;
}
fn isy_out(bytes: []const u8) void {
    for (bytes) |b| {
        if (isy_len == isy_buf.len) isy_flush();
        isy_buf[isy_len] = b;
        isy_len += 1;
    }
}
fn isy_put_i128(v: i128) void {
    var tmp: [64]u8 = undefined;
    var n: usize = 0;
    var u: u128 = if (v < 0) @as(u128, @intCast(-(v + 1))) + 1 else @as(u128, @intCast(v));
    while (true) {
        tmp[n] = @as(u8, @intCast(u % 10)) + '0';
        n += 1;
        u /= 10;
        if (u == 0) break;
    }
    if (v < 0) isy_out("-");
    while (n > 0) {
        n -= 1;
        isy_out(tmp[n .. n + 1]);
    }
}
fn isy_put_dec(m: i128, s: usize) void {
    if (s == 0) return isy_put_i128(m);
    var tmp: [64]u8 = undefined;
    var n: usize = 0;
    var u: u128 = if (m < 0) @as(u128, @intCast(-m)) else @as(u128, @intCast(m));
    while (true) {
        tmp[n] = @as(u8, @intCast(u % 10)) + '0';
        n += 1;
        u /= 10;
        if (u == 0) break;
    }
    while (n < s + 1) {
        tmp[n] = '0';
        n += 1;
    }
    if (m < 0) isy_out("-");
    while (n > s) {
        n -= 1;
        isy_out(tmp[n .. n + 1]);
    }
    isy_out(".");
    while (n > 0) {
        n -= 1;
        isy_out(tmp[n .. n + 1]);
    }
}
fn isy_put_bool(b: bool) void {
    isy_out(if (b) "true" else "false");
}
fn isy_end(status: []const u8, code: []const u8) noreturn {
    isy_out("X ");
    isy_out(status);
    isy_out(" ");
    isy_out(code);
    isy_out(" ");
    isy_put_i128(@as(i128, isy_steps));
    isy_out("\n");
    isy_flush();
    std.process.exit(0);
}
fn isy_fail(code: []const u8) noreturn {
    isy_end("ERROR", code);
}
fn isy_limit(code: []const u8) noreturn {
    isy_end("LIMIT_REACHED", code);
}
fn isy_tick() void {
    isy_steps += 1;
    if (isy_steps > isy_max_steps) isy_limit("max_steps");
}
fn isy_enter() void {
    isy_tick();
    if (isy_depth + 1 > isy_max_depth) isy_limit("max_call_depth");
    isy_depth += 1;
}
fn isy_emit_check() void {
    if (isy_emits >= isy_max_emits) isy_limit("max_emits");
    isy_emits += 1;
}
fn isy_fit(v: i128, lo: i128, hi: i128, bits: u7, ovf: u8) i128 {
    if (v >= lo and v <= hi) return v;
    if (ovf == 0) isy_fail("OVERFLOW");
    if (ovf == 2) return if (v > hi) hi else lo;
    const w: i128 = @as(i128, 1) << bits;
    return @mod(v - lo, w) + lo;
}
fn isy_mul_u64(a: u64, b: u64, ovf: u8) u64 {
    const r = @mulWithOverflow(a, b);
    if (r[1] == 0) return r[0];
    if (ovf == 0) isy_fail("OVERFLOW");
    return if (ovf == 1) r[0] else std.math.maxInt(u64);
}
fn isy_rdiv(num: i128, den: i128, mode: u8) i128 {
    const q = @divTrunc(num, den);
    const r = @rem(num, den);
    if (r == 0) return q;
    if (mode == 3) isy_fail("INEXACT");
    if (mode == 2) return q;
    const sign: i128 = if ((num < 0) != (den < 0)) -1 else 1;
    const ar: i128 = if (r < 0) -r else r;
    const ad: i128 = if (den < 0) -den else den;
    if (2 * ar > ad) return q + sign;
    if (2 * ar < ad) return q;
    if (mode == 1) return q + sign;
    ISY_HALF_EVEN_TIE
}
fn isy_dec_fit(m: i128, max: i128) i128 {
    if (m > max or m < -max) isy_fail("OVERFLOW");
    return m;
}
// Identidad en tiempo de ejecución: las constantes de la IR pasan por aquí para que
// Zig no las evalúe en compilación (si no, `while true {}` o `x / 0` con literal
// vuelven inalcanzable o inválido código que la spec sí permite).
fn isy_k(comptime T: type, v: T) T {
    return v;
}
// Relleno en tiempo de ejecución: `[_]T{v} ** n` con `v` runtime hace que LLVM
// expanda las n copias ([u8; 65536] tardaba >45 s con ReleaseSafe). Un bucle
// explícito compila en ~10 s y conserva la semántica de copia.
fn isy_repeat(comptime T: type, comptime n: usize, v: T) [n]T {
    var a: [n]T = undefined;
    for (&a) |*x| x.* = v;
    return a;
}
fn isy_arg(s: [*:0]const u8) i128 {
    var i: usize = 0;
    var neg = false;
    var v: i128 = 0;
    if (s[0] == '-') {
        neg = true;
        i = 1;
    }
    while (s[i] != 0) : (i += 1) v = v * 10 + (s[i] - '0');
    return if (neg) -v else v;
}
"""


def diverts(s: dict) -> bool:
    """La sentencia nunca deja seguir al bloque (return, break, continue o if/else que desvían)."""
    if s["s"] in ("return", "break", "continue"):
        return True
    if s["s"] == "if" and s["else"] is not None:
        return any(diverts(x) for x in s["then"]) and any(diverts(x) for x in s["else"])
    return False


HALF_EVEN_TIE = {
    None: "return if (@rem(q, 2) == 0) q else q + sign;",
    # Sabotaje deliberado: half_even se comporta como half_up en los empates.
    "half_even_as_half_up": "return q + sign;",
}
SABOTAGES = ("half_even_as_half_up", "div_floor")


class ZigEmitter:
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

    # --- tipos ----------------------------------------------------------------
    def ztype(self, t) -> str:
        if isinstance(t, BoolT):
            return "bool"
        if isinstance(t, IntT):
            return f"{'i' if t.signed else 'u'}{t.bits}"
        if isinstance(t, DecT):
            return "i64"
        return f"[{t.n}]{self.ztype(t.elem)}"

    def zero(self, t) -> str:
        if isinstance(t, BoolT):
            return "false"
        if isinstance(t, ArrT):
            return f"[_]{self.ztype(t.elem)}{{{self.zero(t.elem)}}} ** {t.n}"
        return "0"

    @staticmethod
    def fit_args(t: IntT) -> str:
        return f"{t.lo}, {t.hi}, {t.bits}, {OVF_CODE[t.ovf]}"

    def narrow(self, t, i128_expr: str) -> str:
        return f"@as({self.ztype(t)}, @intCast({i128_expr}))"

    # --- utilidades -----------------------------------------------------------
    def put(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def temp(self, t, value: str) -> str:
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"const {name}: {self.ztype(t)} = {value};")
        return name

    # --- módulo ---------------------------------------------------------------
    def emit(self) -> str:
        bodies = [self.function(fn) for fn in self.module["functions"]]
        main = next(f for f in self.module["functions"] if f["name"] == "main")
        return "\n".join([f"// generado por isyco.backends.zig desde ISY-IR {self.module['source_sha256']}",
                          RUNTIME.replace("ISY_HALF_EVEN_TIE", HALF_EVEN_TIE.get(self.sabotage, HALF_EVEN_TIE[None])),
                          *bodies, self.zig_main(main), ""])

    def function(self, fn: dict) -> str:
        self.lines, self.indent, self.tmp = [], 1, 0
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        params = ", ".join(f"p{p}: {self.ztype(self.local_types[p])}" for p in fn["params"])
        ret = ty_from_json(fn["ret"])
        for i, t in enumerate(self.local_types):
            init = f"p{i}" if i in fn["params"] else self.zero(t)
            self.put(f"var l{i}: {self.ztype(t)} = {init};")
            self.put(f"_ = &l{i};")
        self.put("isy_enter();")
        self.block(fn["body"])
        if ret is None and not any(diverts(s) for s in fn["body"]):
            self.put("isy_depth -= 1;")
        # Con valor de retorno no hace falta nada: el validador garantiza que todo camino
        # retorna, y Zig lo comprueba por su cuenta.
        header = f"fn f_{fn['name']}({params}) {'void' if ret is None else self.ztype(ret)}"
        return f"{header} {{\n" + "\n".join(self.lines) + "\n}\n"

    def zig_main(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        count = sum(types[p].n if isinstance(types[p], ArrT) else 1 for p in fn["params"])
        lines = ["pub fn main(init: std.process.Init.Minimal) void {",
                 "    const argv = init.args.vector;",
                 f"    if (argv.len != {4 + count}) std.process.exit(2);",
                 "    isy_max_steps = @as(u64, @intCast(isy_arg(argv[1])));",
                 "    isy_max_depth = @as(u64, @intCast(isy_arg(argv[2])));",
                 "    isy_max_emits = @as(u64, @intCast(isy_arg(argv[3])));"]
        argi = 4
        names = []
        for p in fn["params"]:
            t = types[p]
            names.append(f"a{p}")
            if isinstance(t, ArrT):
                lines.append(f"    var a{p}: {self.ztype(t)} = undefined;")
                for k in range(t.n):
                    lines.append(f"    a{p}[{k}] = {self.arg(t.elem, argi)};")
                    argi += 1
            else:
                lines.append(f"    const a{p}: {self.ztype(t)} = {self.arg(t, argi)};")
                argi += 1
        call = f"f_main({', '.join(names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    const r: {self.ztype(ret)} = {call};")
            lines.append('    isy_out("R ");')
            lines.append(f"    {self.put_call(ret, 'r')};")
            lines.append('    isy_out("\\n");')
        lines += ['    isy_end("HALTED", "-");', "}"]
        return "\n".join(lines)

    def arg(self, t, i: int) -> str:
        if isinstance(t, BoolT):
            return f"(isy_arg(argv[{i}]) != 0)"
        return self.narrow(t, f"isy_arg(argv[{i}])")

    @staticmethod
    def put_call(t, value: str) -> str:
        if isinstance(t, BoolT):
            return f"isy_put_bool({value})"
        if isinstance(t, IntT):
            return f"isy_put_i128(@as(i128, {value}))"
        return f"isy_put_dec(@as(i128, {value}), {t.s})"

    # --- sentencias -----------------------------------------------------------
    def block(self, stmts: list) -> None:
        """Zig rechaza código inalcanzable: se corta el bloque tras una sentencia que
        siempre desvía (return/break/continue, o if/else que desvían en ambas ramas).
        Lo cortado nunca se ejecuta, así que la semántica no cambia."""
        for s in stmts:
            self.stmt(s)
            if diverts(s):
                return

    def nested(self, header: str, stmts: list) -> None:
        self.put(header)
        self.indent += 1
        self.block(stmts)
        self.indent -= 1
        self.put("}")

    def index_check(self, index: str, n: int) -> None:
        self.put(f"if (@as(i128, {index}) < 0 or @as(i128, {index}) >= {n}) isy_fail(\"INDEX_OUT_OF_BOUNDS\");")

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        self.put(f"isy_tick(); // {kind} {s['at']}")
        if kind in ("let", "set"):
            value = self.expr(s["value"])
            self.put(f"l{s['local']} = {value};")
        elif kind == "set_index":
            index = self.expr(s["index"])
            value = self.expr(s["value"])
            self.index_check(index, self.local_types[s["local"]].n)
            self.put(f"l{s['local']}[@as(usize, @intCast({index}))] = {value};")
        elif kind == "if":
            cond = self.expr(s["cond"])
            self.nested(f"if ({cond}) {{", s["then"])
            if s["else"] is not None:
                self.nested("else {", s["else"])
        elif kind == "while":
            self.put("while (true) {")
            self.indent += 1
            self.put("isy_tick();")
            cond = self.expr(s["cond"])
            self.put(f"if (!{cond}) break;")
            self.nested("{", s["body"])
            self.indent -= 1
            self.put("}")
        elif kind == "break":
            self.put("break;")
        elif kind == "continue":
            self.put("continue;")
        elif kind == "return":
            if s["value"] is None:
                self.put("isy_depth -= 1;")
                self.put("return;")
            else:
                value = self.expr(s["value"])
                self.put("isy_depth -= 1;")
                self.put(f"return {value};")
        elif kind == "emit":
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            self.put("isy_emit_check();")
            self.put('isy_out("E ");')
            self.put(f"{self.put_call(t, value)};")
            self.put('isy_out("\\n");')
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            call = f"f_{s['fn']}({', '.join(args)})"
            self.put(f"{call};" if self.rets[s["fn"]] is None else f"_ = {call};")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, BoolT):
                return f"isy_k(bool, {'true' if value else 'false'})"
            return f"isy_k({self.ztype(t)}, {value})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"f_{e['fn']}({', '.join(args)})")
        if kind == "index":
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            self.index_check(index, ty_from_json(e["base"]["ty"]).n)
            return self.temp(t, f"{base}[@as(usize, @intCast({index}))]")
        if kind == "cast":
            return self.cast(e, t)
        if kind == "not":
            return f"(!{self.expr(e['e'])})"
        if kind == "neg":
            x = self.expr(e["e"])
            if isinstance(t, IntT):
                return self.temp(t, self.narrow(t, f"isy_fit(-@as(i128, {x}), {self.fit_args(t)})"))
            return self.temp(t, self.narrow(t, f"isy_dec_fit(-@as(i128, {x}), {t.max_m})"))
        if kind in ("and", "or"):
            first = self.expr(e["a"])
            self.tmp += 1
            name = f"t{self.tmp}"
            self.put(f"var {name}: bool = {first};")
            self.put(f"if ({'' if kind == 'and' else '!'}{name}) {{")
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
            self.put(f"var {name}: {self.ztype(t)} = undefined;")
            for k, item in enumerate(e["elems"]):
                self.put(f"{name}[{k}] = {self.expr(item)};")
            return name
        if kind == "repeat":
            value = self.expr(e["elem"])
            return self.temp(t, f"isy_repeat({self.ztype(t.elem)}, {t.n}, {value})")
        raise AssertionError(kind)

    def binary(self, e: dict, t) -> str:
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            if op in ("div", "rem"):
                self.put(f"if ({b} == 0) isy_fail(\"DIV_ZERO\");")
                fn = "@divTrunc" if op == "div" else "@rem"
                if op == "div" and self.sabotage == "div_floor":
                    fn = "@divFloor"   # sabotaje deliberado: división piso en vez de truncada
                exact = f"{fn}(@as(i128, {a}), @as(i128, {b}))"
            elif op == "mul" and t.bits == 64 and not t.signed:
                return self.temp(t, f"isy_mul_u64({a}, {b}, {OVF_CODE[t.ovf]})")
            else:
                exact = f"(@as(i128, {a}) {ARITH[op]} @as(i128, {b}))"
            return self.temp(t, self.narrow(t, f"isy_fit({exact}, {self.fit_args(t)})"))
        rnd = ROUND_CODE[t.rnd]
        scale = 10 ** t.s
        if op in ("add", "sub"):
            return self.temp(t, self.narrow(t, f"isy_dec_fit(@as(i128, {a}) {ARITH[op]} @as(i128, {b}), {t.max_m})"))
        if op == "mul":
            return self.temp(t, self.narrow(
                t, f"isy_dec_fit(isy_rdiv(@as(i128, {a}) * @as(i128, {b}), {scale}, {rnd}), {t.max_m})"))
        self.put(f"if ({b} == 0) isy_fail(\"DIV_ZERO\");")
        return self.temp(t, self.narrow(
            t, f"isy_dec_fit(isy_rdiv(@as(i128, {a}) * {scale}, @as(i128, {b}), {rnd}), {t.max_m})"))

    def cast(self, e: dict, dst) -> str:
        x = self.expr(e["e"])
        src = ty_from_json(e["e"]["ty"])
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, self.narrow(dst, f"isy_fit(@as(i128, {x}), {self.fit_args(dst)})"))
        if isinstance(src, IntT):
            return self.temp(dst, self.narrow(dst, f"isy_dec_fit(@as(i128, {x}) * {10 ** dst.s}, {dst.max_m})"))
        if isinstance(dst, IntT):
            return self.temp(dst, self.narrow(
                dst, f"isy_fit(@divTrunc(@as(i128, {x}), {10 ** src.s}), {self.fit_args(dst)})"))
        return self.temp(dst, self.narrow(dst, f"isy_dec_fit(isy_rdiv(@as(i128, {x}) * {10 ** dst.s}, "
                                               f"{10 ** src.s}, {ROUND_CODE[dst.rnd]}), {dst.max_m})"))


class ZigBackend(Backend):
    name = "zig"
    extension = ".zig"
    features = ALL_FEATURES
    sabotages = SABOTAGES

    def toolchain(self) -> str | None:
        if not shutil.which("zig") or platform.system() != "Linux":
            return None
        return "zig " + subprocess.run(["zig", "version"], capture_output=True, text=True).stdout.strip()

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return ZigEmitter(module, sabotage).emit()

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return ["zig", "build-exe", "-O", "ReleaseSafe", *extra_flags,
                f"-femit-bin={binary}", str(source)]


BACKEND = ZigBackend()
