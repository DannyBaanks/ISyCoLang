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

isy-ir/0.2 (CORE v0.3), sin compartir código con C ni Rust:
- str<N> es `IsyStr(N)` (struct genérico en comptime, por valor);
- cada struct es un `struct` de Zig; `==` lo resuelve `isy_eq`, que recorre el
  tipo con `@typeInfo` en comptime (un str compara solo sus `len` bytes);
- texto -> número con `u128` y `*%`/`+%` explícitos (ReleaseSafe atrapa el resto).
"""
from __future__ import annotations

import platform
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
// ---- isy-ir/0.2 (CORE v0.3): str<N> por valor, salida escapada, texto <-> número ----
fn IsyStr(comptime N: usize) type {
    return struct {
        len: u32,
        v: [N]u8,
        pub const isy_str = true;
        fn s(self: *const @This()) []const u8 {
            return self.v[0..self.len];
        }
    };
}
fn isy_str(comptime N: usize, b: []const u8) IsyStr(N) {
    if (b.len > N) isy_fail("OVERFLOW");
    var r: IsyStr(N) = undefined;
    r.len = @intCast(b.len);
    @memcpy(r.v[0..b.len], b);
    return r;
}
fn isy_cat(comptime N: usize, a: []const u8, b: []const u8) IsyStr(N) {
    if (a.len + b.len > N) isy_fail("OVERFLOW");
    var r: IsyStr(N) = undefined;
    r.len = @intCast(a.len + b.len);
    @memcpy(r.v[0..a.len], a);
    @memcpy(r.v[a.len .. a.len + b.len], b);
    return r;
}
// Sabotaje de prueba: corta en silencio en vez de OVERFLOW (viola S3).
fn isy_cat_trunc(comptime N: usize, a: []const u8, b: []const u8) IsyStr(N) {
    var r: IsyStr(N) = undefined;
    const n1 = @min(a.len, N);
    const n2 = @min(b.len, N - n1);
    @memcpy(r.v[0..n1], a[0..n1]);
    @memcpy(r.v[n1 .. n1 + n2], b[0..n2]);
    r.len = @intCast(n1 + n2);
    return r;
}
// Igualdad por valor (S4, P5): recorre el tipo en comptime; un str compara solo `len` bytes.
fn isy_eq(comptime T: type, a: *const T, b: *const T) bool {
    switch (@typeInfo(T)) {
        .@"struct" => |info| {
            if (@hasDecl(T, "isy_str")) return std.mem.eql(u8, a.v[0..a.len], b.v[0..b.len]);
            inline for (info.fields) |f| {
                if (!isy_eq(f.type, &@field(a.*, f.name), &@field(b.*, f.name))) return false;
            }
            return true;
        },
        .array => |info| {
            for (a, b) |*x, *y| {
                if (!isy_eq(info.child, x, y)) return false;
            }
            return true;
        },
        else => return a.* == b.*,
    }
}
// Carga de una línea E/R: barra invertida y salto de línea escapados (BACKEND §3).
fn isy_out_byte(b: u8) void {
    if (b == '\\') {
        isy_out("\\\\");
    } else if (b == '\n') {
        isy_out("\\n");
    } else {
        isy_out(&[_]u8{b});
    }
}
fn isy_put_text(t: []const u8) void {
    for (t) |b| isy_out_byte(b);
}
fn isy_put_json_text(t: []const u8) void {
    isy_out_byte('"');
    for (t) |b| {
        switch (b) {
            '"' => {
                isy_out_byte('\\');
                isy_out_byte('"');
            },
            '\\' => {
                isy_out_byte('\\');
                isy_out_byte('\\');
            },
            '\n' => {
                isy_out_byte('\\');
                isy_out_byte('n');
            },
            '\t' => {
                isy_out_byte('\\');
                isy_out_byte('t');
            },
            else => isy_out_byte(b),
        }
    }
    isy_out_byte('"');
}
fn isy_allowed(x: i128) bool {
    return x == 9 or x == 10 or (x >= 32 and x <= 126);
}
fn isy_fmt_i128(buf: *[64]u8, v: i128) usize {
    var tmp: [64]u8 = undefined;
    var n: usize = 0;
    var u: u128 = if (v < 0) @as(u128, @intCast(-(v + 1))) + 1 else @as(u128, @intCast(v));
    while (true) {
        tmp[n] = @as(u8, @intCast(u % 10)) + '0';
        n += 1;
        u /= 10;
        if (u == 0) break;
    }
    var k: usize = 0;
    if (v < 0) {
        buf[k] = '-';
        k += 1;
    }
    while (n > 0) {
        n -= 1;
        buf[k] = tmp[n];
        k += 1;
    }
    return k;
}
fn isy_fmt_dec(buf: *[64]u8, m: i128, s: usize) usize {
    if (s == 0) return isy_fmt_i128(buf, m);
    var tmp: [64]u8 = undefined;
    var n: usize = 0;
    var u: u128 = @as(u128, @intCast(if (m < 0) -m else m));
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
    var k: usize = 0;
    if (m < 0) {
        buf[k] = '-';
        k += 1;
    }
    while (n > s) {
        n -= 1;
        buf[k] = tmp[n];
        k += 1;
    }
    buf[k] = '.';
    k += 1;
    while (n > 0) {
        n -= 1;
        buf[k] = tmp[n];
        k += 1;
    }
    return k;
}
// Magnitud de una tira de dígitos. big = el valor real es >= 2^123 (no cabe en ningún
// tipo); mag sigue siendo el exacto módulo 2^128 (operaciones *% y +%), lo que wrap necesita.
const IsyMag = struct { mag: u128, big: bool };
fn isy_digits(d: []const u8) IsyMag {
    var mag: u128 = 0;
    var big = false;
    for (d) |b| {
        if (mag >= (@as(u128, 1) << 123)) big = true;
        mag = mag *% 10 +% @as(u128, b - '0');
    }
    if (mag >= (@as(u128, 1) << 123)) big = true;
    return .{ .mag = mag, .big = big };
}
fn isy_is_digits(d: []const u8) bool {
    for (d) |b| {
        if (b < '0' or b > '9') return false;
    }
    return true;
}
fn isy_parse_int(t: []const u8, lo: i128, hi: i128, bits: u7, ovf: u8) i128 {
    const neg = t.len > 0 and t[0] == '-';
    const d = if (neg) t[1..] else t;
    if (d.len == 0 or !isy_is_digits(d) or (d[0] == '0' and d.len > 1) or (neg and d.len == 1 and d[0] == '0'))
        isy_fail("BAD_FORMAT");
    const r = isy_digits(d);
    if (!r.big) {
        const v: i128 = @intCast(r.mag);
        return isy_fit(if (neg) -v else v, lo, hi, bits, ovf);
    }
    if (ovf == 0) isy_fail("OVERFLOW");
    if (ovf == 2) return if (neg) lo else hi;
    const u: u128 = if (neg) @as(u128, 0) -% r.mag else r.mag;
    const w: u128 = @as(u128, 1) << bits;
    const x: i128 = @intCast(u & (w - 1));
    return if (x > hi) x - @as(i128, @intCast(w)) else x;
}
fn isy_parse_dec(t: []const u8, scale: usize, max: i128) i64 {
    const neg = t.len > 0 and t[0] == '-';
    const d = if (neg) t[1..] else t;
    var int_len: usize = 0;
    while (int_len < d.len and d[int_len] >= '0' and d[int_len] <= '9') int_len += 1;
    if (int_len == 0 or (d[0] == '0' and int_len > 1)) isy_fail("BAD_FORMAT");
    var frac: []const u8 = d[0..0];
    if (scale == 0) {
        if (int_len != d.len) isy_fail("BAD_FORMAT");
    } else {
        if (d.len != int_len + 1 + scale or d[int_len] != '.' or !isy_is_digits(d[int_len + 1 ..]))
            isy_fail("BAD_FORMAT");
        frac = d[int_len + 1 ..];
    }
    var zero = true;
    for (d) |b| {
        if (b >= '1' and b <= '9') zero = false;
    }
    if (neg and zero) isy_fail("BAD_FORMAT");
    const whole = isy_digits(d[0..int_len]);
    if (whole.big or whole.mag > @as(u128, @intCast(max))) isy_fail("OVERFLOW");
    var pow: u128 = 1;
    for (0..scale) |_| pow *= 10;
    const mag = whole.mag * pow + isy_digits(frac).mag;
    if (mag > @as(u128, @intCast(max))) isy_fail("OVERFLOW");
    const m: i64 = @intCast(mag);
    return if (neg) -m else m;
}
fn isy_parse_bool(t: []const u8) bool {
    if (std.mem.eql(u8, t, "true")) return true;
    if (std.mem.eql(u8, t, "false")) return false;
    isy_fail("BAD_FORMAT");
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
SABOTAGES = ("half_even_as_half_up", "div_floor", "str_concat_truncates")

# Presupuesto de comptime que el emisor se autoconcede (Z1): el de fábrica de Zig más ocho
# ramas por instanciación de `str` del propio cuerpo. Cuesta una (medido: 960 sitios con una
# firma de cuatro parámetros caben en los 1000 de fábrica y 1024 revientan), así que el ocho
# es margen, no aritmética.
CUOTA_BASE = 1000
CUOTA_SITIO = 8


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
        self.structs: dict[str, str] = {}      # repr(StructT) -> nombre del struct de Zig
        self.struct_defs: list[str] = []
        self.ancho: dict[int, str] = {}        # N -> alias del tipo `IsyStr(N)`
        self.aliases: list[str] = []

    # --- tipos ----------------------------------------------------------------
    def ztype(self, t) -> str:
        if isinstance(t, StrT):
            return self.alias_ancho(t.n)
        if isinstance(t, StructT):
            key = repr(t)
            if key not in self.structs:
                name = f"S{len(self.structs)}_{type_ident(t.name)}"
                self.structs[key] = name
                fields = " ".join(f"f_{fn}: {self.ztype(ft)}," for fn, ft in t.fields)
                self.struct_defs.append(f"const {name} = struct {{ {fields} }};")
            return self.structs[key]
        if isinstance(t, BoolT):
            return "bool"
        if isinstance(t, IntT):
            return f"{'i' if t.signed else 'u'}{t.bits}"
        if isinstance(t, DecT):
            return "i64"
        return f"[{t.n}]{self.ztype(t.elem)}"

    def alias_ancho(self, n: int) -> str:
        """Un `IsyStr(N)` declarado por ancho, no uno por uso.

        Medido en Z1: evaluar la firma de un clone con 1024 parámetros `IsyStr(2)` agota el
        presupuesto de comptime de Zig (~1 rama por instancia) y ninguna cuota escrita dentro
        de un cuerpo lo alcanza, porque el marco es el de la declaración. El tipo es el mismo.
        """
        if n not in self.ancho:
            nombre = f"Str{n}"
            self.ancho[n] = nombre
            self.aliases.append(f"const {nombre} = IsyStr({n});")
        return self.ancho[n]

    def cuota(self, lineas: list[str]) -> list[str]:
        """Cuota de comptime proporcional a las instanciaciones del propio cuerpo.

        Zig cuesta una rama por `isy_str(...)` en el marco de la función —dos antes del alias,
        cuando cada sitio instanciaba además su tipo—: medido en Z1, 960 sitios con una firma
        de cuatro parámetros caben en los 1000 de fábrica y 1024 revientan. Ocho por sitio
        deja ocho veces de margen sin apagar la guarda, que sigue siendo finita y sigue
        creciendo solo con el código que el emisor genera de verdad.
        """
        sitios = sum(l.count("isy_str(") for l in lineas)
        if not sitios:
            return lineas
        return [f"    comptime {{ @setEvalBranchQuota({CUOTA_BASE + CUOTA_SITIO * sitios}); }}"] + lineas

    def zero(self, t) -> str:
        if isinstance(t, BoolT):
            return "false"
        if self.v2_type(t):
            # Todo local se escribe con su `let` antes de leerse (lo exige el validador);
            # `undefined` evita que Zig construya en comptime arreglos de 64 KB.
            return "undefined"
        if isinstance(t, ArrT):
            return f"[_]{self.ztype(t.elem)}{{{self.zero(t.elem)}}} ** {t.n}"
        return "0"

    @staticmethod
    def v2_type(t) -> bool:
        if isinstance(t, (StrT, StructT)):
            return True
        return isinstance(t, ArrT) and isinstance(t.elem, (StrT, StructT))

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
        main_src = self.zig_main(main)
        return "\n".join([f"// generado por isyco.backends.zig desde ISY-IR {self.module['source_sha256']}",
                          RUNTIME.replace("ISY_HALF_EVEN_TIE", HALF_EVEN_TIE.get(self.sabotage, HALF_EVEN_TIE[None])),
                          *self.aliases, *self.struct_defs, *bodies, main_src, ""])

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
        header = f"fn {fn_ident(fn['name'])}({params}) {'void' if ret is None else self.ztype(ret)}"
        return f"{header} {{\n" + "\n".join(self.cuota(self.lines)) + "\n}\n"

    def zig_main(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        count = sum(self.leaf_count(types[p]) for p in fn["params"])
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
            if isinstance(t, (ArrT, StrT, StructT)):
                lines.append(f"    var a{p}: {self.ztype(t)} = undefined;")
                argi = self.read_args(t, f"a{p}", argi, lines)
            else:
                lines.append(f"    const a{p}: {self.ztype(t)} = {self.arg(t, argi)};")
                argi += 1
        call = f"f_main({', '.join(names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    const r: {self.ztype(ret)} = {call};")
            lines.append('    isy_out("R ");')
            lines += ["    " + x for x in self.put_top(ret, "r")]
            lines.append('    isy_out("\\n");')
        lines += ['    isy_end("HALTED", "-");', "}"]
        return "\n".join([lines[0], *self.cuota(lines[1:-1]), "}"])

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
            lines.append(f"    {target} = isy_str({t.n}, std.mem.span(argv[{argi}]));")
        else:
            lines.append(f"    {target} = {self.arg(t, argi)};")
        return argi + 1

    def put_top(self, t, value: str) -> list[str]:
        """Carga de E/R: escalar canónico, str tal cual, arreglo/struct como JSON."""
        if isinstance(t, StrT):
            return [f"isy_put_text({value}.s());"]
        if isinstance(t, (ArrT, StructT)):
            return self.json(t, value, 0)
        return [f"{self.put_call(t, value)};"]

    def json(self, t, x: str, depth: int) -> list[str]:
        """Sentencias que escriben x como JSON canónico (escalares entre comillas)."""
        if isinstance(t, StrT):
            return [f"isy_put_json_text({x}.s());"]
        if isinstance(t, ArrT):
            i = f"j{depth}"   # `i0` sería el tipo primitivo entero de 0 bits en Zig
            return ['isy_out("[");', f"for (0..{t.n}) |{i}| {{",
                    f'    if ({i} > 0) isy_out(",");',
                    *["    " + line for line in self.json(t.elem, f"{x}[{i}]", depth + 1)],
                    "}", 'isy_out("]");']
        if isinstance(t, StructT):
            out = ['isy_out("{");']
            for k, (fname, ft) in enumerate(t.fields):
                out.append(f'isy_out("{"," if k else ""}\\"{fname}\\":");')
                out += self.json(ft, f"{x}.f_{fname}", depth)
            return out + ['isy_out("}");']
        return ['isy_out("\\"");', f"{self.put_call(t, x)};", 'isy_out("\\"");']

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
        elif kind == "set_path":
            keys = [self.expr(step["index"]) if "index" in step else None for step in s["path"]]
            value = self.expr(s["value"])
            target, t = f"l{s['local']}", self.local_types[s["local"]]
            for step, key in zip(s["path"], keys):     # rangos al guardar, en orden (E8)
                if "index" in step:
                    self.index_check(key, t.n)
                    target, t = f"{target}[@as(usize, @intCast({key}))]", t.elem
                else:
                    target, t = f"{target}.f_{step['field']}", t.field(step["field"])
            self.put(f"{target} = {value};")
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
            for line in self.put_top(t, value):
                self.put(line)
            self.put('isy_out("\\n");')
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            call = f"{fn_ident(s['fn'])}({', '.join(args)})"
            self.put(f"{call};" if self.rets[s["fn"]] is None else f"_ = {call};")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, StrT):
                return self.temp(t, f"isy_str({t.n}, {zig_string(value)})")
            if isinstance(t, BoolT):
                return f"isy_k(bool, {'true' if value else 'false'})"
            return f"isy_k({self.ztype(t)}, {value})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"{fn_ident(e['fn'])}({', '.join(args)})")
        if kind == "index" and isinstance(ty_from_json(e["base"]["ty"]), StrT):
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            self.put(f"if (@as(i128, {index}) < 0 or @as(i128, {index}) >= @as(i128, {base}.len)) "
                     f"isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            return self.temp(t, f"{base}.v[@as(usize, @intCast({index}))]")
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
            at = ty_from_json(e["a"]["ty"])
            if isinstance(at, StrT):
                op = e["op"]
                if op in ("eq", "ne"):
                    return f"({'' if op == 'eq' else '!'}std.mem.eql(u8, {a}.s(), {b}.s()))"
                order = {"lt": "== .lt", "le": "!= .gt", "gt": "== .gt", "ge": "!= .lt"}[op]
                return f"(std.mem.order(u8, {a}.s(), {b}.s()) {order})"
            if isinstance(at, (ArrT, StructT)):
                ta, tb = self.temp(at, a), self.temp(at, b)
                return f"({'' if e['op'] == 'eq' else '!'}isy_eq({self.ztype(at)}, &{ta}, &{tb}))"
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
        return self.expr_v2(kind, e, t)

    def expr_v2(self, kind: str, e: dict, t) -> str:
        """Nodos de isy-ir/0.2 (CORE v0.3)."""
        if kind == "concat":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            fn = "isy_cat_trunc" if self.sabotage == "str_concat_truncates" else "isy_cat"
            return self.temp(t, f"{fn}({t.n}, {a}.s(), {b}.s())")
        if kind == "widen":
            return self.temp(t, f"isy_str({t.n}, {self.expr(e['e'])}.s())")
        if kind == "len":
            return f"@as(i64, {self.expr(e['e'])}.len)"
        if kind == "slice":
            x = self.expr(e["e"])
            lo = self.expr(e["lo"])
            hi = self.expr(e["hi"])
            self.put(f"if (@as(i128, {lo}) < 0 or @as(i128, {lo}) > @as(i128, {hi}) or "
                     f"@as(i128, {hi}) > @as(i128, {x}.len)) isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            return self.temp(t, f"isy_str({t.n}, {x}.v[@as(usize, @intCast({lo}))..@as(usize, @intCast({hi}))])")
        if kind == "chr":
            code = self.expr(e["e"])
            self.put(f"if (!isy_allowed(@as(i128, {code}))) isy_fail(\"BAD_CHAR\");")
            return self.temp(t, f"isy_str(1, &[_]u8{{@as(u8, @intCast({code}))}})")
        if kind == "field":
            return f"{self.expr(e['base'])}.f_{e['name']}"
        if kind == "struct":
            self.tmp += 1
            name = f"t{self.tmp}"
            self.put(f"var {name}: {self.ztype(t)} = undefined;")
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
        if isinstance(dst, StrT):
            if isinstance(src, StrT):
                return self.temp(dst, f"isy_str({dst.n}, {x}.s())")
            if isinstance(src, BoolT):
                return self.temp(dst, f'isy_str({dst.n}, if ({x}) "true" else "false")')
            self.tmp += 1
            buf = f"b{self.tmp}"
            self.put(f"var {buf}: [64]u8 = undefined;")
            if isinstance(src, IntT):
                self.put(f"const {buf}n = isy_fmt_i128(&{buf}, @as(i128, {x}));")
            else:
                self.put(f"const {buf}n = isy_fmt_dec(&{buf}, @as(i128, {x}), {src.s});")
            return self.temp(dst, f"isy_str({dst.n}, {buf}[0..{buf}n])")
        if isinstance(src, StrT):
            if isinstance(dst, BoolT):
                return self.temp(dst, f"isy_parse_bool({x}.s())")
            if isinstance(dst, IntT):
                return self.temp(dst, self.narrow(dst, f"isy_parse_int({x}.s(), {self.fit_args(dst)})"))
            return self.temp(dst, f"isy_parse_dec({x}.s(), {dst.s}, {dst.max_m})")
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, self.narrow(dst, f"isy_fit(@as(i128, {x}), {self.fit_args(dst)})"))
        if isinstance(src, IntT):
            return self.temp(dst, self.narrow(dst, f"isy_dec_fit(@as(i128, {x}) * {10 ** dst.s}, {dst.max_m})"))
        if isinstance(dst, IntT):
            return self.temp(dst, self.narrow(
                dst, f"isy_fit(@divTrunc(@as(i128, {x}), {10 ** src.s}), {self.fit_args(dst)})"))
        return self.temp(dst, self.narrow(dst, f"isy_dec_fit(isy_rdiv(@as(i128, {x}) * {10 ** dst.s}, "
                                               f"{10 ** src.s}, {ROUND_CODE[dst.rnd]}), {dst.max_m})"))


def zig_string(text: str) -> str:
    """Literal de string de Zig con exactamente esos bytes (ASCII permitido, P1)."""
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}
    return '"' + "".join(escapes.get(ch, ch) for ch in text) + '"'


class ZigBackend(Backend):
    name = "zig"
    extension = ".zig"
    features = ALL_FEATURES
    sabotages = SABOTAGES

    def toolchain(self) -> str | None:
        if not shutil.which("zig") or platform.system() != "Linux":
            return None
        return "zig " + subprocess.run(["zig", "version"], capture_output=True, text=True).stdout.strip()

    @con_pila
    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return ZigEmitter(module, sabotage).emit()

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return ["zig", "build-exe", "-O", "ReleaseSafe", *extra_flags,
                f"-femit-bin={binary}", str(source)]


BACKEND = ZigBackend()
