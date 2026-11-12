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

isy-ir/0.2 (CORE v0.3):
- str<N> es `struct { uint32_t len; char v[N]; }` (valor por copia, sin heap);
- cada struct de ISyCoLang es un struct de C con campos `f_<nombre>`; `==` y la
  salida JSON usan funciones generadas por tipo (nunca memcmp: hay relleno y
  bytes más allá de `len`);
- leer números desde texto es exacto con __int128 aunque el texto tenga miles de
  dígitos (wrap toma los bits bajos, trap/sat solo necesitan saber que no cabe);
- en las líneas E/R del protocolo, la barra invertida y el salto de línea van
  escapados (spec/BACKEND.md §3): un str puede contener saltos de línea.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..ir import ty_from_json
from ..pila import con_pila
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical
from .base import ALL_FEATURES, Backend, fn_ident, type_ident

ROUND_CODE = {"half_even": 0, "half_up": 1, "down": 2, "exact": 3}
OVF_CODE = {"trap": 0, "wrap": 1, "sat": 2}
C_CMP = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
C_ARITH = {"add": "+", "sub": "-", "mul": "*"}

RUNTIME = r"""
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

/* ---- isy-ir/0.2: str<N> y salida escapada -------------------------------- */
/* Un byte de la carga de una línea E/R: '\' y '\n' van escapados (BACKEND §3). */
static void isy_out(char c) {
    if (c == '\\') fputs("\\\\", stdout);
    else if (c == '\n') fputs("\\n", stdout);
    else putchar(c);
}
static void isy_put_text(const char *v, uint32_t n) { for (uint32_t i = 0; i < n; i++) isy_out(v[i]); }
/* Texto como string JSON (escapes mínimos, como json.dumps sobre ASCII). */
static void isy_put_json_text(const char *v, uint32_t n) {
    isy_out('"');
    for (uint32_t i = 0; i < n; i++) {
        char c = v[i];
        if (c == '"') { isy_out('\\'); isy_out('"'); }
        else if (c == '\\') { isy_out('\\'); isy_out('\\'); }
        else if (c == '\n') { isy_out('\\'); isy_out('n'); }
        else if (c == '\t') { isy_out('\\'); isy_out('t'); }
        else isy_out(c);
    }
    isy_out('"');
}
static int isy_allowed(i128 c) { return c == 9 || c == 10 || (c >= 32 && c <= 126); }
/* Copia n bytes a un str de capacidad cap; si no caben, OVERFLOW (S3). */
static void isy_str_set(char *dst, uint32_t *dst_len, uint32_t cap, const char *src, uint64_t n) {
    if (n > cap) isy_fail("OVERFLOW");
    memmove(dst, src, (size_t)n);
    *dst_len = (uint32_t)n;
}
static void isy_str_cat(char *dst, uint32_t *dst_len, uint32_t cap,
                        const char *a, uint32_t an, const char *b, uint32_t bn) {
    if ((uint64_t)an + bn > cap) isy_fail("OVERFLOW");
    memmove(dst, a, an);
    memmove(dst + an, b, bn);
    *dst_len = an + bn;
}
static int isy_strcmp(const char *a, uint32_t an, const char *b, uint32_t bn) {
    uint32_t n = an < bn ? an : bn;
    int c = memcmp(a, b, n);   /* sobre bytes como unsigned char: orden de bytes */
    if (c != 0) return c < 0 ? -1 : 1;
    return an < bn ? -1 : an > bn ? 1 : 0;
}
static uint32_t isy_fmt_i128(char *buf, i128 v) {
    char tmp[64];
    int n = 0, neg = v < 0;
    unsigned __int128 u = neg ? (unsigned __int128)(-(v + 1)) + 1 : (unsigned __int128)v;
    do { tmp[n++] = (char)('0' + (int)(u % 10)); u /= 10; } while (u);
    uint32_t k = 0;
    if (neg) buf[k++] = '-';
    while (n) buf[k++] = tmp[--n];
    return k;
}
static uint32_t isy_fmt_dec(char *buf, i128 m, int s) {
    if (s == 0) return isy_fmt_i128(buf, m);
    char tmp[64];
    int n = 0, neg = m < 0;
    unsigned __int128 u = neg ? (unsigned __int128)(-m) : (unsigned __int128)m;
    do { tmp[n++] = (char)('0' + (int)(u % 10)); u /= 10; } while (u);
    while (n < s + 1) tmp[n++] = '0';
    uint32_t k = 0;
    if (neg) buf[k++] = '-';
    while (n > s) buf[k++] = tmp[--n];
    buf[k++] = '.';
    while (n) buf[k++] = tmp[--n];
    return k;
}
/* Dígitos [i, j) -> magnitud. big = el valor real es >= 2^123 (no cabe en ningún
   tipo); aun así mag guarda el valor exacto módulo 2^128, que es lo que wrap necesita. */
static unsigned __int128 isy_digits(const char *s, uint32_t i, uint32_t j, int *big) {
    unsigned __int128 mag = 0;
    *big = 0;
    for (uint32_t k = i; k < j; k++) {
        if (mag >= ((unsigned __int128)1 << 123)) *big = 1;
        mag = mag * 10 + (unsigned)(s[k] - '0');
    }
    if (mag >= ((unsigned __int128)1 << 123)) *big = 1;
    return mag;
}
/* `s as int<...>`: forma canónica de entero (CORE v0.3 §2.5), luego la regla ovf. */
static i128 isy_parse_int(const char *s, uint32_t n, i128 lo, i128 hi, int bits, int ovf) {
    uint32_t i = 0;
    int neg = 0;
    if (n > 0 && s[0] == '-') { neg = 1; i = 1; }
    if (i >= n) isy_fail("BAD_FORMAT");
    for (uint32_t k = i; k < n; k++) if (s[k] < '0' || s[k] > '9') isy_fail("BAD_FORMAT");
    if (s[i] == '0' && n - i > 1) isy_fail("BAD_FORMAT");
    if (neg && n - i == 1 && s[i] == '0') isy_fail("BAD_FORMAT");
    int big;
    unsigned __int128 mag = isy_digits(s, i, n, &big);
    if (!big) return isy_fit(neg ? -(i128)mag : (i128)mag, lo, hi, bits, ovf);
    if (ovf == 0) isy_fail("OVERFLOW");
    if (ovf == 2) return neg ? lo : hi;
    unsigned __int128 u = neg ? (unsigned __int128)0 - mag : mag;
    unsigned __int128 w = (unsigned __int128)1 << bits;
    i128 r = (i128)(u & (w - 1));
    return r > hi ? r - (i128)w : r;
}
/* `s as dec<p,s>`: forma canónica exacta del tipo destino (P3), luego p dígitos. */
static int64_t isy_parse_dec(const char *s, uint32_t n, int scale, i128 max) {
    uint32_t i = 0, k;
    int neg = 0;
    if (n > 0 && s[0] == '-') { neg = 1; i = 1; }
    for (k = i; k < n && s[k] >= '0' && s[k] <= '9'; k++) {}
    if (k == i || (s[i] == '0' && k - i > 1)) isy_fail("BAD_FORMAT");
    uint32_t int_end = k;
    if (scale == 0) {
        if (k != n) isy_fail("BAD_FORMAT");
    } else {
        if (k >= n || s[k] != '.' || n - k - 1 != (uint32_t)scale) isy_fail("BAD_FORMAT");
        for (uint32_t q = k + 1; q < n; q++) if (s[q] < '0' || s[q] > '9') isy_fail("BAD_FORMAT");
    }
    int zero = 1;
    for (uint32_t q = i; q < n; q++) if (s[q] >= '1' && s[q] <= '9') zero = 0;
    if (neg && zero) isy_fail("BAD_FORMAT");
    int big1, big2;
    unsigned __int128 whole = isy_digits(s, i, int_end, &big1);
    unsigned __int128 frac = scale ? isy_digits(s, int_end + 1, n, &big2) : 0;
    if (big1 || whole > (unsigned __int128)max) isy_fail("OVERFLOW");
    unsigned __int128 pow = 1;
    for (int q = 0; q < scale; q++) pow *= 10;
    unsigned __int128 mag = whole * pow + frac;
    if (mag > (unsigned __int128)max) isy_fail("OVERFLOW");
    return neg ? -(int64_t)mag : (int64_t)mag;
}
static int isy_parse_bool(const char *s, uint32_t n) {
    if (n == 4 && memcmp(s, "true", 4) == 0) return 1;
    if (n == 5 && memcmp(s, "false", 5) == 0) return 0;
    isy_fail("BAD_FORMAT");
    return 0;
}
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
        if sabotage not in HALF_EVEN_TIE and sabotage not in ("div_floor", "str_concat_truncates"):
            raise ValueError(sabotage)
        self.module = module
        self.sabotage = sabotage
        self.arrays: dict[str, str] = {}   # json del tipo arreglo -> nombre del struct
        self.typedefs: list[str] = []
        self.helpers: dict[str, tuple[str, str]] = {}   # clave -> (nombre, definición)
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
        if isinstance(t, StrT):
            key = repr(t)
            if key not in self.arrays:
                self.arrays[key] = f"isy_str{t.n}"
                self.typedefs.append(f"typedef struct {{ uint32_t len; char v[{t.n}]; }} isy_str{t.n};")
            return self.arrays[key]
        if isinstance(t, StructT):
            key = repr(t)
            if key not in self.arrays:
                fields = " ".join(f"{self.ctype(ft)} f_{fname};" for fname, ft in t.fields)
                name = f"isy_st{len(self.arrays)}_{type_ident(t.name)}"
                self.arrays[key] = name
                self.typedefs.append(f"typedef struct {{ {fields} }} {name};")
            return self.arrays[key]
        raise AssertionError(t)

    @staticmethod
    def aggregate(t) -> bool:
        return isinstance(t, (ArrT, StrT, StructT))

    # --- funciones generadas por tipo: igualdad y salida JSON (isy-ir/0.2) --------
    def helper(self, kind: str, t, body_fn) -> str:
        key = f"{kind}:{t!r}"
        if key not in self.helpers:
            name = f"isy_{kind}{len(self.helpers)}"
            self.helpers[key] = (name, "")           # reservado antes de generar dependencias
            self.helpers[key] = (name, body_fn(name))
        return self.helpers[key][0]

    def eq_expr(self, t, a: str, b: str) -> str:
        """Igualdad de dos lvalues de tipo t (CORE v0.3 S4/P5), campo por campo."""
        if isinstance(t, StrT):
            return f"({a}.len == {b}.len && memcmp({a}.v, {b}.v, {a}.len) == 0)"
        if isinstance(t, (ArrT, StructT)):
            return f"{self.eq_fn(t)}(&{a}, &{b})"
        return f"({a} == {b})"

    def eq_fn(self, t) -> str:
        def body(name):
            ct = self.ctype(t)
            if isinstance(t, ArrT):
                inner = self.eq_expr(t.elem, "a->v[i]", "b->v[i]")
                code = f"for (uint32_t i = 0; i < {t.n}; i++) if (!{inner}) return 0;\n    return 1;"
            else:
                code = "return " + " && ".join(self.eq_expr(ft, f"a->f_{fn}", f"b->f_{fn}")
                                               for fn, ft in t.fields) + ";"
            return f"static int {name}(const {ct} *a, const {ct} *b) {{\n    {code}\n}}"
        return self.helper("eq", t, body)

    def json_value(self, t, x: str) -> str:
        """Sentencias que imprimen x (lvalue) dentro de un JSON: escalares entre comillas."""
        if isinstance(t, StrT):
            return f"isy_put_json_text({x}.v, {x}.len);"
        if isinstance(t, (ArrT, StructT)):
            return f"{self.put_fn(t)}(&{x});"
        return f"isy_out('\"'); {self.put_call(t, x)}; isy_out('\"');"

    def put_fn(self, t) -> str:
        def body(name):
            ct = self.ctype(t)
            if isinstance(t, ArrT):
                code = (f"isy_out('['); for (uint32_t i = 0; i < {t.n}; i++) {{ if (i) isy_out(','); "
                        f"{self.json_value(t.elem, 'x->v[i]')} }} isy_out(']');")
            else:
                parts = []
                for k, (fn, ft) in enumerate(t.fields):
                    sep = "," if k else ""
                    parts.append(f'fputs("{sep}\\"{fn}\\":", stdout); {self.json_value(ft, f"x->f_{fn}")}')
                code = "isy_out('{'); " + " ".join(parts) + " isy_out('}');"
            return f"static void {name}(const {ct} *x) {{\n    {code}\n}}"
        return self.helper("put", t, body)

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
        # Prototipos primero: un helper se reserva antes que los de sus campos.
        helpers = [d.split("\n")[0].rstrip(" {") + ";" for _, d in self.helpers.values()]
        helpers += [definition for _, definition in self.helpers.values()]
        return "\n".join([
            f"/* generado por isyco.backends.c desde ISY-IR {self.module['source_sha256']} */",
            runtime, *self.typedefs, "", *helpers, "", *protos, "", *bodies, main_src, ""])

    def signature(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        params = ", ".join(f"{self.ctype(types[p])} l{p}" for p in fn["params"]) or "void"
        return f"static {'void' if ret is None else self.ctype(ret)} {fn_ident(fn['name'])}({params})"

    def function(self, fn: dict) -> str:
        self.fn, self.tmp, self.lines, self.indent = fn, 0, [], 1
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        for i, t in enumerate(self.local_types):
            if i not in fn["params"]:
                self.put(f"{self.ctype(t)} l{i} = {{0}};" if self.aggregate(t)
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
        count = sum(self.leaf_count(types[p]) for p in fn["params"])
        lines.append(f"    if (argc != {4 + count}) return 2;")
        lines.append("    isy_max_steps = strtoull(argv[1], 0, 10);")
        lines.append("    isy_max_depth = strtoull(argv[2], 0, 10);")
        lines.append("    isy_max_emits = strtoull(argv[3], 0, 10);")
        argi = 4
        names = []
        for p in fn["params"]:
            t = types[p]
            names.append(f"a{p}")
            lines.append(f"    {self.ctype(t)} a{p}{' = {0}' if self.aggregate(t) else ''};")
            argi = self.read_args(t, f"a{p}", argi, lines)
        call = f"f_main({', '.join(names)})"
        if ret is None:
            lines.append(f"    {call};")
        else:
            lines.append(f"    {self.ctype(ret)} r = {call};")
            lines.append("    fputs(\"R \", stdout);")
            lines.append(f"    {self.put_top(ret, 'r')}")
        lines += ["    isy_end(\"HALTED\", NULL);", "    return 0;", "}"]
        return "\n".join(lines)

    def leaf_count(self, t) -> int:
        if isinstance(t, ArrT):
            return t.n * self.leaf_count(t.elem)
        if isinstance(t, StructT):
            return sum(self.leaf_count(ft) for _, ft in t.fields)
        return 1

    def read_args(self, t, target: str, argi: int, lines: list) -> int:
        """Lee el argumento aplanado (ISY_BACKEND/1 §3) en target; devuelve el siguiente índice."""
        if isinstance(t, ArrT):
            for k in range(t.n):
                argi = self.read_args(t.elem, f"{target}.v[{k}]", argi, lines)
            return argi
        if isinstance(t, StructT):
            for fname, ft in t.fields:
                argi = self.read_args(ft, f"{target}.f_{fname}", argi, lines)
            return argi
        if isinstance(t, StrT):
            lines.append(f"    {{ size_t n = strlen(argv[{argi}]); {target}.len = (uint32_t)n; "
                         f"memcpy({target}.v, argv[{argi}], n); }}")
            return argi + 1
        lines.append(f"    {target} = ({self.ctype(t)}){self.parse_arg(t, argi)};")
        return argi + 1

    def put_top(self, t, value: str) -> str:
        """Carga de una línea E/R: escalar canónico, str tal cual, arreglo/struct como JSON."""
        if isinstance(t, StrT):
            return f"isy_put_text({value}.v, {value}.len); putchar('\\n');"
        if isinstance(t, (ArrT, StructT)):
            return f"{{ {self.ctype(t)} isy_pv = {value}; {self.put_fn(t)}(&isy_pv); }} putchar('\\n');"
        return f"{self.put_call(t, value)}; putchar('\\n');"

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
        elif kind == "set_path":
            keys = [self.expr(step["index"]) if "index" in step else None for step in s["path"]]
            value = self.expr(s["value"])
            target, t = f"l{s['local']}", self.local_types[s["local"]]
            for step, key in zip(s["path"], keys):     # rangos al guardar, en orden (E8)
                if "index" in step:
                    self.put(f"if ((i128){key} < 0 || (i128){key} >= {t.n}) isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
                    target, t = f"{target}.v[{key}]", t.elem
                else:
                    target, t = f"{target}.f_{step['field']}", t.field(step["field"])
            self.put(f"{target} = {value};")
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
            self.put(f"fputs(\"E \", stdout); {self.put_top(t, value)}")
        elif kind == "call":
            args = [self.expr(a) for a in s["args"]]
            self.put(f"{fn_ident(s['fn'])}({', '.join(args)});")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        """Emite las sentencias previas necesarias y devuelve una expresión C sin efectos."""
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, StrT):
                name = self.temp(t, "{0}")
                self.put(f"{name}.len = {len(value)}; memcpy({name}.v, {c_string(value)}, {len(value)});")
                return name
            if isinstance(t, BoolT):
                return "1" if value else "0"
            return f"(({self.ctype(t)}){c_i128(value)})"
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = [self.expr(a) for a in e["args"]]
            return self.temp(t, f"{fn_ident(e['fn'])}({', '.join(args)})")
        if kind == "index" and isinstance(ty_from_json(e["base"]["ty"]), StrT):
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            self.put(f"if ((i128){index} < 0 || (i128){index} >= (i128){base}.len) "
                     f"isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            return self.temp(t, f"(uint8_t){base}.v[{index}]")
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
            at = ty_from_json(e["a"]["ty"])
            if isinstance(at, StrT):
                return f"(isy_strcmp({a}.v, {a}.len, {b}.v, {b}.len) {C_CMP[e['op']]} 0)"
            if isinstance(at, (ArrT, StructT)):
                ta, tb = self.temp(at, a), self.temp(at, b)
                return f"({'' if e['op'] == 'eq' else '!'}{self.eq_expr(at, ta, tb)})"
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
        return self.expr_v2(kind, e, t)

    def expr_v2(self, kind: str, e: dict, t) -> str:
        """Nodos de isy-ir/0.2 (CORE v0.3)."""
        if kind == "concat":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            name = self.temp(t, "{0}")
            if self.sabotage == "str_concat_truncates":
                # Sabotaje deliberado: cortar en silencio en vez de OVERFLOW (viola S3).
                self.put(f"{{ uint32_t n1 = {a}.len < {t.n} ? {a}.len : {t.n}; "
                         f"uint32_t n2 = n1 + {b}.len > {t.n} ? {t.n} - n1 : {b}.len; "
                         f"memmove({name}.v, {a}.v, n1); memmove({name}.v + n1, {b}.v, n2); "
                         f"{name}.len = n1 + n2; }}")
                return name
            self.put(f"isy_str_cat({name}.v, &{name}.len, {t.n}, {a}.v, {a}.len, {b}.v, {b}.len);")
            return name
        if kind == "widen":
            x = self.expr(e["e"])
            name = self.temp(t, "{0}")
            self.put(f"isy_str_set({name}.v, &{name}.len, {t.n}, {x}.v, {x}.len);")
            return name
        if kind == "len":
            return f"((int64_t){self.expr(e['e'])}.len)"
        if kind == "slice":
            x = self.expr(e["e"])
            lo = self.expr(e["lo"])
            hi = self.expr(e["hi"])
            self.put(f"if ((i128){lo} < 0 || (i128){lo} > (i128){hi} || (i128){hi} > (i128){x}.len) "
                     f"isy_fail(\"INDEX_OUT_OF_BOUNDS\");")
            name = self.temp(t, "{0}")
            self.put(f"isy_str_set({name}.v, &{name}.len, {t.n}, {x}.v + (size_t){lo}, "
                     f"(uint64_t)((i128){hi} - (i128){lo}));")
            return name
        if kind == "chr":
            code = self.expr(e["e"])
            self.put(f"if (!isy_allowed((i128){code})) isy_fail(\"BAD_CHAR\");")
            name = self.temp(t, "{0}")
            self.put(f"{name}.len = 1; {name}.v[0] = (char){code};")
            return name
        if kind == "field":
            return f"{self.expr(e['base'])}.f_{e['name']}"
        if kind == "struct":
            name = self.temp(t, "{0}")
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
        if isinstance(src, StrT) or isinstance(dst, StrT):
            return self.str_cast(x, src, dst)
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(dst, f"({self.ctype(dst)})isy_fit((i128){x}, {self.fit_args(dst)})")
        if isinstance(src, IntT):
            return self.temp(dst, f"(int64_t)isy_dec_fit((i128){x} * {c_i128(10 ** dst.s)}, {c_i128(dst.max_m)})")
        if isinstance(dst, IntT):
            return self.temp(dst, f"({self.ctype(dst)})isy_fit((i128){x} / {c_i128(10 ** src.s)}, {self.fit_args(dst)})")
        return self.temp(dst, "(int64_t)isy_dec_fit(isy_rdiv((i128){x} * {num}, {den}, {rnd}), {mx})".format(
            x=x, num=c_i128(10 ** dst.s), den=c_i128(10 ** src.s), rnd=ROUND_CODE[dst.rnd],
            mx=c_i128(dst.max_m)))


    def str_cast(self, x: str, src, dst) -> str:
        """CORE v0.3 §2.5: conversiones con str en forma canónica."""
        if isinstance(dst, StrT):
            name = self.temp(dst, "{0}")
            if isinstance(src, StrT):
                self.put(f"isy_str_set({name}.v, &{name}.len, {dst.n}, {x}.v, {x}.len);")
                return name
            self.tmp += 1
            buf = f"b{self.tmp}"
            self.put(f"char {buf}[64]; uint32_t {buf}n;")
            if isinstance(src, BoolT):
                self.put(f"{buf}n = {x} ? 4 : 5; memcpy({buf}, {x} ? \"true\" : \"false\", {buf}n);")
            elif isinstance(src, IntT):
                self.put(f"{buf}n = isy_fmt_i128({buf}, (i128){x});")
            else:
                self.put(f"{buf}n = isy_fmt_dec({buf}, (i128){x}, {src.s});")
            self.put(f"isy_str_set({name}.v, &{name}.len, {dst.n}, {buf}, {buf}n);")
            return name
        if isinstance(dst, BoolT):
            return self.temp(dst, f"isy_parse_bool({x}.v, {x}.len)")
        if isinstance(dst, IntT):
            return self.temp(dst, f"({self.ctype(dst)})isy_parse_int({x}.v, {x}.len, {self.fit_args(dst)})")
        return self.temp(dst, f"isy_parse_dec({x}.v, {x}.len, {dst.s}, {c_i128(dst.max_m)})")


def c_string(text: str) -> str:
    """Literal de C con exactamente esos bytes (solo ASCII permitido, P1)."""
    out = []
    for c in text:
        if c in '\\"?':
            out.append("\\" + c)
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


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
    features = ALL_FEATURES
    sabotages = ("half_even_as_half_up", "div_floor", "str_concat_truncates")

    def toolchain(self) -> str | None:
        try:
            cc = find_cc()
        except RuntimeError:
            return None
        first = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.split("\n")[0]
        return f"{cc}: {first}"

    @con_pila
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
