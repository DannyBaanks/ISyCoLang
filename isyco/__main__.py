"""CLI de ISyCoLang.

    python3 -m isyco run PROGRAMA.isy [--input JSON] [--via ast|ir|c|rust|zig|pydecimal] [--trace stmt --trace-out F]
    python3 -m isyco ir  PROGRAMA.isy        # imprime la ISY-IR canónica

`run` imprime el documento de resultado (JSON canónico, spec §10.2); con
`--via c|rust|zig|pydecimal` compila a un binario nativo (o al programa Python
generado) y no produce traza. Código de salida:
0 HALTED · 2 INVALID_PROGRAM · 3 ERROR · 4 LIMIT_REACHED · 5 TIMEOUT · 1 uso/IO o fallo del backend.
`ir` sale con 0 si el programa es válido y 2 si no.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import InvalidProgram
from .backends import registry as backend_registry
from .interp import DEFAULT_LIMITS, TRACE_LEVELS, canonical_json, run
from .ir import canonical_bytes
from .ir_interp import compile_ir, run_via_ir
from .lexer import header_version
from .source import Bundle

EXIT = {"HALTED": 0, "INVALID_PROGRAM": 2, "ERROR": 3, "LIMIT_REACHED": 4, "TIMEOUT": 5}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="isyco")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="ejecutar un programa .isy")
    run_p.add_argument("program", type=Path)
    run_p.add_argument("--input", default="[]", help="arreglo JSON de strings canónicos")
    for name, default in DEFAULT_LIMITS.items():
        run_p.add_argument("--" + name.replace("_", "-"), type=int, default=default)
    run_p.add_argument("--timeout-ms", type=int, default=60_000)
    run_p.add_argument("--via", choices=("ast", "ir", *backend_registry()), default="ast",
                       help="ast = referencia; ir = intérprete de ISY-IR; "
                            "c/rust/zig/pydecimal = binario compilado")
    run_p.add_argument("--trace", choices=TRACE_LEVELS, default="none")
    run_p.add_argument("--trace-out", type=Path)
    ir_p = sub.add_parser("ir", help="imprimir la ISY-IR canónica de un programa")
    ir_p.add_argument("program", type=Path)
    args = parser.parse_args(argv)

    try:
        data = args.program.read_bytes()
        if header_version(data.decode("utf-8", "replace")) == "0.4":
            # CORE v0.4 P1: los módulos se buscan desde la carpeta del archivo principal.
            data = Bundle.from_path(args.program)
        inputs = json.loads(args.input) if args.cmd == "run" else None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"isyco: {exc}", file=sys.stderr)
        return 1

    if args.cmd == "ir":
        try:
            module = compile_ir(data)
        except InvalidProgram as err:
            print(f"INVALID_PROGRAM({err.code}) at {err.at}: {err.detail}", file=sys.stderr)
            return 2
        sys.stdout.write(canonical_bytes(module).decode("utf-8") + "\n")
        return 0

    limits = {name: getattr(args, name) for name in DEFAULT_LIMITS}
    if args.via not in ("ast", "ir"):
        from .backends import registry
        backend = registry().get(args.via)
        if backend is None or not backend.toolchain():
            print(f"isyco: toolchain de {args.via} no instalado", file=sys.stderr)
            return 1
        runner = backend.run
    else:
        runner = run_via_ir if args.via == "ir" else run
    result, trace = runner(data, inputs, limits, args.trace, args.timeout_ms)
    if args.trace_out is not None:
        args.trace_out.write_text("".join(canonical_json(row) + "\n" for row in trace),
                                  encoding="utf-8")
    print(canonical_json(result))
    return EXIT.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
