"""ISY-IR v0.1: lowering desde el AST chequeado y serialización canónica (spec/IR.md).

La IR es estructurada (sin CFG ni SSA), completamente tipada y explícita:
- toda expresión lleva su tipo (`ty`) y su posición de fuente (`at`);
- los literales ya no son polimórficos: son `const` con valor en forma canónica;
- las variables son índices en la tabla `locals` de la función (sin nombres
  ambiguos aunque dos bloques hermanos reusen un nombre);
- las conversiones son nodos `cast` explícitos.
"""
from __future__ import annotations

import hashlib
import json

from . import ast as A
from .types import ArrT, BoolT, DecT, IntT, canonical

SCHEMA = "isy-ir/0.1"
BIN_OPS = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}
CMP_OPS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


# --- tipos -------------------------------------------------------------------------

def ty_to_json(t):
    if t is None:
        return None
    if isinstance(t, BoolT):
        return {"t": "bool"}
    if isinstance(t, IntT):
        return {"t": "int", "bits": t.bits, "signed": t.signed, "ovf": t.ovf}
    if isinstance(t, DecT):
        return {"t": "dec", "p": t.p, "s": t.s, "rnd": t.rnd}
    if isinstance(t, ArrT):
        return {"t": "arr", "elem": ty_to_json(t.elem), "n": t.n}
    raise AssertionError(t)


class IRTypeError(ValueError):
    pass


def ty_from_json(j):
    """Lee un tipo de la IR; lanza IRTypeError si no es un tipo v0.1 bien formado."""
    if j is None:
        return None
    if not isinstance(j, dict):
        raise IRTypeError(f"tipo no es objeto: {j!r}")
    kind = j.get("t")
    if kind == "bool" and set(j) == {"t"}:
        return BoolT()
    if kind == "int" and set(j) == {"t", "bits", "signed", "ovf"}:
        if j["bits"] in (8, 16, 32, 64) and isinstance(j["signed"], bool) \
                and j["ovf"] in ("trap", "wrap", "sat"):
            return IntT(j["bits"], j["signed"], j["ovf"])
    if kind == "dec" and set(j) == {"t", "p", "s", "rnd"}:
        p, s = j["p"], j["s"]
        if isinstance(p, int) and isinstance(s, int) and 1 <= p <= 18 and 0 <= s <= p \
                and j["rnd"] in ("half_even", "half_up", "down", "exact"):
            return DecT(p, s, j["rnd"])
    if kind == "arr" and set(j) == {"t", "elem", "n"}:
        elem = ty_from_json(j["elem"])
        if not isinstance(elem, ArrT) and isinstance(j["n"], int) and 1 <= j["n"] <= 65536:
            return ArrT(elem, j["n"])
    raise IRTypeError(f"tipo inválido: {j!r}")


# --- lowering ----------------------------------------------------------------------

