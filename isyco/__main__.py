"""CLI: python3 -m isyco run PROGRAMA.isy [--input JSON] [--trace stmt --trace-out F]

Imprime el documento de resultado (JSON canónico, spec §10.2). Código de salida:
0 HALTED · 2 INVALID_PROGRAM · 3 ERROR · 4 LIMIT_REACHED · 5 TIMEOUT · 1 uso/IO.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .interp import DEFAULT_LIMITS, TRACE_LEVELS, canonical_json, run

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
    run_p.add_argument("--trace", choices=TRACE_LEVELS, default="none")
    run_p.add_argument("--trace-out", type=Path)
    args = parser.parse_args(argv)

    try:
        data = args.program.read_bytes()
        inputs = json.loads(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"isyco: {exc}", file=sys.stderr)
        return 1
    limits = {name: getattr(args, name) for name in DEFAULT_LIMITS}
    result, trace = run(data, inputs, limits, args.trace, args.timeout_ms)
    if args.trace_out is not None:
        args.trace_out.write_text("".join(canonical_json(row) + "\n" for row in trace),
                                  encoding="utf-8")
    print(canonical_json(result))
    return EXIT[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
