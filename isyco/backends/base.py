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
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ..errors import InvalidProgram
from ..interp import DEFAULT_LIMITS, canonical_json
from ..interp import run as run_reference
from ..ir import SCHEMA_V2, ty_from_json
from ..ir_interp import compile_ir
from ..types import ArrT, BoolT, DecT, IntT, StrT, StructT, parse_canonical

BUILD_ROOT = Path(__file__).resolve().parents[2] / "build"
GNU_TIME = "/usr/bin/time" if Path("/usr/bin/time").exists() else None   # GNU time: pico de memoria

ALL_FEATURES = frozenset(
    {f"int{bits}" for bits in (8, 16, 32, 64)}
    | {"unsigned", "ovf:trap", "ovf:wrap", "ovf:sat", "dec", "dec:half_even", "dec:half_up",
       "dec:down", "dec:exact", "bool", "arrays", "calls", "recursion", "while", "emit",
       "ir0.2", "str", "struct"})
# Lo que trae isy-ir/0.2 (CORE v0.3): ningún backend nativo lo implementa todavía.
V2_FEATURES = frozenset({"ir0.2", "str", "struct"})


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
    elif isinstance(t, StrT):
        out.add("str")
    elif isinstance(t, StructT):
        out.add("struct")
        for _, ft in t.fields:
            _type_features(ft, out)


def features_of(module: dict) -> set[str]:
    """Capacidades que un módulo ISY-IR necesita de un backend."""
    out: set[str] = set()
    if module.get("schema") == SCHEMA_V2:
        out.add("ir0.2")
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
    features: frozenset = ALL_FEATURES - V2_FEATURES
    sabotages: tuple = ()

    def toolchain(self) -> str | None:
        raise NotImplementedError

    def emit(self, module: dict, sabotage: str | None = None) -> str:
        raise NotImplementedError

    def compile_cmd(self, source: Path, binary: Path, extra_flags: tuple) -> list[str]:
        raise NotImplementedError

    # --- compilación con caché ------------------------------------------------
    def build(self, source: str, extra_flags: tuple = ()) -> tuple[Path, float | None]:
        """Binario compilado y ms de compilación (None si venía de la caché)."""
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
            return binary, None
        directory.mkdir(parents=True, exist_ok=True)
        src = directory / f"{key}{self.extension}"
        src.write_text(source, encoding="utf-8")
        tmp = directory / f"{key}.tmp{os.getpid()}"
        start = time.perf_counter()
        proc = subprocess.run(self.compile_cmd(src, tmp, extra_flags), capture_output=True,
                              text=True, cwd=directory)
        compile_ms = (time.perf_counter() - start) * 1000
        if proc.returncode != 0:
            raise RuntimeError(f"{self.name}: el compilador falló:\n{(proc.stderr or proc.stdout)[:4000]}")
        tmp.replace(binary)
        return binary, compile_ms

    # --- ejecución ------------------------------------------------------------
    def run(self, data: bytes, inputs: list, limits: dict | None = None, trace: str = "none",
            timeout_ms: int | None = 60_000, sabotage: str | None = None,
            extra_flags: tuple = ()) -> tuple[dict, list]:
        """Mismo contrato que interp.run. No produce traza.

        Agrega `cost` (spec/BACKEND.md §3.1): medido, no semántico; nunca se compara
        en conformidad."""
        lim = dict(DEFAULT_LIMITS)
        lim.update(limits or {})
        try:
            module = compile_ir(data)
        except InvalidProgram:
            return run_reference(data, inputs, limits)   # frontend compartido
        if not inputs_valid(module, inputs):
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
        args = raw_args(module, inputs)
        binary, compile_ms = self.build(self.emit(module, sabotage), extra_flags)
        argv = [str(binary), str(lim["max_steps"]), str(lim["max_call_depth"]),
                str(lim["max_emits"]), *args]
        returncode, stdout, stderr, cost = run_measured(
            argv, None if timeout_ms is None else timeout_ms / 1000)
        cost["compile_ms"] = None if compile_ms is None else round(compile_ms, 3)
        result["cost"] = cost
        if returncode is None:
            result.update(status="TIMEOUT", code=None, emits=[], steps=None)
            result["return"] = None
            return result, []
        result.update(parse_output(stdout))
        if returncode != 0 or stderr:
            result["backend_stderr"] = stderr[:2000]
            result["backend_exit"] = returncode
            if returncode != 0:
                result["status"] = "BACKEND_CRASH"
        return result, []


