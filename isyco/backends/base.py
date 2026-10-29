"""ISY_BACKEND/1: driver compartido por los backends nativos (spec/BACKEND.md).

Un backend concreto solo aporta:
- `name` y `features` (capacidades de la IR que implementa; ver features_of);
- `emit(module, sabotage)` -> código fuente en su lenguaje;
- `compile_cmd(source_path, binary_path)` -> comando del toolchain;
- `toolchain()` -> versión del compilador, o None si no está instalado.

Todo lo demás (validar la IR, revisar capacidades, validar la entrada, compilar
con caché, ejecutar con límites y leer el protocolo E/R/X) vive aquí, igual
para todos.
"""
from __future__ import annotations

import hashlib
import os
import resource
import subprocess
from pathlib import Path

from ..errors import InvalidProgram
from ..interp import DEFAULT_LIMITS, canonical_json
from ..interp import run as run_reference
from ..ir import ty_from_json
from ..ir_interp import compile_ir
from ..types import ArrT, BoolT, DecT, IntT, parse_canonical

BUILD_ROOT = Path(__file__).resolve().parents[2] / "build"

ALL_FEATURES = frozenset(
    {f"int{bits}" for bits in (8, 16, 32, 64)}
    | {"unsigned", "ovf:trap", "ovf:wrap", "ovf:sat", "dec", "dec:half_even", "dec:half_up",
       "dec:down", "dec:exact", "bool", "arrays", "calls", "recursion", "while", "emit"})


# --- capacidades -------------------------------------------------------------------

def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _type_features(t, out: set) -> None:
    if isinstance(t, BoolT):
        out.add("bool")
    elif isinstance(t, IntT):
        out.add(f"int{t.bits}")
        out.add(f"ovf:{t.ovf}")
        if not t.signed:
            out.add("unsigned")
    elif isinstance(t, DecT):
        out.update({"dec", f"dec:{t.rnd}"})
    elif isinstance(t, ArrT):
        out.add("arrays")
        _type_features(t.elem, out)


def features_of(module: dict) -> set[str]:
    """Capacidades que un módulo ISY-IR necesita de un backend."""
    out: set[str] = set()
    calls: dict[str, set[str]] = {}
    for fn in module["functions"]:
        calls[fn["name"]] = set()
        for local in fn["locals"]:
            _type_features(ty_from_json(local["ty"]), out)
        for node in _walk(fn["body"]):
            if "ty" in node:
                _type_features(ty_from_json(node["ty"]), out)
            if node.get("k") == "call" or node.get("s") == "call":
                out.add("calls")
                calls[fn["name"]].add(node["fn"])
            if node.get("s") == "while":
                out.add("while")
            if node.get("s") == "emit":
                out.add("emit")
    # recursión = algún ciclo en el grafo de llamadas
    def reaches(start: str, target: str, seen: set) -> bool:
        for nxt in calls.get(start, ()):
            if nxt == target or (nxt not in seen and reaches(nxt, target, seen | {nxt})):
                return True
        return False
    if any(reaches(name, name, {name}) for name in calls):
        out.add("recursion")
    return out


# --- backend ------------------------------------------------------------------------

