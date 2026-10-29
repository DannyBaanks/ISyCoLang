"""Intérprete de referencia v0.1: la semántica normativa de ISyCoLang.

Legible antes que rápido. Toda la aritmética es exacta (int de Python y
Fraction) y se ajusta al tipo con las reglas de spec §3.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from fractions import Fraction

from . import ast as A
from .checker import check
from .errors import HostTimeout, InvalidProgram, IsyError, LimitReached, RuntimeFault
from .lexer import decode, tokenize
from .parser import parse
from .types import (ArrT, BoolT, DecT, IntT, canonical, cast, dec_fit, int_fit,
                    int_trunc_div, parse_canonical, round_scaled)

DEFAULT_LIMITS = {"max_steps": 1_000_000, "max_call_depth": 256, "max_emits": 100_000}
TRACE_LEVELS = ("none", "stmt", "full")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


def _copy(value):
    return list(value) if isinstance(value, list) else value


@dataclass
class Frame:
    fn: A.Fn
    scopes: list = field(default_factory=lambda: [{}])

    def get(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise AssertionError(name)

    def set(self, name, value):
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name] = value
                return
        raise AssertionError(name)


class Interpreter:
    def __init__(self, program: A.Program, limits: dict, trace: str = "none",
                 timeout_ms: int | None = None):
        self.program = program
        self.limits = limits
        self.trace_level = trace
        self.trace: list[dict] = []
        self.emits: list[str] = []
        self.steps = 0
        self.frames: list[Frame] = []
        self.deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000

    # --- contabilidad -----------------------------------------------------------
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
            row["locals"] = {name: self.show(value)
                             for scope in frame.scopes for name, value in scope.items()}
        self.trace.append(row)

    @staticmethod
    def show(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, list):
            return [Interpreter.show(v) for v in value]
        return str(value)

    # --- llamadas ---------------------------------------------------------------
    def call(self, fn: A.Fn, args: list, at: str):
        self.tick(at)
        if len(self.frames) + 1 > self.limits["max_call_depth"]:
            raise LimitReached("max_call_depth", at)
        frame = Frame(fn)
        for (name, _, _), value in zip(fn.params, args):
            frame.scopes[0][name] = _copy(value)
        self.frames.append(frame)
        self.event("enter", fn.at, args=[canonical(v, t) for v, (_, t, _) in zip(args, fn.params)])
        try:
            self.block(fn.body)
            result = None
        except _Return as ret:
            result = ret.value
        self.event("return", fn.at, value=None if fn.ret is None else canonical(result, fn.ret))
        self.frames.pop()
        return result

    # --- sentencias -------------------------------------------------------------
    def block(self, block: A.Block) -> None:
        frame = self.frames[-1]
        frame.scopes.append({})
        try:
            for stmt in block.stmts:
                self.stmt(stmt)
        finally:
            frame.scopes.pop()

    def stmt(self, s) -> None:
        frame = self.frames[-1]
        self.tick(s.at)
        if isinstance(s, A.Let):
            value = _copy(self.eval(s.expr))
            frame.scopes[-1][s.name] = value
            self.event("assign", s.at, name=s.name, value=canonical(value, s.type))
        elif isinstance(s, A.Assign):
            if s.index is None:
                value = _copy(self.eval(s.expr))
                frame.set(s.name, value)
                self.event("assign", s.at, name=s.name, value=canonical(value, s.target_ty))
            else:
                index = self.eval(s.index)
                value = self.eval(s.expr)
                array = frame.get(s.name)
                if not 0 <= index < len(array):
                    raise RuntimeFault("INDEX_OUT_OF_BOUNDS", s.at, str(index))
                array[index] = value
                self.event("assign", s.at, name=s.name, index=str(index),
                           value=canonical(value, s.target_ty))
        elif isinstance(s, A.If):
            taken = self.eval(s.cond)
            self.event("branch", s.at, taken="then" if taken else "else")
            if taken:
                self.block(s.then)
            elif isinstance(s.els, A.If):
                self.stmt(s.els)  # `else if` es otra if_stmt: cuenta su propio paso
            elif s.els is not None:
                self.block(s.els)
        elif isinstance(s, A.While):
            while True:
                self.tick(s.at)
                cond = self.eval(s.cond)
                self.event("loop_test", s.at, value="true" if cond else "false")
                if not cond:
                    return
                try:
                    self.block(s.body)
                except _Break:
                    return
                except _Continue:
                    continue
        elif isinstance(s, A.Break):
            raise _Break()
        elif isinstance(s, A.Continue):
            raise _Continue()
        elif isinstance(s, A.Return):
            raise _Return(None if s.expr is None else _copy(self.eval(s.expr)))
        elif isinstance(s, A.Emit):
            value = self.eval(s.expr)
            if len(self.emits) >= self.limits["max_emits"]:
                raise LimitReached("max_emits", s.at)
            text = canonical(value, s.expr.ty)
            self.emits.append(text)
            self.event("emit", s.at, value=text)
        elif isinstance(s, A.ExprStmt):
            self.eval(s.call)
        else:
            raise AssertionError(s)

    # --- expresiones ------------------------------------------------------------
    def eval(self, e):
        if isinstance(e, (A.IntLit, A.DecLit)):
            return e.val
        if isinstance(e, A.BoolLit):
            return e.value
        if isinstance(e, A.Name):
            return self.frames[-1].get(e.name)
        if isinstance(e, A.Call):
            args = [self.eval(arg) for arg in e.args]
            return self.call(self.program.fns[e.name], args, e.at)
        if isinstance(e, A.Index):
            array = self.eval(e.base)
            index = self.eval(e.index)
            if not 0 <= index < len(array):
                raise RuntimeFault("INDEX_OUT_OF_BOUNDS", e.at, str(index))
            return array[index]
        if isinstance(e, A.Cast):
            return cast(self.eval(e.expr), e.expr.ty, e.target, e.at)
        if isinstance(e, A.Unary):
            value = self.eval(e.expr)
            if e.op == "not":
                return not value
            if isinstance(e.ty, IntT):
                return int_fit(e.ty, -value, e.at)
            return dec_fit(e.ty, -value, e.at)
        if isinstance(e, A.Binary):
            return self.binary(e)
        if isinstance(e, A.ArrLit):
            return [self.eval(item) for item in e.elems]
        if isinstance(e, A.ArrRep):
            value = self.eval(e.elem)
            return [value] * e.n
        raise AssertionError(e)

    def binary(self, e: A.Binary):
        if e.op == "and":
            return self.eval(e.left) and self.eval(e.right)
        if e.op == "or":
            return self.eval(e.left) or self.eval(e.right)
        a = self.eval(e.left)
        b = self.eval(e.right)
        op = e.op
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        ty = e.ty
        if isinstance(ty, IntT):
            if op in ("/", "%") and b == 0:
                raise RuntimeFault("DIV_ZERO", e.at)
            if op == "+":
                exact = a + b
            elif op == "-":
                exact = a - b
            elif op == "*":
                exact = a * b
            elif op == "/":
                exact = int_trunc_div(a, b)
            else:
                return a - int_trunc_div(a, b) * b
            return int_fit(ty, exact, e.at)
        # decimales: a y b son enteros escalados por 10**s
        scale = 10 ** ty.s
        if op == "+":
            return dec_fit(ty, a + b, e.at)
        if op == "-":
            return dec_fit(ty, a - b, e.at)
        if op == "*":
            return dec_fit(ty, round_scaled(Fraction(a * b, scale), ty.rnd, e.at), e.at)
        if b == 0:
            raise RuntimeFault("DIV_ZERO", e.at)
        return dec_fit(ty, round_scaled(Fraction(a * scale, b), ty.rnd, e.at), e.at)


# --- API -------------------------------------------------------------------------

def load(data: bytes) -> A.Program:
    """Lee, parsea y chequea; lanza InvalidProgram si algo falla."""
    program = parse(tokenize(decode(data)))
    check(program)
    return program


def run(data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
        timeout_ms: int | None = None) -> tuple[dict, list[dict]]:
    """Ejecuta un programa y devuelve (documento de resultado, eventos de traza)."""
    if trace not in TRACE_LEVELS:
        raise ValueError(trace)
    lim = dict(DEFAULT_LIMITS)
    lim.update(limits or {})
    result = {
        "schema": "isyco.result/0.1",
        "program_sha256": hashlib.sha256(data).hexdigest(),
        "input_sha256": hashlib.sha256(canonical_json(inputs).encode("utf-8")).hexdigest(),
        "limits": lim,
        "status": "HALTED", "code": None, "emits": [], "return": None, "steps": 0,
    }
    interp = None
    try:
        program = load(data)
        main = program.fns["main"]
        if not isinstance(inputs, list) or len(inputs) != len(main.params):
            raise InvalidProgram("BAD_INPUT", main.at, "número de argumentos")
        args = []
        for text, (name, ty, at) in zip(inputs, main.params):
            value = parse_canonical(text, ty)
            if value is None:
                raise InvalidProgram("BAD_INPUT", at, f"{name}={text!r} no es forma canónica de {ty}")
            args.append(value)
        interp = Interpreter(program, lim, trace, timeout_ms)
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 50 * lim["max_call_depth"] + 1000))
        try:
            value = interp.call(main, args, main.at)
        finally:
            sys.setrecursionlimit(old_limit)
        if main.ret is not None:
            result["return"] = canonical(value, main.ret)
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
