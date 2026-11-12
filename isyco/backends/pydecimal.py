"""Backend Python decimal: ISY-IR v0.1 -> Python 3 (modulo `decimal`) -> shebang ejecutable.

Ola 2 de F5 (spec/BACKEND.md §6). Implementa la misma semántica que los backends
nativos, pero con otro sustrato: los valores `dec` son `decimal.Decimal` (la
referencia usa enteros escalados), las sumas/restas y comparaciones pasan por el
módulo `decimal`, y TODO redondeo decide con los dígitos que genera la división y
`quantize` de CPython (`iny_rdiv`), no con aritmética entera hecha a mano.

Contrato del binario generado: idéntico a los nativos (ISY_BACKEND/1 §3):

    ./prog MAX_STEPS MAX_CALL_DEPTH MAX_EMITS ARG...

`compile_cmd` solo valida sintaxis (`py_compile`), copia y marca +x: el
"binario" es el fuente con shebang `#!/usr/bin/env python3`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import ALL_FEATURES, Backend, fn_ident
from ..ir import ty_from_json
from ..pila import con_pila
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical

SABOTAGES = ("half_even_as_half_up", "div_floor", "str_concat_truncates")
OVF_CODE = {"trap": 0, "wrap": 1, "sat": 2}

RUNTIME = r"""
import json
import sys
from decimal import Decimal, Inexact, ROUND_DOWN, getcontext, localcontext

sys.setrecursionlimit(10000)
getcontext().prec = 999
_DEC_TENTH = Decimal("0.1")

isy_steps = isy_depth = isy_emits = 0
isy_max_steps = isy_max_depth = isy_max_emits = 0


def isy_end(status, code):
    sys.stdout.write("X %s %s %d\n" % (status, code if code else "-", isy_steps))
    sys.stdout.flush()
    sys.exit(0)


def isy_fail(code):
    isy_end("ERROR", code)


def isy_limit(code):
    isy_end("LIMIT_REACHED", code)


def isy_tick():
    global isy_steps
    isy_steps += 1
    if isy_steps > isy_max_steps:
        isy_limit("max_steps")


def isy_enter():
    global isy_depth
    isy_tick()
    if isy_depth + 1 > isy_max_depth:
        isy_limit("max_call_depth")
    isy_depth += 1


def isy_leave():
    global isy_depth
    isy_depth -= 1


def isy_emit_check():
    global isy_emits
    if isy_emits >= isy_max_emits:
        isy_limit("max_emits")
    isy_emits += 1


def isy_fit(v, lo, hi, bits, ovf):
    if lo <= v <= hi:
        return v
    if ovf == 0:
        isy_fail("OVERFLOW")
    if ovf == 2:
        return hi if v > hi else lo
    w = 1 << bits
    return ((v - lo) % w) + lo


