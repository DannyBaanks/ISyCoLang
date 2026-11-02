// generado por isyco.backends.zig desde ISY-IR 52a2803975adf30db03bdb6cd975b4dc724faa5ebfdeddc21e5f90fc5e98c9b5
const std = @import("std");

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
    return if (@rem(q, 2) == 0) q else q + sign;
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

fn f_main() i64 {
    isy_enter();
    isy_tick(); // emit 5:5
    const t1: IsyStr(1) = isy_str(1, "x");
    const t2: IsyStr(1) = isy_str(1, "x");
    const t3: IsyStr(1) = isy_str(1, "x");
    const t4: IsyStr(1) = isy_str(1, "x");
    const t5: i64 = m_5multi11111111(t1, t2, t3, t4);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t5));
    isy_out("\n");
    isy_tick(); // emit 6:5
    const t6: IsyStr(1) = isy_str(1, "x");
    const t7: IsyStr(1) = isy_str(1, "x");
    const t8: IsyStr(1) = isy_str(1, "x");
    const t9: IsyStr(2) = isy_str(2, "xx");
    const t10: i64 = m_5multi11111112(t6, t7, t8, t9);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t10));
    isy_out("\n");
    isy_tick(); // emit 7:5
    const t11: IsyStr(1) = isy_str(1, "x");
    const t12: IsyStr(1) = isy_str(1, "x");
    const t13: IsyStr(1) = isy_str(1, "x");
    const t14: IsyStr(3) = isy_str(3, "xxx");
    const t15: i64 = m_5multi11111113(t11, t12, t13, t14);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t15));
    isy_out("\n");
    isy_tick(); // emit 8:5
    const t16: IsyStr(1) = isy_str(1, "x");
    const t17: IsyStr(1) = isy_str(1, "x");
    const t18: IsyStr(1) = isy_str(1, "x");
    const t19: IsyStr(4) = isy_str(4, "xxxx");
    const t20: i64 = m_5multi11111114(t16, t17, t18, t19);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t20));
    isy_out("\n");
    isy_tick(); // emit 9:5
    const t21: IsyStr(1) = isy_str(1, "x");
    const t22: IsyStr(1) = isy_str(1, "x");
    const t23: IsyStr(2) = isy_str(2, "xx");
    const t24: IsyStr(1) = isy_str(1, "x");
    const t25: i64 = m_5multi11111211(t21, t22, t23, t24);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t25));
    isy_out("\n");
    isy_tick(); // emit 10:5
    const t26: IsyStr(1) = isy_str(1, "x");
    const t27: IsyStr(1) = isy_str(1, "x");
    const t28: IsyStr(2) = isy_str(2, "xx");
    const t29: IsyStr(2) = isy_str(2, "xx");
    const t30: i64 = m_5multi11111212(t26, t27, t28, t29);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t30));
    isy_out("\n");
    isy_tick(); // emit 11:5
    const t31: IsyStr(1) = isy_str(1, "x");
    const t32: IsyStr(1) = isy_str(1, "x");
    const t33: IsyStr(2) = isy_str(2, "xx");
    const t34: IsyStr(3) = isy_str(3, "xxx");
    const t35: i64 = m_5multi11111213(t31, t32, t33, t34);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t35));
    isy_out("\n");
    isy_tick(); // emit 12:5
    const t36: IsyStr(1) = isy_str(1, "x");
    const t37: IsyStr(1) = isy_str(1, "x");
    const t38: IsyStr(2) = isy_str(2, "xx");
    const t39: IsyStr(4) = isy_str(4, "xxxx");
    const t40: i64 = m_5multi11111214(t36, t37, t38, t39);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t40));
    isy_out("\n");
    isy_tick(); // emit 13:5
    const t41: IsyStr(1) = isy_str(1, "x");
    const t42: IsyStr(1) = isy_str(1, "x");
    const t43: IsyStr(3) = isy_str(3, "xxx");
    const t44: IsyStr(1) = isy_str(1, "x");
    const t45: i64 = m_5multi11111311(t41, t42, t43, t44);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t45));
    isy_out("\n");
    isy_tick(); // emit 14:5
    const t46: IsyStr(1) = isy_str(1, "x");
    const t47: IsyStr(1) = isy_str(1, "x");
    const t48: IsyStr(3) = isy_str(3, "xxx");
    const t49: IsyStr(2) = isy_str(2, "xx");
    const t50: i64 = m_5multi11111312(t46, t47, t48, t49);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t50));
    isy_out("\n");
    isy_tick(); // emit 15:5
    const t51: IsyStr(1) = isy_str(1, "x");
    const t52: IsyStr(1) = isy_str(1, "x");
    const t53: IsyStr(3) = isy_str(3, "xxx");
    const t54: IsyStr(3) = isy_str(3, "xxx");
    const t55: i64 = m_5multi11111313(t51, t52, t53, t54);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t55));
    isy_out("\n");
    isy_tick(); // emit 16:5
    const t56: IsyStr(1) = isy_str(1, "x");
    const t57: IsyStr(1) = isy_str(1, "x");
    const t58: IsyStr(3) = isy_str(3, "xxx");
    const t59: IsyStr(4) = isy_str(4, "xxxx");
    const t60: i64 = m_5multi11111314(t56, t57, t58, t59);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t60));
    isy_out("\n");
    isy_tick(); // emit 17:5
    const t61: IsyStr(1) = isy_str(1, "x");
    const t62: IsyStr(1) = isy_str(1, "x");
    const t63: IsyStr(4) = isy_str(4, "xxxx");
    const t64: IsyStr(1) = isy_str(1, "x");
    const t65: i64 = m_5multi11111411(t61, t62, t63, t64);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t65));
    isy_out("\n");
    isy_tick(); // emit 18:5
    const t66: IsyStr(1) = isy_str(1, "x");
    const t67: IsyStr(1) = isy_str(1, "x");
    const t68: IsyStr(4) = isy_str(4, "xxxx");
    const t69: IsyStr(2) = isy_str(2, "xx");
    const t70: i64 = m_5multi11111412(t66, t67, t68, t69);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t70));
    isy_out("\n");
    isy_tick(); // emit 19:5
    const t71: IsyStr(1) = isy_str(1, "x");
    const t72: IsyStr(1) = isy_str(1, "x");
    const t73: IsyStr(4) = isy_str(4, "xxxx");
    const t74: IsyStr(3) = isy_str(3, "xxx");
    const t75: i64 = m_5multi11111413(t71, t72, t73, t74);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t75));
    isy_out("\n");
    isy_tick(); // emit 20:5
    const t76: IsyStr(1) = isy_str(1, "x");
    const t77: IsyStr(1) = isy_str(1, "x");
    const t78: IsyStr(4) = isy_str(4, "xxxx");
    const t79: IsyStr(4) = isy_str(4, "xxxx");
    const t80: i64 = m_5multi11111414(t76, t77, t78, t79);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t80));
    isy_out("\n");
    isy_tick(); // emit 21:5
    const t81: IsyStr(1) = isy_str(1, "x");
    const t82: IsyStr(2) = isy_str(2, "xx");
    const t83: IsyStr(1) = isy_str(1, "x");
    const t84: IsyStr(1) = isy_str(1, "x");
    const t85: i64 = m_5multi11121111(t81, t82, t83, t84);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t85));
    isy_out("\n");
    isy_tick(); // emit 22:5
    const t86: IsyStr(1) = isy_str(1, "x");
    const t87: IsyStr(2) = isy_str(2, "xx");
    const t88: IsyStr(1) = isy_str(1, "x");
    const t89: IsyStr(2) = isy_str(2, "xx");
    const t90: i64 = m_5multi11121112(t86, t87, t88, t89);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t90));
    isy_out("\n");
    isy_tick(); // emit 23:5
    const t91: IsyStr(1) = isy_str(1, "x");
    const t92: IsyStr(2) = isy_str(2, "xx");
    const t93: IsyStr(1) = isy_str(1, "x");
    const t94: IsyStr(3) = isy_str(3, "xxx");
    const t95: i64 = m_5multi11121113(t91, t92, t93, t94);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t95));
    isy_out("\n");
    isy_tick(); // emit 24:5
    const t96: IsyStr(1) = isy_str(1, "x");
    const t97: IsyStr(2) = isy_str(2, "xx");
    const t98: IsyStr(1) = isy_str(1, "x");
    const t99: IsyStr(4) = isy_str(4, "xxxx");
    const t100: i64 = m_5multi11121114(t96, t97, t98, t99);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t100));
    isy_out("\n");
    isy_tick(); // emit 25:5
    const t101: IsyStr(1) = isy_str(1, "x");
    const t102: IsyStr(2) = isy_str(2, "xx");
    const t103: IsyStr(2) = isy_str(2, "xx");
    const t104: IsyStr(1) = isy_str(1, "x");
    const t105: i64 = m_5multi11121211(t101, t102, t103, t104);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t105));
    isy_out("\n");
    isy_tick(); // emit 26:5
    const t106: IsyStr(1) = isy_str(1, "x");
    const t107: IsyStr(2) = isy_str(2, "xx");
    const t108: IsyStr(2) = isy_str(2, "xx");
    const t109: IsyStr(2) = isy_str(2, "xx");
    const t110: i64 = m_5multi11121212(t106, t107, t108, t109);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t110));
    isy_out("\n");
    isy_tick(); // emit 27:5
    const t111: IsyStr(1) = isy_str(1, "x");
    const t112: IsyStr(2) = isy_str(2, "xx");
    const t113: IsyStr(2) = isy_str(2, "xx");
    const t114: IsyStr(3) = isy_str(3, "xxx");
    const t115: i64 = m_5multi11121213(t111, t112, t113, t114);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t115));
    isy_out("\n");
    isy_tick(); // emit 28:5
    const t116: IsyStr(1) = isy_str(1, "x");
    const t117: IsyStr(2) = isy_str(2, "xx");
    const t118: IsyStr(2) = isy_str(2, "xx");
    const t119: IsyStr(4) = isy_str(4, "xxxx");
    const t120: i64 = m_5multi11121214(t116, t117, t118, t119);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t120));
    isy_out("\n");
    isy_tick(); // emit 29:5
    const t121: IsyStr(1) = isy_str(1, "x");
    const t122: IsyStr(2) = isy_str(2, "xx");
    const t123: IsyStr(3) = isy_str(3, "xxx");
    const t124: IsyStr(1) = isy_str(1, "x");
    const t125: i64 = m_5multi11121311(t121, t122, t123, t124);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t125));
    isy_out("\n");
    isy_tick(); // emit 30:5
    const t126: IsyStr(1) = isy_str(1, "x");
    const t127: IsyStr(2) = isy_str(2, "xx");
    const t128: IsyStr(3) = isy_str(3, "xxx");
    const t129: IsyStr(2) = isy_str(2, "xx");
    const t130: i64 = m_5multi11121312(t126, t127, t128, t129);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t130));
    isy_out("\n");
    isy_tick(); // emit 31:5
    const t131: IsyStr(1) = isy_str(1, "x");
    const t132: IsyStr(2) = isy_str(2, "xx");
    const t133: IsyStr(3) = isy_str(3, "xxx");
    const t134: IsyStr(3) = isy_str(3, "xxx");
    const t135: i64 = m_5multi11121313(t131, t132, t133, t134);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t135));
    isy_out("\n");
    isy_tick(); // emit 32:5
    const t136: IsyStr(1) = isy_str(1, "x");
    const t137: IsyStr(2) = isy_str(2, "xx");
    const t138: IsyStr(3) = isy_str(3, "xxx");
    const t139: IsyStr(4) = isy_str(4, "xxxx");
    const t140: i64 = m_5multi11121314(t136, t137, t138, t139);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t140));
    isy_out("\n");
    isy_tick(); // emit 33:5
    const t141: IsyStr(1) = isy_str(1, "x");
    const t142: IsyStr(2) = isy_str(2, "xx");
    const t143: IsyStr(4) = isy_str(4, "xxxx");
    const t144: IsyStr(1) = isy_str(1, "x");
    const t145: i64 = m_5multi11121411(t141, t142, t143, t144);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t145));
    isy_out("\n");
    isy_tick(); // emit 34:5
    const t146: IsyStr(1) = isy_str(1, "x");
    const t147: IsyStr(2) = isy_str(2, "xx");
    const t148: IsyStr(4) = isy_str(4, "xxxx");
    const t149: IsyStr(2) = isy_str(2, "xx");
    const t150: i64 = m_5multi11121412(t146, t147, t148, t149);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t150));
    isy_out("\n");
    isy_tick(); // emit 35:5
    const t151: IsyStr(1) = isy_str(1, "x");
    const t152: IsyStr(2) = isy_str(2, "xx");
    const t153: IsyStr(4) = isy_str(4, "xxxx");
    const t154: IsyStr(3) = isy_str(3, "xxx");
    const t155: i64 = m_5multi11121413(t151, t152, t153, t154);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t155));
    isy_out("\n");
    isy_tick(); // emit 36:5
    const t156: IsyStr(1) = isy_str(1, "x");
    const t157: IsyStr(2) = isy_str(2, "xx");
    const t158: IsyStr(4) = isy_str(4, "xxxx");
    const t159: IsyStr(4) = isy_str(4, "xxxx");
    const t160: i64 = m_5multi11121414(t156, t157, t158, t159);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t160));
    isy_out("\n");
    isy_tick(); // emit 37:5
    const t161: IsyStr(1) = isy_str(1, "x");
    const t162: IsyStr(3) = isy_str(3, "xxx");
    const t163: IsyStr(1) = isy_str(1, "x");
    const t164: IsyStr(1) = isy_str(1, "x");
    const t165: i64 = m_5multi11131111(t161, t162, t163, t164);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t165));
    isy_out("\n");
    isy_tick(); // emit 38:5
    const t166: IsyStr(1) = isy_str(1, "x");
    const t167: IsyStr(3) = isy_str(3, "xxx");
    const t168: IsyStr(1) = isy_str(1, "x");
    const t169: IsyStr(2) = isy_str(2, "xx");
    const t170: i64 = m_5multi11131112(t166, t167, t168, t169);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t170));
    isy_out("\n");
    isy_tick(); // emit 39:5
    const t171: IsyStr(1) = isy_str(1, "x");
    const t172: IsyStr(3) = isy_str(3, "xxx");
    const t173: IsyStr(1) = isy_str(1, "x");
    const t174: IsyStr(3) = isy_str(3, "xxx");
    const t175: i64 = m_5multi11131113(t171, t172, t173, t174);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t175));
    isy_out("\n");
    isy_tick(); // emit 40:5
    const t176: IsyStr(1) = isy_str(1, "x");
    const t177: IsyStr(3) = isy_str(3, "xxx");
    const t178: IsyStr(1) = isy_str(1, "x");
    const t179: IsyStr(4) = isy_str(4, "xxxx");
    const t180: i64 = m_5multi11131114(t176, t177, t178, t179);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t180));
    isy_out("\n");
    isy_tick(); // emit 41:5
    const t181: IsyStr(1) = isy_str(1, "x");
    const t182: IsyStr(3) = isy_str(3, "xxx");
    const t183: IsyStr(2) = isy_str(2, "xx");
    const t184: IsyStr(1) = isy_str(1, "x");
    const t185: i64 = m_5multi11131211(t181, t182, t183, t184);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t185));
    isy_out("\n");
    isy_tick(); // emit 42:5
    const t186: IsyStr(1) = isy_str(1, "x");
    const t187: IsyStr(3) = isy_str(3, "xxx");
    const t188: IsyStr(2) = isy_str(2, "xx");
    const t189: IsyStr(2) = isy_str(2, "xx");
    const t190: i64 = m_5multi11131212(t186, t187, t188, t189);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t190));
    isy_out("\n");
    isy_tick(); // emit 43:5
    const t191: IsyStr(1) = isy_str(1, "x");
    const t192: IsyStr(3) = isy_str(3, "xxx");
    const t193: IsyStr(2) = isy_str(2, "xx");
    const t194: IsyStr(3) = isy_str(3, "xxx");
    const t195: i64 = m_5multi11131213(t191, t192, t193, t194);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t195));
    isy_out("\n");
    isy_tick(); // emit 44:5
    const t196: IsyStr(1) = isy_str(1, "x");
    const t197: IsyStr(3) = isy_str(3, "xxx");
    const t198: IsyStr(2) = isy_str(2, "xx");
    const t199: IsyStr(4) = isy_str(4, "xxxx");
    const t200: i64 = m_5multi11131214(t196, t197, t198, t199);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t200));
    isy_out("\n");
    isy_tick(); // emit 45:5
    const t201: IsyStr(1) = isy_str(1, "x");
    const t202: IsyStr(3) = isy_str(3, "xxx");
    const t203: IsyStr(3) = isy_str(3, "xxx");
    const t204: IsyStr(1) = isy_str(1, "x");
    const t205: i64 = m_5multi11131311(t201, t202, t203, t204);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t205));
    isy_out("\n");
    isy_tick(); // emit 46:5
    const t206: IsyStr(1) = isy_str(1, "x");
    const t207: IsyStr(3) = isy_str(3, "xxx");
    const t208: IsyStr(3) = isy_str(3, "xxx");
    const t209: IsyStr(2) = isy_str(2, "xx");
    const t210: i64 = m_5multi11131312(t206, t207, t208, t209);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t210));
    isy_out("\n");
    isy_tick(); // emit 47:5
    const t211: IsyStr(1) = isy_str(1, "x");
    const t212: IsyStr(3) = isy_str(3, "xxx");
    const t213: IsyStr(3) = isy_str(3, "xxx");
    const t214: IsyStr(3) = isy_str(3, "xxx");
    const t215: i64 = m_5multi11131313(t211, t212, t213, t214);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t215));
    isy_out("\n");
    isy_tick(); // emit 48:5
    const t216: IsyStr(1) = isy_str(1, "x");
    const t217: IsyStr(3) = isy_str(3, "xxx");
    const t218: IsyStr(3) = isy_str(3, "xxx");
    const t219: IsyStr(4) = isy_str(4, "xxxx");
    const t220: i64 = m_5multi11131314(t216, t217, t218, t219);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t220));
    isy_out("\n");
    isy_tick(); // emit 49:5
    const t221: IsyStr(1) = isy_str(1, "x");
    const t222: IsyStr(3) = isy_str(3, "xxx");
    const t223: IsyStr(4) = isy_str(4, "xxxx");
    const t224: IsyStr(1) = isy_str(1, "x");
    const t225: i64 = m_5multi11131411(t221, t222, t223, t224);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t225));
    isy_out("\n");
    isy_tick(); // emit 50:5
    const t226: IsyStr(1) = isy_str(1, "x");
    const t227: IsyStr(3) = isy_str(3, "xxx");
    const t228: IsyStr(4) = isy_str(4, "xxxx");
    const t229: IsyStr(2) = isy_str(2, "xx");
    const t230: i64 = m_5multi11131412(t226, t227, t228, t229);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t230));
    isy_out("\n");
    isy_tick(); // emit 51:5
    const t231: IsyStr(1) = isy_str(1, "x");
    const t232: IsyStr(3) = isy_str(3, "xxx");
    const t233: IsyStr(4) = isy_str(4, "xxxx");
    const t234: IsyStr(3) = isy_str(3, "xxx");
    const t235: i64 = m_5multi11131413(t231, t232, t233, t234);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t235));
    isy_out("\n");
    isy_tick(); // emit 52:5
    const t236: IsyStr(1) = isy_str(1, "x");
    const t237: IsyStr(3) = isy_str(3, "xxx");
    const t238: IsyStr(4) = isy_str(4, "xxxx");
    const t239: IsyStr(4) = isy_str(4, "xxxx");
    const t240: i64 = m_5multi11131414(t236, t237, t238, t239);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t240));
    isy_out("\n");
    isy_tick(); // emit 53:5
    const t241: IsyStr(1) = isy_str(1, "x");
    const t242: IsyStr(4) = isy_str(4, "xxxx");
    const t243: IsyStr(1) = isy_str(1, "x");
    const t244: IsyStr(1) = isy_str(1, "x");
    const t245: i64 = m_5multi11141111(t241, t242, t243, t244);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t245));
    isy_out("\n");
    isy_tick(); // emit 54:5
    const t246: IsyStr(1) = isy_str(1, "x");
    const t247: IsyStr(4) = isy_str(4, "xxxx");
    const t248: IsyStr(1) = isy_str(1, "x");
    const t249: IsyStr(2) = isy_str(2, "xx");
    const t250: i64 = m_5multi11141112(t246, t247, t248, t249);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t250));
    isy_out("\n");
    isy_tick(); // emit 55:5
    const t251: IsyStr(1) = isy_str(1, "x");
    const t252: IsyStr(4) = isy_str(4, "xxxx");
    const t253: IsyStr(1) = isy_str(1, "x");
    const t254: IsyStr(3) = isy_str(3, "xxx");
    const t255: i64 = m_5multi11141113(t251, t252, t253, t254);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t255));
    isy_out("\n");
    isy_tick(); // emit 56:5
    const t256: IsyStr(1) = isy_str(1, "x");
    const t257: IsyStr(4) = isy_str(4, "xxxx");
    const t258: IsyStr(1) = isy_str(1, "x");
    const t259: IsyStr(4) = isy_str(4, "xxxx");
    const t260: i64 = m_5multi11141114(t256, t257, t258, t259);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t260));
    isy_out("\n");
    isy_tick(); // emit 57:5
    const t261: IsyStr(1) = isy_str(1, "x");
    const t262: IsyStr(4) = isy_str(4, "xxxx");
    const t263: IsyStr(2) = isy_str(2, "xx");
    const t264: IsyStr(1) = isy_str(1, "x");
    const t265: i64 = m_5multi11141211(t261, t262, t263, t264);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t265));
    isy_out("\n");
    isy_tick(); // emit 58:5
    const t266: IsyStr(1) = isy_str(1, "x");
    const t267: IsyStr(4) = isy_str(4, "xxxx");
    const t268: IsyStr(2) = isy_str(2, "xx");
    const t269: IsyStr(2) = isy_str(2, "xx");
    const t270: i64 = m_5multi11141212(t266, t267, t268, t269);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t270));
    isy_out("\n");
    isy_tick(); // emit 59:5
    const t271: IsyStr(1) = isy_str(1, "x");
    const t272: IsyStr(4) = isy_str(4, "xxxx");
    const t273: IsyStr(2) = isy_str(2, "xx");
    const t274: IsyStr(3) = isy_str(3, "xxx");
    const t275: i64 = m_5multi11141213(t271, t272, t273, t274);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t275));
    isy_out("\n");
    isy_tick(); // emit 60:5
    const t276: IsyStr(1) = isy_str(1, "x");
    const t277: IsyStr(4) = isy_str(4, "xxxx");
    const t278: IsyStr(2) = isy_str(2, "xx");
    const t279: IsyStr(4) = isy_str(4, "xxxx");
    const t280: i64 = m_5multi11141214(t276, t277, t278, t279);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t280));
    isy_out("\n");
    isy_tick(); // emit 61:5
    const t281: IsyStr(1) = isy_str(1, "x");
    const t282: IsyStr(4) = isy_str(4, "xxxx");
    const t283: IsyStr(3) = isy_str(3, "xxx");
    const t284: IsyStr(1) = isy_str(1, "x");
    const t285: i64 = m_5multi11141311(t281, t282, t283, t284);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t285));
    isy_out("\n");
    isy_tick(); // emit 62:5
    const t286: IsyStr(1) = isy_str(1, "x");
    const t287: IsyStr(4) = isy_str(4, "xxxx");
    const t288: IsyStr(3) = isy_str(3, "xxx");
    const t289: IsyStr(2) = isy_str(2, "xx");
    const t290: i64 = m_5multi11141312(t286, t287, t288, t289);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t290));
    isy_out("\n");
    isy_tick(); // emit 63:5
    const t291: IsyStr(1) = isy_str(1, "x");
    const t292: IsyStr(4) = isy_str(4, "xxxx");
    const t293: IsyStr(3) = isy_str(3, "xxx");
    const t294: IsyStr(3) = isy_str(3, "xxx");
    const t295: i64 = m_5multi11141313(t291, t292, t293, t294);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t295));
    isy_out("\n");
    isy_tick(); // emit 64:5
    const t296: IsyStr(1) = isy_str(1, "x");
    const t297: IsyStr(4) = isy_str(4, "xxxx");
    const t298: IsyStr(3) = isy_str(3, "xxx");
    const t299: IsyStr(4) = isy_str(4, "xxxx");
    const t300: i64 = m_5multi11141314(t296, t297, t298, t299);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t300));
    isy_out("\n");
    isy_tick(); // emit 65:5
    const t301: IsyStr(1) = isy_str(1, "x");
    const t302: IsyStr(4) = isy_str(4, "xxxx");
    const t303: IsyStr(4) = isy_str(4, "xxxx");
    const t304: IsyStr(1) = isy_str(1, "x");
    const t305: i64 = m_5multi11141411(t301, t302, t303, t304);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t305));
    isy_out("\n");
    isy_tick(); // emit 66:5
    const t306: IsyStr(1) = isy_str(1, "x");
    const t307: IsyStr(4) = isy_str(4, "xxxx");
    const t308: IsyStr(4) = isy_str(4, "xxxx");
    const t309: IsyStr(2) = isy_str(2, "xx");
    const t310: i64 = m_5multi11141412(t306, t307, t308, t309);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t310));
    isy_out("\n");
    isy_tick(); // emit 67:5
    const t311: IsyStr(1) = isy_str(1, "x");
    const t312: IsyStr(4) = isy_str(4, "xxxx");
    const t313: IsyStr(4) = isy_str(4, "xxxx");
    const t314: IsyStr(3) = isy_str(3, "xxx");
    const t315: i64 = m_5multi11141413(t311, t312, t313, t314);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t315));
    isy_out("\n");
    isy_tick(); // emit 68:5
    const t316: IsyStr(1) = isy_str(1, "x");
    const t317: IsyStr(4) = isy_str(4, "xxxx");
    const t318: IsyStr(4) = isy_str(4, "xxxx");
    const t319: IsyStr(4) = isy_str(4, "xxxx");
    const t320: i64 = m_5multi11141414(t316, t317, t318, t319);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t320));
    isy_out("\n");
    isy_tick(); // emit 69:5
    const t321: IsyStr(2) = isy_str(2, "xx");
    const t322: IsyStr(1) = isy_str(1, "x");
    const t323: IsyStr(1) = isy_str(1, "x");
    const t324: IsyStr(1) = isy_str(1, "x");
    const t325: i64 = m_5multi12111111(t321, t322, t323, t324);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t325));
    isy_out("\n");
    isy_tick(); // emit 70:5
    const t326: IsyStr(2) = isy_str(2, "xx");
    const t327: IsyStr(1) = isy_str(1, "x");
    const t328: IsyStr(1) = isy_str(1, "x");
    const t329: IsyStr(2) = isy_str(2, "xx");
    const t330: i64 = m_5multi12111112(t326, t327, t328, t329);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t330));
    isy_out("\n");
    isy_tick(); // emit 71:5
    const t331: IsyStr(2) = isy_str(2, "xx");
    const t332: IsyStr(1) = isy_str(1, "x");
    const t333: IsyStr(1) = isy_str(1, "x");
    const t334: IsyStr(3) = isy_str(3, "xxx");
    const t335: i64 = m_5multi12111113(t331, t332, t333, t334);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t335));
    isy_out("\n");
    isy_tick(); // emit 72:5
    const t336: IsyStr(2) = isy_str(2, "xx");
    const t337: IsyStr(1) = isy_str(1, "x");
    const t338: IsyStr(1) = isy_str(1, "x");
    const t339: IsyStr(4) = isy_str(4, "xxxx");
    const t340: i64 = m_5multi12111114(t336, t337, t338, t339);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t340));
    isy_out("\n");
    isy_tick(); // emit 73:5
    const t341: IsyStr(2) = isy_str(2, "xx");
    const t342: IsyStr(1) = isy_str(1, "x");
    const t343: IsyStr(2) = isy_str(2, "xx");
    const t344: IsyStr(1) = isy_str(1, "x");
    const t345: i64 = m_5multi12111211(t341, t342, t343, t344);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t345));
    isy_out("\n");
    isy_tick(); // emit 74:5
    const t346: IsyStr(2) = isy_str(2, "xx");
    const t347: IsyStr(1) = isy_str(1, "x");
    const t348: IsyStr(2) = isy_str(2, "xx");
    const t349: IsyStr(2) = isy_str(2, "xx");
    const t350: i64 = m_5multi12111212(t346, t347, t348, t349);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t350));
    isy_out("\n");
    isy_tick(); // emit 75:5
    const t351: IsyStr(2) = isy_str(2, "xx");
    const t352: IsyStr(1) = isy_str(1, "x");
    const t353: IsyStr(2) = isy_str(2, "xx");
    const t354: IsyStr(3) = isy_str(3, "xxx");
    const t355: i64 = m_5multi12111213(t351, t352, t353, t354);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t355));
    isy_out("\n");
    isy_tick(); // emit 76:5
    const t356: IsyStr(2) = isy_str(2, "xx");
    const t357: IsyStr(1) = isy_str(1, "x");
    const t358: IsyStr(2) = isy_str(2, "xx");
    const t359: IsyStr(4) = isy_str(4, "xxxx");
    const t360: i64 = m_5multi12111214(t356, t357, t358, t359);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t360));
    isy_out("\n");
    isy_tick(); // emit 77:5
    const t361: IsyStr(2) = isy_str(2, "xx");
    const t362: IsyStr(1) = isy_str(1, "x");
    const t363: IsyStr(3) = isy_str(3, "xxx");
    const t364: IsyStr(1) = isy_str(1, "x");
    const t365: i64 = m_5multi12111311(t361, t362, t363, t364);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t365));
    isy_out("\n");
    isy_tick(); // emit 78:5
    const t366: IsyStr(2) = isy_str(2, "xx");
    const t367: IsyStr(1) = isy_str(1, "x");
    const t368: IsyStr(3) = isy_str(3, "xxx");
    const t369: IsyStr(2) = isy_str(2, "xx");
    const t370: i64 = m_5multi12111312(t366, t367, t368, t369);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t370));
    isy_out("\n");
    isy_tick(); // emit 79:5
    const t371: IsyStr(2) = isy_str(2, "xx");
    const t372: IsyStr(1) = isy_str(1, "x");
    const t373: IsyStr(3) = isy_str(3, "xxx");
    const t374: IsyStr(3) = isy_str(3, "xxx");
    const t375: i64 = m_5multi12111313(t371, t372, t373, t374);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t375));
    isy_out("\n");
    isy_tick(); // emit 80:5
    const t376: IsyStr(2) = isy_str(2, "xx");
    const t377: IsyStr(1) = isy_str(1, "x");
    const t378: IsyStr(3) = isy_str(3, "xxx");
    const t379: IsyStr(4) = isy_str(4, "xxxx");
    const t380: i64 = m_5multi12111314(t376, t377, t378, t379);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t380));
    isy_out("\n");
    isy_tick(); // emit 81:5
    const t381: IsyStr(2) = isy_str(2, "xx");
    const t382: IsyStr(1) = isy_str(1, "x");
    const t383: IsyStr(4) = isy_str(4, "xxxx");
    const t384: IsyStr(1) = isy_str(1, "x");
    const t385: i64 = m_5multi12111411(t381, t382, t383, t384);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t385));
    isy_out("\n");
    isy_tick(); // emit 82:5
    const t386: IsyStr(2) = isy_str(2, "xx");
    const t387: IsyStr(1) = isy_str(1, "x");
    const t388: IsyStr(4) = isy_str(4, "xxxx");
    const t389: IsyStr(2) = isy_str(2, "xx");
    const t390: i64 = m_5multi12111412(t386, t387, t388, t389);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t390));
    isy_out("\n");
    isy_tick(); // emit 83:5
    const t391: IsyStr(2) = isy_str(2, "xx");
    const t392: IsyStr(1) = isy_str(1, "x");
    const t393: IsyStr(4) = isy_str(4, "xxxx");
    const t394: IsyStr(3) = isy_str(3, "xxx");
    const t395: i64 = m_5multi12111413(t391, t392, t393, t394);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t395));
    isy_out("\n");
    isy_tick(); // emit 84:5
    const t396: IsyStr(2) = isy_str(2, "xx");
    const t397: IsyStr(1) = isy_str(1, "x");
    const t398: IsyStr(4) = isy_str(4, "xxxx");
    const t399: IsyStr(4) = isy_str(4, "xxxx");
    const t400: i64 = m_5multi12111414(t396, t397, t398, t399);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t400));
    isy_out("\n");
    isy_tick(); // emit 85:5
    const t401: IsyStr(2) = isy_str(2, "xx");
    const t402: IsyStr(2) = isy_str(2, "xx");
    const t403: IsyStr(1) = isy_str(1, "x");
    const t404: IsyStr(1) = isy_str(1, "x");
    const t405: i64 = m_5multi12121111(t401, t402, t403, t404);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t405));
    isy_out("\n");
    isy_tick(); // emit 86:5
    const t406: IsyStr(2) = isy_str(2, "xx");
    const t407: IsyStr(2) = isy_str(2, "xx");
    const t408: IsyStr(1) = isy_str(1, "x");
    const t409: IsyStr(2) = isy_str(2, "xx");
    const t410: i64 = m_5multi12121112(t406, t407, t408, t409);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t410));
    isy_out("\n");
    isy_tick(); // emit 87:5
    const t411: IsyStr(2) = isy_str(2, "xx");
    const t412: IsyStr(2) = isy_str(2, "xx");
    const t413: IsyStr(1) = isy_str(1, "x");
    const t414: IsyStr(3) = isy_str(3, "xxx");
    const t415: i64 = m_5multi12121113(t411, t412, t413, t414);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t415));
    isy_out("\n");
    isy_tick(); // emit 88:5
    const t416: IsyStr(2) = isy_str(2, "xx");
    const t417: IsyStr(2) = isy_str(2, "xx");
    const t418: IsyStr(1) = isy_str(1, "x");
    const t419: IsyStr(4) = isy_str(4, "xxxx");
    const t420: i64 = m_5multi12121114(t416, t417, t418, t419);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t420));
    isy_out("\n");
    isy_tick(); // emit 89:5
    const t421: IsyStr(2) = isy_str(2, "xx");
    const t422: IsyStr(2) = isy_str(2, "xx");
    const t423: IsyStr(2) = isy_str(2, "xx");
    const t424: IsyStr(1) = isy_str(1, "x");
    const t425: i64 = m_5multi12121211(t421, t422, t423, t424);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t425));
    isy_out("\n");
    isy_tick(); // emit 90:5
    const t426: IsyStr(2) = isy_str(2, "xx");
    const t427: IsyStr(2) = isy_str(2, "xx");
    const t428: IsyStr(2) = isy_str(2, "xx");
    const t429: IsyStr(2) = isy_str(2, "xx");
    const t430: i64 = m_5multi12121212(t426, t427, t428, t429);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t430));
    isy_out("\n");
    isy_tick(); // emit 91:5
    const t431: IsyStr(2) = isy_str(2, "xx");
    const t432: IsyStr(2) = isy_str(2, "xx");
    const t433: IsyStr(2) = isy_str(2, "xx");
    const t434: IsyStr(3) = isy_str(3, "xxx");
    const t435: i64 = m_5multi12121213(t431, t432, t433, t434);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t435));
    isy_out("\n");
    isy_tick(); // emit 92:5
    const t436: IsyStr(2) = isy_str(2, "xx");
    const t437: IsyStr(2) = isy_str(2, "xx");
    const t438: IsyStr(2) = isy_str(2, "xx");
    const t439: IsyStr(4) = isy_str(4, "xxxx");
    const t440: i64 = m_5multi12121214(t436, t437, t438, t439);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t440));
    isy_out("\n");
    isy_tick(); // emit 93:5
    const t441: IsyStr(2) = isy_str(2, "xx");
    const t442: IsyStr(2) = isy_str(2, "xx");
    const t443: IsyStr(3) = isy_str(3, "xxx");
    const t444: IsyStr(1) = isy_str(1, "x");
    const t445: i64 = m_5multi12121311(t441, t442, t443, t444);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t445));
    isy_out("\n");
    isy_tick(); // emit 94:5
    const t446: IsyStr(2) = isy_str(2, "xx");
    const t447: IsyStr(2) = isy_str(2, "xx");
    const t448: IsyStr(3) = isy_str(3, "xxx");
    const t449: IsyStr(2) = isy_str(2, "xx");
    const t450: i64 = m_5multi12121312(t446, t447, t448, t449);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t450));
    isy_out("\n");
    isy_tick(); // emit 95:5
    const t451: IsyStr(2) = isy_str(2, "xx");
    const t452: IsyStr(2) = isy_str(2, "xx");
    const t453: IsyStr(3) = isy_str(3, "xxx");
    const t454: IsyStr(3) = isy_str(3, "xxx");
    const t455: i64 = m_5multi12121313(t451, t452, t453, t454);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t455));
    isy_out("\n");
    isy_tick(); // emit 96:5
    const t456: IsyStr(2) = isy_str(2, "xx");
    const t457: IsyStr(2) = isy_str(2, "xx");
    const t458: IsyStr(3) = isy_str(3, "xxx");
    const t459: IsyStr(4) = isy_str(4, "xxxx");
    const t460: i64 = m_5multi12121314(t456, t457, t458, t459);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t460));
    isy_out("\n");
    isy_tick(); // emit 97:5
    const t461: IsyStr(2) = isy_str(2, "xx");
    const t462: IsyStr(2) = isy_str(2, "xx");
    const t463: IsyStr(4) = isy_str(4, "xxxx");
    const t464: IsyStr(1) = isy_str(1, "x");
    const t465: i64 = m_5multi12121411(t461, t462, t463, t464);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t465));
    isy_out("\n");
    isy_tick(); // emit 98:5
    const t466: IsyStr(2) = isy_str(2, "xx");
    const t467: IsyStr(2) = isy_str(2, "xx");
    const t468: IsyStr(4) = isy_str(4, "xxxx");
    const t469: IsyStr(2) = isy_str(2, "xx");
    const t470: i64 = m_5multi12121412(t466, t467, t468, t469);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t470));
    isy_out("\n");
    isy_tick(); // emit 99:5
    const t471: IsyStr(2) = isy_str(2, "xx");
    const t472: IsyStr(2) = isy_str(2, "xx");
    const t473: IsyStr(4) = isy_str(4, "xxxx");
    const t474: IsyStr(3) = isy_str(3, "xxx");
    const t475: i64 = m_5multi12121413(t471, t472, t473, t474);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t475));
    isy_out("\n");
    isy_tick(); // emit 100:5
    const t476: IsyStr(2) = isy_str(2, "xx");
    const t477: IsyStr(2) = isy_str(2, "xx");
    const t478: IsyStr(4) = isy_str(4, "xxxx");
    const t479: IsyStr(4) = isy_str(4, "xxxx");
    const t480: i64 = m_5multi12121414(t476, t477, t478, t479);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t480));
    isy_out("\n");
    isy_tick(); // emit 101:5
    const t481: IsyStr(2) = isy_str(2, "xx");
    const t482: IsyStr(3) = isy_str(3, "xxx");
    const t483: IsyStr(1) = isy_str(1, "x");
    const t484: IsyStr(1) = isy_str(1, "x");
    const t485: i64 = m_5multi12131111(t481, t482, t483, t484);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t485));
    isy_out("\n");
    isy_tick(); // emit 102:5
    const t486: IsyStr(2) = isy_str(2, "xx");
    const t487: IsyStr(3) = isy_str(3, "xxx");
    const t488: IsyStr(1) = isy_str(1, "x");
    const t489: IsyStr(2) = isy_str(2, "xx");
    const t490: i64 = m_5multi12131112(t486, t487, t488, t489);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t490));
    isy_out("\n");
    isy_tick(); // emit 103:5
    const t491: IsyStr(2) = isy_str(2, "xx");
    const t492: IsyStr(3) = isy_str(3, "xxx");
    const t493: IsyStr(1) = isy_str(1, "x");
    const t494: IsyStr(3) = isy_str(3, "xxx");
    const t495: i64 = m_5multi12131113(t491, t492, t493, t494);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t495));
    isy_out("\n");
    isy_tick(); // emit 104:5
    const t496: IsyStr(2) = isy_str(2, "xx");
    const t497: IsyStr(3) = isy_str(3, "xxx");
    const t498: IsyStr(1) = isy_str(1, "x");
    const t499: IsyStr(4) = isy_str(4, "xxxx");
    const t500: i64 = m_5multi12131114(t496, t497, t498, t499);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t500));
    isy_out("\n");
    isy_tick(); // emit 105:5
    const t501: IsyStr(2) = isy_str(2, "xx");
    const t502: IsyStr(3) = isy_str(3, "xxx");
    const t503: IsyStr(2) = isy_str(2, "xx");
    const t504: IsyStr(1) = isy_str(1, "x");
    const t505: i64 = m_5multi12131211(t501, t502, t503, t504);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t505));
    isy_out("\n");
    isy_tick(); // emit 106:5
    const t506: IsyStr(2) = isy_str(2, "xx");
    const t507: IsyStr(3) = isy_str(3, "xxx");
    const t508: IsyStr(2) = isy_str(2, "xx");
    const t509: IsyStr(2) = isy_str(2, "xx");
    const t510: i64 = m_5multi12131212(t506, t507, t508, t509);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t510));
    isy_out("\n");
    isy_tick(); // emit 107:5
    const t511: IsyStr(2) = isy_str(2, "xx");
    const t512: IsyStr(3) = isy_str(3, "xxx");
    const t513: IsyStr(2) = isy_str(2, "xx");
    const t514: IsyStr(3) = isy_str(3, "xxx");
    const t515: i64 = m_5multi12131213(t511, t512, t513, t514);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t515));
    isy_out("\n");
    isy_tick(); // emit 108:5
    const t516: IsyStr(2) = isy_str(2, "xx");
    const t517: IsyStr(3) = isy_str(3, "xxx");
    const t518: IsyStr(2) = isy_str(2, "xx");
    const t519: IsyStr(4) = isy_str(4, "xxxx");
    const t520: i64 = m_5multi12131214(t516, t517, t518, t519);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t520));
    isy_out("\n");
    isy_tick(); // emit 109:5
    const t521: IsyStr(2) = isy_str(2, "xx");
    const t522: IsyStr(3) = isy_str(3, "xxx");
    const t523: IsyStr(3) = isy_str(3, "xxx");
    const t524: IsyStr(1) = isy_str(1, "x");
    const t525: i64 = m_5multi12131311(t521, t522, t523, t524);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t525));
    isy_out("\n");
    isy_tick(); // emit 110:5
    const t526: IsyStr(2) = isy_str(2, "xx");
    const t527: IsyStr(3) = isy_str(3, "xxx");
    const t528: IsyStr(3) = isy_str(3, "xxx");
    const t529: IsyStr(2) = isy_str(2, "xx");
    const t530: i64 = m_5multi12131312(t526, t527, t528, t529);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t530));
    isy_out("\n");
    isy_tick(); // emit 111:5
    const t531: IsyStr(2) = isy_str(2, "xx");
    const t532: IsyStr(3) = isy_str(3, "xxx");
    const t533: IsyStr(3) = isy_str(3, "xxx");
    const t534: IsyStr(3) = isy_str(3, "xxx");
    const t535: i64 = m_5multi12131313(t531, t532, t533, t534);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t535));
    isy_out("\n");
    isy_tick(); // emit 112:5
    const t536: IsyStr(2) = isy_str(2, "xx");
    const t537: IsyStr(3) = isy_str(3, "xxx");
    const t538: IsyStr(3) = isy_str(3, "xxx");
    const t539: IsyStr(4) = isy_str(4, "xxxx");
    const t540: i64 = m_5multi12131314(t536, t537, t538, t539);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t540));
    isy_out("\n");
    isy_tick(); // emit 113:5
    const t541: IsyStr(2) = isy_str(2, "xx");
    const t542: IsyStr(3) = isy_str(3, "xxx");
    const t543: IsyStr(4) = isy_str(4, "xxxx");
    const t544: IsyStr(1) = isy_str(1, "x");
    const t545: i64 = m_5multi12131411(t541, t542, t543, t544);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t545));
    isy_out("\n");
    isy_tick(); // emit 114:5
    const t546: IsyStr(2) = isy_str(2, "xx");
    const t547: IsyStr(3) = isy_str(3, "xxx");
    const t548: IsyStr(4) = isy_str(4, "xxxx");
    const t549: IsyStr(2) = isy_str(2, "xx");
    const t550: i64 = m_5multi12131412(t546, t547, t548, t549);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t550));
    isy_out("\n");
    isy_tick(); // emit 115:5
    const t551: IsyStr(2) = isy_str(2, "xx");
    const t552: IsyStr(3) = isy_str(3, "xxx");
    const t553: IsyStr(4) = isy_str(4, "xxxx");
    const t554: IsyStr(3) = isy_str(3, "xxx");
    const t555: i64 = m_5multi12131413(t551, t552, t553, t554);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t555));
    isy_out("\n");
    isy_tick(); // emit 116:5
    const t556: IsyStr(2) = isy_str(2, "xx");
    const t557: IsyStr(3) = isy_str(3, "xxx");
    const t558: IsyStr(4) = isy_str(4, "xxxx");
    const t559: IsyStr(4) = isy_str(4, "xxxx");
    const t560: i64 = m_5multi12131414(t556, t557, t558, t559);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t560));
    isy_out("\n");
    isy_tick(); // emit 117:5
    const t561: IsyStr(2) = isy_str(2, "xx");
    const t562: IsyStr(4) = isy_str(4, "xxxx");
    const t563: IsyStr(1) = isy_str(1, "x");
    const t564: IsyStr(1) = isy_str(1, "x");
    const t565: i64 = m_5multi12141111(t561, t562, t563, t564);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t565));
    isy_out("\n");
    isy_tick(); // emit 118:5
    const t566: IsyStr(2) = isy_str(2, "xx");
    const t567: IsyStr(4) = isy_str(4, "xxxx");
    const t568: IsyStr(1) = isy_str(1, "x");
    const t569: IsyStr(2) = isy_str(2, "xx");
    const t570: i64 = m_5multi12141112(t566, t567, t568, t569);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t570));
    isy_out("\n");
    isy_tick(); // emit 119:5
    const t571: IsyStr(2) = isy_str(2, "xx");
    const t572: IsyStr(4) = isy_str(4, "xxxx");
    const t573: IsyStr(1) = isy_str(1, "x");
    const t574: IsyStr(3) = isy_str(3, "xxx");
    const t575: i64 = m_5multi12141113(t571, t572, t573, t574);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t575));
    isy_out("\n");
    isy_tick(); // emit 120:5
    const t576: IsyStr(2) = isy_str(2, "xx");
    const t577: IsyStr(4) = isy_str(4, "xxxx");
    const t578: IsyStr(1) = isy_str(1, "x");
    const t579: IsyStr(4) = isy_str(4, "xxxx");
    const t580: i64 = m_5multi12141114(t576, t577, t578, t579);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t580));
    isy_out("\n");
    isy_tick(); // emit 121:5
    const t581: IsyStr(2) = isy_str(2, "xx");
    const t582: IsyStr(4) = isy_str(4, "xxxx");
    const t583: IsyStr(2) = isy_str(2, "xx");
    const t584: IsyStr(1) = isy_str(1, "x");
    const t585: i64 = m_5multi12141211(t581, t582, t583, t584);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t585));
    isy_out("\n");
    isy_tick(); // emit 122:5
    const t586: IsyStr(2) = isy_str(2, "xx");
    const t587: IsyStr(4) = isy_str(4, "xxxx");
    const t588: IsyStr(2) = isy_str(2, "xx");
    const t589: IsyStr(2) = isy_str(2, "xx");
    const t590: i64 = m_5multi12141212(t586, t587, t588, t589);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t590));
    isy_out("\n");
    isy_tick(); // emit 123:5
    const t591: IsyStr(2) = isy_str(2, "xx");
    const t592: IsyStr(4) = isy_str(4, "xxxx");
    const t593: IsyStr(2) = isy_str(2, "xx");
    const t594: IsyStr(3) = isy_str(3, "xxx");
    const t595: i64 = m_5multi12141213(t591, t592, t593, t594);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t595));
    isy_out("\n");
    isy_tick(); // emit 124:5
    const t596: IsyStr(2) = isy_str(2, "xx");
    const t597: IsyStr(4) = isy_str(4, "xxxx");
    const t598: IsyStr(2) = isy_str(2, "xx");
    const t599: IsyStr(4) = isy_str(4, "xxxx");
    const t600: i64 = m_5multi12141214(t596, t597, t598, t599);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t600));
    isy_out("\n");
    isy_tick(); // emit 125:5
    const t601: IsyStr(2) = isy_str(2, "xx");
    const t602: IsyStr(4) = isy_str(4, "xxxx");
    const t603: IsyStr(3) = isy_str(3, "xxx");
    const t604: IsyStr(1) = isy_str(1, "x");
    const t605: i64 = m_5multi12141311(t601, t602, t603, t604);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t605));
    isy_out("\n");
    isy_tick(); // emit 126:5
    const t606: IsyStr(2) = isy_str(2, "xx");
    const t607: IsyStr(4) = isy_str(4, "xxxx");
    const t608: IsyStr(3) = isy_str(3, "xxx");
    const t609: IsyStr(2) = isy_str(2, "xx");
    const t610: i64 = m_5multi12141312(t606, t607, t608, t609);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t610));
    isy_out("\n");
    isy_tick(); // emit 127:5
    const t611: IsyStr(2) = isy_str(2, "xx");
    const t612: IsyStr(4) = isy_str(4, "xxxx");
    const t613: IsyStr(3) = isy_str(3, "xxx");
    const t614: IsyStr(3) = isy_str(3, "xxx");
    const t615: i64 = m_5multi12141313(t611, t612, t613, t614);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t615));
    isy_out("\n");
    isy_tick(); // emit 128:5
    const t616: IsyStr(2) = isy_str(2, "xx");
    const t617: IsyStr(4) = isy_str(4, "xxxx");
    const t618: IsyStr(3) = isy_str(3, "xxx");
    const t619: IsyStr(4) = isy_str(4, "xxxx");
    const t620: i64 = m_5multi12141314(t616, t617, t618, t619);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t620));
    isy_out("\n");
    isy_tick(); // emit 129:5
    const t621: IsyStr(2) = isy_str(2, "xx");
    const t622: IsyStr(4) = isy_str(4, "xxxx");
    const t623: IsyStr(4) = isy_str(4, "xxxx");
    const t624: IsyStr(1) = isy_str(1, "x");
    const t625: i64 = m_5multi12141411(t621, t622, t623, t624);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t625));
    isy_out("\n");
    isy_tick(); // emit 130:5
    const t626: IsyStr(2) = isy_str(2, "xx");
    const t627: IsyStr(4) = isy_str(4, "xxxx");
    const t628: IsyStr(4) = isy_str(4, "xxxx");
    const t629: IsyStr(2) = isy_str(2, "xx");
    const t630: i64 = m_5multi12141412(t626, t627, t628, t629);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t630));
    isy_out("\n");
    isy_tick(); // emit 131:5
    const t631: IsyStr(2) = isy_str(2, "xx");
    const t632: IsyStr(4) = isy_str(4, "xxxx");
    const t633: IsyStr(4) = isy_str(4, "xxxx");
    const t634: IsyStr(3) = isy_str(3, "xxx");
    const t635: i64 = m_5multi12141413(t631, t632, t633, t634);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t635));
    isy_out("\n");
    isy_tick(); // emit 132:5
    const t636: IsyStr(2) = isy_str(2, "xx");
    const t637: IsyStr(4) = isy_str(4, "xxxx");
    const t638: IsyStr(4) = isy_str(4, "xxxx");
    const t639: IsyStr(4) = isy_str(4, "xxxx");
    const t640: i64 = m_5multi12141414(t636, t637, t638, t639);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t640));
    isy_out("\n");
    isy_tick(); // emit 133:5
    const t641: IsyStr(3) = isy_str(3, "xxx");
    const t642: IsyStr(1) = isy_str(1, "x");
    const t643: IsyStr(1) = isy_str(1, "x");
    const t644: IsyStr(1) = isy_str(1, "x");
    const t645: i64 = m_5multi13111111(t641, t642, t643, t644);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t645));
    isy_out("\n");
    isy_tick(); // emit 134:5
    const t646: IsyStr(3) = isy_str(3, "xxx");
    const t647: IsyStr(1) = isy_str(1, "x");
    const t648: IsyStr(1) = isy_str(1, "x");
    const t649: IsyStr(2) = isy_str(2, "xx");
    const t650: i64 = m_5multi13111112(t646, t647, t648, t649);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t650));
    isy_out("\n");
    isy_tick(); // emit 135:5
    const t651: IsyStr(3) = isy_str(3, "xxx");
    const t652: IsyStr(1) = isy_str(1, "x");
    const t653: IsyStr(1) = isy_str(1, "x");
    const t654: IsyStr(3) = isy_str(3, "xxx");
    const t655: i64 = m_5multi13111113(t651, t652, t653, t654);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t655));
    isy_out("\n");
    isy_tick(); // emit 136:5
    const t656: IsyStr(3) = isy_str(3, "xxx");
    const t657: IsyStr(1) = isy_str(1, "x");
    const t658: IsyStr(1) = isy_str(1, "x");
    const t659: IsyStr(4) = isy_str(4, "xxxx");
    const t660: i64 = m_5multi13111114(t656, t657, t658, t659);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t660));
    isy_out("\n");
    isy_tick(); // emit 137:5
    const t661: IsyStr(3) = isy_str(3, "xxx");
    const t662: IsyStr(1) = isy_str(1, "x");
    const t663: IsyStr(2) = isy_str(2, "xx");
    const t664: IsyStr(1) = isy_str(1, "x");
    const t665: i64 = m_5multi13111211(t661, t662, t663, t664);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t665));
    isy_out("\n");
    isy_tick(); // emit 138:5
    const t666: IsyStr(3) = isy_str(3, "xxx");
    const t667: IsyStr(1) = isy_str(1, "x");
    const t668: IsyStr(2) = isy_str(2, "xx");
    const t669: IsyStr(2) = isy_str(2, "xx");
    const t670: i64 = m_5multi13111212(t666, t667, t668, t669);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t670));
    isy_out("\n");
    isy_tick(); // emit 139:5
    const t671: IsyStr(3) = isy_str(3, "xxx");
    const t672: IsyStr(1) = isy_str(1, "x");
    const t673: IsyStr(2) = isy_str(2, "xx");
    const t674: IsyStr(3) = isy_str(3, "xxx");
    const t675: i64 = m_5multi13111213(t671, t672, t673, t674);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t675));
    isy_out("\n");
    isy_tick(); // emit 140:5
    const t676: IsyStr(3) = isy_str(3, "xxx");
    const t677: IsyStr(1) = isy_str(1, "x");
    const t678: IsyStr(2) = isy_str(2, "xx");
    const t679: IsyStr(4) = isy_str(4, "xxxx");
    const t680: i64 = m_5multi13111214(t676, t677, t678, t679);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t680));
    isy_out("\n");
    isy_tick(); // emit 141:5
    const t681: IsyStr(3) = isy_str(3, "xxx");
    const t682: IsyStr(1) = isy_str(1, "x");
    const t683: IsyStr(3) = isy_str(3, "xxx");
    const t684: IsyStr(1) = isy_str(1, "x");
    const t685: i64 = m_5multi13111311(t681, t682, t683, t684);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t685));
    isy_out("\n");
    isy_tick(); // emit 142:5
    const t686: IsyStr(3) = isy_str(3, "xxx");
    const t687: IsyStr(1) = isy_str(1, "x");
    const t688: IsyStr(3) = isy_str(3, "xxx");
    const t689: IsyStr(2) = isy_str(2, "xx");
    const t690: i64 = m_5multi13111312(t686, t687, t688, t689);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t690));
    isy_out("\n");
    isy_tick(); // emit 143:5
    const t691: IsyStr(3) = isy_str(3, "xxx");
    const t692: IsyStr(1) = isy_str(1, "x");
    const t693: IsyStr(3) = isy_str(3, "xxx");
    const t694: IsyStr(3) = isy_str(3, "xxx");
    const t695: i64 = m_5multi13111313(t691, t692, t693, t694);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t695));
    isy_out("\n");
    isy_tick(); // emit 144:5
    const t696: IsyStr(3) = isy_str(3, "xxx");
    const t697: IsyStr(1) = isy_str(1, "x");
    const t698: IsyStr(3) = isy_str(3, "xxx");
    const t699: IsyStr(4) = isy_str(4, "xxxx");
    const t700: i64 = m_5multi13111314(t696, t697, t698, t699);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t700));
    isy_out("\n");
    isy_tick(); // emit 145:5
    const t701: IsyStr(3) = isy_str(3, "xxx");
    const t702: IsyStr(1) = isy_str(1, "x");
    const t703: IsyStr(4) = isy_str(4, "xxxx");
    const t704: IsyStr(1) = isy_str(1, "x");
    const t705: i64 = m_5multi13111411(t701, t702, t703, t704);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t705));
    isy_out("\n");
    isy_tick(); // emit 146:5
    const t706: IsyStr(3) = isy_str(3, "xxx");
    const t707: IsyStr(1) = isy_str(1, "x");
    const t708: IsyStr(4) = isy_str(4, "xxxx");
    const t709: IsyStr(2) = isy_str(2, "xx");
    const t710: i64 = m_5multi13111412(t706, t707, t708, t709);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t710));
    isy_out("\n");
    isy_tick(); // emit 147:5
    const t711: IsyStr(3) = isy_str(3, "xxx");
    const t712: IsyStr(1) = isy_str(1, "x");
    const t713: IsyStr(4) = isy_str(4, "xxxx");
    const t714: IsyStr(3) = isy_str(3, "xxx");
    const t715: i64 = m_5multi13111413(t711, t712, t713, t714);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t715));
    isy_out("\n");
    isy_tick(); // emit 148:5
    const t716: IsyStr(3) = isy_str(3, "xxx");
    const t717: IsyStr(1) = isy_str(1, "x");
    const t718: IsyStr(4) = isy_str(4, "xxxx");
    const t719: IsyStr(4) = isy_str(4, "xxxx");
    const t720: i64 = m_5multi13111414(t716, t717, t718, t719);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t720));
    isy_out("\n");
    isy_tick(); // emit 149:5
    const t721: IsyStr(3) = isy_str(3, "xxx");
    const t722: IsyStr(2) = isy_str(2, "xx");
    const t723: IsyStr(1) = isy_str(1, "x");
    const t724: IsyStr(1) = isy_str(1, "x");
    const t725: i64 = m_5multi13121111(t721, t722, t723, t724);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t725));
    isy_out("\n");
    isy_tick(); // emit 150:5
    const t726: IsyStr(3) = isy_str(3, "xxx");
    const t727: IsyStr(2) = isy_str(2, "xx");
    const t728: IsyStr(1) = isy_str(1, "x");
    const t729: IsyStr(2) = isy_str(2, "xx");
    const t730: i64 = m_5multi13121112(t726, t727, t728, t729);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t730));
    isy_out("\n");
    isy_tick(); // emit 151:5
    const t731: IsyStr(3) = isy_str(3, "xxx");
    const t732: IsyStr(2) = isy_str(2, "xx");
    const t733: IsyStr(1) = isy_str(1, "x");
    const t734: IsyStr(3) = isy_str(3, "xxx");
    const t735: i64 = m_5multi13121113(t731, t732, t733, t734);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t735));
    isy_out("\n");
    isy_tick(); // emit 152:5
    const t736: IsyStr(3) = isy_str(3, "xxx");
    const t737: IsyStr(2) = isy_str(2, "xx");
    const t738: IsyStr(1) = isy_str(1, "x");
    const t739: IsyStr(4) = isy_str(4, "xxxx");
    const t740: i64 = m_5multi13121114(t736, t737, t738, t739);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t740));
    isy_out("\n");
    isy_tick(); // emit 153:5
    const t741: IsyStr(3) = isy_str(3, "xxx");
    const t742: IsyStr(2) = isy_str(2, "xx");
    const t743: IsyStr(2) = isy_str(2, "xx");
    const t744: IsyStr(1) = isy_str(1, "x");
    const t745: i64 = m_5multi13121211(t741, t742, t743, t744);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t745));
    isy_out("\n");
    isy_tick(); // emit 154:5
    const t746: IsyStr(3) = isy_str(3, "xxx");
    const t747: IsyStr(2) = isy_str(2, "xx");
    const t748: IsyStr(2) = isy_str(2, "xx");
    const t749: IsyStr(2) = isy_str(2, "xx");
    const t750: i64 = m_5multi13121212(t746, t747, t748, t749);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t750));
    isy_out("\n");
    isy_tick(); // emit 155:5
    const t751: IsyStr(3) = isy_str(3, "xxx");
    const t752: IsyStr(2) = isy_str(2, "xx");
    const t753: IsyStr(2) = isy_str(2, "xx");
    const t754: IsyStr(3) = isy_str(3, "xxx");
    const t755: i64 = m_5multi13121213(t751, t752, t753, t754);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t755));
    isy_out("\n");
    isy_tick(); // emit 156:5
    const t756: IsyStr(3) = isy_str(3, "xxx");
    const t757: IsyStr(2) = isy_str(2, "xx");
    const t758: IsyStr(2) = isy_str(2, "xx");
    const t759: IsyStr(4) = isy_str(4, "xxxx");
    const t760: i64 = m_5multi13121214(t756, t757, t758, t759);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t760));
    isy_out("\n");
    isy_tick(); // emit 157:5
    const t761: IsyStr(3) = isy_str(3, "xxx");
    const t762: IsyStr(2) = isy_str(2, "xx");
    const t763: IsyStr(3) = isy_str(3, "xxx");
    const t764: IsyStr(1) = isy_str(1, "x");
    const t765: i64 = m_5multi13121311(t761, t762, t763, t764);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t765));
    isy_out("\n");
    isy_tick(); // emit 158:5
    const t766: IsyStr(3) = isy_str(3, "xxx");
    const t767: IsyStr(2) = isy_str(2, "xx");
    const t768: IsyStr(3) = isy_str(3, "xxx");
    const t769: IsyStr(2) = isy_str(2, "xx");
    const t770: i64 = m_5multi13121312(t766, t767, t768, t769);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t770));
    isy_out("\n");
    isy_tick(); // emit 159:5
    const t771: IsyStr(3) = isy_str(3, "xxx");
    const t772: IsyStr(2) = isy_str(2, "xx");
    const t773: IsyStr(3) = isy_str(3, "xxx");
    const t774: IsyStr(3) = isy_str(3, "xxx");
    const t775: i64 = m_5multi13121313(t771, t772, t773, t774);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t775));
    isy_out("\n");
    isy_tick(); // emit 160:5
    const t776: IsyStr(3) = isy_str(3, "xxx");
    const t777: IsyStr(2) = isy_str(2, "xx");
    const t778: IsyStr(3) = isy_str(3, "xxx");
    const t779: IsyStr(4) = isy_str(4, "xxxx");
    const t780: i64 = m_5multi13121314(t776, t777, t778, t779);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t780));
    isy_out("\n");
    isy_tick(); // emit 161:5
    const t781: IsyStr(3) = isy_str(3, "xxx");
    const t782: IsyStr(2) = isy_str(2, "xx");
    const t783: IsyStr(4) = isy_str(4, "xxxx");
    const t784: IsyStr(1) = isy_str(1, "x");
    const t785: i64 = m_5multi13121411(t781, t782, t783, t784);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t785));
    isy_out("\n");
    isy_tick(); // emit 162:5
    const t786: IsyStr(3) = isy_str(3, "xxx");
    const t787: IsyStr(2) = isy_str(2, "xx");
    const t788: IsyStr(4) = isy_str(4, "xxxx");
    const t789: IsyStr(2) = isy_str(2, "xx");
    const t790: i64 = m_5multi13121412(t786, t787, t788, t789);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t790));
    isy_out("\n");
    isy_tick(); // emit 163:5
    const t791: IsyStr(3) = isy_str(3, "xxx");
    const t792: IsyStr(2) = isy_str(2, "xx");
    const t793: IsyStr(4) = isy_str(4, "xxxx");
    const t794: IsyStr(3) = isy_str(3, "xxx");
    const t795: i64 = m_5multi13121413(t791, t792, t793, t794);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t795));
    isy_out("\n");
    isy_tick(); // emit 164:5
    const t796: IsyStr(3) = isy_str(3, "xxx");
    const t797: IsyStr(2) = isy_str(2, "xx");
    const t798: IsyStr(4) = isy_str(4, "xxxx");
    const t799: IsyStr(4) = isy_str(4, "xxxx");
    const t800: i64 = m_5multi13121414(t796, t797, t798, t799);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t800));
    isy_out("\n");
    isy_tick(); // emit 165:5
    const t801: IsyStr(3) = isy_str(3, "xxx");
    const t802: IsyStr(3) = isy_str(3, "xxx");
    const t803: IsyStr(1) = isy_str(1, "x");
    const t804: IsyStr(1) = isy_str(1, "x");
    const t805: i64 = m_5multi13131111(t801, t802, t803, t804);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t805));
    isy_out("\n");
    isy_tick(); // emit 166:5
    const t806: IsyStr(3) = isy_str(3, "xxx");
    const t807: IsyStr(3) = isy_str(3, "xxx");
    const t808: IsyStr(1) = isy_str(1, "x");
    const t809: IsyStr(2) = isy_str(2, "xx");
    const t810: i64 = m_5multi13131112(t806, t807, t808, t809);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t810));
    isy_out("\n");
    isy_tick(); // emit 167:5
    const t811: IsyStr(3) = isy_str(3, "xxx");
    const t812: IsyStr(3) = isy_str(3, "xxx");
    const t813: IsyStr(1) = isy_str(1, "x");
    const t814: IsyStr(3) = isy_str(3, "xxx");
    const t815: i64 = m_5multi13131113(t811, t812, t813, t814);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t815));
    isy_out("\n");
    isy_tick(); // emit 168:5
    const t816: IsyStr(3) = isy_str(3, "xxx");
    const t817: IsyStr(3) = isy_str(3, "xxx");
    const t818: IsyStr(1) = isy_str(1, "x");
    const t819: IsyStr(4) = isy_str(4, "xxxx");
    const t820: i64 = m_5multi13131114(t816, t817, t818, t819);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t820));
    isy_out("\n");
    isy_tick(); // emit 169:5
    const t821: IsyStr(3) = isy_str(3, "xxx");
    const t822: IsyStr(3) = isy_str(3, "xxx");
    const t823: IsyStr(2) = isy_str(2, "xx");
    const t824: IsyStr(1) = isy_str(1, "x");
    const t825: i64 = m_5multi13131211(t821, t822, t823, t824);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t825));
    isy_out("\n");
    isy_tick(); // emit 170:5
    const t826: IsyStr(3) = isy_str(3, "xxx");
    const t827: IsyStr(3) = isy_str(3, "xxx");
    const t828: IsyStr(2) = isy_str(2, "xx");
    const t829: IsyStr(2) = isy_str(2, "xx");
    const t830: i64 = m_5multi13131212(t826, t827, t828, t829);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t830));
    isy_out("\n");
    isy_tick(); // emit 171:5
    const t831: IsyStr(3) = isy_str(3, "xxx");
    const t832: IsyStr(3) = isy_str(3, "xxx");
    const t833: IsyStr(2) = isy_str(2, "xx");
    const t834: IsyStr(3) = isy_str(3, "xxx");
    const t835: i64 = m_5multi13131213(t831, t832, t833, t834);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t835));
    isy_out("\n");
    isy_tick(); // emit 172:5
    const t836: IsyStr(3) = isy_str(3, "xxx");
    const t837: IsyStr(3) = isy_str(3, "xxx");
    const t838: IsyStr(2) = isy_str(2, "xx");
    const t839: IsyStr(4) = isy_str(4, "xxxx");
    const t840: i64 = m_5multi13131214(t836, t837, t838, t839);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t840));
    isy_out("\n");
    isy_tick(); // emit 173:5
    const t841: IsyStr(3) = isy_str(3, "xxx");
    const t842: IsyStr(3) = isy_str(3, "xxx");
    const t843: IsyStr(3) = isy_str(3, "xxx");
    const t844: IsyStr(1) = isy_str(1, "x");
    const t845: i64 = m_5multi13131311(t841, t842, t843, t844);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t845));
    isy_out("\n");
    isy_tick(); // emit 174:5
    const t846: IsyStr(3) = isy_str(3, "xxx");
    const t847: IsyStr(3) = isy_str(3, "xxx");
    const t848: IsyStr(3) = isy_str(3, "xxx");
    const t849: IsyStr(2) = isy_str(2, "xx");
    const t850: i64 = m_5multi13131312(t846, t847, t848, t849);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t850));
    isy_out("\n");
    isy_tick(); // emit 175:5
    const t851: IsyStr(3) = isy_str(3, "xxx");
    const t852: IsyStr(3) = isy_str(3, "xxx");
    const t853: IsyStr(3) = isy_str(3, "xxx");
    const t854: IsyStr(3) = isy_str(3, "xxx");
    const t855: i64 = m_5multi13131313(t851, t852, t853, t854);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t855));
    isy_out("\n");
    isy_tick(); // emit 176:5
    const t856: IsyStr(3) = isy_str(3, "xxx");
    const t857: IsyStr(3) = isy_str(3, "xxx");
    const t858: IsyStr(3) = isy_str(3, "xxx");
    const t859: IsyStr(4) = isy_str(4, "xxxx");
    const t860: i64 = m_5multi13131314(t856, t857, t858, t859);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t860));
    isy_out("\n");
    isy_tick(); // emit 177:5
    const t861: IsyStr(3) = isy_str(3, "xxx");
    const t862: IsyStr(3) = isy_str(3, "xxx");
    const t863: IsyStr(4) = isy_str(4, "xxxx");
    const t864: IsyStr(1) = isy_str(1, "x");
    const t865: i64 = m_5multi13131411(t861, t862, t863, t864);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t865));
    isy_out("\n");
    isy_tick(); // emit 178:5
    const t866: IsyStr(3) = isy_str(3, "xxx");
    const t867: IsyStr(3) = isy_str(3, "xxx");
    const t868: IsyStr(4) = isy_str(4, "xxxx");
    const t869: IsyStr(2) = isy_str(2, "xx");
    const t870: i64 = m_5multi13131412(t866, t867, t868, t869);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t870));
    isy_out("\n");
    isy_tick(); // emit 179:5
    const t871: IsyStr(3) = isy_str(3, "xxx");
    const t872: IsyStr(3) = isy_str(3, "xxx");
    const t873: IsyStr(4) = isy_str(4, "xxxx");
    const t874: IsyStr(3) = isy_str(3, "xxx");
    const t875: i64 = m_5multi13131413(t871, t872, t873, t874);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t875));
    isy_out("\n");
    isy_tick(); // emit 180:5
    const t876: IsyStr(3) = isy_str(3, "xxx");
    const t877: IsyStr(3) = isy_str(3, "xxx");
    const t878: IsyStr(4) = isy_str(4, "xxxx");
    const t879: IsyStr(4) = isy_str(4, "xxxx");
    const t880: i64 = m_5multi13131414(t876, t877, t878, t879);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t880));
    isy_out("\n");
    isy_tick(); // emit 181:5
    const t881: IsyStr(3) = isy_str(3, "xxx");
    const t882: IsyStr(4) = isy_str(4, "xxxx");
    const t883: IsyStr(1) = isy_str(1, "x");
    const t884: IsyStr(1) = isy_str(1, "x");
    const t885: i64 = m_5multi13141111(t881, t882, t883, t884);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t885));
    isy_out("\n");
    isy_tick(); // emit 182:5
    const t886: IsyStr(3) = isy_str(3, "xxx");
    const t887: IsyStr(4) = isy_str(4, "xxxx");
    const t888: IsyStr(1) = isy_str(1, "x");
    const t889: IsyStr(2) = isy_str(2, "xx");
    const t890: i64 = m_5multi13141112(t886, t887, t888, t889);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t890));
    isy_out("\n");
    isy_tick(); // emit 183:5
    const t891: IsyStr(3) = isy_str(3, "xxx");
    const t892: IsyStr(4) = isy_str(4, "xxxx");
    const t893: IsyStr(1) = isy_str(1, "x");
    const t894: IsyStr(3) = isy_str(3, "xxx");
    const t895: i64 = m_5multi13141113(t891, t892, t893, t894);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t895));
    isy_out("\n");
    isy_tick(); // emit 184:5
    const t896: IsyStr(3) = isy_str(3, "xxx");
    const t897: IsyStr(4) = isy_str(4, "xxxx");
    const t898: IsyStr(1) = isy_str(1, "x");
    const t899: IsyStr(4) = isy_str(4, "xxxx");
    const t900: i64 = m_5multi13141114(t896, t897, t898, t899);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t900));
    isy_out("\n");
    isy_tick(); // emit 185:5
    const t901: IsyStr(3) = isy_str(3, "xxx");
    const t902: IsyStr(4) = isy_str(4, "xxxx");
    const t903: IsyStr(2) = isy_str(2, "xx");
    const t904: IsyStr(1) = isy_str(1, "x");
    const t905: i64 = m_5multi13141211(t901, t902, t903, t904);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t905));
    isy_out("\n");
    isy_tick(); // emit 186:5
    const t906: IsyStr(3) = isy_str(3, "xxx");
    const t907: IsyStr(4) = isy_str(4, "xxxx");
    const t908: IsyStr(2) = isy_str(2, "xx");
    const t909: IsyStr(2) = isy_str(2, "xx");
    const t910: i64 = m_5multi13141212(t906, t907, t908, t909);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t910));
    isy_out("\n");
    isy_tick(); // emit 187:5
    const t911: IsyStr(3) = isy_str(3, "xxx");
    const t912: IsyStr(4) = isy_str(4, "xxxx");
    const t913: IsyStr(2) = isy_str(2, "xx");
    const t914: IsyStr(3) = isy_str(3, "xxx");
    const t915: i64 = m_5multi13141213(t911, t912, t913, t914);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t915));
    isy_out("\n");
    isy_tick(); // emit 188:5
    const t916: IsyStr(3) = isy_str(3, "xxx");
    const t917: IsyStr(4) = isy_str(4, "xxxx");
    const t918: IsyStr(2) = isy_str(2, "xx");
    const t919: IsyStr(4) = isy_str(4, "xxxx");
    const t920: i64 = m_5multi13141214(t916, t917, t918, t919);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t920));
    isy_out("\n");
    isy_tick(); // emit 189:5
    const t921: IsyStr(3) = isy_str(3, "xxx");
    const t922: IsyStr(4) = isy_str(4, "xxxx");
    const t923: IsyStr(3) = isy_str(3, "xxx");
    const t924: IsyStr(1) = isy_str(1, "x");
    const t925: i64 = m_5multi13141311(t921, t922, t923, t924);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t925));
    isy_out("\n");
    isy_tick(); // emit 190:5
    const t926: IsyStr(3) = isy_str(3, "xxx");
    const t927: IsyStr(4) = isy_str(4, "xxxx");
    const t928: IsyStr(3) = isy_str(3, "xxx");
    const t929: IsyStr(2) = isy_str(2, "xx");
    const t930: i64 = m_5multi13141312(t926, t927, t928, t929);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t930));
    isy_out("\n");
    isy_tick(); // emit 191:5
    const t931: IsyStr(3) = isy_str(3, "xxx");
    const t932: IsyStr(4) = isy_str(4, "xxxx");
    const t933: IsyStr(3) = isy_str(3, "xxx");
    const t934: IsyStr(3) = isy_str(3, "xxx");
    const t935: i64 = m_5multi13141313(t931, t932, t933, t934);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t935));
    isy_out("\n");
    isy_tick(); // emit 192:5
    const t936: IsyStr(3) = isy_str(3, "xxx");
    const t937: IsyStr(4) = isy_str(4, "xxxx");
    const t938: IsyStr(3) = isy_str(3, "xxx");
    const t939: IsyStr(4) = isy_str(4, "xxxx");
    const t940: i64 = m_5multi13141314(t936, t937, t938, t939);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t940));
    isy_out("\n");
    isy_tick(); // emit 193:5
    const t941: IsyStr(3) = isy_str(3, "xxx");
    const t942: IsyStr(4) = isy_str(4, "xxxx");
    const t943: IsyStr(4) = isy_str(4, "xxxx");
    const t944: IsyStr(1) = isy_str(1, "x");
    const t945: i64 = m_5multi13141411(t941, t942, t943, t944);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t945));
    isy_out("\n");
    isy_tick(); // emit 194:5
    const t946: IsyStr(3) = isy_str(3, "xxx");
    const t947: IsyStr(4) = isy_str(4, "xxxx");
    const t948: IsyStr(4) = isy_str(4, "xxxx");
    const t949: IsyStr(2) = isy_str(2, "xx");
    const t950: i64 = m_5multi13141412(t946, t947, t948, t949);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t950));
    isy_out("\n");
    isy_tick(); // emit 195:5
    const t951: IsyStr(3) = isy_str(3, "xxx");
    const t952: IsyStr(4) = isy_str(4, "xxxx");
    const t953: IsyStr(4) = isy_str(4, "xxxx");
    const t954: IsyStr(3) = isy_str(3, "xxx");
    const t955: i64 = m_5multi13141413(t951, t952, t953, t954);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t955));
    isy_out("\n");
    isy_tick(); // emit 196:5
    const t956: IsyStr(3) = isy_str(3, "xxx");
    const t957: IsyStr(4) = isy_str(4, "xxxx");
    const t958: IsyStr(4) = isy_str(4, "xxxx");
    const t959: IsyStr(4) = isy_str(4, "xxxx");
    const t960: i64 = m_5multi13141414(t956, t957, t958, t959);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t960));
    isy_out("\n");
    isy_tick(); // emit 197:5
    const t961: IsyStr(4) = isy_str(4, "xxxx");
    const t962: IsyStr(1) = isy_str(1, "x");
    const t963: IsyStr(1) = isy_str(1, "x");
    const t964: IsyStr(1) = isy_str(1, "x");
    const t965: i64 = m_5multi14111111(t961, t962, t963, t964);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t965));
    isy_out("\n");
    isy_tick(); // emit 198:5
    const t966: IsyStr(4) = isy_str(4, "xxxx");
    const t967: IsyStr(1) = isy_str(1, "x");
    const t968: IsyStr(1) = isy_str(1, "x");
    const t969: IsyStr(2) = isy_str(2, "xx");
    const t970: i64 = m_5multi14111112(t966, t967, t968, t969);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t970));
    isy_out("\n");
    isy_tick(); // emit 199:5
    const t971: IsyStr(4) = isy_str(4, "xxxx");
    const t972: IsyStr(1) = isy_str(1, "x");
    const t973: IsyStr(1) = isy_str(1, "x");
    const t974: IsyStr(3) = isy_str(3, "xxx");
    const t975: i64 = m_5multi14111113(t971, t972, t973, t974);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t975));
    isy_out("\n");
    isy_tick(); // emit 200:5
    const t976: IsyStr(4) = isy_str(4, "xxxx");
    const t977: IsyStr(1) = isy_str(1, "x");
    const t978: IsyStr(1) = isy_str(1, "x");
    const t979: IsyStr(4) = isy_str(4, "xxxx");
    const t980: i64 = m_5multi14111114(t976, t977, t978, t979);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t980));
    isy_out("\n");
    isy_tick(); // emit 201:5
    const t981: IsyStr(4) = isy_str(4, "xxxx");
    const t982: IsyStr(1) = isy_str(1, "x");
    const t983: IsyStr(2) = isy_str(2, "xx");
    const t984: IsyStr(1) = isy_str(1, "x");
    const t985: i64 = m_5multi14111211(t981, t982, t983, t984);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t985));
    isy_out("\n");
    isy_tick(); // emit 202:5
    const t986: IsyStr(4) = isy_str(4, "xxxx");
    const t987: IsyStr(1) = isy_str(1, "x");
    const t988: IsyStr(2) = isy_str(2, "xx");
    const t989: IsyStr(2) = isy_str(2, "xx");
    const t990: i64 = m_5multi14111212(t986, t987, t988, t989);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t990));
    isy_out("\n");
    isy_tick(); // emit 203:5
    const t991: IsyStr(4) = isy_str(4, "xxxx");
    const t992: IsyStr(1) = isy_str(1, "x");
    const t993: IsyStr(2) = isy_str(2, "xx");
    const t994: IsyStr(3) = isy_str(3, "xxx");
    const t995: i64 = m_5multi14111213(t991, t992, t993, t994);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t995));
    isy_out("\n");
    isy_tick(); // emit 204:5
    const t996: IsyStr(4) = isy_str(4, "xxxx");
    const t997: IsyStr(1) = isy_str(1, "x");
    const t998: IsyStr(2) = isy_str(2, "xx");
    const t999: IsyStr(4) = isy_str(4, "xxxx");
    const t1000: i64 = m_5multi14111214(t996, t997, t998, t999);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1000));
    isy_out("\n");
    isy_tick(); // emit 205:5
    const t1001: IsyStr(4) = isy_str(4, "xxxx");
    const t1002: IsyStr(1) = isy_str(1, "x");
    const t1003: IsyStr(3) = isy_str(3, "xxx");
    const t1004: IsyStr(1) = isy_str(1, "x");
    const t1005: i64 = m_5multi14111311(t1001, t1002, t1003, t1004);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1005));
    isy_out("\n");
    isy_tick(); // emit 206:5
    const t1006: IsyStr(4) = isy_str(4, "xxxx");
    const t1007: IsyStr(1) = isy_str(1, "x");
    const t1008: IsyStr(3) = isy_str(3, "xxx");
    const t1009: IsyStr(2) = isy_str(2, "xx");
    const t1010: i64 = m_5multi14111312(t1006, t1007, t1008, t1009);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1010));
    isy_out("\n");
    isy_tick(); // emit 207:5
    const t1011: IsyStr(4) = isy_str(4, "xxxx");
    const t1012: IsyStr(1) = isy_str(1, "x");
    const t1013: IsyStr(3) = isy_str(3, "xxx");
    const t1014: IsyStr(3) = isy_str(3, "xxx");
    const t1015: i64 = m_5multi14111313(t1011, t1012, t1013, t1014);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1015));
    isy_out("\n");
    isy_tick(); // emit 208:5
    const t1016: IsyStr(4) = isy_str(4, "xxxx");
    const t1017: IsyStr(1) = isy_str(1, "x");
    const t1018: IsyStr(3) = isy_str(3, "xxx");
    const t1019: IsyStr(4) = isy_str(4, "xxxx");
    const t1020: i64 = m_5multi14111314(t1016, t1017, t1018, t1019);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1020));
    isy_out("\n");
    isy_tick(); // emit 209:5
    const t1021: IsyStr(4) = isy_str(4, "xxxx");
    const t1022: IsyStr(1) = isy_str(1, "x");
    const t1023: IsyStr(4) = isy_str(4, "xxxx");
    const t1024: IsyStr(1) = isy_str(1, "x");
    const t1025: i64 = m_5multi14111411(t1021, t1022, t1023, t1024);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1025));
    isy_out("\n");
    isy_tick(); // emit 210:5
    const t1026: IsyStr(4) = isy_str(4, "xxxx");
    const t1027: IsyStr(1) = isy_str(1, "x");
    const t1028: IsyStr(4) = isy_str(4, "xxxx");
    const t1029: IsyStr(2) = isy_str(2, "xx");
    const t1030: i64 = m_5multi14111412(t1026, t1027, t1028, t1029);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1030));
    isy_out("\n");
    isy_tick(); // emit 211:5
    const t1031: IsyStr(4) = isy_str(4, "xxxx");
    const t1032: IsyStr(1) = isy_str(1, "x");
    const t1033: IsyStr(4) = isy_str(4, "xxxx");
    const t1034: IsyStr(3) = isy_str(3, "xxx");
    const t1035: i64 = m_5multi14111413(t1031, t1032, t1033, t1034);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1035));
    isy_out("\n");
    isy_tick(); // emit 212:5
    const t1036: IsyStr(4) = isy_str(4, "xxxx");
    const t1037: IsyStr(1) = isy_str(1, "x");
    const t1038: IsyStr(4) = isy_str(4, "xxxx");
    const t1039: IsyStr(4) = isy_str(4, "xxxx");
    const t1040: i64 = m_5multi14111414(t1036, t1037, t1038, t1039);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1040));
    isy_out("\n");
    isy_tick(); // emit 213:5
    const t1041: IsyStr(4) = isy_str(4, "xxxx");
    const t1042: IsyStr(2) = isy_str(2, "xx");
    const t1043: IsyStr(1) = isy_str(1, "x");
    const t1044: IsyStr(1) = isy_str(1, "x");
    const t1045: i64 = m_5multi14121111(t1041, t1042, t1043, t1044);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1045));
    isy_out("\n");
    isy_tick(); // emit 214:5
    const t1046: IsyStr(4) = isy_str(4, "xxxx");
    const t1047: IsyStr(2) = isy_str(2, "xx");
    const t1048: IsyStr(1) = isy_str(1, "x");
    const t1049: IsyStr(2) = isy_str(2, "xx");
    const t1050: i64 = m_5multi14121112(t1046, t1047, t1048, t1049);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1050));
    isy_out("\n");
    isy_tick(); // emit 215:5
    const t1051: IsyStr(4) = isy_str(4, "xxxx");
    const t1052: IsyStr(2) = isy_str(2, "xx");
    const t1053: IsyStr(1) = isy_str(1, "x");
    const t1054: IsyStr(3) = isy_str(3, "xxx");
    const t1055: i64 = m_5multi14121113(t1051, t1052, t1053, t1054);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1055));
    isy_out("\n");
    isy_tick(); // emit 216:5
    const t1056: IsyStr(4) = isy_str(4, "xxxx");
    const t1057: IsyStr(2) = isy_str(2, "xx");
    const t1058: IsyStr(1) = isy_str(1, "x");
    const t1059: IsyStr(4) = isy_str(4, "xxxx");
    const t1060: i64 = m_5multi14121114(t1056, t1057, t1058, t1059);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1060));
    isy_out("\n");
    isy_tick(); // emit 217:5
    const t1061: IsyStr(4) = isy_str(4, "xxxx");
    const t1062: IsyStr(2) = isy_str(2, "xx");
    const t1063: IsyStr(2) = isy_str(2, "xx");
    const t1064: IsyStr(1) = isy_str(1, "x");
    const t1065: i64 = m_5multi14121211(t1061, t1062, t1063, t1064);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1065));
    isy_out("\n");
    isy_tick(); // emit 218:5
    const t1066: IsyStr(4) = isy_str(4, "xxxx");
    const t1067: IsyStr(2) = isy_str(2, "xx");
    const t1068: IsyStr(2) = isy_str(2, "xx");
    const t1069: IsyStr(2) = isy_str(2, "xx");
    const t1070: i64 = m_5multi14121212(t1066, t1067, t1068, t1069);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1070));
    isy_out("\n");
    isy_tick(); // emit 219:5
    const t1071: IsyStr(4) = isy_str(4, "xxxx");
    const t1072: IsyStr(2) = isy_str(2, "xx");
    const t1073: IsyStr(2) = isy_str(2, "xx");
    const t1074: IsyStr(3) = isy_str(3, "xxx");
    const t1075: i64 = m_5multi14121213(t1071, t1072, t1073, t1074);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1075));
    isy_out("\n");
    isy_tick(); // emit 220:5
    const t1076: IsyStr(4) = isy_str(4, "xxxx");
    const t1077: IsyStr(2) = isy_str(2, "xx");
    const t1078: IsyStr(2) = isy_str(2, "xx");
    const t1079: IsyStr(4) = isy_str(4, "xxxx");
    const t1080: i64 = m_5multi14121214(t1076, t1077, t1078, t1079);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1080));
    isy_out("\n");
    isy_tick(); // emit 221:5
    const t1081: IsyStr(4) = isy_str(4, "xxxx");
    const t1082: IsyStr(2) = isy_str(2, "xx");
    const t1083: IsyStr(3) = isy_str(3, "xxx");
    const t1084: IsyStr(1) = isy_str(1, "x");
    const t1085: i64 = m_5multi14121311(t1081, t1082, t1083, t1084);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1085));
    isy_out("\n");
    isy_tick(); // emit 222:5
    const t1086: IsyStr(4) = isy_str(4, "xxxx");
    const t1087: IsyStr(2) = isy_str(2, "xx");
    const t1088: IsyStr(3) = isy_str(3, "xxx");
    const t1089: IsyStr(2) = isy_str(2, "xx");
    const t1090: i64 = m_5multi14121312(t1086, t1087, t1088, t1089);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1090));
    isy_out("\n");
    isy_tick(); // emit 223:5
    const t1091: IsyStr(4) = isy_str(4, "xxxx");
    const t1092: IsyStr(2) = isy_str(2, "xx");
    const t1093: IsyStr(3) = isy_str(3, "xxx");
    const t1094: IsyStr(3) = isy_str(3, "xxx");
    const t1095: i64 = m_5multi14121313(t1091, t1092, t1093, t1094);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1095));
    isy_out("\n");
    isy_tick(); // emit 224:5
    const t1096: IsyStr(4) = isy_str(4, "xxxx");
    const t1097: IsyStr(2) = isy_str(2, "xx");
    const t1098: IsyStr(3) = isy_str(3, "xxx");
    const t1099: IsyStr(4) = isy_str(4, "xxxx");
    const t1100: i64 = m_5multi14121314(t1096, t1097, t1098, t1099);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1100));
    isy_out("\n");
    isy_tick(); // emit 225:5
    const t1101: IsyStr(4) = isy_str(4, "xxxx");
    const t1102: IsyStr(2) = isy_str(2, "xx");
    const t1103: IsyStr(4) = isy_str(4, "xxxx");
    const t1104: IsyStr(1) = isy_str(1, "x");
    const t1105: i64 = m_5multi14121411(t1101, t1102, t1103, t1104);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1105));
    isy_out("\n");
    isy_tick(); // emit 226:5
    const t1106: IsyStr(4) = isy_str(4, "xxxx");
    const t1107: IsyStr(2) = isy_str(2, "xx");
    const t1108: IsyStr(4) = isy_str(4, "xxxx");
    const t1109: IsyStr(2) = isy_str(2, "xx");
    const t1110: i64 = m_5multi14121412(t1106, t1107, t1108, t1109);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1110));
    isy_out("\n");
    isy_tick(); // emit 227:5
    const t1111: IsyStr(4) = isy_str(4, "xxxx");
    const t1112: IsyStr(2) = isy_str(2, "xx");
    const t1113: IsyStr(4) = isy_str(4, "xxxx");
    const t1114: IsyStr(3) = isy_str(3, "xxx");
    const t1115: i64 = m_5multi14121413(t1111, t1112, t1113, t1114);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1115));
    isy_out("\n");
    isy_tick(); // emit 228:5
    const t1116: IsyStr(4) = isy_str(4, "xxxx");
    const t1117: IsyStr(2) = isy_str(2, "xx");
    const t1118: IsyStr(4) = isy_str(4, "xxxx");
    const t1119: IsyStr(4) = isy_str(4, "xxxx");
    const t1120: i64 = m_5multi14121414(t1116, t1117, t1118, t1119);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1120));
    isy_out("\n");
    isy_tick(); // emit 229:5
    const t1121: IsyStr(4) = isy_str(4, "xxxx");
    const t1122: IsyStr(3) = isy_str(3, "xxx");
    const t1123: IsyStr(1) = isy_str(1, "x");
    const t1124: IsyStr(1) = isy_str(1, "x");
    const t1125: i64 = m_5multi14131111(t1121, t1122, t1123, t1124);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1125));
    isy_out("\n");
    isy_tick(); // emit 230:5
    const t1126: IsyStr(4) = isy_str(4, "xxxx");
    const t1127: IsyStr(3) = isy_str(3, "xxx");
    const t1128: IsyStr(1) = isy_str(1, "x");
    const t1129: IsyStr(2) = isy_str(2, "xx");
    const t1130: i64 = m_5multi14131112(t1126, t1127, t1128, t1129);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1130));
    isy_out("\n");
    isy_tick(); // emit 231:5
    const t1131: IsyStr(4) = isy_str(4, "xxxx");
    const t1132: IsyStr(3) = isy_str(3, "xxx");
    const t1133: IsyStr(1) = isy_str(1, "x");
    const t1134: IsyStr(3) = isy_str(3, "xxx");
    const t1135: i64 = m_5multi14131113(t1131, t1132, t1133, t1134);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1135));
    isy_out("\n");
    isy_tick(); // emit 232:5
    const t1136: IsyStr(4) = isy_str(4, "xxxx");
    const t1137: IsyStr(3) = isy_str(3, "xxx");
    const t1138: IsyStr(1) = isy_str(1, "x");
    const t1139: IsyStr(4) = isy_str(4, "xxxx");
    const t1140: i64 = m_5multi14131114(t1136, t1137, t1138, t1139);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1140));
    isy_out("\n");
    isy_tick(); // emit 233:5
    const t1141: IsyStr(4) = isy_str(4, "xxxx");
    const t1142: IsyStr(3) = isy_str(3, "xxx");
    const t1143: IsyStr(2) = isy_str(2, "xx");
    const t1144: IsyStr(1) = isy_str(1, "x");
    const t1145: i64 = m_5multi14131211(t1141, t1142, t1143, t1144);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1145));
    isy_out("\n");
    isy_tick(); // emit 234:5
    const t1146: IsyStr(4) = isy_str(4, "xxxx");
    const t1147: IsyStr(3) = isy_str(3, "xxx");
    const t1148: IsyStr(2) = isy_str(2, "xx");
    const t1149: IsyStr(2) = isy_str(2, "xx");
    const t1150: i64 = m_5multi14131212(t1146, t1147, t1148, t1149);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1150));
    isy_out("\n");
    isy_tick(); // emit 235:5
    const t1151: IsyStr(4) = isy_str(4, "xxxx");
    const t1152: IsyStr(3) = isy_str(3, "xxx");
    const t1153: IsyStr(2) = isy_str(2, "xx");
    const t1154: IsyStr(3) = isy_str(3, "xxx");
    const t1155: i64 = m_5multi14131213(t1151, t1152, t1153, t1154);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1155));
    isy_out("\n");
    isy_tick(); // emit 236:5
    const t1156: IsyStr(4) = isy_str(4, "xxxx");
    const t1157: IsyStr(3) = isy_str(3, "xxx");
    const t1158: IsyStr(2) = isy_str(2, "xx");
    const t1159: IsyStr(4) = isy_str(4, "xxxx");
    const t1160: i64 = m_5multi14131214(t1156, t1157, t1158, t1159);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1160));
    isy_out("\n");
    isy_tick(); // emit 237:5
    const t1161: IsyStr(4) = isy_str(4, "xxxx");
    const t1162: IsyStr(3) = isy_str(3, "xxx");
    const t1163: IsyStr(3) = isy_str(3, "xxx");
    const t1164: IsyStr(1) = isy_str(1, "x");
    const t1165: i64 = m_5multi14131311(t1161, t1162, t1163, t1164);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1165));
    isy_out("\n");
    isy_tick(); // emit 238:5
    const t1166: IsyStr(4) = isy_str(4, "xxxx");
    const t1167: IsyStr(3) = isy_str(3, "xxx");
    const t1168: IsyStr(3) = isy_str(3, "xxx");
    const t1169: IsyStr(2) = isy_str(2, "xx");
    const t1170: i64 = m_5multi14131312(t1166, t1167, t1168, t1169);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1170));
    isy_out("\n");
    isy_tick(); // emit 239:5
    const t1171: IsyStr(4) = isy_str(4, "xxxx");
    const t1172: IsyStr(3) = isy_str(3, "xxx");
    const t1173: IsyStr(3) = isy_str(3, "xxx");
    const t1174: IsyStr(3) = isy_str(3, "xxx");
    const t1175: i64 = m_5multi14131313(t1171, t1172, t1173, t1174);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1175));
    isy_out("\n");
    isy_tick(); // emit 240:5
    const t1176: IsyStr(4) = isy_str(4, "xxxx");
    const t1177: IsyStr(3) = isy_str(3, "xxx");
    const t1178: IsyStr(3) = isy_str(3, "xxx");
    const t1179: IsyStr(4) = isy_str(4, "xxxx");
    const t1180: i64 = m_5multi14131314(t1176, t1177, t1178, t1179);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1180));
    isy_out("\n");
    isy_tick(); // emit 241:5
    const t1181: IsyStr(4) = isy_str(4, "xxxx");
    const t1182: IsyStr(3) = isy_str(3, "xxx");
    const t1183: IsyStr(4) = isy_str(4, "xxxx");
    const t1184: IsyStr(1) = isy_str(1, "x");
    const t1185: i64 = m_5multi14131411(t1181, t1182, t1183, t1184);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1185));
    isy_out("\n");
    isy_tick(); // emit 242:5
    const t1186: IsyStr(4) = isy_str(4, "xxxx");
    const t1187: IsyStr(3) = isy_str(3, "xxx");
    const t1188: IsyStr(4) = isy_str(4, "xxxx");
    const t1189: IsyStr(2) = isy_str(2, "xx");
    const t1190: i64 = m_5multi14131412(t1186, t1187, t1188, t1189);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1190));
    isy_out("\n");
    isy_tick(); // emit 243:5
    const t1191: IsyStr(4) = isy_str(4, "xxxx");
    const t1192: IsyStr(3) = isy_str(3, "xxx");
    const t1193: IsyStr(4) = isy_str(4, "xxxx");
    const t1194: IsyStr(3) = isy_str(3, "xxx");
    const t1195: i64 = m_5multi14131413(t1191, t1192, t1193, t1194);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1195));
    isy_out("\n");
    isy_tick(); // emit 244:5
    const t1196: IsyStr(4) = isy_str(4, "xxxx");
    const t1197: IsyStr(3) = isy_str(3, "xxx");
    const t1198: IsyStr(4) = isy_str(4, "xxxx");
    const t1199: IsyStr(4) = isy_str(4, "xxxx");
    const t1200: i64 = m_5multi14131414(t1196, t1197, t1198, t1199);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1200));
    isy_out("\n");
    isy_tick(); // emit 245:5
    const t1201: IsyStr(4) = isy_str(4, "xxxx");
    const t1202: IsyStr(4) = isy_str(4, "xxxx");
    const t1203: IsyStr(1) = isy_str(1, "x");
    const t1204: IsyStr(1) = isy_str(1, "x");
    const t1205: i64 = m_5multi14141111(t1201, t1202, t1203, t1204);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1205));
    isy_out("\n");
    isy_tick(); // emit 246:5
    const t1206: IsyStr(4) = isy_str(4, "xxxx");
    const t1207: IsyStr(4) = isy_str(4, "xxxx");
    const t1208: IsyStr(1) = isy_str(1, "x");
    const t1209: IsyStr(2) = isy_str(2, "xx");
    const t1210: i64 = m_5multi14141112(t1206, t1207, t1208, t1209);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1210));
    isy_out("\n");
    isy_tick(); // emit 247:5
    const t1211: IsyStr(4) = isy_str(4, "xxxx");
    const t1212: IsyStr(4) = isy_str(4, "xxxx");
    const t1213: IsyStr(1) = isy_str(1, "x");
    const t1214: IsyStr(3) = isy_str(3, "xxx");
    const t1215: i64 = m_5multi14141113(t1211, t1212, t1213, t1214);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1215));
    isy_out("\n");
    isy_tick(); // emit 248:5
    const t1216: IsyStr(4) = isy_str(4, "xxxx");
    const t1217: IsyStr(4) = isy_str(4, "xxxx");
    const t1218: IsyStr(1) = isy_str(1, "x");
    const t1219: IsyStr(4) = isy_str(4, "xxxx");
    const t1220: i64 = m_5multi14141114(t1216, t1217, t1218, t1219);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1220));
    isy_out("\n");
    isy_tick(); // emit 249:5
    const t1221: IsyStr(4) = isy_str(4, "xxxx");
    const t1222: IsyStr(4) = isy_str(4, "xxxx");
    const t1223: IsyStr(2) = isy_str(2, "xx");
    const t1224: IsyStr(1) = isy_str(1, "x");
    const t1225: i64 = m_5multi14141211(t1221, t1222, t1223, t1224);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1225));
    isy_out("\n");
    isy_tick(); // emit 250:5
    const t1226: IsyStr(4) = isy_str(4, "xxxx");
    const t1227: IsyStr(4) = isy_str(4, "xxxx");
    const t1228: IsyStr(2) = isy_str(2, "xx");
    const t1229: IsyStr(2) = isy_str(2, "xx");
    const t1230: i64 = m_5multi14141212(t1226, t1227, t1228, t1229);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1230));
    isy_out("\n");
    isy_tick(); // emit 251:5
    const t1231: IsyStr(4) = isy_str(4, "xxxx");
    const t1232: IsyStr(4) = isy_str(4, "xxxx");
    const t1233: IsyStr(2) = isy_str(2, "xx");
    const t1234: IsyStr(3) = isy_str(3, "xxx");
    const t1235: i64 = m_5multi14141213(t1231, t1232, t1233, t1234);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1235));
    isy_out("\n");
    isy_tick(); // emit 252:5
    const t1236: IsyStr(4) = isy_str(4, "xxxx");
    const t1237: IsyStr(4) = isy_str(4, "xxxx");
    const t1238: IsyStr(2) = isy_str(2, "xx");
    const t1239: IsyStr(4) = isy_str(4, "xxxx");
    const t1240: i64 = m_5multi14141214(t1236, t1237, t1238, t1239);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1240));
    isy_out("\n");
    isy_tick(); // emit 253:5
    const t1241: IsyStr(4) = isy_str(4, "xxxx");
    const t1242: IsyStr(4) = isy_str(4, "xxxx");
    const t1243: IsyStr(3) = isy_str(3, "xxx");
    const t1244: IsyStr(1) = isy_str(1, "x");
    const t1245: i64 = m_5multi14141311(t1241, t1242, t1243, t1244);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1245));
    isy_out("\n");
    isy_tick(); // emit 254:5
    const t1246: IsyStr(4) = isy_str(4, "xxxx");
    const t1247: IsyStr(4) = isy_str(4, "xxxx");
    const t1248: IsyStr(3) = isy_str(3, "xxx");
    const t1249: IsyStr(2) = isy_str(2, "xx");
    const t1250: i64 = m_5multi14141312(t1246, t1247, t1248, t1249);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1250));
    isy_out("\n");
    isy_tick(); // emit 255:5
    const t1251: IsyStr(4) = isy_str(4, "xxxx");
    const t1252: IsyStr(4) = isy_str(4, "xxxx");
    const t1253: IsyStr(3) = isy_str(3, "xxx");
    const t1254: IsyStr(3) = isy_str(3, "xxx");
    const t1255: i64 = m_5multi14141313(t1251, t1252, t1253, t1254);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1255));
    isy_out("\n");
    isy_tick(); // emit 256:5
    const t1256: IsyStr(4) = isy_str(4, "xxxx");
    const t1257: IsyStr(4) = isy_str(4, "xxxx");
    const t1258: IsyStr(3) = isy_str(3, "xxx");
    const t1259: IsyStr(4) = isy_str(4, "xxxx");
    const t1260: i64 = m_5multi14141314(t1256, t1257, t1258, t1259);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1260));
    isy_out("\n");
    isy_tick(); // emit 257:5
    const t1261: IsyStr(4) = isy_str(4, "xxxx");
    const t1262: IsyStr(4) = isy_str(4, "xxxx");
    const t1263: IsyStr(4) = isy_str(4, "xxxx");
    const t1264: IsyStr(1) = isy_str(1, "x");
    const t1265: i64 = m_5multi14141411(t1261, t1262, t1263, t1264);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1265));
    isy_out("\n");
    isy_tick(); // emit 258:5
    const t1266: IsyStr(4) = isy_str(4, "xxxx");
    const t1267: IsyStr(4) = isy_str(4, "xxxx");
    const t1268: IsyStr(4) = isy_str(4, "xxxx");
    const t1269: IsyStr(2) = isy_str(2, "xx");
    const t1270: i64 = m_5multi14141412(t1266, t1267, t1268, t1269);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1270));
    isy_out("\n");
    isy_tick(); // emit 259:5
    const t1271: IsyStr(4) = isy_str(4, "xxxx");
    const t1272: IsyStr(4) = isy_str(4, "xxxx");
    const t1273: IsyStr(4) = isy_str(4, "xxxx");
    const t1274: IsyStr(3) = isy_str(3, "xxx");
    const t1275: i64 = m_5multi14141413(t1271, t1272, t1273, t1274);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1275));
    isy_out("\n");
    isy_tick(); // emit 260:5
    const t1276: IsyStr(4) = isy_str(4, "xxxx");
    const t1277: IsyStr(4) = isy_str(4, "xxxx");
    const t1278: IsyStr(4) = isy_str(4, "xxxx");
    const t1279: IsyStr(4) = isy_str(4, "xxxx");
    const t1280: i64 = m_5multi14141414(t1276, t1277, t1278, t1279);
    isy_emit_check();
    isy_out("E ");
    isy_put_i128(@as(i128, t1280));
    isy_out("\n");
    isy_tick(); // return 261:5
    isy_depth -= 1;
    return isy_k(i64, 0);
}

