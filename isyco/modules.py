"""Módulos de CORE v0.4: carga, chequeo de imports y enlace a un solo programa.

El resultado es un `Program` como el de un archivo único, con los nombres de los
módulos importados calificados por su ruta (P7: `geo/punto.isy` aporta
`geo.punto.f`, `geo.punto.P`). Desde ahí el checker, la IR y los backends no
saben que hubo varios archivos.

Orden de los errores (CORE v0.4 §5): el archivo principal → sus imports en el
orden escrito, en profundidad (existe → no está en el camino → cabecera → lexer y
parser → sus imports) → enlace de cada módulo en orden de carga.
"""
from __future__ import annotations

import dataclasses
import hashlib

from . import ast as A
from .errors import InvalidProgram
from .lexer import decode, header_version, tokenize
from .parser import parse
from .source import Bundle
from .types import ArrT, NamedT


def load_program(source) -> A.Program:
    """bytes o Bundle -> Program enlazado (sin chequear tipos todavía)."""
    if not isinstance(source, Bundle):
        program = parse(tokenize(decode(source)))
        if program.imports:   # un archivo suelto no tiene de dónde leer módulos
            raise InvalidProgram("UNKNOWN_MODULE", program.imports[0].at, program.imports[0].file)
        return program
    root = parse(tokenize(decode(source.main_bytes)))
    if root.version != "0.4":
        return root
    loaded: dict[str, A.Program] = {}

    def visit(program: A.Program, path_stack: tuple) -> None:
        for imp in program.imports:
            data = source.get(imp.file)
            if data is None:
                raise InvalidProgram("UNKNOWN_MODULE", imp.at, imp.file)
            if imp.file in path_stack:
                raise InvalidProgram("IMPORT_CYCLE", imp.at, " -> ".join(path_stack + (imp.file,)))
            if imp.file in loaded:
                continue
            text = decode(data)
            if header_version(text) != "0.4":
                raise InvalidProgram("VERSION_MISMATCH", imp.at, imp.file)
            module = parse(tokenize(text, prefix=f"{imp.file}:"))
            loaded[imp.file] = module
            visit(module, path_stack + (imp.file,))

    visit(root, (source.main,))
    return _link(root, loaded, source)


def module_prefix(path: str) -> str:
    """`geo/punto.isy` -> `geo.punto.` (P7)."""
    return path[: -len(".isy")].replace("/", ".") + "."


class _Linker:
    def __init__(self, program: A.Program, prefix: str, modules: dict):
        self.program = program
        self.prefix = prefix
        self.modules = modules                     # ruta -> Program (sin renombrar)
        self.aliases = {imp.alias: imp.file for imp in program.imports}

    # --- espacio de nombres del archivo (P2, P3) ---------------------------------
    def check_aliases(self) -> None:
        seen: set[str] = set()
        for imp in self.program.imports:
            if imp.alias in seen:
                raise InvalidProgram("DUPLICATE_NAME", imp.at, imp.alias)
            seen.add(imp.alias)
        for name, decl in list(self.program.structs.items()) + list(self.program.fns.items()):
            if name in self.aliases:
                raise InvalidProgram("DUPLICATE_NAME", decl.at, name)
        for fn in self.program.fns.values():
            for name, _, at in fn.params:
                if name in self.aliases:
                    raise InvalidProgram("DUPLICATE_NAME", at, name)
            for node in _walk(fn.body):
                if isinstance(node, A.Let) and node.name in self.aliases:
                    raise InvalidProgram("DUPLICATE_NAME", node.at, node.name)

    # --- resolución de nombres (M1, M2) -----------------------------------------
    def resolve(self, name: str, at: str, kind: str) -> str:
        """kind: "fns" o "structs". Devuelve el nombre ya enlazado."""
        if "." not in name:
            own = getattr(self.program, kind)
            return self.prefix + name if name in own else name   # si no existe, lo dice el checker
        alias, member = name.split(".", 1)
        if alias not in self.aliases:
            raise InvalidProgram("UNKNOWN_NAME", at, f"{alias} no es un import de este archivo")
        target_path = self.aliases[alias]
        target = self.modules[target_path]
        if member not in getattr(target, kind):
            raise InvalidProgram("UNKNOWN_NAME", at, name)
        if member not in target.public:
            raise InvalidProgram("NOT_PUBLIC", at, name)
        return module_prefix(target_path) + member

    def type_(self, t):
        if isinstance(t, NamedT):
            return NamedT(self.resolve(t.name, t.at, "structs"), t.at)
        if isinstance(t, ArrT):
            return ArrT(self.type_(t.elem), t.n)
        return t

    def link(self) -> tuple[dict, dict]:
        self.check_aliases()
        structs = {}
        for name, decl in self.program.structs.items():
            fields = [(fname, self.type_(ty), at) for fname, ty, at in decl.fields]
            structs[self.prefix + name] = A.StructDecl(decl.at, self.prefix + name, fields)
        fns = {}
        for name, fn in self.program.fns.items():
            params = [(pname, self.type_(ty), at) for pname, ty, at in fn.params]
            for node in _walk(fn.body):
                if isinstance(node, A.Call):
                    node.name = self.resolve(node.name, node.at, "fns")
                elif isinstance(node, A.StructLit):
                    node.name = self.resolve(node.name, node.at, "structs")
                elif isinstance(node, A.Let):
                    node.type = self.type_(node.type)
                elif isinstance(node, A.Cast):
                    node.target = self.type_(node.target)
            fns[self.prefix + name] = A.Fn(fn.at, self.prefix + name, params, self.type_(fn.ret),
                                           fn.emits, fn.body)
        return fns, structs


def _link(root: A.Program, loaded: dict, source: Bundle) -> A.Program:
    fns, structs = {}, {}
    for program, prefix in [(root, "")] + [(m, module_prefix(p)) for p, m in loaded.items()]:
        more_fns, more_structs = _Linker(program, prefix, loaded).link()
        fns.update(more_fns)
        structs.update(more_structs)
    modules = {path: hashlib.sha256(source.get(path) or b"").hexdigest() for path in loaded}
    return A.Program(fns, root.version, structs, [], set(), modules)


def _walk(node):
    """Todos los nodos del AST bajo `node` (sentencias y expresiones), en orden de fuente."""
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, (A.Expr, A.Stmt, A.Block)):
        yield node
        for f in dataclasses.fields(node):
            if f.name not in ("ty", "target_ty", "steps_ty", "type", "target"):
                yield from _walk(getattr(node, f.name))
