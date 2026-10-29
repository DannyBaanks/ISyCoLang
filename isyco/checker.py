"""Chequeo estático: nombres, tipos, literales, efectos y retornos (spec §3–§6).

Anota cada expresión con `ty` y cada literal con `val` (su valor ya resuelto al
tipo esperado). Todo error es INVALID_PROGRAM y se reporta el primero en orden
de fuente.
"""
from __future__ import annotations

from . import ast as A
from .errors import InvalidProgram
from .types import INT_ALIASES, ArrT, BoolT, DecT, IntT, is_numeric, is_scalar

ARITH = {"+", "-", "*", "/", "%"}
ORDER = {"<", "<=", ">", ">="}


def is_poly(e) -> bool:
    """Expresión sin tipo propio: literales numéricos y aritmética solo de ellos."""
    if isinstance(e, (A.IntLit, A.DecLit)):
        return True
    if isinstance(e, A.Unary) and e.op == "-":
        return is_poly(e.expr)
    if isinstance(e, A.Binary) and e.op in ARITH:
        return is_poly(e.left) and is_poly(e.right)
    return False


class Checker:
    def __init__(self, program: A.Program):
        self.program = program
        self.fn: A.Fn | None = None
        self.scopes: list[dict] = []
        self.loop_depth = 0
        self.emits = False

    def check(self) -> None:
        if "main" not in self.program.fns:
            raise InvalidProgram("NO_MAIN", "1:1")
        main = self.program.fns["main"]
        if main.ret is not None and not is_scalar(main.ret):
            raise InvalidProgram("TYPE_MISMATCH", main.at, "main debe retornar un escalar")
        for fn in self.program.fns.values():
            self.check_fn(fn)

    # --- funciones ------------------------------------------------------------
    def check_fn(self, fn: A.Fn) -> None:
        self.fn, self.loop_depth, self.emits = fn, 0, False
        self.scopes = [{}]
        for name, ty, at in fn.params:
            self.declare(name, ty, at)
        self.block(fn.body)
        if fn.ret is not None and not self.always_returns(fn.body):
            raise InvalidProgram("MISSING_RETURN", fn.at, fn.name)
        if self.emits and not fn.emits:
            raise InvalidProgram("UNDECLARED_EFFECT", fn.at, fn.name)

    def always_returns(self, node) -> bool:
        if isinstance(node, A.Block):
            return any(self.always_returns(s) for s in node.stmts)
        if isinstance(node, A.Return):
            return True
        if isinstance(node, A.If):
            return (node.els is not None and self.always_returns(node.then)
                    and self.always_returns(node.els))
        return False  # while puede no ejecutarse

    # --- nombres --------------------------------------------------------------
    def declare(self, name: str, ty, at: str) -> None:
        if any(name in scope for scope in self.scopes):
            raise InvalidProgram("DUPLICATE_NAME", at, name)
        self.scopes[-1][name] = ty

    def lookup(self, name: str, at: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise InvalidProgram("UNKNOWN_NAME", at, name)

    # --- sentencias -----------------------------------------------------------
    def block(self, block: A.Block) -> None:
        self.scopes.append({})
        for stmt in block.stmts:
            self.stmt(stmt)
        self.scopes.pop()

    def stmt(self, s) -> None:
        if isinstance(s, A.Let):
            self.expect(s.expr, s.type)
            self.declare(s.name, s.type, s.at)
        elif isinstance(s, A.Assign):
            ty = self.lookup(s.name, s.at)
            if s.index is not None:
                if not isinstance(ty, ArrT):
                    raise InvalidProgram("TYPE_MISMATCH", s.at, "indexar algo que no es arreglo")
                self.index_type(s.index)
                ty = ty.elem
            s.target_ty = ty
            self.expect(s.expr, ty)
        elif isinstance(s, A.If):
            self.expect(s.cond, BoolT())
            self.block(s.then)
            if isinstance(s.els, A.Block):
                self.block(s.els)
            elif s.els is not None:
                self.stmt(s.els)
        elif isinstance(s, A.While):
            self.expect(s.cond, BoolT())
            self.loop_depth += 1
            self.block(s.body)
            self.loop_depth -= 1
        elif isinstance(s, (A.Break, A.Continue)):
            if self.loop_depth == 0:
                raise InvalidProgram("BAD_LOOP_CONTROL", s.at)
        elif isinstance(s, A.Return):
            if self.fn.ret is None:
                if s.expr is not None:
                    raise InvalidProgram("TYPE_MISMATCH", s.at, "la función no retorna valor")
            else:
                if s.expr is None:
                    raise InvalidProgram("TYPE_MISMATCH", s.at, "falta el valor de retorno")
                self.expect(s.expr, self.fn.ret)
        elif isinstance(s, A.Emit):
            ty = self.typeof(s.expr, None)
            if not is_scalar(ty):
                raise InvalidProgram("TYPE_MISMATCH", s.at, "emit solo acepta escalares")
            self.emits = True
        elif isinstance(s, A.ExprStmt):
            self.call(s.call, allow_void=True)
        else:
            raise AssertionError(s)

    # --- expresiones ----------------------------------------------------------
    def expect(self, e, ty) -> None:
        got = self.typeof(e, ty)
        if got != ty:
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"se esperaba {ty}, llegó {got}")

    def index_type(self, e) -> None:
        # CORE v0.2 C1: un índice sin tipo propio (literales) toma i64.
        hint = INT_ALIASES["i64"] if self.program.version != "0.1" and is_poly(e) else None
        ty = self.typeof(e, hint)
        if not isinstance(ty, IntT):
            raise InvalidProgram("TYPE_MISMATCH", e.at, "el índice debe ser entero")

    def typeof(self, e, expected):
        ty = self._typeof(e, expected)
        e.ty = ty
        return ty

    def _typeof(self, e, expected):
        if isinstance(e, A.IntLit):
            return self.int_literal(e, expected)
        if isinstance(e, A.DecLit):
            return self.dec_literal(e, expected)
        if isinstance(e, A.BoolLit):
            return BoolT()
        if isinstance(e, A.Name):
            return self.lookup(e.name, e.at)
        if isinstance(e, A.Call):
            return self.call(e, allow_void=False)
        if isinstance(e, A.Index):
            base = self.typeof(e.base, None)
            if not isinstance(base, ArrT):
                raise InvalidProgram("TYPE_MISMATCH", e.at, "indexar algo que no es arreglo")
            self.index_type(e.index)
            return base.elem
        if isinstance(e, A.Cast):
            return self.cast(e)
        if isinstance(e, A.Unary):
            if e.op == "not":
                self.expect(e.expr, BoolT())
                return BoolT()
            ty = self.typeof(e.expr, expected if is_poly(e.expr) else None)
            if not is_numeric(ty):
                raise InvalidProgram("TYPE_MISMATCH", e.at, "'-' requiere un número")
            return ty
        if isinstance(e, A.Binary):
            return self.binary(e, expected)
        if isinstance(e, (A.ArrLit, A.ArrRep)):
            return self.array_literal(e, expected)
        raise AssertionError(e)

    def int_literal(self, e: A.IntLit, expected):
        if expected is None:
            raise InvalidProgram("AMBIGUOUS_LITERAL", e.at)
        if isinstance(expected, IntT):
            if not expected.lo <= e.value <= expected.hi:
                raise InvalidProgram("LITERAL_OUT_OF_RANGE", e.at, f"{e.value} en {expected}")
            e.val = e.value
            return expected
        if isinstance(expected, DecT):
            m = e.value * 10 ** expected.s
            if abs(m) > expected.max_m:
                raise InvalidProgram("LITERAL_OUT_OF_RANGE", e.at, f"{e.value} en {expected}")
            e.val = m
            return expected
        raise InvalidProgram("TYPE_MISMATCH", e.at, f"literal numérico donde se esperaba {expected}")

    def dec_literal(self, e: A.DecLit, expected):
        if expected is None:
            raise InvalidProgram("AMBIGUOUS_LITERAL", e.at)
        if not isinstance(expected, DecT):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"literal decimal donde se esperaba {expected}")
        if e.scale > expected.s:
            raise InvalidProgram("LITERAL_SCALE", e.at, f"{e.scale} decimales en {expected}")
        m = e.digits * 10 ** (expected.s - e.scale)
        if abs(m) > expected.max_m:
            raise InvalidProgram("LITERAL_OUT_OF_RANGE", e.at, str(expected))
        e.val = m
        return expected

    def binary(self, e: A.Binary, expected):
        if e.op in ("and", "or"):
            self.expect(e.left, BoolT())
            self.expect(e.right, BoolT())
            return BoolT()
        is_cmp = e.op not in ARITH
        operand_hint = None if is_cmp else expected
        if not is_poly(e.left):
            lt = self.typeof(e.left, None)
            rt = self.typeof(e.right, lt)
        elif not is_poly(e.right):
            rt = self.typeof(e.right, None)
            lt = self.typeof(e.left, rt)
        else:
            if operand_hint is None:
                raise InvalidProgram("AMBIGUOUS_LITERAL", e.at)
            lt = self.typeof(e.left, operand_hint)
            rt = self.typeof(e.right, operand_hint)
        if lt != rt:
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{lt} {e.op} {rt}")
        if is_cmp:
            if isinstance(lt, ArrT) or (e.op in ORDER and isinstance(lt, BoolT)):
                raise InvalidProgram("TYPE_MISMATCH", e.at, f"no se puede comparar {lt}")
            return BoolT()
        if not is_numeric(lt) or (e.op == "%" and isinstance(lt, DecT)):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"'{e.op}' no aplica a {lt}")
        return lt

    def cast(self, e: A.Cast):
        target = e.target
        src = self.typeof(e.expr, target if is_poly(e.expr) else None)
        if not (is_numeric(src) and is_numeric(target)):
            raise InvalidProgram("BAD_CAST", e.at, f"{src} as {target}")
        return target

    def array_literal(self, e, expected):
        if not isinstance(expected, ArrT):
            raise InvalidProgram("AMBIGUOUS_LITERAL", e.at, "arreglo literal sin tipo esperado")
        if isinstance(e, A.ArrLit):
            if len(e.elems) != expected.n:
                raise InvalidProgram("TYPE_MISMATCH", e.at, f"{len(e.elems)} elementos para {expected}")
            for item in e.elems:
                self.expect(item, expected.elem)
        else:
            if e.n != expected.n:
                raise InvalidProgram("TYPE_MISMATCH", e.at, f"[_; {e.n}] para {expected}")
            self.expect(e.elem, expected.elem)
        return expected

    def call(self, e: A.Call, allow_void: bool):
        callee = self.program.fns.get(e.name)
        if callee is None:
            raise InvalidProgram("UNKNOWN_NAME", e.at, e.name)
        if len(e.args) != len(callee.params):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{e.name} espera {len(callee.params)} argumentos")
        for arg, (_, ty, _) in zip(e.args, callee.params):
            self.expect(arg, ty)
        if callee.emits:
            self.emits = True
        if callee.ret is None and not allow_void:
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{e.name} no retorna valor")
        return callee.ret


def check(program: A.Program) -> None:
    Checker(program).check()