def run_measured(argv: list[str], timeout_s: float | None) -> tuple[int | None, str, str, dict]:
    """Ejecuta el binario y mide su costo (spec/BACKEND.md §3.1).

    - wall/user/sys: wait4 sobre el hijo (incluye al lanzador `time` si se usa; ~1 ms).
    - max_rss_kb: lo reporta GNU time (`/usr/bin/time -f %M`). No se puede leer del
      rusage de un hijo de Python: Linux conserva el pico de memoria a través de
      execve, así que mediría al intérprete (~12 MB) y no al binario. Sin GNU time
      queda en None (no medido), nunca estimado.

    Devuelve (returncode, stdout, stderr, cost); returncode None = TIMEOUT.
    """
    rss_file = None
    if GNU_TIME:
        fd, rss_file = tempfile.mkstemp(prefix="isy_rss_")
        os.close(fd)
        argv = [GNU_TIME, "-f", "%M", "-o", rss_file, *argv]
    start = time.perf_counter()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            preexec_fn=_raise_stack_limit, start_new_session=True)
    chunks = {"out": b"", "err": b""}

    def drain(stream, key):
        chunks[key] = stream.read()

    readers = [threading.Thread(target=drain, args=(proc.stdout, "out")),
               threading.Thread(target=drain, args=(proc.stderr, "err"))]
    for t in readers:
        t.start()
    timed_out = threading.Event()
    timer = None
    if timeout_s is not None:
        def kill():
            timed_out.set()
            try:
                os.killpg(proc.pid, 9)   # grupo entero: el lanzador y el binario
            except ProcessLookupError:
                pass
        timer = threading.Timer(timeout_s, kill)
        timer.start()
    _, status, usage = os.wait4(proc.pid, 0)
    wall_ms = (time.perf_counter() - start) * 1000
    proc.returncode = os.waitstatus_to_exitcode(status)   # ya cosechado: que Popen no espere
    if timer is not None:
        timer.cancel()
    for t in readers:
        t.join()
    proc.stdout.close()
    proc.stderr.close()
    max_rss_kb = None
    if rss_file is not None:
        lines = Path(rss_file).read_text().strip().splitlines()
        os.unlink(rss_file)
        if lines and lines[-1].isdigit():
            max_rss_kb = int(lines[-1])
    cost = {"wall_ms": round(wall_ms, 3), "user_ms": round(usage.ru_utime * 1000, 3),
            "sys_ms": round(usage.ru_stime * 1000, 3), "max_rss_kb": max_rss_kb}
    # TIMEOUT solo si el temporizador lo mató; si terminó solo justo a tiempo, cuenta su resultado.
    returncode = None if timed_out.is_set() and proc.returncode == -9 else proc.returncode
    return (returncode, chunks["out"].decode("utf-8", "replace"),
            chunks["err"].decode("utf-8", "replace"), cost)


def _raise_stack_limit() -> None:
    """Pila grande para recursión profunda con arreglos copiados por valor (hasta el hard limit)."""
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    target = hard if hard != resource.RLIM_INFINITY else 1 << 30
    if soft != resource.RLIM_INFINITY and soft < target:
        resource.setrlimit(resource.RLIMIT_STACK, (target, hard))


def missing_features(backend, data: bytes) -> list[str]:
    """Capacidades que `data` necesita y `backend` no declara ([] si es inválido)."""
    try:
        module = compile_ir(data)
    except InvalidProgram:
        return []
    return sorted(features_of(module) - set(backend.features))


def inputs_valid(module: dict, inputs: list) -> bool:
    main = next(f for f in module["functions"] if f["name"] == "main")
    types = [ty_from_json(main["locals"][p]["ty"]) for p in main["params"]]
    return isinstance(inputs, list) and len(inputs) == len(types) \
        and all(parse_canonical(text, t) is not None for text, t in zip(inputs, types))


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
        out.extend(_flatten(value, t))
    return out


def _flatten(value, t) -> list[str]:
    """Valor -> argumentos crudos (§3): arreglos y structs aplanados en orden, str tal cual."""
    if isinstance(t, ArrT):
        return [a for v in value for a in _flatten(v, t.elem)]
    if isinstance(t, StructT):
        return [a for fname, ft in t.fields for a in _flatten(value[fname], ft)]
    if isinstance(t, StrT):
        return [value]
    return [str(int(value))]


def _unescape(payload: str) -> str:
    """Carga de una línea E/R: `\\\\` es una barra invertida y `\\n` un salto de línea."""
    out, i = [], 0
    while i < len(payload):
        if payload[i] == "\\" and i + 1 < len(payload):
            out.append("\n" if payload[i + 1] == "n" else payload[i + 1])
            i += 2
        else:
            out.append(payload[i])
            i += 1
    return "".join(out)


def parse_output(stdout: str) -> dict:
    emits, ret, status, code, steps = [], None, None, None, None
    for line in stdout.split("\n"):
        if line.startswith("E "):
            emits.append(_unescape(line[2:]))
        elif line.startswith("R "):
            ret = _unescape(line[2:])
        elif line.startswith("X "):
            _, status, code, steps = line.split(" ")
            code = None if code == "-" else code
            steps = int(steps)
    if status is None:
        return {"status": "BACKEND_CRASH", "code": None, "emits": emits, "return": ret, "steps": None}
    return {"status": status, "code": code, "emits": emits, "return": ret, "steps": steps}

