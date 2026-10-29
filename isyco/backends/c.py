"""Backend C: ISY-IR v0.1 -> C (GNU C11) -> binario nativo con gcc/clang.

Contrato del binario generado:
    ./prog MAX_STEPS MAX_CALL_DEPTH MAX_EMITS ARG...
Cada ARG es un valor crudo: entero en base 10, decimal como entero escalado m,
bool como 1/0; un arreglo se pasa aplanado, elemento por elemento.
Salida por stdout, una línea por evento:
    E <forma canónica>        un emit
    R <forma canónica>        valor de retorno de main (si tiene)
    X <status> <code|-> <steps>   siempre la última línea

Garantías de la traducción (spec/CORE.md):
- orden de evaluación de izquierda a derecha: toda subexpresión que puede
  fallar o tener efectos se materializa en una temporal, en orden;
- sin comportamiento indefinido: la aritmética entera se calcula exacta en
  __int128 y se ajusta con trap/wrap/sat; u64*u64 usa __builtin_mul_overflow;
- decimales como int64_t escalado (p <= 18) con producto exacto en __int128;
- arreglos como struct: C los copia por valor, igual que la spec;
- pasos, profundidad y emits se cuentan exactamente como la referencia.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..ir import ty_from_json
from ..types import ArrT, BoolT, DecT, IntT, parse_canonical
from .base import ALL_FEATURES, V2_FEATURES, Backend

ROUND_CODE = {"half_even": 0, "half_up": 1, "down": 2, "exact": 3}
OVF_CODE = {"trap": 0, "wrap": 1, "sat": 2}
C_CMP = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
C_ARITH = {"add": "+", "sub": "-", "mul": "*"}

RUNTIME = r"""
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef __int128 i128;
static uint64_t isy_steps, isy_max_steps, isy_depth, isy_max_depth, isy_emits, isy_max_emits;

static void isy_end(const char *status, const char *code) {
    printf("X %s %s %" PRIu64 "\n", status, code ? code : "-", isy_steps);
    exit(0);
}
static void isy_fail(const char *code) { isy_end("ERROR", code); }
static void isy_limit(const char *code) { isy_end("LIMIT_REACHED", code); }
static inline void isy_tick(void) { if (++isy_steps > isy_max_steps) isy_limit("max_steps"); }
static inline void isy_enter(void) {
    isy_tick();
    if (isy_depth + 1 > isy_max_depth) isy_limit("max_call_depth");
    isy_depth++;
}
static inline void isy_emit_check(void) {
    if (isy_emits >= isy_max_emits) isy_limit("max_emits");
    isy_emits++;
}

/* Ajusta el resultado exacto v al rango [lo, hi]. ovf: 0 trap, 1 wrap, 2 sat. */
static i128 isy_fit(i128 v, i128 lo, i128 hi, int bits, int ovf) {
    if (v >= lo && v <= hi) return v;
    if (ovf == 0) isy_fail("OVERFLOW");
    if (ovf == 2) return v > hi ? hi : lo;
    i128 w = (i128)1 << bits;
    i128 r = (v - lo) % w;
    if (r < 0) r += w;
    return r + lo;
}

/* u64 * u64 puede no caber en i128: se resuelve con el builtin. */
static uint64_t isy_mul_u64(uint64_t a, uint64_t b, int ovf) {
    uint64_t r;
    if (!__builtin_mul_overflow(a, b, &r)) return r;
    if (ovf == 0) isy_fail("OVERFLOW");
    return ovf == 1 ? r : UINT64_MAX;
}

/* Cociente num/den redondeado una vez. mode: 0 half_even, 1 half_up, 2 down, 3 exact. */
static i128 isy_rdiv(i128 num, i128 den, int mode) {
    i128 q = num / den, r = num % den;
    if (r == 0) return q;
    if (mode == 3) isy_fail("INEXACT");
    if (mode == 2) return q;
    i128 ar = r < 0 ? -r : r, ad = den < 0 ? -den : den;
    int sign = ((num < 0) != (den < 0)) ? -1 : 1;
    if (2 * ar > ad) return q + sign;
    if (2 * ar < ad) return q;
    if (mode == 1) return q + sign;
    ISY_HALF_EVEN_TIE
}

static i128 isy_dec_fit(i128 m, i128 max) {
    if (m > max || m < -max) isy_fail("OVERFLOW");
    return m;
}

