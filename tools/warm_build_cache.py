"""Precompila en paralelo los binarios del corpus y de los diferenciales.

Uso: python3 tools/warm_build_cache.py [--only c,rust,zig] [--jobs N] [--sabotages]

La caché de build/ es por hash del fuente generado, así que esto no cambia ningún
resultado: solo evita que la suite o el gate compilen uno por uno en frío. Compilar
en paralelo es seguro: cada compilación escribe a temporales propios (pid + hilo) y los
publica con un renombre atómico (isyco/backends/base.py, Backend.build).

Un fuente que muere en el compilador del toolchain no aborta el mapa: `pool.map`
propaga la excepción y se pierden los trabajos ya terminados, justo lo contrario de
dejar la caché caliente. Cada trabajo devuelve su fila del arnés (o `None`) y la
herramienta las imprime todas; sale 1 si alguno falló, para que nadie lea «N binarios
listos» sobre M fuentes muertos.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco.backends import available  # noqa: E402
from isyco.backends.base import missing_features  # noqa: E402
from isyco.conformance import load_all  # noqa: E402
from isyco.difftest import DEC_TYPES, INT_TYPES, program_for, str_program  # noqa: E402
from isyco.errors import InvalidProgram  # noqa: E402
from isyco.harness import intento  # noqa: E402
from isyco.ir_interp import compile_ir  # noqa: E402


def jobs_for(backend, programs, sabotages: bool):
    for data in programs:
        if missing_features(backend, data):
            continue
        try:
            module = compile_ir(data)
        except InvalidProgram:
            continue
        for sabotage in (None, *(backend.sabotages if sabotages else ())):
            yield backend, module, sabotage


def _uno(job):
    """Compila un trabajo y devuelve su fila del arnés: nunca sube el fallo del toolchain."""
    backend, source = job
    _, fr = intento(backend.build, source, fase="warm_build",
                    contexto={"leg": "warm_build", "backend": backend.name})
    return fr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--sabotages", action="store_true", help="también los binarios saboteados")
    args = parser.parse_args()
    only = set(filter(None, args.only.split(",")))
    programs = [c["program"] for c in load_all(ROOT)]
    programs += [program_for(t) for t in INT_TYPES + DEC_TYPES] + [str_program()]
    todo, seen = [], set()
    for name, backend in available().items():
        if only and name not in only:
            continue
        for job in jobs_for(backend, programs, args.sabotages):
            source = backend.emit(job[1], job[2])
            if (name, source) not in seen:        # el mismo binario una sola vez
                seen.add((name, source))
                todo.append((backend, source))
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        filas = [f for f in pool.map(_uno, todo) if f is not None]
    muertos = len(filas)
    codigos = ", ".join(sorted({f["code"] for f in filas})) or "ninguno"
    print(f"{len(todo) - muertos} binarios listos, {muertos} fallaron ({codigos}) en "
          f"{time.perf_counter() - start:.1f} s con {args.jobs} hilos")
    for f in filas:
        print(f"  {f['backend']}: {f['code']}: {(f['detail'] or f['excerpt'])[:160]}",
              file=sys.stderr)
    return 1 if muertos else 0


if __name__ == "__main__":
    raise SystemExit(main())
