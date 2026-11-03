"""Chequeo estático: nombres, tipos, literales, efectos y retornos (spec §3–§6).

Anota cada expresión con `ty` y cada literal con `val` (su valor ya resuelto al
tipo esperado). Todo error es INVALID_PROGRAM y se reporta el primero en orden
de fuente.
"""
from __future__ import annotations

import dataclasses

from . import ast as A
from . import specialize as spec
from .errors import InvalidProgram
from .types import (INT_ALIASES, MAX_STR, MAX_VALUE_SIZE, U8, ArrT, BoolT, ContextStrT, DecT,
                    IntT, NamedT, StrT, StructT, is_numeric, is_scalar, type_size)
from .versions import has

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


#: campos que no son sub-AST: tipos anotados por este checker, no expresiones
_NOT_AST = ("ty", "target_ty", "steps_ty", "type", "target")


def static_len(value):
    """CORE v0.5 V1: reemplaza `len(a)` con `a: [T; N]` por el entero `N` en el AST.

    Es estático porque lo resuelve el tipo, no la ejecución: la capacidad `N` ya es un dato
    del tipo, así que el nodo desaparece antes de la IR — ningún backend nuevo, ninguna
    capacidad nueva, `features_of` intacta (el mismo movimiento de v0.4 con los imports).
    `len(s)` de v0.3 §2.4 no se toca: sigue siendo una operación. Se llama después de
    chequear, con los `ty` llenados: el literal carga `ty` y `val` como los habría dejado
    `int_literal` con `expected = i64`, que es el tipo que el checker ya le dio al `len`.
    """
    if isinstance(value, list):
        return [static_len(v) for v in value]
    if isinstance(value, tuple):
        return tuple(static_len(v) for v in value)
    if isinstance(value, (A.Expr, A.Stmt, A.Block)):
        for f in dataclasses.fields(value):
            if f.name not in _NOT_AST:
                setattr(value, f.name, static_len(getattr(value, f.name)))
        if isinstance(value, A.Len) and isinstance(value.expr.ty, ArrT):
            lit = A.IntLit(value.at, value.expr.ty.n)
            lit.ty, lit.val = INT_ALIASES["i64"], value.expr.ty.n
            return lit
    return value


