"""Backends de ISyCoLang: reciben ISY-IR validada (spec/IR.md, spec/BACKEND.md)."""
from __future__ import annotations


def registry() -> dict:
    """Backends registrados (nombre -> instancia), aunque su toolchain no esté instalado."""
    from .c import BACKEND as C
    from .rust import BACKEND as RUST
    from .zig import BACKEND as ZIG
    from .pydecimal import BACKEND as PYDECIMAL
    return {b.name: b for b in (C, RUST, ZIG, PYDECIMAL)}


def available() -> dict:
    """Solo los backends cuyo toolchain está instalado en este host."""
    return {name: b for name, b in registry().items() if b.toolchain()}