class _FnLowering:
    def __init__(self, fn: A.Fn):
        self.fn = fn
        self.locals: list[dict] = []
        self.scopes: list[dict] = [{}]

    def new_local(self, name: str, ty) -> int:
        self.locals.append({"name": name, "ty": ty_to_json(ty)})
        index = len(self.locals) - 1
        self.scopes[-1][name] = index
        return index

    def lookup(self, name: str) -> int:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise AssertionError(name)

    def lower(self) -> dict:
        params = [self.new_local(name, ty) for name, ty, _ in self.fn.params]
        body = self.block(self.fn.body)
        return {"name": self.fn.name, "at": self.fn.at, "params": params,
                "ret": ty_to_json(self.fn.ret), "emits": self.fn.emits,
                "locals": self.locals, "body": body}

    def block(self, block: A.Block) -> list:
        self.scopes.append({})
        stmts = [self.stmt(s) for s in block.stmts]
        self.scopes.pop()
        return stmts

    def stmt(self, s) -> dict:
        at = s.at
        if isinstance(s, A.Let):
            value = self.expr(s.expr)
            return {"s": "let", "at": at, "local": self.new_local(s.name, s.type), "value": value}
        if isinstance(s, A.Assign):
            local = self.lookup(s.name)
            if s.index is None:
                return {"s": "set", "at": at, "local": local, "value": self.expr(s.expr)}
            return {"s": "set_index", "at": at, "local": local,
                    "index": self.expr(s.index), "value": self.expr(s.expr)}
        if isinstance(s, A.If):
            if s.els is None:
                els = None
            elif isinstance(s.els, A.If):
                els = [self.stmt(s.els)]
            else:
                els = self.block(s.els)
            return {"s": "if", "at": at, "cond": self.expr(s.cond),
                    "then": self.block(s.then), "else": els}
        if isinstance(s, A.While):
            return {"s": "while", "at": at, "cond": self.expr(s.cond), "body": self.block(s.body)}
        if isinstance(s, A.Break):
            return {"s": "break", "at": at}
        if isinstance(s, A.Continue):
            return {"s": "continue", "at": at}
        if isinstance(s, A.Return):
            return {"s": "return", "at": at,
                    "value": None if s.expr is None else self.expr(s.expr)}
        if isinstance(s, A.Emit):
            return {"s": "emit", "at": at, "value": self.expr(s.expr)}
        if isinstance(s, A.ExprStmt):
            call = s.call
            return {"s": "call", "at": at, "call_at": call.at, "fn": call.name,
                    "args": [self.expr(a) for a in call.args]}
        raise AssertionError(s)

    def expr(self, e) -> dict:
        node = {"at": e.at, "ty": ty_to_json(e.ty)}
        if isinstance(e, (A.IntLit, A.DecLit)):
            node.update(k="const", v=canonical(e.val, e.ty))
        elif isinstance(e, A.BoolLit):
            node.update(k="const", v="true" if e.value else "false")
        elif isinstance(e, A.Name):
            node.update(k="local", id=self.lookup(e.name))
        elif isinstance(e, A.Call):
            node.update(k="call", fn=e.name, args=[self.expr(a) for a in e.args])
        elif isinstance(e, A.Index):
            node.update(k="index", base=self.expr(e.base), index=self.expr(e.index))
        elif isinstance(e, A.Cast):
            node.update(k="cast", e=self.expr(e.expr))
        elif isinstance(e, A.Unary):
            node.update(k="not" if e.op == "not" else "neg", e=self.expr(e.expr))
        elif isinstance(e, A.Binary):
            a, b = self.expr(e.left), self.expr(e.right)
            if e.op in ("and", "or"):
                node.update(k=e.op, a=a, b=b)
            elif e.op in CMP_OPS:
                node.update(k="cmp", op=CMP_OPS[e.op], a=a, b=b)
            else:
                node.update(k="bin", op=BIN_OPS[e.op], a=a, b=b)
        elif isinstance(e, A.ArrLit):
            node.update(k="array", elems=[self.expr(x) for x in e.elems])
        elif isinstance(e, A.ArrRep):
            node.update(k="repeat", elem=self.expr(e.elem))
        else:
            raise AssertionError(e)
        return node


def lower(program: A.Program, source_sha256: str) -> dict:
    """Programa ya chequeado -> módulo ISY-IR (dict JSON)."""
    return {"schema": SCHEMA, "source_sha256": source_sha256,
            "functions": [_FnLowering(fn).lower() for fn in program.fns.values()]}


# --- identidad -----------------------------------------------------------------------

def canonical_bytes(module: dict) -> bytes:
    return json.dumps(module, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _strip(value):
    """Quita lo que no es semántica: posiciones de fuente y el hash del fuente."""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items()
                if k not in ("at", "call_at", "source_sha256")}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def ir_hash(module: dict) -> str:
    return hashlib.sha256(canonical_bytes(module)).hexdigest()


def semantic_hash(module: dict) -> str:
    return hashlib.sha256(canonical_bytes(_strip(module))).hexdigest()