def isy_trunc_div(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def isy_trunc_rem(a, b):
    return a - isy_trunc_div(a, b) * b


def isy_rdiv(num, den, mode):
    # Cociente num/den redondeado UNA vez a entero (spec §3.5). La decisión
    # (dígito de décimos y si hay dígitos más allá) la toman la división y
    # `quantize` del módulo `decimal`, con truncamiento y la bandera Inexact.
    q = isy_trunc_div(num, den)
    if num - q * den == 0:
        return q
    if mode == "exact":
        isy_fail("INEXACT")
    if mode == "down":
        return q
    sign = -1 if (num < 0) != (den < 0) else 1
    with localcontext() as ctx:
        ctx.prec = len(str(abs(q))) + 2
        ctx.rounding = ROUND_DOWN
        t = (Decimal(num) / Decimal(den)).quantize(_DEC_TENTH)
        beyond = bool(ctx.flags[Inexact])
    last = t.as_tuple().digits[-1]
    if last < 5:
        return q
    if last > 5 or beyond or mode == "half_up":
        return q + sign
    ISY_TIE


def isy_dec_fit(m, mx):
    if m > mx or m < -mx:
        isy_fail("OVERFLOW")
    return m


def isy_m(v, s):
    # Valor dec (Decimal en unidades de 10^-s) -> entero escalado exacto.
    return int(v.scaleb(s))


def isy_mkdec(m, s):
    return Decimal(m).scaleb(-s)


def isy_fmt_dec(m, s):
    if s == 0:
        return str(m)
    digits = str(abs(m)).zfill(s + 1)
    return ("-" if m < 0 else "") + digits[:-s] + "." + digits[-s:]


def isy_escape(text):
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def isy_str_set(x, cap):
    if len(x) > cap:
        isy_fail("OVERFLOW")
    return x


def isy_str_cat(a, b, cap):
    if len(a) + len(b) > cap:
        isy_fail("OVERFLOW")
    return a + b


def isy_str_cat_trunc(a, b, cap):
    n1 = len(a) if len(a) < cap else cap
    n2 = cap - n1 if n1 + len(b) > cap else len(b)
    return a[:n1] + b[:n2]


def isy_slice(x, lo, hi, cap):
    if lo < 0 or lo > hi or hi > len(x):
        isy_fail("INDEX_OUT_OF_BOUNDS")
    return isy_str_set(x[lo:hi], cap)


def isy_chr(code):
    if code != 9 and code != 10 and not (32 <= code <= 126):
        isy_fail("BAD_CHAR")
    return chr(code)


def isy_copy(v):
    if isinstance(v, list):
        return [isy_copy(x) for x in v]
    if isinstance(v, dict):
        return {k: isy_copy(x) for k, x in v.items()}
    return v


def isy_parse_bool(x):
    if x == "true":
        return True
    if x == "false":
        return False
    isy_fail("BAD_FORMAT")


def isy_parse_int(x, lo, hi, bits, ovf):
    i = 1 if x[:1] == "-" else 0
    if i >= len(x):
        isy_fail("BAD_FORMAT")
    body = x[i:]
    if any(c < "0" or c > "9" for c in body):
        isy_fail("BAD_FORMAT")
    if body[:1] == "0" and len(body) > 1:
        isy_fail("BAD_FORMAT")
    if i == 1 and body == "0":
        isy_fail("BAD_FORMAT")
    return isy_fit(int(x), lo, hi, bits, ovf)


def isy_parse_dec(x, scale, mx):
    i = 1 if x[:1] == "-" else 0
    n = len(x)
    k = i
    while k < n and "0" <= x[k] <= "9":
        k += 1
    if k == i or (x[i:i + 1] == "0" and k - i > 1):
        isy_fail("BAD_FORMAT")
    int_end = k
    if scale == 0:
        if k != n:
            isy_fail("BAD_FORMAT")
    else:
        if k >= n or x[k] != "." or n - k - 1 != scale:
            isy_fail("BAD_FORMAT")
        if any(c < "0" or c > "9" for c in x[k + 1:]):
            isy_fail("BAD_FORMAT")
    if i == 1 and all(c == "0" or c == "." for c in x[i:]):
        isy_fail("BAD_FORMAT")
    whole = int(x[i:int_end])
    frac = int(x[int_end + 1:]) if scale else 0
    if whole > mx:
        isy_fail("OVERFLOW")
    m = whole * 10 ** scale + frac
    if m > mx:
        isy_fail("OVERFLOW")
    return isy_mkdec(-m if i == 1 else m, scale)
"""

TIE_CODE = {
    None: 'return q if q % 2 == 0 else q + sign',
    # Sabotaje deliberado: half_even se comporta como half_up en los empates.
    "half_even_as_half_up": 'return q + sign',
}


def py_str(text: str) -> str:
    """Literal de Python con exactamente esos bytes (repr: solo ASCII, P1)."""
    return repr(text)


class PyEmitter:
    def __init__(self, module: dict, sabotage: str | None = None):
        if sabotage not in TIE_CODE and sabotage not in ("div_floor", "str_concat_truncates"):
            raise ValueError(sabotage)
        self.module = module
        self.sabotage = sabotage
        self.lines: list[str] = []
        self.indent = 1
        self.tmp = 0
        self.fn: dict | None = None
        self.local_types: list = []

    def fn_by_name(self, name: str) -> dict:
        return self.functions_by_name[name]

    def call_args(self, fn: dict, args_expr: list[str]) -> list[str]:
        """Argumentos copiados donde su tipo es agregado: la llamada es por valor
        (CORE §3.2); sin la copia, la mutación del parámetro se fugaría al
        valor del llamador (033/233 del corpus lo verifican)."""
        types = [ty_from_json(fn["locals"][p]["ty"]) for p in fn["params"]]
        return [self.cp(t, a) for t, a in zip(types, args_expr)]

    # --- utilidades de emisión ------------------------------------------------
    def put(self, line: str) -> None:
        self.lines.append("    " * self.indent + line)

    def temp(self, value: str) -> str:
        self.tmp += 1
        name = f"t{self.tmp}"
        self.put(f"{name} = {value}")
        return name

    @staticmethod
    def aggregate(t) -> bool:
        # str es inmutable en Python: la referencia es el valor. Copiar solo agrega.
        return isinstance(t, (ArrT, StructT))

    def cp(self, t, value: str) -> str:
        """Valor almacenado: los agredados se copian por valor (CORE §3, sin aliasing)."""
        return f"isy_copy({value})" if self.aggregate(t) else value

    def put_top(self, t, v: str) -> str:
        """Expresión que produce la carga de una línea E/R (sin el prefijo)."""
        if isinstance(t, StrT):
            return f"isy_escape({v})"
        if isinstance(t, (ArrT, StructT)):
            # El JSON va por la misma salida escapada que los demás (isy_out):
            # el backslash del escape JSON se dobla para que el parse lo revierta.
            return f"isy_escape(json.dumps({self.json_of(t, v, 0)}, separators=(',', ':')))"
        if isinstance(t, BoolT):
            return f"('true' if {v} else 'false')"
        if isinstance(t, IntT):
            return f"str({v})"
        return f"isy_fmt_dec(isy_m({v}, {t.s}), {t.s})"

    def json_of(self, t, v: str, depth: int) -> str:
        """Expresión Python con el valor JSON (escalares como strings, §10.2)."""
        if isinstance(t, StrT):
            return v
        if isinstance(t, BoolT):
            return f"('true' if {v} else 'false')"
        if isinstance(t, IntT):
            return f"str({v})"
        if isinstance(t, DecT):
            return f"isy_fmt_dec(isy_m({v}, {t.s}), {t.s})"
        if isinstance(t, ArrT):
            e = f"e{depth}"
            return f"[{self.json_of(t.elem, e, depth + 1)} for {e} in {v}]"
        parts = ", ".join(f"{fn!r}: {self.json_of(ft, f'{v}[{fn!r}]', depth + 1)}"
                          for fn, ft in t.fields)
        return "{" + parts + "}"

    # --- módulo ---------------------------------------------------------------
    def emit(self) -> str:
        self.functions_by_name = {f["name"]: f for f in self.module["functions"]}
        functions = [self.function(fn) for fn in self.module["functions"]]
        main_src = self.main_src(next(f for f in self.module["functions"]
                                      if f["name"] == "main"))
        runtime = RUNTIME.replace("ISY_TIE", TIE_CODE.get(self.sabotage, TIE_CODE[None]))
        return "\n".join([
            "#!/usr/bin/env python3",
            f"# generado por isyco.backends.pydecimal desde ISY-IR "
            f"{self.module['source_sha256']}",
            runtime, *functions, main_src, ""])

    def function(self, fn: dict) -> str:
        self.fn, self.tmp, self.lines, self.indent = fn, 0, [], 1
        self.local_types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        params = ", ".join(f"l{p}" for p in fn["params"])
        header = f"def {fn_ident(fn['name'])}({params}):"
        self.put("isy_enter()")
        self.block(fn["body"])
        if fn["ret"] is None:
            self.put("isy_leave()")
            self.put("return")
        else:
            self.put('raise RuntimeError("inalcanzable: el validador exige retorno en todo camino")')
        return header + "\n" + "\n".join(self.lines)

    def leaf_count(self, t) -> int:
        if isinstance(t, ArrT):
            return t.n * self.leaf_count(t.elem)
        if isinstance(t, StructT):
            return sum(self.leaf_count(ft) for _, ft in t.fields)
        return 1

    def read_arg(self, t, argv: str, i: int) -> tuple[str, int]:
        """Argumento aplanado (ISY_BACKEND/1 §3) -> expresión que reconstruye el valor."""
        if isinstance(t, ArrT):
            items, k = [], i
            for _ in range(t.n):
                item, k = self.read_arg(t.elem, argv, k)
                items.append(item)
            return "[" + ", ".join(items) + "]", k
        if isinstance(t, StructT):
            parts, k = [], i
            for fname, ft in t.fields:
                item, k = self.read_arg(ft, argv, k)
                parts.append(f"{fname!r}: {item}")
            return "{" + ", ".join(parts) + "}", k
        if isinstance(t, StrT):
            return f"{argv}[{i}]", i + 1
        if isinstance(t, BoolT):
            return f"({argv}[{i}] == '1')", i + 1
        if isinstance(t, IntT):
            return f"int({argv}[{i}])", i + 1
        return f"isy_mkdec(int({argv}[{i}]), {t.s})", i + 1

    def main_src(self, fn: dict) -> str:
        types = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        ret = ty_from_json(fn["ret"])
        count = sum(self.leaf_count(types[p]) for p in fn["params"])
        lines = ["# --- arranque: argumentos crudos y documento de resultado (CORE §10.2) ---",
                 "if __name__ == '__main__':",
                 "    _a = sys.argv[1:]",
                 f"    if len(_a) != {3 + count}:",
                 "        sys.exit(2)",
                 "    isy_max_steps = int(_a[0])",
                 "    isy_max_depth = int(_a[1])",
                 "    isy_max_emits = int(_a[2])"]
        names, i = [], 3
        for p in fn["params"]:
            expr, i = self.read_arg(types[p], "_a", i)
            names.append(expr)
        call = f"{fn_ident('main')}({', '.join(names)})"
        if ret is None:
            lines.append(f"    {call}")
        else:
            lines.append(f"    _r = {call}")
            lines.append(f"    print('R ' + {self.put_top(ret, '_r')})")
        lines.append("    isy_end('HALTED', None)")
        return "\n".join(lines)

    # --- sentencias -----------------------------------------------------------
    def block(self, stmts: list) -> None:
        for s in stmts:
            self.stmt(s)

    def nested(self, header: str, stmts: list, footer: str | None = None) -> None:
        self.put(header)
        self.indent += 1
        self.block(stmts)
        self.indent -= 1
        if footer is not None:
            self.put(footer)

    def stmt(self, s: dict) -> None:
        kind = s["s"]
        self.put(f"isy_tick()  # {kind} {s['at']}")
        if kind in ("let", "set"):
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            self.put(f"l{s['local']} = {self.cp(t, value)}")
        elif kind == "set_index":
            index = self.expr(s["index"])
            value = self.expr(s["value"])
            arr = self.local_types[s["local"]]
            self.put(f"if not (0 <= ({index}) < {arr.n}): "
                     f"isy_fail('INDEX_OUT_OF_BOUNDS')")
            self.put(f"l{s['local']}[{index}] = {self.cp(arr.elem, value)}")
        elif kind == "set_path":
            keys = [self.expr(step["index"]) if "index" in step else None
                    for step in s["path"]]
            value = self.expr(s["value"])
            target, t = f"l{s['local']}", self.local_types[s["local"]]
            for step, key in zip(s["path"], keys):     # rangos al guardar, en orden (E8)
                if "index" in step:
                    self.put(f"if not (0 <= ({key}) < {t.n}): "
                             f"isy_fail('INDEX_OUT_OF_BOUNDS')")
                    target, t = f"{target}[{key}]", t.elem
                else:
                    target, t = f"{target}[{step['field']!r}]", t.field(step["field"])
            self.put(f"{target} = {self.cp(t, value)}")
        elif kind == "if":
            cond = self.expr(s["cond"])
            self.nested(f"if ({cond}):", s["then"])
            if s["else"] is not None:
                self.nested("else:", s["else"])
        elif kind == "while":
            self.put("while True:")
            self.indent += 1
            self.put("isy_tick()")
            cond = self.expr(s["cond"])
            self.put(f"if not ({cond}): break")
            self.block(s["body"])
            self.indent -= 1
        elif kind == "break":
            self.put("break")
        elif kind == "continue":
            self.put("continue")
        elif kind == "return":
            if s["value"] is None:
                self.put("isy_leave()")
                self.put("return")
            else:
                value = self.expr(s["value"])
                self.put("isy_leave()")
                self.put(f"return {value}")
        elif kind == "emit":
            value = self.expr(s["value"])
            t = ty_from_json(s["value"]["ty"])
            self.put("isy_emit_check()")
            self.put(f"print('E ' + {self.put_top(t, value)})")
        elif kind == "call":
            args = self.call_args(self.fn_by_name(s["fn"]),
                                  [self.expr(a) for a in s["args"]])
            self.put(f"{fn_ident(s['fn'])}({', '.join(args)})")
        else:
            raise AssertionError(kind)

    # --- expresiones ----------------------------------------------------------
    def expr(self, e: dict) -> str:
        """Emite las sentencias previas necesarias y devuelve una expresión pura de Python."""
        kind = e["k"]
        t = ty_from_json(e["ty"])
        if kind == "const":
            value = parse_canonical(e["v"], t)
            if isinstance(t, StrT):
                return py_str(value)
            if isinstance(t, BoolT):
                return "True" if value else "False"
            if isinstance(t, DecT):
                return f"isy_mkdec({value}, {t.s})"
            return repr(value)
        if kind == "local":
            return f"l{e['id']}"
        if kind == "call":
            args = self.call_args(self.fn_by_name(e["fn"]),
                                  [self.expr(a) for a in e["args"]])
            return self.temp(f"{fn_ident(e['fn'])}({', '.join(args)})")
        if kind == "index":
            base = self.expr(e["base"])
            index = self.expr(e["index"])
            bt = ty_from_json(e["base"]["ty"])
            bound = f"len({base})" if isinstance(bt, StrT) else str(bt.n)
            self.put(f"if not (0 <= ({index}) < ({bound})): "
                     f"isy_fail('INDEX_OUT_OF_BOUNDS')")
            if isinstance(bt, StrT):
                return self.temp(f"ord({base}[{index}])")
            return self.temp(f"{base}[{index}]")
        if kind == "cast":
            return self.cast(e, t)
        if kind == "not":
            return f"(not {self.expr(e['e'])})"
        if kind == "neg":
            x = self.expr(e["e"])
            if isinstance(t, IntT):
                return self.temp(f"isy_fit(-({x}), {t.lo}, {t.hi}, {t.bits}, "
                                 f"{OVF_CODE[t.ovf]})")
            return self.temp(f"isy_mkdec(isy_dec_fit(-isy_m({x}, {t.s}), "
                             f"{t.max_m}), {t.s})")
        if kind in ("and", "or"):
            result = self.temp(self.expr(e["a"]))
            self.put(f"if {'(' if kind == 'and' else 'not ('}{result}):")
            self.indent += 1
            self.put(f"{result} = {self.expr(e['b'])}")
            self.indent -= 1
            return result
        if kind == "cmp":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            op = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=",
                  "gt": ">", "ge": ">="}[e["op"]]
            return f"({a} {op} {b})"
        if kind == "bin":
            return self.binary(e, t)
        if kind == "array":
            items = [self.cp(t.elem, self.expr(item)) for item in e["elems"]]
            return self.temp("[" + ", ".join(items) + "]")
        if kind == "repeat":
            value = self.expr(e["elem"])
            if self.aggregate(t.elem):
                return self.temp(f"[isy_copy({value}) for _ in range({t.n})]")
            return self.temp(f"[{value}] * {t.n}")
        return self.expr_v2(kind, e, t)

    def expr_v2(self, kind: str, e: dict, t) -> str:
        """Nodos de isy-ir/0.2 (CORE v0.3)."""
        if kind == "concat":
            a = self.expr(e["a"])
            b = self.expr(e["b"])
            if self.sabotage == "str_concat_truncates":
                # Sabotaje deliberado: cortar en silencio en vez de OVERFLOW (viola S3).
                return self.temp(f"isy_str_cat_trunc({a}, {b}, {t.n})")
            return self.temp(f"isy_str_cat({a}, {b}, {t.n})")
        if kind == "widen":
            x = self.expr(e["e"])
            return self.temp(f"isy_str_set({x}, {t.n})")
        if kind == "len":
            return f"len({self.expr(e['e'])})"
        if kind == "slice":
            x = self.expr(e["e"])
            lo = self.expr(e["lo"])
            hi = self.expr(e["hi"])
            return self.temp(f"isy_slice({x}, {lo}, {hi}, {t.n})")
        if kind == "chr":
            code = self.expr(e["e"])
            return self.temp(f"isy_chr({code})")
        if kind == "field":
            return f"{self.expr(e['base'])}[{e['name']!r}]"
        if kind == "struct":
            # En el orden escrito: es el orden de evaluación.
            parts = []
            for item in e["fields"]:
                value = self.expr(item["value"])
                ft = ty_from_json(item["value"]["ty"])
                parts.append(f"{item['name']!r}: {self.cp(ft, value)}")
            return self.temp("{" + ", ".join(parts) + "}")
        raise AssertionError(kind)

    def binary(self, e: dict, t) -> str:
        a = self.expr(e["a"])
        b = self.expr(e["b"])
        op = e["op"]
        if isinstance(t, IntT):
            lo, hi, bits, ovf = t.lo, t.hi, t.bits, OVF_CODE[t.ovf]
            if op in ("div", "rem"):
                self.put(f"if ({b}) == 0: isy_fail('DIV_ZERO')")
                if op == "div":
                    expr = f"{a} // {b}" if self.sabotage == "div_floor" \
                        else f"isy_trunc_div({a}, {b})"
                else:
                    expr = f"isy_trunc_rem({a}, {b})"
                return self.temp(f"isy_fit({expr}, {lo}, {hi}, {bits}, {ovf})")
            if op == "neg":
                raise AssertionError("neg es un nodo propio")
            arith = {"add": "+", "sub": "-", "mul": "*"}[op]
            return self.temp(f"isy_fit({a} {arith} {b}, {lo}, {hi}, {bits}, {ovf})")
        mx, scale, rnd = t.max_m, 10 ** t.s, t.rnd
        if op in ("add", "sub"):
            arith = "+" if op == "add" else "-"
            return self.temp(f"isy_mkdec(isy_dec_fit(isy_m({a} {arith} {b}, {t.s}), "
                             f"{mx}), {t.s})")
        if op == "mul":
            return self.temp(f"isy_mkdec(isy_dec_fit(isy_rdiv(isy_m({a}, {t.s}) * "
                             f"isy_m({b}, {t.s}), {scale}, '{rnd}'), {mx}), {t.s})")
        self.put(f"if ({b}) == 0: isy_fail('DIV_ZERO')")
        return self.temp(f"isy_mkdec(isy_dec_fit(isy_rdiv(isy_m({a}, {t.s}) * {scale}, "
                         f"isy_m({b}, {t.s}), '{rnd}'), {mx}), {t.s})")

    def cast(self, e: dict, dst) -> str:
        x = self.expr(e["e"])
        src = ty_from_json(e["e"]["ty"])
        if isinstance(src, StrT) or isinstance(dst, StrT):
            return self.str_cast(x, src, dst)
        if isinstance(src, IntT) and isinstance(dst, IntT):
            return self.temp(f"isy_fit({x}, {dst.lo}, {dst.hi}, {dst.bits}, "
                             f"{OVF_CODE[dst.ovf]})")
        if isinstance(src, IntT):
            return self.temp(f"isy_mkdec(isy_dec_fit({x} * {10 ** dst.s}, "
                             f"{dst.max_m}), {dst.s})")
        if isinstance(dst, IntT):
            return self.temp(f"isy_fit(isy_trunc_div(isy_m({x}, {src.s}), "
                             f"{10 ** src.s}), {dst.lo}, {dst.hi}, {dst.bits}, "
                             f"{OVF_CODE[dst.ovf]})")
        return self.temp(f"isy_mkdec(isy_dec_fit(isy_rdiv(isy_m({x}, {src.s}) * "
                         f"{10 ** dst.s}, {10 ** src.s}, '{dst.rnd}'), {dst.max_m}), "
                         f"{dst.s})")

    def str_cast(self, x: str, src, dst) -> str:
        """CORE v0.3 §2.5: conversiones con str en forma canónica."""
        if isinstance(dst, StrT):
            if isinstance(src, StrT):
                return self.temp(f"isy_str_set({x}, {dst.n})")
            if isinstance(src, BoolT):
                text = f"('true' if {x} else 'false')"
            elif isinstance(src, IntT):
                text = f"str({x})"
            else:
                text = f"isy_fmt_dec(isy_m({x}, {src.s}), {src.s})"
            return self.temp(f"isy_str_set({text}, {dst.n})")
        if isinstance(dst, BoolT):
            return self.temp(f"isy_parse_bool({x})")
        if isinstance(dst, IntT):
            return self.temp(f"isy_parse_int({x}, {dst.lo}, {dst.hi}, {dst.bits}, "
                             f"{OVF_CODE[dst.ovf]})")
        return self.temp(f"isy_parse_dec({x}, {dst.s}, {dst.max_m})")


def emit_py(module: dict, sabotage: str | None = None) -> str:
    return PyEmitter(module, sabotage).emit()


# --- backend ISY_BACKEND/1 ------------------------------------------------------------


class PyDecimalBackend(Backend):
    name = "pydecimal"
    extension = ".py"
    features = ALL_FEATURES
    sabotages = SABOTAGES
    # El "binario" es un proceso de CPython (~13 MB), no un ELF; el techo de
    # coste de tests/test_backends.py lo declara el propio backend.
    rss_ceiling_kb = 64_000

    def toolchain(self) -> str | None:
        py = shutil.which("python3")
        if not py:
            return None
        proc = subprocess.run([py, "--version"], capture_output=True, text=True)
        line = (proc.stdout + proc.stderr).strip().splitlines()[0]
        return f"{py}: {line}"

    @con_pila
    def emit(self, module: dict, sabotage: str | None = None) -> str:
        return emit_py(module, sabotage)

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        # py_compile valida la sintaxis (falla de compilación real); luego el
        # fuente con shebang se marca ejecutable: eso es todo lo que corre.
        return ["bash", "-c", 'python3 -m py_compile "$1" && cp "$1" "$2" && chmod +x "$2"',
                "pyc", str(source), str(binary)]


BACKEND = PyDecimalBackend()


def run_pydecimal(data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
                  timeout_ms: int | None = 60_000, sabotage: str | None = None,
                  extra_flags: tuple = ()) -> tuple[dict, list]:
    """Mismo contrato que interp.run, ejecutando el programa generado con Python 3."""
    return BACKEND.run(data, inputs, limits, trace, timeout_ms, sabotage, extra_flags)
