"""Intérprete de ISY-IR v0.1 / v0.2.

Ejecuta el JSON de la IR, no el AST. El gate de F3 exige que su resultado y su
traza sean idénticos byte a byte a los del intérprete de referencia en todo el
corpus. Comparte con la referencia solo la aritmética de `types.py`, que está
verificada aparte contra el módulo `decimal`.
"""
from __future__ import annotations

import hashlib
import sys
import time
from fractions import Fraction

from .errors import HostTimeout, InvalidProgram, IsyError, LimitReached, RuntimeFault
from .interp import DEFAULT_LIMITS, TRACE_LEVELS, canonical_json, load
from .ir import ir_hash, lower, ty_from_json
from .ir_validate import validate
from .types import (IntT, StrT, allowed_char, canonical, canonical_text, cast, dec_fit, int_fit,
                    int_trunc_div, parse_canonical, round_scaled)


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


def _copy(value):
    if isinstance(value, list):
        return [_copy(v) for v in value]
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    return value


class _Fn:
    """Función de la IR con sus tipos ya leídos."""

    def __init__(self, j: dict):
        self.j = j
        self.name = j["name"]
        self.at = j["at"]
        self.params = j["params"]
        self.ret = ty_from_json(j["ret"])
        self.local_names = [loc["name"] for loc in j["locals"]]
        self.local_types = [ty_from_json(loc["ty"]) for loc in j["locals"]]


class _Frame:
    def __init__(self, fn: _Fn):
        self.fn = fn
        self.values: dict[int, object] = {}
        self.scopes: list[list[int]] = [[]]  # locales visibles, en orden de declaración