def _valores_ast(value):
    """Contenido de un campo, achatando listas, tuplas, sets y valores de dict."""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _valores_ast(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _valores_ast(item)
    else:
        yield value


def _es_nodo(v) -> bool:
    return dataclasses.is_dataclass(v) and type(v).__module__ == A.__name__


def expr_depth(program: A.Program) -> tuple[int, str]:
    """Cadena más larga de nodos de expresión del programa y `at` de su raíz.

    Recorrido explícito, no recursivo: la guarda que mide el fondo no puede ser la que agote
    la pila que mide (Z2). Y se mide aparte del anidamiento que cuenta el parser: una suma
    izquierda de k términos no hace bajar ni un frame al parser y aun así anida k niveles.
    """
    raices: list[A.Expr] = []
    pila: list = [program]
    while pila:
        nodo = pila.pop()
        for campo in dataclasses.fields(nodo):
            for v in _valores_ast(getattr(nodo, campo.name)):
                if isinstance(v, A.Expr):
                    raices.append(v)
                elif _es_nodo(v):
                    pila.append(v)
    mejor, donde = 0, "1:1"
    pila = [(e, 1) for e in raices]
    while pila:
        nodo, d = pila.pop()
        if d > mejor:
            mejor, donde = d, nodo.at
        for campo in dataclasses.fields(nodo):
            for v in _valores_ast(getattr(nodo, campo.name)):
                if isinstance(v, A.Expr):
                    pila.append((v, d + 1))
    return mejor, donde


class Checker:
    def __init__(self, program: A.Program):
        self.program = program
        self.fn: A.Fn | None = None
        self.scopes: list[dict] = []
        self.loop_depth = 0
        self.emits = False
        self.v03 = has(program.version, "v03")   # v0.4 y v0.5 traen lo de v0.3
        self.v05 = has(program.version, "v05")
        self.struct_types: dict[str, StructT] = {}
        self.specs: dict[str, A.Fn] = {}         # V6: especializaciones ya chequeadas
        self.spec_counts: dict[str, int] = {}    # P4: resoluciones por definición fuente

    def check(self) -> None:
        # Z2: antes de tocar nada recursivo. Sin esta guarda el checker bajaba 242 términos
        # y reventaba con RecursionError del anfitrión (985 de 999 frames eran de copy.deepcopy
        # por el clon de V6); con ella el rechazo es del idioma: INVALID_PROGRAM/SPEC_LIMIT.
        hondo, donde = expr_depth(self.program)
        if hondo > A.MAX_EXPR_DEPTH:
            raise InvalidProgram("SPEC_LIMIT", donde,
                                 f"una expresión anida {hondo} niveles y la cota es "
                                 f"{A.MAX_EXPR_DEPTH} (CORE v0.5 §7)")
        if self.v03:
            self.check_structs()
        if "main" not in self.program.fns:
            raise InvalidProgram("NO_MAIN", "1:1")
        main = self.program.fns["main"]
        if self.v03:
            # Firmas resueltas antes de los cuerpos: una llamada puede preceder a la función.
            for fn in self.program.fns.values():
                fn.params = [(name, self.resolve(ty), at) for name, ty, at in fn.params]
                fn.ret = self.resolve(fn.ret)
        elif main.ret is not None and not is_scalar(main.ret):
            raise InvalidProgram("TYPE_MISMATCH", main.at, "main debe retornar un escalar")
        if spec.is_contextual(main):
            raise InvalidProgram("TYPE_MISMATCH", main.at,
                                 "main: ninguna llamada fija la capacidad del str pelado")
        pelados = [name for name, fn in self.program.fns.items() if spec.is_contextual(fn)]
        for fn in list(self.program.fns.values()):
            if spec.is_contextual(fn):
                continue    # V6: la definición pelada no se chequea; se chequea cada copia
            self.check_fn(fn)
        for name in pelados:
            # Sin llamadas no hay código: la definición original desaparece antes de la IR,
            # así que `str` pelado nunca llega a `ty_to_json` ni a `type_size`.
            del self.program.fns[name]
        if self.v05:
            # V1 se aplica sobre las funciones que sobreviven al chequeo —incluidas las copias
            # de V6—, con los `ty` ya llenados y el cuerpo de los pelados original fuera.
            for fn in self.program.fns.values():
                fn.body = static_len(fn.body)

    # --- structs y tipos con nombre (CORE v0.3 §3, §5, §7.1) -------------------
    def check_structs(self) -> None:
        decls = self.program.structs

        def names_in(t):
            if isinstance(t, NamedT):
                yield t
            elif isinstance(t, ArrT):
                yield from names_in(t.elem)

        for decl in decls.values():
            for _, ty, _ in decl.fields:
                for named in names_in(ty):
                    if named.name not in decls:
                        raise InvalidProgram("UNKNOWN_NAME", named.at, named.name)
        deps = {name: {n.name for _, ty, _ in d.fields for n in names_in(ty)} for name, d in decls.items()}

        def reaches(start, target, seen):
            for nxt in deps[start]:
                if nxt == target or (nxt not in seen and reaches(nxt, target, seen | {nxt})):
                    return True
            return False

        for name, decl in decls.items():
            if reaches(name, name, {name}):
                raise InvalidProgram("RECURSIVE_TYPE", decl.at, name)
        for name, decl in decls.items():
            if type_size(self.struct_type(name)) > MAX_VALUE_SIZE:
                raise InvalidProgram("TYPE_TOO_LARGE", decl.at, name)

    def struct_type(self, name: str) -> StructT:
        if name not in self.struct_types:
            decl = self.program.structs[name]
            self.struct_types[name] = StructT(
                name, tuple((fname, self.resolve(ty, check_size=False)) for fname, ty, _ in decl.fields))
        return self.struct_types[name]

    def resolve(self, t, check_size: bool = True):
        """Tipo escrito en el fuente -> tipo resuelto (structs por nombre)."""
        if isinstance(t, NamedT):
            if t.name not in self.program.structs:
                raise InvalidProgram("UNKNOWN_NAME", t.at, t.name)
            out = self.struct_type(t.name)
            at = t.at
        elif isinstance(t, ArrT):
            out = ArrT(self.resolve(t.elem, check_size=False), t.n)
            at = None
        else:
            return t
        if check_size and type_size(out) > MAX_VALUE_SIZE:
            raise InvalidProgram("TYPE_TOO_LARGE", at, str(out))
        return out

    def size_ok(self, t, at) -> None:
        if self.v03 and type_size(t) > MAX_VALUE_SIZE:
            raise InvalidProgram("TYPE_TOO_LARGE", at, str(t))

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
            if s.type is None:
                # CORE v0.5 V2: el `let x` sintético del `for` no trae anotación — su tipo es
                # el del elemento. Desde aquí es un `let` igual que el escrito a mano.
                self.typeof(s.expr, None)
                s.type = s.expr.ty
            if self.v03:
                s.type = self.resolve(s.type)
                self.size_ok(s.type, s.at)
            self.expect(s.expr, s.type)
            self.declare(s.name, s.type, s.at)
        elif isinstance(s, A.AssignPath):
            ty = self.lookup(s.name, s.at)
            s.steps_ty = []
            for kind, item in s.path:
                s.steps_ty.append(ty)
                if kind == "index":
                    if isinstance(ty, StrT):
                        raise InvalidProgram("NOT_ASSIGNABLE", s.at, "los str son inmutables")
                    if not isinstance(ty, ArrT):
                        raise InvalidProgram("TYPE_MISMATCH", s.at, "indexar algo que no es arreglo")
                    self.index_type(item)
                    ty = ty.elem
                else:
                    if not isinstance(ty, StructT):
                        raise InvalidProgram("TYPE_MISMATCH", s.at, f".{item} sobre {ty}")
                    if ty.field(item) is None:
                        raise InvalidProgram("UNKNOWN_NAME", s.at, item)
                    ty = ty.field(item)
            s.target_ty = ty
            self.expect(s.expr, ty)
        elif isinstance(s, A.Assign):
            ty = self.lookup(s.name, s.at)
            if s.index is not None:
                if isinstance(ty, StrT):
                    raise InvalidProgram("NOT_ASSIGNABLE", s.at, "los str son inmutables")
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
            if not self.v03 and not is_scalar(ty):
                raise InvalidProgram("TYPE_MISMATCH", s.at, "emit solo acepta escalares")
            self.emits = True
        elif isinstance(s, A.ExprStmt):
            self.call(s.call, allow_void=True)
        else:
            raise AssertionError(s)

    # --- expresiones ----------------------------------------------------------
    def expect(self, e, ty) -> None:
        got = self.typeof(e, ty)
        # CORE v0.3 S5: str<N> se ensancha a str<M> si N <= M (única conversión implícita).
        widen = isinstance(got, StrT) and isinstance(ty, StrT) and got.n <= ty.n
        if got != ty and not widen:
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"se esperaba {ty}, llegó {got}")

    def index_type(self, e) -> None:
        # CORE v0.2 C1: un índice sin tipo propio (literales) toma i64.
        hint = INT_ALIASES["i64"] if has(self.program.version, "v02") and is_poly(e) else None
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
            # V6-bis: la capacidad esperada en esta posición es la que resuelve un
            # retorno pelado; sin espera explícita (emit, sentencia, comparación) se
            # rechaza, no se inventa un ancho.
            return self.call(e, allow_void=False, expected=expected)
        if isinstance(e, A.StrLit):
            if isinstance(expected, StrT) and len(e.value) > expected.n:
                raise InvalidProgram("LITERAL_OUT_OF_RANGE", e.at, f"{len(e.value)} bytes en {expected}")
            return StrT(max(len(e.value), 1))
        if isinstance(e, A.Field):
            base = self.typeof(e.base, None)
            if not isinstance(base, StructT):
                raise InvalidProgram("TYPE_MISMATCH", e.at, f".{e.name} sobre {base}")
            if base.field(e.name) is None:
                raise InvalidProgram("UNKNOWN_NAME", e.at, e.name)
            return base.field(e.name)
        if isinstance(e, A.StructLit):
            return self.struct_literal(e)
        if isinstance(e, A.Len):
            ty = self.typeof(e.expr, None)
            if isinstance(ty, ArrT):
                # V1: solo con cabecera 0.5. En 0.1-0.4 `len` sigue siendo una operación
                # de strings y un arreglo es TYPE_MISMATCH, sin cambiar programas viejos.
                if not self.v05:
                    raise InvalidProgram("TYPE_MISMATCH", e.at,
                                         f"len de {ty} llegó con CORE v0.5 (V1): len requiere un str")
                return INT_ALIASES["i64"]
            if not isinstance(ty, StrT):
                raise InvalidProgram("TYPE_MISMATCH", e.at, "len requiere un str")
            return INT_ALIASES["i64"]
        if isinstance(e, A.Slice):
            ty = self.typeof(e.expr, None)
            if not isinstance(ty, StrT):
                raise InvalidProgram("TYPE_MISMATCH", e.at, "slice requiere un str")
            self.index_type(e.lo)
            self.index_type(e.hi)
            return ty
        if isinstance(e, A.Chr):
            self.index_type(e.expr)
            return StrT(1)
        if isinstance(e, A.Index):
            base = self.typeof(e.base, None)
            if isinstance(base, StrT):
                self.index_type(e.index)
                return U8
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
            if isinstance(lt, StrT):
                return self.str_binary(e, lt, expected)
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
            # v0.3 (S4, P5): == y != también entre structs y entre arreglos; el orden no.
            composite = isinstance(lt, (ArrT, StructT))
            if (composite and (not self.v03 or e.op in ORDER)) \
                    or (e.op in ORDER and isinstance(lt, BoolT)):
                raise InvalidProgram("TYPE_MISMATCH", e.at, f"no se puede comparar {lt}")
            return BoolT()
        if not is_numeric(lt) or (e.op == "%" and isinstance(lt, DecT)):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"'{e.op}' no aplica a {lt}")
        return lt

    def str_binary(self, e: A.Binary, lt: StrT, expected):
        """CORE v0.3 §2.4: concatenación y comparación de strings (capacidades libres)."""
        rt = self.typeof(e.right, None)
        if not isinstance(rt, StrT):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{lt} {e.op} {rt}")
        if e.op in ARITH:
            if e.op != "+":
                raise InvalidProgram("TYPE_MISMATCH", e.at, f"'{e.op}' no aplica a str")
            if isinstance(expected, StrT):
                return expected
            return StrT(min(lt.n + rt.n, MAX_STR))
        return BoolT()

    def struct_literal(self, e: A.StructLit):
        if e.name not in self.program.structs:
            raise InvalidProgram("UNKNOWN_NAME", e.at, e.name)
        ty = self.struct_type(e.name)
        written = [name for name, _, _ in e.fields]
        if sorted(written) != sorted(name for name, _ in ty.fields) or len(set(written)) != len(written):
            raise InvalidProgram("BAD_FIELDS", e.at, f"{e.name}: {written}")
        for name, expr, _ in e.fields:
            self.expect(expr, ty.field(name))
        return ty

    def cast(self, e: A.Cast):
        if self.v03:
            e.target = self.resolve(e.target)
            target = e.target
            if isinstance(target, StrT):
                src = self.typeof(e.expr, target)
            else:
                src = self.typeof(e.expr, target if is_poly(e.expr) else None)
            scalar = (BoolT, IntT, DecT)
            if (isinstance(src, StrT) and isinstance(target, (StrT,) + scalar)) \
                    or (isinstance(src, scalar) and isinstance(target, StrT)):
                return target
        else:
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

    def call(self, e: A.Call, allow_void: bool, expected=None):
        callee = self.program.fns.get(e.name)
        if callee is None:
            raise InvalidProgram("UNKNOWN_NAME", e.at, e.name)
        if len(e.args) != len(callee.params):
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{e.name} espera {len(callee.params)} argumentos")
        destino = None
        if spec.is_contextual(callee):
            callee, destino = self.specialize(e, callee, expected)
        else:
            for arg, (_, ty, _) in zip(e.args, callee.params):
                self.expect(arg, ty)
        if callee.emits:
            self.emits = True
        if callee.ret is None and not allow_void:
            raise InvalidProgram("TYPE_MISMATCH", e.at, f"{e.name} no retorna valor")
        if destino is not None:
            e.name = destino
        return callee.ret

    def specialize(self, e: A.Call, callee: A.Fn, expected=None):
        """V6/V6-bis: instancia la firma y chequea la copia, una sola vez por resolución.

        - Parámetro pelado (V6): la capacidad es el tipo real del argumento. Si no es
          `str`, es TYPE_MISMATCH **en el argumento**.
        - Retorno pelado (V6-bis): la capacidad es la **esperada en la posición de
          llamada** —el tipo declarado del `let`, el `return` del que llama, el blanco
          de un `cast`, el parámetro concreto del destinatario—. Si nada la fija, es
          TYPE_MISMATCH en el llamado: `str` pelado no significa `MAX_STR` ni ningún
          número por defecto.

        No hay inferencia permisiva en ninguna de las dos orillas: un `str<8>` pedido
        con un `str<16>` nunca se recorta. La copia se chequea en el sitio de su primera
        llamada y una sola vez: la clave ya registrada antes de entrar corta la
        recursión, incluida la mutua.
        """
        pelados = spec.contextual_slots(callee)
        widths = []
        for i, (arg, (_, ty, _)) in enumerate(zip(e.args, callee.params)):
            if i not in pelados:
                self.expect(arg, ty)
                continue
            got = self.typeof(arg, None)
            if not isinstance(got, StrT):
                raise InvalidProgram("TYPE_MISMATCH", arg.at, f"se esperaba str, llegó {got}")
            widths.append(got.n)
        widths = tuple(widths)
        ret_width = None
        if isinstance(callee.ret, ContextStrT):
            if not isinstance(expected, StrT):
                raise InvalidProgram("TYPE_MISMATCH", e.at,
                                     f"ninguna capacidad esperada fija el retorno pelado de {callee.name}")
            ret_width = expected.n
        name = spec.spec_name(callee.name, widths, ret_width)
        if name not in self.specs:
            # P4: el presupuesto gasta resoluciones, no sitios de llamada — dos llamadas con
            # el mismo ancho comparten copia y consumen una sola vez.
            conteo = self.spec_counts.get(callee.name, 0) + 1
            self.spec_counts[callee.name] = conteo
            if conteo > spec.MAX_CLONES_PER_DEFINITION:
                raise InvalidProgram("SPEC_LIMIT", e.at,
                                     f"{callee.name} pasa de {spec.MAX_CLONES_PER_DEFINITION} "
                                     f"especializaciones por definición (CORE v0.5 §7)")
            clone = spec.make_clone(callee, name, widths, ret_width)
            self.specs[name] = clone
            self.program.fns[name] = clone
            guardado = (self.fn, self.scopes, self.loop_depth, self.emits)
            try:
                self.check_fn(clone)
            finally:
                self.fn, self.scopes, self.loop_depth, self.emits = guardado
        return self.specs[name], name


def check(program: A.Program) -> None:
    Checker(program).check()
