"""Nodos del AST. `at` = "línea:columna"; `ty` lo llena el checker."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Expr:
    at: str
    ty: object = field(default=None, init=False, compare=False)


@dataclass
class IntLit(Expr):
    value: int = 0
    val: object = field(default=None, init=False)  # valor ya resuelto al tipo


@dataclass
class DecLit(Expr):
    digits: int = 0   # entero sin punto: "12.50" -> 1250
    scale: int = 0    # decimales escritos: "12.50" -> 2
    val: object = field(default=None, init=False)


@dataclass
class BoolLit(Expr):
    value: bool = False


@dataclass
class Name(Expr):
    name: str = ""


@dataclass
class Call(Expr):
    name: str = ""
    args: list = field(default_factory=list)


@dataclass
class Index(Expr):
    base: Expr = None
    index: Expr = None


@dataclass
class Cast(Expr):
    expr: Expr = None
    target: object = None


@dataclass
class Unary(Expr):
    op: str = ""
    expr: Expr = None


@dataclass
class Binary(Expr):
    op: str = ""
    left: Expr = None
    right: Expr = None


@dataclass
class ArrLit(Expr):
    elems: list = field(default_factory=list)


@dataclass
class ArrRep(Expr):
    elem: Expr = None
    n: int = 0


# --- CORE v0.3 -----------------------------------------------------------------

@dataclass
class StrLit(Expr):
    value: str = ""


@dataclass
class Field(Expr):
    base: Expr = None
    name: str = ""


@dataclass
class StructLit(Expr):
    name: str = ""
    fields: list = field(default_factory=list)   # [(nombre, expr, at)] en orden escrito


@dataclass
class Len(Expr):
    expr: Expr = None


@dataclass
class Slice(Expr):
    expr: Expr = None
    lo: Expr = None
    hi: Expr = None


@dataclass
class Chr(Expr):
    expr: Expr = None


@dataclass
class Stmt:
    at: str


@dataclass
class Block:
    stmts: list


@dataclass
class Let(Stmt):
    name: str = ""
    type: object = None
    expr: Expr = None


@dataclass
class Assign(Stmt):
    name: str = ""
    index: Expr | None = None
    expr: Expr = None
    target_ty: object = field(default=None, init=False)


@dataclass
class AssignPath(Stmt):
    """CORE v0.3 §3.3: `x.f = e`, `a[i].f = e`, `p.xs[i] = e`…"""
    name: str = ""
    path: list = field(default_factory=list)   # [("index", expr) | ("field", nombre)]
    expr: Expr = None
    target_ty: object = field(default=None, init=False)
    steps_ty: list = field(default_factory=list, init=False)  # tipo antes de cada paso


@dataclass
class If(Stmt):
    cond: Expr = None
    then: Block = None
    els: object = None  # Block | If | None


@dataclass
class While(Stmt):
    cond: Expr = None
    body: Block = None


@dataclass
class Break(Stmt):
    pass


@dataclass
class Continue(Stmt):
    pass


@dataclass
class Return(Stmt):
    expr: Expr | None = None


@dataclass
class Emit(Stmt):
    expr: Expr = None


@dataclass
class ExprStmt(Stmt):
    call: Call = None


@dataclass
class Fn:
    at: str
    name: str
    params: list          # [(nombre, tipo, at)]
    ret: object           # tipo o None
    emits: bool
    body: Block


@dataclass
class StructDecl:
    at: str
    name: str
    fields: list          # [(nombre, tipo, at)]


@dataclass
class Program:
    fns: dict             # nombre -> Fn, en orden de aparición
    version: str = "0.1"  # de la cabecera; decide reglas de CORE v0.2/v0.3
    structs: dict = field(default_factory=dict)   # nombre -> StructDecl (v0.3)