class IRInterpreter:
    def __init__(self, module: dict, limits: dict, trace: str = "none",
                 timeout_ms: int | None = None):
        self.fns = {j["name"]: _Fn(j) for j in module["functions"]}
        self.types: dict[int, object] = {}  # id(nodo) -> tipo leído (caché)
        self.limits = limits
        self.trace_level = trace
        self.trace: list[dict] = []
        self.emits: list[str] = []
        self.steps = 0
        self.frames: list[_Frame] = []
        self.deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000

    def ty(self, node):
        key = id(node)
        if key not in self.types:
            self.types[key] = ty_from_json(node["ty"])
        return self.types[key]

    # --- contabilidad (idéntica a la referencia) --------------------------------
    def tick(self, at: str) -> None:
        self.steps += 1
        if self.steps > self.limits["max_steps"]:
            raise LimitReached("max_steps", at)
        if self.deadline is not None and self.steps % 1024 == 0 and time.monotonic() > self.deadline:
            raise HostTimeout("timeout_ms", at)

    def event(self, kind: str, at: str, **data) -> None:
        if self.trace_level == "none":
            return
        row = {"step": self.steps, "fn": self.frames[-1].fn.name if self.frames else None,
               "at": at, "kind": kind, **data}
        if self.trace_level == "full" and self.frames:
            frame = self.frames[-1]
            row["locals"] = {frame.fn.local_names[i]: canonical(frame.values[i], frame.fn.local_types[i])
                             for scope in frame.scopes for i in scope}
        self.trace.append(row)

    # --- llamadas ---------------------------------------------------------------
    def call(self, fn: _Fn, args: list, at: str):
        self.tick(at)
        if len(self.frames) + 1 > self.limits["max_call_depth"]:
            raise LimitReached("max_call_depth", at)
        frame = _Frame(fn)
        for local, value in zip(fn.params, args):
            frame.values[local] = _copy(value)
            frame.scopes[0].append(local)
        self.frames.append(frame)
        self.event("enter", fn.at, args=[canonical(v, fn.local_types[p])
                                         for v, p in zip(args, fn.params)])
        try:
            self.block(fn.j["body"])
            result = None
        except _Return as ret:
            result = ret.value
        self.event("return", fn.at, value=None if fn.ret is None else canonical(result, fn.ret))
        self.frames.pop()
        return result

    # --- sentencias -------------------------------------------------------------
    def block(self, stmts: list) -> None:
        frame = self.frames[-1]
        frame.scopes.append([])
        try:
            for s in stmts:
                self.stmt(s)
        finally:
            frame.scopes.pop()

    def stmt(self, s: dict) -> None:
        frame = self.frames[-1]
        at = s["at"]
        self.tick(at)
        kind = s["s"]
        if kind in ("let", "set"):
            local = s["local"]
            value = _copy(self.eval(s["value"]))
            frame.values[local] = value
            if kind == "let":
                frame.scopes[-1].append(local)
            self.event("assign", at, name=frame.fn.local_names[local],
                       value=canonical(value, frame.fn.local_types[local]))
        elif kind == "set_index":
            local = s["local"]
            index = self.eval(s["index"])
            value = self.eval(s["value"])
            array = frame.values[local]
            if not 0 <= index < len(array):
                raise RuntimeFault("INDEX_OUT_OF_BOUNDS", at, str(index))
            array[index] = value
            self.event("assign", at, name=frame.fn.local_names[local], index=str(index),
                       value=canonical(value, frame.fn.local_types[local].elem))
        elif kind == "set_path":
            local = s["local"]
            keys = [self.eval(step["index"]) if "index" in step else step["field"] for step in s["path"]]
            value = _copy(self.eval(s["value"]))
            container = frame.values[local]
            ty = frame.fn.local_types[local]
            for i, (step, key) in enumerate(zip(s["path"], keys)):
                if "index" in step:
                    if not 0 <= key < len(container):
                        raise RuntimeFault("INDEX_OUT_OF_BOUNDS", at, str(key))
                    ty = ty.elem
                else:
                    ty = ty.field(key)
                if i == len(keys) - 1:
                    container[key] = value
                else:
                    container = container[key]
            text = "".join(f"[{k}]" if "index" in step else f".{k}" for step, k in zip(s["path"], keys))
            self.event("assign", at, name=frame.fn.local_names[local], path=text,
                       value=canonical(value, ty))
        elif kind == "if":
            taken = self.eval(s["cond"])
            self.event("branch", at, taken="then" if taken else "else")
            if taken:
                self.block(s["then"])
            elif s["else"] is not None:
                self.block(s["else"])
        elif kind == "while":
            while True:
                self.tick(at)
                cond = self.eval(s["cond"])
                self.event("loop_test", at, value="true" if cond else "false")
                if not cond:
                    return
                try:
                    self.block(s["body"])
                except _Break:
                    return
                except _Continue:
                    continue
        elif kind == "break":
            raise _Break()
        elif kind == "continue":
            raise _Continue()
        elif kind == "return":
            raise _Return(None if s["value"] is None else _copy(self.eval(s["value"])))
        elif kind == "emit":
            value = self.eval(s["value"])
            if len(self.emits) >= self.limits["max_emits"]:
                raise LimitReached("max_emits", at)
            text = canonical_text(value, self.ty(s["value"]))
            self.emits.append(text)
            self.event("emit", at, value=text)
        elif kind == "call":
            args = [self.eval(a) for a in s["args"]]
            self.call(self.fns[s["fn"]], args, s["call_at"])
        else:
            raise AssertionError(kind)

    # --- expresiones ------------------------------------------------------------
    def eval(self, e: dict):
        kind = e["k"]
        at = e["at"]
        if kind == "const":
            return parse_canonical(e["v"], self.ty(e))
        if kind == "local":
            return self.frames[-1].values[e["id"]]
        if kind == "call":
            args = [self.eval(a) for a in e["args"]]
            return self.call(self.fns[e["fn"]], args, at)
        if kind == "index":
            array = self.eval(e["base"])
            index = self.eval(e["index"])
            if not 0 <= index < len(array):
                raise RuntimeFault("INDEX_OUT_OF_BOUNDS", at, str(index))
            if isinstance(array, str):
                return ord(array[index])
            return array[index]
        if kind == "concat":
            text = self.eval(e["a"]) + self.eval(e["b"])
            if len(text) > self.ty(e).n:
                raise RuntimeFault("OVERFLOW", at)
            return text
        if kind == "widen":
            return self.eval(e["e"])
        if kind == "len":
            return len(self.eval(e["e"]))
        if kind == "slice":
            text = self.eval(e["e"])
            lo = self.eval(e["lo"])
            hi = self.eval(e["hi"])
            if not 0 <= lo <= hi <= len(text):
                raise RuntimeFault("INDEX_OUT_OF_BOUNDS", at)
            return text[lo:hi]
        if kind == "chr":
            code = self.eval(e["e"])
            if not (0 <= code < 128 and allowed_char(chr(code))):
                raise RuntimeFault("BAD_CHAR", at)
            return chr(code)
        if kind == "field":
            return self.eval(e["base"])[e["name"]]
        if kind == "struct":
            values = {f["name"]: _copy(self.eval(f["value"])) for f in e["fields"]}
            return {name: values[name] for name, _ in self.ty(e).fields}
        if kind == "cast":
            return cast(self.eval(e["e"]), self.ty(e["e"]), self.ty(e), at)
        if kind == "not":
            return not self.eval(e["e"])
        if kind == "neg":
            value = self.eval(e["e"])
            ty = self.ty(e)
            return int_fit(ty, -value, at) if isinstance(ty, IntT) else dec_fit(ty, -value, at)
        if kind == "and":
            return self.eval(e["a"]) and self.eval(e["b"])
        if kind == "or":
            return self.eval(e["a"]) or self.eval(e["b"])
        if kind == "cmp":
            a, b = self.eval(e["a"]), self.eval(e["b"])
            op = e["op"]
            # Solo la comparación pedida: eq/ne valen sobre structs, el orden no existe ahí.
            return {"eq": lambda: a == b, "ne": lambda: a != b, "lt": lambda: a < b,
                    "le": lambda: a <= b, "gt": lambda: a > b, "ge": lambda: a >= b}[op]()
        if kind == "bin":
            return self.arith(e["op"], self.eval(e["a"]), self.eval(e["b"]), self.ty(e), at)
        if kind == "array":
            return [self.eval(x) for x in e["elems"]]
        if kind == "repeat":
            return [self.eval(e["elem"])] * self.ty(e).n
        raise AssertionError(kind)

    @staticmethod
    def arith(op, a, b, ty, at):
        if isinstance(ty, IntT):
            if op in ("div", "rem") and b == 0:
                raise RuntimeFault("DIV_ZERO", at)
            if op == "rem":
                return a - int_trunc_div(a, b) * b
            exact = {"add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
                     "div": lambda: int_trunc_div(a, b)}[op]()
            return int_fit(ty, exact, at)
        scale = 10 ** ty.s
        if op == "add":
            return dec_fit(ty, a + b, at)
        if op == "sub":
            return dec_fit(ty, a - b, at)
        if op == "mul":
            return dec_fit(ty, round_scaled(Fraction(a * b, scale), ty.rnd, at), at)
        if b == 0:
            raise RuntimeFault("DIV_ZERO", at)
        return dec_fit(ty, round_scaled(Fraction(a * scale, b), ty.rnd, at), at)