fn m_5multi11111111(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111112(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111113(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111114(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111211(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111212(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111213(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111214(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111311(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111312(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111313(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111314(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111411(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111412(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111413(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11111414(p0: IsyStr(1), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121111(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121112(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121113(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121114(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121211(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121212(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121213(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121214(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121311(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121312(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121313(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121314(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121411(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121412(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121413(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11121414(p0: IsyStr(1), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131111(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131112(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131113(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131114(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131211(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131212(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131213(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131214(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131311(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131312(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131313(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131314(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131411(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131412(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131413(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11131414(p0: IsyStr(1), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141111(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141112(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141113(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141114(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141211(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141212(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141213(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141214(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141311(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141312(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141313(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141314(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141411(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141412(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141413(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi11141414(p0: IsyStr(1), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(1) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111111(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111112(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111113(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111114(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111211(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111212(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111213(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111214(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111311(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111312(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111313(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111314(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111411(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111412(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111413(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12111414(p0: IsyStr(2), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121111(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121112(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121113(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121114(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121211(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121212(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121213(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121214(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121311(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121312(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121313(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121314(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121411(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121412(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121413(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12121414(p0: IsyStr(2), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131111(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131112(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131113(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131114(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131211(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131212(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131213(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131214(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131311(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131312(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131313(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131314(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131411(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131412(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131413(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12131414(p0: IsyStr(2), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141111(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141112(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141113(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141114(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141211(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141212(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141213(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141214(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141311(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141312(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141313(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141314(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141411(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141412(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141413(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi12141414(p0: IsyStr(2), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(2) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111111(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111112(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111113(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111114(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111211(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111212(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111213(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111214(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111311(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111312(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111313(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111314(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111411(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111412(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111413(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13111414(p0: IsyStr(3), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121111(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121112(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121113(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121114(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121211(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121212(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121213(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121214(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121311(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121312(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121313(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121314(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121411(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121412(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121413(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13121414(p0: IsyStr(3), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131111(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131112(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131113(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131114(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131211(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131212(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131213(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131214(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131311(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131312(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131313(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131314(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131411(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131412(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131413(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13131414(p0: IsyStr(3), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141111(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141112(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141113(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141114(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141211(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141212(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141213(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141214(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141311(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141312(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141313(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141314(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141411(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141412(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141413(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi13141414(p0: IsyStr(3), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(3) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111111(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111112(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111113(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111114(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111211(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111212(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111213(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111214(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111311(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111312(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111313(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111314(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111411(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111412(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111413(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14111414(p0: IsyStr(4), p1: IsyStr(1), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(1) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121111(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121112(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121113(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121114(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121211(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121212(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121213(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121214(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121311(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121312(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121313(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121314(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121411(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121412(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121413(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14121414(p0: IsyStr(4), p1: IsyStr(2), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(2) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131111(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131112(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131113(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131114(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131211(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131212(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131213(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131214(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131311(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131312(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131313(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131314(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131411(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131412(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131413(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14131414(p0: IsyStr(4), p1: IsyStr(3), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(3) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141111(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141112(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141113(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141114(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(1), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(1) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141211(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141212(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141213(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141214(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(2), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(2) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141311(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141312(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141313(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141314(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(3), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(3) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141411(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(1)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(1) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141412(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(2)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(2) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141413(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(3)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(3) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

fn m_5multi14141414(p0: IsyStr(4), p1: IsyStr(4), p2: IsyStr(4), p3: IsyStr(4)) i64 {
    var l0: IsyStr(4) = p0;
    _ = &l0;
    var l1: IsyStr(4) = p1;
    _ = &l1;
    var l2: IsyStr(4) = p2;
    _ = &l2;
    var l3: IsyStr(4) = p3;
    _ = &l3;
    isy_enter();
    isy_tick(); // return 3:55
    const t1: i64 = @as(i64, @intCast(isy_fit((@as(i128, @as(i64, l0.len)) + @as(i128, @as(i64, l1.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t2: i64 = @as(i64, @intCast(isy_fit((@as(i128, t1) + @as(i128, @as(i64, l2.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    const t3: i64 = @as(i64, @intCast(isy_fit((@as(i128, t2) + @as(i128, @as(i64, l3.len))), -9223372036854775808, 9223372036854775807, 64, 0)));
    isy_depth -= 1;
    return t3;
}

pub fn main(init: std.process.Init.Minimal) void {
    const argv = init.args.vector;
    if (argv.len != 4) std.process.exit(2);
    isy_max_steps = @as(u64, @intCast(isy_arg(argv[1])));
    isy_max_depth = @as(u64, @intCast(isy_arg(argv[2])));
    isy_max_emits = @as(u64, @intCast(isy_arg(argv[3])));
    const r: i64 = f_main();
    isy_out("R ");
    isy_put_i128(@as(i128, r));
    isy_out("\n");
    isy_end("HALTED", "-");
}