static void isy_put_i128(i128 v) {
    char buf[64];
    int n = 0;
    int neg = v < 0;
    unsigned __int128 u = neg ? (unsigned __int128)(-(v + 1)) + 1 : (unsigned __int128)v;
    do { buf[n++] = (char)('0' + (int)(u % 10)); u /= 10; } while (u);
    if (neg) putchar('-');
    while (n) putchar(buf[--n]);
}
static void isy_put_dec(i128 m, int s) {
    if (s == 0) { isy_put_i128(m); return; }
    char buf[64];
    int n = 0;
    int neg = m < 0;
    unsigned __int128 u = neg ? (unsigned __int128)(-m) : (unsigned __int128)m;
    do { buf[n++] = (char)('0' + (int)(u % 10)); u /= 10; } while (u);
    while (n < s + 1) buf[n++] = '0';
    if (neg) putchar('-');
    while (n > s) putchar(buf[--n]);
    putchar('.');
    while (n) putchar(buf[--n]);
}
static void isy_put_bool(int b) { fputs(b ? "true" : "false", stdout); }
"""

HALF_EVEN_TIE = {
    None: "return (q % 2 == 0) ? q : q + sign;",
    # Sabotaje deliberado: half_even se comporta como half_up en los empates.
    "half_even_as_half_up": "return q + sign;",
}


def c_i128(v: int) -> str:
    return f"((i128){v}ULL)" if v >= 0 else f"(-((i128){-v}ULL))"


class CEmitter:
    def __init__(self, module: dict, sabotage: str | None = None):
        if sabotage not in HALF_EVEN_TIE and sabotage not in ("div_floor",):
            raise ValueError(sabotage)
        self.module = module
        self.sabotage = sabotage
        self.arrays: dict[str, str] = {}   # json del tipo arreglo -> nombre del struct
        self.typedefs: list[str] = []
        self.lines: list[str] = []
        self.indent = 1
        self.tmp = 0
        self.fn: dict | None = None
        self.local_types: list = []

    # --- tipos ----------------------------------------------------------------
    def ctype(self, t) -> str:
        if isinstance(t, BoolT):
            return "int"
        if isinstance(t, IntT):
            return f"{'' if t.signed else 'u'}int{t.bits}_t"
        if isinstance(t, DecT):
            return "int64_t"
        if isinstance(t, ArrT):
            key = repr(t)
            if key not in self.arrays:
                name = f"isy_arr{len(self.arrays)}"
                self.arrays[key] = name
                self.typedefs.append(f"typedef struct {{ {self.ctype(t.elem)} v[{t.n}]; }} {name};")
            return self.arrays[key]
        raise AssertionError(t)

    @staticmethod
    def fit_args(t: IntT) -> str:
        return f"{c_i128(t.lo)}, {c_i128(t.hi)}, {t.bits}, {OVF_CODE[t.ovf]}"

    # --- utilidades de emisión ------------------------------------------------
    def put(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def temp(self, t, value: str) -> str:
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"{self.ctype(t)} {name} = {value};")
        return name

    # --- módulo ---------------------------------------------------------------
    def emit(self) -> str:
        functions = self.module["functions"]
        protos, bodies = [], []
        for fn in functions:
            protos.append(self.signature(fn) + ";")
        for fn in functions:
            bodies.append(self.function(fn))
        main_src = self.c_main(next(f for f in functions if f["name"] == "main"))
        runtime = RUNTIME.replace("ISY_HALF_EVEN_TIE", HALF_EVEN_TIE.get(self.sabotage, HALF_EVEN_TIE[None]))
        return "\n".join([
            f"/* generado por isyco.backends.c desde ISY-IR {self.module['source_sha256']} */",
            runtime, *self.typedefs, "", *protos, "", *bodies, main_src, ""])

    def signature(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        params = ", ".join(f"{self.ctype(types[p])} l{p}" for p in fn["params"]) or "void"
        return f"static {'void' if ret is None else self.ctype(ret)} f_{fn['name']}({params})"

    def function(self, fn: dict) -> str:
        self.fn, self.tmp, self.lines, self.indent = fn, 0, [], 1
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        for i, t in enumerate(self.local_types):
            if i not in fn["params"]:
                self.put(f"{self.ctype(t)} l{i} = {{0}};" if isinstance(t, ArrT)
                         else f"{self.ctype(t)} l{i} = 0;")
        self.put("isy_enter();")
        self.block(fn["body"])
        if fn["ret"] is None:
            self.put("isy_depth--;")
            self.put("return;")
        else:
            self.put("abort(); /* inalcanzable: el validador exige retorno en todo camino */")
        return f"{self.signature(fn)} {{\n" + "\n".join(self.lines) + "\n}\n"

    def c_main(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        lines = ["int main(int argc, char **argv) {",
                 "    setvbuf(stdout, NULL, _IOFBF, 1 << 16);"]
        count = sum(t.n if isinstance(t, ArrT) else 1 for t in (types[p] for p in fn["params"]))
        lines.append(f"    if (argc != {4 + count}) return 2;")
        lines.append("    isy_max_steps = strtoull(argv[1], 0, 10);")
        lines.append("    isy_max_depth = strtoull(argv[2], 0, 10);")
        lines.append("    isy_max_emits = strtoull(argv[3], 0, 10);")
        argi = 4
        names = []
        for p in fn["params"]:
            t = types[p]
            names.append(f"a{p}")
            if isinstance(t, ArrT):
                lines.append(f"    {self.ctype(t)} a{p};")
                for k in range(t.n):
                    lines.append(f"    a{p}.v[{k}] = ({self.ctype(t.elem)}){self.parse_arg(t.elem, argi)};")
                    argi += 1
            else:
                lines.append(f"    {self.ctype(t)} a{p} = ({self.ctype(t)}){self.parse_arg(t, argi)};")
                argi += 1
        call = f"f_main({', '.join(names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    {self.ctype(ret)} r = {call};")
            lines.append("    fputs(\"R \", stdout);")
            lines.append(f"    {self.put_call(ret, 'r')};")
            lines.append("    putchar('\\n');")
        lines += ["    isy_end(\"HALTED\", NULL);", "    return 0;", "}"]
        return "\n".join(lines)

    @staticmethod
    def parse_arg(t, i: int) -> str:
        if isinstance(t, IntT) and not t.signed:
            return f"strtoull(argv[{i}], 0, 10)"
        return f"strtoll(argv[{i}], 0, 10)"

    @staticmethod
    def put_call(t, value: str) -> str:
        if isinstance(t, BoolT):
            return f"isy_put_bool({value})"
        if isinstance(t, IntT):
            return f"isy_put_i128((i128){value})"
        return f"isy_put_dec((i128){value}, {t.s})"

    # --- sentencias -----------------------------------------------------------
    def block(self, stmts: list) -> None:
        for s in stmts:
            self.stmt(s)

    def nested(self, header: str, stmts: list, footer: str = "}") -> None:
        self.put(header)
        self.indent += 1
        self.block(stmts)
        self.indent -= 1
        self.put(footer)

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        self.put(f"isy_tick(); /* {kind} {s['at']} */")
        if kind in ("let", "set"):
            value = self.expr(s["value"])
            self.put(f"l{s['local']} = {value};")
        elif kind == "set_index":
            index = self.expr(s["index"])
            value = self.expr(s["value"])
            n = self.local_types[s["local"]].n
            self.put(f"if ((i128){index} < 0 || (i128){index} >= {n}) isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            self.put(f"l{s['local']}.v[{index}] = {value};")
        elif kind == "if":
            cond = self.expr(s["cond"])
            self.nested(f"if ({cond}) {{", s["then"])
            if s["else"] is not None:
                self.nested("else {", s["else"])
        elif kind == "while":
            self.put("for (;;) {")
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
                self.put("isy_depth--;")
                self.put("return;")
            else:
                value = self.expr(s["value"])
                self.put("isy_depth--;")
                self.put(f"return {value};")
        elif kind == "emit":
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            self.put("isy_emit_check();")
            self.put(f"fputs(\"E \", stdout); {self.put_call(t, value)}; putchar('\\n');")
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            self.put(f"f_{s['fn']}({', '.join(args)});")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        """Emite las sentencias previas necesarias y devuelve una expresión C sin efectos."""
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, BoolT):
                return "1" if value else "0"
            return f"(({self.ctype(t)}){c_i128(value)})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"f_{e['fn']}({', '.join(args)})")
        if kind == "index":
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            n = ty_from_json(e["base"]["ty"]).n
            self.put(f"if ((i128){index} < 0 || (i128){index} >= {n}) isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            return self.temp(t, f"{base}.v[{index}]")
        if kind == "cast":
            return self.cast(e, t)
        if kind == "not":
            return f"(!{self.expr(e['e'])})"
        if kind == "neg":
            x = self.expr(e["e"])
            if isinstance(t, IntT):
                return self.temp(t, f"({self.ctype(t)})isy_fit(-(i128){x}, {self.fit_args(t)})")
            return self.temp(t, f"(int64_t)isy_dec_fit(-(i128){x}, {c_i128(t.max_m)})")
        if kind in ("and", "or"):
            result = self.temp(t, self.expr(e["a"]))
            self.put(f"if ({'' if kind == 'and' else '!'}{result}) {{")
            self.indent += 1
            self.put(f"{result} = {self.expr(e['b'])};")
            self.indent -= 1
            self.put("}")
            return result
        if kind == "cmp":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            return f"({a} {C_CMP[e['op']]} {b})"
        if kind == "bin":
            return self.binary(e, t)
        if kind == "array":
            name = self.temp(t, "{0}")
            for k, item in enumerate(e["elems"]):
                self.put(f"{name}.v[{k}] = {self.expr(item)};")
            return name
        if kind == "repeat":
            value = self.expr(e["elem"])
            name = self.temp(t, "{0}")
            self.put(f"for (int k = 0; k < {t.n}; k++) {name}.v[k] = {value};")
            return name
        raise AssertionError(kind)

    def binary(self, e: dict, t) -> str:
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            if op in ("div", "rem"):
                self.put(f"if ({b} == 0) isy_fail(\"DIV_ZERO\");")
                if op == "div" and self.sabotage == "div_floor":
                    # Sabotaje deliberado: división piso en vez de truncada.
                    exact = f"(((i128){a} / (i128){b}) - ((((i128){a} % (i128){b}) != 0) && ((((i128){a}) < 0) != (((i128){b}) < 0))))"
                else:
                    exact = f"((i128){a} {'/' if op == 'div' else '%'} (i128){b})"
            elif op == "mul" and t.bits == 64 and not t.signed:
                return self.temp(t, f"isy_mul_u64({a}, {b}, {OVF_CODE[t.ovf]})")
            else:
                exact = f"((i128){a} {C_ARITH[op]} (i128){b})"
            return self.temp(t, f"({self.ctype(t)})isy_fit({exact}, {self.fit_args(t)})")
        max_m = c_i128(t.max_m)
        scale = c_i128(10 ** t.s)
        rnd = ROUND_CODE[t.rnd]
        if op in ("add", "sub"):
            return self.temp(t, f"(int64_t)isy_dec_fit((i128){a} {C_ARITH[op]} (i128){b}, {max_m})")
        if op == "mul":
            return self.temp(t, f"(int64_t)isy_dec_fit(isy_rdiv((i128){a} * (i128){b}, {scale}, {rnd}), {max_m})")
        self.put(f"if ({b} == 0) isy_fail(\"DIV_ZERO\");")
        return self.temp(t, f"(int64_t)isy_dec_fit(isy_rdiv((i128){a} * {scale}, (i128){b}, {rnd}), {max_m})")

    def cast(self, e: dict, dst) -> str:
        x = self.expr(e["e"])
        src = ty_from_json(e["e"]["ty"])
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, f"({self.ctype(dst)})isy_fit((i128){x}, {self.fit_args(dst)})")
        if isinstance(src, IntT):
            return self.temp(dst, f"(int64_t)isy_dec_fit((i128){x} * {c_i128(10 ** dst.s)}, {c_i128(dst.max_m)})")
        if isinstance(dst, IntT):
            return self.temp(dst, f"({self.ctype(dst)})isy_fit((i128){x} / {c_i128(10 ** src.s)}, {self.fit_args(dst)})")
        return self.temp(dst, "(int64_t)isy_dec_fit(isy_rdiv((i128){x} * {num}, {den}, {rnd}), {mx})".format(
            x=x, num=c_i128(10 ** dst.s), den=c_i128(10 ** src.s), rnd=ROUND_CODE[dst.rnd],
            mx=c_i128(dst.max_m)))


def emit_c(module: dict, sabotage: str | None = None) -> str:
    return CEmitter(module, sabotage).emit()


# --- backend ISY_BACKEND/1 ------------------------------------------------------------

CFLAGS = ["-std=gnu11", "-O2", "-w"]


def find_cc() -> str:
    for cc in (os.environ.get("ISYCO_CC"), "gcc", "clang", "cc"):
        if cc and shutil.which(cc):
            return cc
    raise RuntimeError("no hay compilador de C (gcc/clang)")


class CBackend(Backend):
    name = "c"
    extension = ".c"
    features = ALL_FEATURES - V2_FEATURES
    sabotages = ("half_even_as_half_up", "div_floor")

    def toolchain(self) -> str | None:
        try:
            cc = find_cc()
        except RuntimeError:
            return None
        first = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.split("\n")[0]
        return f"{cc}: {first}"

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return emit_c(module, sabotage)

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        return [find_cc(), *CFLAGS, *extra_flags, "-o", str(binary), str(source)]


BACKEND = CBackend()


def run_c(data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
          timeout_ms: int | None = 60_000, sabotage: str | None = None,
          extra_flags: tuple = ()) -> tuple[dict, list]:
    """Mismo contrato que interp.run, ejecutando un binario nativo. No produce traza."""
    return BACKEND.run(data, inputs, limits, trace, timeout_ms, sabotage, extra_flags)