# --- API ---------------------------------------------------------------------------

def compile_ir(data: bytes) -> dict:
    """Fuente .isy -> módulo ISY-IR validado (lanza InvalidProgram o IRInvalid)."""
    module = lower(load(data), hashlib.sha256(data).hexdigest())
    validate(module)
    return module


def run_ir(module: dict, program_sha256: str, inputs: list, limits: dict | None = None,
           trace: str = "none", timeout_ms: int | None = None) -> tuple[dict, list[dict]]:
    """Ejecuta un módulo ISY-IR ya validado; mismo documento de resultado que la referencia."""
    if trace not in TRACE_LEVELS:
        raise ValueError(trace)
    lim = dict(DEFAULT_LIMITS)
    lim.update(limits or {})
    result = {
        "schema": "isyco.result/0.1",
        "program_sha256": program_sha256,
        "input_sha256": hashlib.sha256(canonical_json(inputs).encode("utf-8")).hexdigest(),
        "limits": lim,
        "status": "HALTED", "code": None, "emits": [], "return": None, "steps": 0,
    }
    interp = None
    try:
        main_j = next(f for f in module["functions"] if f["name"] == "main")
        main = _Fn(main_j)
        if not isinstance(inputs, list) or len(inputs) != len(main.params):
            raise InvalidProgram("BAD_INPUT", main.at, "número de argumentos")
        args = []
        for text, local in zip(inputs, main.params):
            value = parse_canonical(text, main.local_types[local])
            if value is None:
                raise InvalidProgram("BAD_INPUT", main.at, f"{text!r}")
            args.append(value)
        interp = IRInterpreter(module, lim, trace, timeout_ms)
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 50 * lim["max_call_depth"] + 1000))
        try:
            value = interp.call(interp.fns["main"], args, main.at)
        finally:
            sys.setrecursionlimit(old_limit)
        if main.ret is not None:
            result["return"] = canonical_text(value, main.ret)
    except IsyError as err:
        result["status"] = err.status
        result["code"] = None if isinstance(err, HostTimeout) else err.code
        if interp is not None:
            kind = "limit" if isinstance(err, LimitReached) else "error"
            interp.event(kind, err.at, code=err.code)
    if interp is not None:
        result["emits"] = interp.emits
        result["steps"] = interp.steps
        return result, interp.trace
    return result, []


def run_via_ir(data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
               timeout_ms: int | None = None) -> tuple[dict, list[dict]]:
    """Fuente -> IR -> JSON -> IR (ida y vuelta) -> ejecución. Mismo contrato que interp.run."""
    import json

    program_sha256 = hashlib.sha256(data).hexdigest()
    try:
        module = compile_ir(data)
    except InvalidProgram:
        from .interp import run
        return run(data, inputs, limits, trace, timeout_ms)  # mismo frontend: mismo rechazo
    module = json.loads(json.dumps(module))  # nada que no sea JSON sobrevive
    validate(module)
    assert ir_hash(module)  # identidad calculable
    return run_ir(module, program_sha256, inputs, limits, trace, timeout_ms)
