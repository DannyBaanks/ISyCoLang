"""ISY-IR v0.1 / v0.2: lowering desde el AST chequeado y serialización canónica (spec/IR.md).

La IR es estructurada (sin CFG ni SSA), completamente tipada y explícita:
- toda expresión lleva su tipo (`ty`) y su posición de fuente (`at`);
- los literales ya no son polimórficos: son `const` con valor en forma canónica;
- las variables son índices en la tabla `locals` de la función (sin nombres
  ambiguos aunque dos bloques hermanos reusen un nombre);
- las conversiones son nodos `cast` explícitos (y en v0.2 el ensanchamiento de
  str es un nodo `widen`: ninguna conversión escondida).

Un programa `isyco 0.1`/`0.2` produce `isy-ir/0.1` exactamente como antes; uno
`isyco 0.3` produce `isy-ir/0.2` (str, structs; spec/IR.md §9).
"""
from __future__ import annotations

import hashlib
import json

from . import ast as A
from .types import ArrT, BoolT, DecT, IntT, StrT, StructT, canonical

SCHEMA = "isy-ir/0.1"
SCHEMA_V2 = "isy-ir/0.2"
SCHEMAS = (SCHEMA, SCHEMA_V2)
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
    if isinstance(t, StrT):
        return {"t": "str", "n": t.n}
    if isinstance(t, StructT):
        return {"t": "struct", "name": t.name,
                "fields": [{"name": name, "ty": ty_to_json(ft)} for name, ft in t.fields]}
    raise AssertionError(t)


class IRTypeError(ValueError):
    pass


def ty_from_json(j):
    """Lee un tipo de la IR; lanza IRTypeError si no es un tipo bien formado.

    `str` y `struct` solo son válidos en `isy-ir/0.2`; el validador lo revisa."""
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
    if kind == "str" and set(j) == {"t", "n"}:
        if isinstance(j["n"], int) and not isinstance(j["n"], bool) and 1 <= j["n"] <= 65536:
            return StrT(j["n"])
    if kind == "struct" and set(j) == {"t", "name", "fields"}:
        fields = j["fields"]
        if isinstance(j["name"], str) and isinstance(fields, list) and fields \
                and all(isinstance(f, dict) and set(f) == {"name", "ty"} and isinstance(f["name"], str)
                        for f in fields) \
                and len({f["name"] for f in fields}) == len(fields):
            return StructT(j["name"], tuple((f["name"], ty_from_json(f["ty"])) for f in fields))
    raise IRTypeError(f"tipo inválido: {j!r}")


# --- lowering ----------------------------------------------------------------------

class _FnLowering:
    def __init__(self, fn: A.Fn, program: A.Program):
        self.fn = fn
        self.program = program
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
            value = self.expr_as(s.expr, s.type)
            return {"s": "let", "at": at, "local": self.new_local(s.name, s.type), "value": value}
        if isinstance(s, A.Assign):
            local = self.lookup(s.name)
            if s.index is None:
                return {"s": "set", "at": at, "local": local, "value": self.expr_as(s.expr, s.target_ty)}
            return {"s": "set_index", "at": at, "local": local,
                    "index": self.expr(s.index), "value": self.expr_as(s.expr, s.target_ty)}
        if isinstance(s, A.AssignPath):
            path = [{"index": self.expr(item)} if kind == "index" else {"field": item}
                    for kind, item in s.path]
            return {"s": "set_path", "at": at, "local": self.lookup(s.name), "path": path,
                    "value": self.expr_as(s.expr, s.target_ty)}
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
                    "value": None if s.expr is None else self.expr_as(s.expr, self.fn.ret)}
        if isinstance(s, A.Emit):
            return {"s": "emit", "at": at, "value": self.expr(s.expr)}
        if isinstance(s, A.ExprStmt):
            call = s.call
            return {"s": "call", "at": at, "call_at": call.at, "fn": call.name,
                    "args": self.args(call)}
        raise AssertionError(s)

    def args(self, call: A.Call) -> list:
        params = self.program.fns[call.name].params
        return [self.expr_as(a, ty) for a, (_, ty, _) in zip(call.args, params)]

    def expr_as(self, e, ty) -> dict:
        """Expresión en un contexto que espera `ty`: el ensanchamiento de str se hace explícito."""
        node = self.expr(e)
        if isinstance(ty, StrT) and e.ty != ty:
            return {"at": e.at, "ty": ty_to_json(ty), "k": "widen", "e": node}
        return node

    def expr(self, e) -> dict:
        node = {"at": e.at, "ty": ty_to_json(e.ty)}
        if isinstance(e, (A.IntLit, A.DecLit)):
            node.update(k="const", v=canonical(e.val, e.ty))
        elif isinstance(e, A.StrLit):
            node.update(k="const", v=e.value)
        elif isinstance(e, A.Field):
            node.update(k="field", base=self.expr(e.base), name=e.name)
        elif isinstance(e, A.StructLit):
            node.update(k="struct", fields=[{"name": name, "value": self.expr_as(x, e.ty.field(name))}
                                            for name, x, _ in e.fields])
        elif isinstance(e, A.Len):
            node.update(k="len", e=self.expr(e.expr))
        elif isinstance(e, A.Slice):
            node.update(k="slice", e=self.expr(e.expr), lo=self.expr(e.lo), hi=self.expr(e.hi))
        elif isinstance(e, A.Chr):
            node.update(k="chr", e=self.expr(e.expr))
        elif isinstance(e, A.BoolLit):
            node.update(k="const", v="true" if e.value else "false")
        elif isinstance(e, A.Name):
            node.update(k="local", id=self.lookup(e.name))
        elif isinstance(e, A.Call):
            node.update(k="call", fn=e.name, args=self.args(e))
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
            elif isinstance(e.ty, StrT):
                node.update(k="concat", a=a, b=b)
            else:
                node.update(k="bin", op=BIN_OPS[e.op], a=a, b=b)
        elif isinstance(e, A.ArrLit):
            node.update(k="array", elems=[self.expr_as(x, e.ty.elem) for x in e.elems])
        elif isinstance(e, A.ArrRep):
            node.update(k="repeat", elem=self.expr_as(e.elem, e.ty.elem))
        else:
            raise AssertionError(e)
        return node


def lower(program: A.Program, source_sha256: str) -> dict:
    """Programa ya chequeado -> módulo ISY-IR (dict JSON)."""
    schema = SCHEMA_V2 if program.version in ("0.3", "0.4") else SCHEMA   # v0.4 no cambia la IR
    return {"schema": schema, "source_sha256": source_sha256,
            "functions": [_FnLowering(fn, program).lower() for fn in program.fns.values()]}


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
