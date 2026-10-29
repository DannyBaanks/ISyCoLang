"""Validador de mundo cerrado para ISY-IR v0.1.

No confía en el frontend: vuelve a comprobar tipos, locales, llamadas, efectos,
control y retornos sobre el JSON. Cualquier campo o tipo de nodo desconocido es
un error. Un módulo que pasa este validador tiene semántica definida por
spec/CORE.md + spec/IR.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ir import SCHEMA, IRTypeError, ty_from_json
from .types import ArrT, BoolT, DecT, IntT, is_numeric, is_scalar, parse_canonical

EXPR_FIELDS = {
    "const": {"v"}, "local": {"id"}, "call": {"fn", "args"}, "index": {"base", "index"},
    "cast": {"e"}, "neg": {"e"}, "not": {"e"}, "bin": {"op", "a", "b"},
    "cmp": {"op", "a", "b"}, "and": {"a", "b"}, "or": {"a", "b"},
    "array": {"elems"}, "repeat": {"elem"},
}
STMT_FIELDS = {
    "let": {"local", "value"}, "set": {"local", "value"},
    "set_index": {"local", "index", "value"}, "if": {"cond", "then", "else"},
    "while": {"cond", "body"}, "break": set(), "continue": set(), "return": {"value"},
    "emit": {"value"}, "call": {"call_at", "fn", "args"},
}
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


def _ty(j, path):
    try:
        return ty_from_json(j)
    except IRTypeError as exc:
        raise _Bad("IR_TYPE", path, str(exc)) from None


class Validator:
    def __init__(self, module):
        self.module = module
        self.diags: list[Diagnostic] = []
        self.sigs: dict = {}

    def run(self) -> None:
        m = self.module
        if not isinstance(m, dict) or m.get("schema") != SCHEMA \
                or set(m) != {"schema", "source_sha256", "functions"} \
                or not isinstance(m["functions"], list):
            raise IRInvalid([Diagnostic("IR_SCHEMA", "$", f"se esperaba {SCHEMA}")])
        for i, fn in enumerate(m["functions"]):
            path = f"functions[{i}]"
            try:
                _fields(fn, FN_FIELDS - {"at"}, path, "name")
                name = fn["name"]
                if not isinstance(name, str) or name in self.sigs:
                    raise _Bad("IR_CALL", path, f"nombre de función inválido o repetido: {name!r}")
                locals_ = [_ty(loc.get("ty") if isinstance(loc, dict) else None, f"{path}.locals[{j}]")
                           for j, loc in enumerate(fn["locals"])]
                params = fn["params"]
                if params != list(range(len(params))) or len(params) > len(locals_):
                    raise _Bad("IR_LOCAL", path, "params deben ser los primeros locales 0..k-1")
                self.sigs[name] = ([locals_[p] for p in params], _ty(fn["ret"], f"{path}.ret"),
                                   fn["emits"] is True)
            except _Bad as bad:
                self.diags.append(bad.diag)
        if "main" not in self.sigs:
            self.diags.append(Diagnostic("IR_CALL", "$", "falta main"))
        elif self.sigs["main"][1] is not None and not is_scalar(self.sigs["main"][1]):
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
        if kind not in STMT_FIELDS:
            raise _Bad("IR_NODE", path, f"sentencia desconocida {kind!r}")
        _fields(s, STMT_FIELDS[kind], path, "s")
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
            if not is_scalar(self.expr(s["value"], f"{path}.value")):
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
        if kind not in EXPR_FIELDS:
            raise _Bad("IR_NODE", path, f"expresión desconocida {kind!r}")
        _fields(e, EXPR_FIELDS[kind] | {"ty"}, path, "k")
        ty = _ty(e["ty"], f"{path}.ty")
        got = self._expr(kind, e, ty, path)
        if got != ty:
            raise _Bad("IR_TYPE", path, f"{kind}: el nodo dice {ty}, la regla da {got}")
        return ty

    def _expr(self, kind, e, ty, path):
        if kind == "const":
            if not is_scalar(ty) or parse_canonical(e["v"], ty) is None:
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
            if not isinstance(base, ArrT) or not isinstance(self.expr(e["index"], f"{path}.index"), IntT):
                raise _Bad("IR_TYPE", path, "index requiere arreglo e índice entero")
            return base.elem
        if kind == "cast":
            src = self.expr(e["e"], f"{path}.e")
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
        if kind in ("bin", "cmp"):
            a = self.expr(e["a"], f"{path}.a")
            b = self.expr(e["b"], f"{path}.b")
            if a != b:
                raise _Bad("IR_TYPE", path, f"{a} vs {b}")
            if kind == "cmp":
                if e["op"] not in ("eq", "ne", "lt", "le", "gt", "ge") or isinstance(a, ArrT) \
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
    """Lanza IRInvalid con diagnósticos si el módulo no es ISY-IR v0.1 válido."""
    Validator(module).run()