class Backend:
    name = "abstract"
    extension = ".txt"
    features: frozenset = ALL_FEATURES
    sabotages: tuple = ()

    def toolchain(self) -> str | None:
        raise NotImplementedError

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        raise NotImplementedError

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        raise NotImplementedError

    # --- compilación con caché ------------------------------------------------
    def build(self, source: str, extra_flags: tuple = ()) -> Path:
        # `toolchain()` lanza un subproceso (--version); el diferencial llama a
        # build miles de veces con el mismo binario, así que se memoriza.
        version = getattr(self, "_toolchain_version", None)
        if version is None:
            version = self._toolchain_version = self.toolchain() or "?"
        key = hashlib.sha256("\0".join([self.name, version, *extra_flags, source]).encode()) \
            .hexdigest()[:24]
        directory = BUILD_ROOT / self.name
        binary = directory / key
        if binary.exists():
            return binary
        directory.mkdir(parents=True, exist_ok=True)
        src = directory / f"{key}{self.extension}"
        src.write_text(source, encoding="utf-8")
        tmp = directory / f"{key}.tmp{os.getpid()}"
        proc = subprocess.run(self.compile_cmd(src, tmp, extra_flags), capture_output=True,
                              text=True, cwd=directory)
        if proc.returncode != 0:
            raise RuntimeError(f"{self.name}: el compilador falló:\n{(proc.stderr or proc.stdout)[:4000]}")
        tmp.replace(binary)
        return binary

    # --- ejecución ------------------------------------------------------------
    def run(self, data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
            timeout_ms: int | None = 60_000, sabotage: str | None = None,
            extra_flags: tuple = ()) -> tuple[dict, list]:
        """Mismo contrato que interp.run. No produce traza."""
        lim = dict(DEFAULT_LIMITS)
        lim.update(limits or {})
        try:
            module = compile_ir(data)
        except InvalidProgram:
            return run_reference(data, inputs, limits)   # frontend compartido
        args = raw_args(module, inputs)
        if args is None:
            return run_reference(data, inputs, limits)   # BAD_INPUT lo decide el frontend
        result = {
            "schema": "isyco.result/0.1",
            "program_sha256": hashlib.sha256(data).hexdigest(),
            "input_sha256": hashlib.sha256(canonical_json(inputs).encode("utf-8")).hexdigest(),
            "limits": lim, "backend": self.name,
        }
        missing = sorted(features_of(module) - set(self.features))
        if missing:
            result.update(status="UNSUPPORTED", code=",".join(missing), emits=[], steps=None)
            result["return"] = None
            return result, []
        binary = self.build(self.emit(module, sabotage), extra_flags)
        try:
            proc = subprocess.run(
                [str(binary), str(lim["max_steps"]), str(lim["max_call_depth"]),
                 str(lim["max_emits"]), *args],
                capture_output=True, text=True, preexec_fn=_raise_stack_limit,
                timeout=None if timeout_ms is None else timeout_ms / 1000)
        except subprocess.TimeoutExpired:
            result.update(status="TIMEOUT", code=None, emits=[], steps=None)
            result["return"] = None
            return result, []
        result.update(parse_output(proc.stdout))
        if proc.returncode != 0 or proc.stderr:
            result["backend_stderr"] = proc.stderr[:2000]
            result["backend_exit"] = proc.returncode
            if proc.returncode != 0:
                result["status"] = "BACKEND_CRASH"
        return result, []


def _raise_stack_limit() -> None:
    """Pila grande para recursión profunda con arreglos copiados por valor (hasta el hard limit)."""
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    target = hard if hard != resource.RLIM_INFINITY else 1 << 30
    if soft != resource.RLIM_INFINITY and soft < target:
        resource.setrlimit(resource.RLIMIT_STACK, (target, hard))


def raw_args(module: dict, inputs: list) -> list[str] | None:
    """Valida la entrada canónica (como la referencia) y la pasa a valores crudos."""
    main = next(f for f in module["functions"] if f["name"] == "main")
    types = [ty_from_json(main["locals"][p]["ty"]) for p in main["params"]]
    if not isinstance(inputs, list) or len(inputs) != len(types):
        return None
    out = []
    for text, t in zip(inputs, types):
        value = parse_canonical(text, t)
        if value is None:
            return None
        for v in (value if isinstance(t, ArrT) else [value]):
            out.append(str(int(v)))
    return out


def parse_output(stdout: str) -> dict:
    emits, ret, status, code, steps = [], None, None, None, None
    for line in stdout.split("\n"):
        if line.startswith("E "):
            emits.append(line[2:])
        elif line.startswith("R "):
            ret = line[2:]
        elif line.startswith("X "):
            _, status, code, steps = line.split(" ")
            code = None if code == "-" else code
            steps = int(steps)
    if status is None:
        return {"status": "BACKEND_CRASH", "code": None, "emits": emits, "return": ret, "steps": None}
    return {"status": status, "code": code, "emits": emits, "return": ret, "steps": steps}

