"""Validador de mundo cerrado para ISY-IR v0.1 y v0.2.

No confía en el frontend: vuelve a comprobar tipos, locales, llamadas, efectos,
control y retornos sobre el JSON. Cualquier campo o tipo de nodo desconocido es
un error. Un módulo que pasa este validador tiene semántica definida por
spec/CORE.md + spec/IR.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ir import SCHEMA_V2, SCHEMAS, IRTypeError, ty_from_json
from .types import (INT_ALIASES, U8, ArrT, BoolT, DecT, IntT, StrT, StructT, is_numeric,
                    is_scalar, parse_canonical)

EXPR_FIELDS = {
    "const": {"v"}, "local": {"id"}, "call": {"fn", "args"}, "index": {"base", "index"},
    "cast": {"e"}, "neg": {"e"}, "not": {"e"}, "bin": {"op", "a", "b"},
    "cmp": {"op", "a", "b"}, "and": {"a", "b"}, "or": {"a", "b"},
    "array": {"elems"}, "repeat": {"elem"},
}
EXPR_FIELDS_V2 = {
    "field": {"base", "name"}, "struct": {"fields"}, "len": {"e"}, "slice": {"e", "lo", "hi"},
    "chr": {"e"}, "concat": {"a", "b"}, "widen": {"e"},
}
STMT_FIELDS = {
    "let": {"local", "value"}, "set": {"local", "value"},
    "set_index": {"local", "index", "value"}, "if": {"cond", "then", "else"},
    "while": {"cond", "body"}, "break": set(), "continue": set(), "return": {"value"},
    "emit": {"value"}, "call": {"call_at", "fn", "args"},
}
STMT_FIELDS_V2 = {"set_path": {"local", "path", "value"}}
FN_FIELDS = {"name", "at", "params", "ret", "emits", "locals", "body"}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    message: str


class IRInvalid(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]):
        super().__init__("; ".join(f"{d.code} {d.path}: {d.message}" for d in diagnostics[:5]))
        self.diagnostics = diagnostics


class _Bad(Exception):
    def __init__(self, code: str, path: str, message: str):
        self.diag = Diagnostic(code, path, message)


def _fields(node, expected: set, path: str, tag: str) -> None:
    if not isinstance(node, dict):
        raise _Bad("IR_NODE", path, "no es objeto")
    extra = set(node) - expected - {tag, "at"}
    missing = expected - set(node)
    if extra or missing or not isinstance(node.get("at"), str):
        raise _Bad("IR_NODE", path, f"campos sobrantes {sorted(extra)} / faltantes {sorted(missing)}")


def _has_v2_type(t) -> bool:
    if isinstance(t, (StrT, StructT)):
        return True
    return isinstance(t, ArrT) and _has_v2_type(t.elem)


def _ty(j, path, v2: bool):
    try:
        t = ty_from_json(j)
    except IRTypeError as exc:
        raise _Bad("IR_TYPE", path, str(exc)) from None
    if not v2 and _has_v2_type(t):
        raise _Bad("IR_TYPE", path, f"{t} solo existe en {SCHEMA_V2}")
    return t


class Validator:
    def __init__(self, module):
        self.module = module
        self.diags: list[Diagnostic] = []
        self.sigs: dict = {}
        self.v2 = False

    def run(self) -> None:
        m = self.module
        if not isinstance(m, dict) or m.get("schema") not in SCHEMAS \
                or set(m) != {"schema", "source_sha256", "functions"} \
                or not isinstance(m["functions"], list):
            raise IRInvalid([Diagnostic("IR_SCHEMA", "$", f"se esperaba uno de {SCHEMAS}")])
        self.v2 = m["schema"] == SCHEMA_V2
        for i, fn in enumerate(m["functions"]):
            path = f"functions[{i}]"
            try:
                _fields(fn, FN_FIELDS - {"at"}, path, "name")
                name = fn["name"]
                if not isinstance(name, str) or name in self.sigs:
                    raise _Bad("IR_CALL", path, f"nombre de función inválido o repetido: {name!r}")
                locals_ = [_ty(loc.get("ty") if isinstance(loc, dict) else None, f"{path}.locals[{j}]",
                               self.v2)
                           for j, loc in enumerate(fn["locals"])]
                params = fn["params"]
                if params != list(range(len(params))) or len(params) > len(locals_):
                    raise _Bad("IR_LOCAL", path, "params deben ser los primeros locales 0..k-1")
                self.sigs[name] = ([locals_[p] for p in params], _ty(fn["ret"], f"{path}.ret", self.v2),
                                   fn["emits"] is True)
            except _Bad as bad:
                self.diags.append(bad.diag)
        if "main" not in self.sigs:
            self.diags.append(Diagnostic("IR_CALL", "$", "falta main"))
        elif not self.v2 and self.sigs["main"][1] is not None and not is_scalar(self.sigs["main"][1]):
            self.diags.append(Diagnostic("IR_TYPE", "$", "main debe retornar un escalar"))
        if self.diags:
            raise IRInvalid(self.diags)
        for i, fn in enumerate(m["functions"]):
            try:
                _FnValidator(self, fn, f"functions[{i}]").run()
            except _Bad as bad:
                self.diags.append(bad.diag)
        if self.diags:
            raise IRInvalid(self.diags)


class _FnValidator:
    def __init__(self, parent: Validator, fn: dict, path: str):
        self.sigs = parent.sigs
        self.v2 = parent.v2
        self.stmt_fields = {**STMT_FIELDS, **STMT_FIELDS_V2} if self.v2 else STMT_FIELDS
        self.expr_fields = {**EXPR_FIELDS, **EXPR_FIELDS_V2} if self.v2 else EXPR_FIELDS
        self.fn = fn
        self.path = path
        self.locals = [ty_from_json(loc["ty"]) for loc in fn["locals"]]
        self.names = [loc.get("name") for loc in fn["locals"]]
        self.ret = self.sigs[fn["name"]][1]
        self.declared_emits = fn["emits"]
        self.emits = False
        self.loop_depth = 0
        self.visible: list[set] = [set(fn["params"])]
        self.bound: set = set(fn["params"])

    def run(self) -> None:
        if not all(isinstance(n, str) for n in self.names):
            raise _Bad("IR_LOCAL", self.path, "todo local necesita nombre")
        self.block(self.fn["body"], f"{self.path}.body")
        if len(self.bound) != len(self.locals):
            raise _Bad("IR_LOCAL", self.path, "hay locales que nunca se declaran con let")
        if self.ret is not None and not _always_returns(self.fn["body"]):
            raise _Bad("IR_RETURN", self.path, "falta retorno en algún camino")
        if self.emits and not self.declared_emits:
            raise _Bad("IR_EFFECT", self.path, "emite sin declarar emits")

    def is_visible(self, local) -> bool:
        return any(local in scope for scope in self.visible)

    def local_ty(self, local, path):
        if not isinstance(local, int) or not 0 <= local < len(self.locals) or not self.is_visible(local):
            raise _Bad("IR_LOCAL", path, f"local {local!r} inexistente o fuera de alcance")
        return self.locals[local]

    # --- sentencias -----------------------------------------------------------
    def block(self, stmts, path) -> None:
        if not isinstance(stmts, list):
            raise _Bad("IR_NODE", path, "bloque no es lista")
        self.visible.append(set())
        for i, s in enumerate(stmts):
            self.stmt(s, f"{path}[{i}]")
        self.visible.pop()

    def stmt(self, s, path) -> None:
        kind = s.get("s") if isinstance(s, dict) else None
        if kind not in self.stmt_fields:
            raise _Bad("IR_NODE", path, f"sentencia desconocida {kind!r}")
        _fields(s, self.stmt_fields[kind], path, "s")
        if kind == "let":
            local = s["local"]
            if not isinstance(local, int) or not 0 <= local < len(self.locals) or local in self.bound:
                raise _Bad("IR_LOCAL", path, f"let de local {local!r} inválido o repetido")
            if any(self.names[local] == self.names[o] for scope in self.visible for o in scope):
                raise _Bad("IR_LOCAL", path, f"nombre {self.names[local]!r} ya visible")
            self.expect(s["value"], self.locals[local], f"{path}.value")
            self.bound.add(local)
            self.visible[-1].add(local)
        elif kind == "set":
            self.expect(s["value"], self.local_ty(s["local"], path), f"{path}.value")
        elif kind == "set_index":
            ty = self.local_ty(s["local"], path)
            if not isinstance(ty, ArrT):
                raise _Bad("IR_TYPE", path, "set_index sobre algo que no es arreglo")
            if not isinstance(self.expr(s["index"], f"{path}.index"), IntT):
                raise _Bad("IR_TYPE", path, "índice no entero")
            self.expect(s["value"], ty.elem, f"{path}.value")
        elif kind == "set_path":
            ty = self.local_ty(s["local"], path)
            steps = s["path"]
            if not isinstance(steps, list) or not steps:
                raise _Bad("IR_NODE", path, "set_path sin pasos")
            for i, step in enumerate(steps):
                spath = f"{path}.path[{i}]"
                if isinstance(step, dict) and set(step) == {"index"}:
                    if not isinstance(ty, ArrT):
                        raise _Bad("IR_TYPE", spath, f"index sobre {ty}")
                    if not isinstance(self.expr(step["index"], spath), IntT):
                        raise _Bad("IR_TYPE", spath, "índice no entero")
                    ty = ty.elem
                elif isinstance(step, dict) and set(step) == {"field"}:
                    if not isinstance(ty, StructT) or ty.field(step["field"]) is None:
                        raise _Bad("IR_TYPE", spath, f"campo {step['field']!r} sobre {ty}")
                    ty = ty.field(step["field"])
                else:
                    raise _Bad("IR_NODE", spath, "paso inválido")
            self.expect(s["value"], ty, f"{path}.value")
        elif kind == "if":
            self.expect(s["cond"], BoolT(), f"{path}.cond")
            self.block(s["then"], f"{path}.then")
            if s["else"] is not None:
                self.block(s["else"], f"{path}.else")
        elif kind == "while":
            self.expect(s["cond"], BoolT(), f"{path}.cond")
            self.loop_depth += 1
            self.block(s["body"], f"{path}.body")
            self.loop_depth -= 1
        elif kind in ("break", "continue"):
            if self.loop_depth == 0:
                raise _Bad("IR_CONTROL", path, f"{kind} fuera de while")
        elif kind == "return":
            if (s["value"] is None) != (self.ret is None):
                raise _Bad("IR_RETURN", path, "return no coincide con el tipo de la función")
            if s["value"] is not None:
                self.expect(s["value"], self.ret, f"{path}.value")
        elif kind == "emit":
            if not is_scalar(self.expr(s["value"], f"{path}.value")) and not self.v2:
                raise _Bad("IR_TYPE", path, "emit solo acepta escalares")
            self.emits = True
        elif kind == "call":
            if not isinstance(s["call_at"], str):
                raise _Bad("IR_NODE", path, "call_at")
            self.call(s["fn"], s["args"], path)

    # --- expresiones ----------------------------------------------------------
    def expect(self, e, ty, path) -> None:
        got = self.expr(e, path)
        if got != ty:
            raise _Bad("IR_TYPE", path, f"se esperaba {ty}, el nodo dice {got}")

    def call(self, name, args, path):
        if name not in self.sigs:
            raise _Bad("IR_CALL", path, f"función desconocida {name!r}")
        params, ret, emits = self.sigs[name]
        if not isinstance(args, list) or len(args) != len(params):
            raise _Bad("IR_CALL", path, f"aridad de {name}")
        for i, (arg, ty) in enumerate(zip(args, params)):
            self.expect(arg, ty, f"{path}.args[{i}]")
        if emits:
            self.emits = True
        return ret

    def expr(self, e, path):
        kind = e.get("k") if isinstance(e, dict) else None
        if kind not in self.expr_fields:
            raise _Bad("IR_NODE", path, f"expresión desconocida {kind!r}")
        _fields(e, self.expr_fields[kind] | {"ty"}, path, "k")
        ty = _ty(e["ty"], f"{path}.ty", self.v2)
        got = self._expr(kind, e, ty, path)
        if got != ty:
            raise _Bad("IR_TYPE", path, f"{kind}: el nodo dice {ty}, la regla da {got}")
        return ty

    def _expr(self, kind, e, ty, path):
        if kind == "const":
            if not (is_scalar(ty) or isinstance(ty, StrT)) or parse_canonical(e["v"], ty) is None:
                raise _Bad("IR_TYPE", path, f"const {e['v']!r} no es forma canónica de {ty}")
            return ty
        if kind == "local":
            return self.local_ty(e["id"], path)
        if kind == "call":
            ret = self.call(e["fn"], e["args"], path)
            if ret is None:
                raise _Bad("IR_CALL", path, "llamada sin valor usada como expresión")
            return ret
        if kind == "index":
            base = self.expr(e["base"], f"{path}.base")
            if not isinstance(base, (ArrT, StrT)) or not isinstance(self.expr(e["index"], f"{path}.index"), IntT):
                raise _Bad("IR_TYPE", path, "index requiere arreglo o str e índice entero")
            return U8 if isinstance(base, StrT) else base.elem
        if kind == "cast":
            src = self.expr(e["e"], f"{path}.e")
            scalar = (BoolT, IntT, DecT)
            if (isinstance(src, StrT) and isinstance(ty, (StrT,) + scalar)) \
                    or (isinstance(src, scalar) and isinstance(ty, StrT)):
                return ty
            if not (is_numeric(src) and is_numeric(ty)):
                raise _Bad("IR_TYPE", path, f"cast {src} -> {ty}")
            return ty
        if kind == "neg":
            inner = self.expr(e["e"], f"{path}.e")
            if not is_numeric(inner):
                raise _Bad("IR_TYPE", path, "neg requiere número")
            return inner
        if kind == "not":
            self.expect(e["e"], BoolT(), f"{path}.e")
            return BoolT()
        if kind in ("and", "or"):
            self.expect(e["a"], BoolT(), f"{path}.a")
            self.expect(e["b"], BoolT(), f"{path}.b")
            return BoolT()
        if kind == "cmp" and e.get("op") in ("eq", "ne", "lt", "le", "gt", "ge"):
            a = self.expr(e["a"], f"{path}.a")
            b = self.expr(e["b"], f"{path}.b")
            if isinstance(a, StrT) and isinstance(b, StrT):
                return BoolT()   # v0.3: la capacidad no cuenta al comparar
        if kind in ("bin", "cmp"):
            a = self.expr(e["a"], f"{path}.a")
            b = self.expr(e["b"], f"{path}.b")
            if a != b:
                raise _Bad("IR_TYPE", path, f"{a} vs {b}")
            if kind == "cmp":
                composite = isinstance(a, (ArrT, StructT))
                if e["op"] not in ("eq", "ne", "lt", "le", "gt", "ge") \
                        or (composite and (not self.v2 or e["op"] not in ("eq", "ne"))) \
                        or (e["op"] not in ("eq", "ne") and isinstance(a, BoolT)):
                    raise _Bad("IR_TYPE", path, f"cmp {e['op']} sobre {a}")
                return BoolT()
            if e["op"] not in ("add", "sub", "mul", "div", "rem") or not is_numeric(a) \
                    or (e["op"] == "rem" and isinstance(a, DecT)):
                raise _Bad("IR_TYPE", path, f"bin {e['op']} sobre {a}")
            return a
        if kind == "array":
            if not isinstance(ty, ArrT) or not isinstance(e["elems"], list) or len(e["elems"]) != ty.n:
                raise _Bad("IR_TYPE", path, "array con tamaño incorrecto")
            for i, item in enumerate(e["elems"]):
                self.expect(item, ty.elem, f"{path}.elems[{i}]")
            return ty
        if kind == "repeat":
            if not isinstance(ty, ArrT):
                raise _Bad("IR_TYPE", path, "repeat sin tipo arreglo")
            self.expect(e["elem"], ty.elem, f"{path}.elem")
            return ty
        return self._expr_v2(kind, e, ty, path)

    def _expr_v2(self, kind, e, ty, path):
        def str_of(key):
            t = self.expr(e[key], f"{path}.{key}")
            if not isinstance(t, StrT):
                raise _Bad("IR_TYPE", path, f"{kind}.{key} debe ser str, es {t}")
            return t

        if kind == "concat":
            str_of("a")
            str_of("b")
            if not isinstance(ty, StrT):
                raise _Bad("IR_TYPE", path, "concat debe dar str")
            return ty
        if kind == "widen":
            src = str_of("e")
            if not isinstance(ty, StrT) or src.n > ty.n:
                raise _Bad("IR_TYPE", path, f"widen {src} -> {ty} no ensancha")
            return ty
        if kind == "len":
            str_of("e")
            return INT_ALIASES["i64"]
        if kind == "slice":
            src = str_of("e")
            for key in ("lo", "hi"):
                if not isinstance(self.expr(e[key], f"{path}.{key}"), IntT):
                    raise _Bad("IR_TYPE", path, f"slice.{key} no entero")
            return src
        if kind == "chr":
            if not isinstance(self.expr(e["e"], f"{path}.e"), IntT):
                raise _Bad("IR_TYPE", path, "chr requiere entero")
            return StrT(1)
        if kind == "field":
            base = self.expr(e["base"], f"{path}.base")
            if not isinstance(base, StructT) or base.field(e["name"]) is None:
                raise _Bad("IR_TYPE", path, f"campo {e['name']!r} sobre {base}")
            return base.field(e["name"])
        if kind == "struct":
            items = e["fields"]
            if not isinstance(ty, StructT) or not isinstance(items, list) \
                    or not all(isinstance(f, dict) and set(f) == {"name", "value"} for f in items):
                raise _Bad("IR_TYPE", path, "struct mal formado")
            names = [f["name"] for f in items]
            if sorted(names) != sorted(n for n, _ in ty.fields) or len(set(names)) != len(names):
                raise _Bad("IR_TYPE", path, f"campos {names} para {ty}")
            for i, f in enumerate(items):
                self.expect(f["value"], ty.field(f["name"]), f"{path}.fields[{i}]")
            return ty
        raise AssertionError(kind)


def _always_returns(stmts) -> bool:
    for s in stmts:
        if s["s"] == "return":
            return True
        if s["s"] == "if" and s["else"] is not None \
                and _always_returns(s["then"]) and _always_returns(s["else"]):
            return True
    return False


def validate(module) -> None:
    """Lanza IRInvalid con diagnósticos si el módulo no es ISY-IR v0.1/v0.2 válido."""
    Validator(module).run()
