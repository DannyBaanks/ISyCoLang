"""Especializaciones de CORE v0.5 (V6/V6-bis): una copia por resolución de capacidad.

`fn pad(s: str, ancho: i64)` no fija la capacidad de `s`: la fija cada sitio de
llamada. El checker resuelve la capacidad concreta (desde el tipo real del
argumento en V6, desde la capacidad esperada en el retorno en V6-bis) y pide aquí
la copia correspondiente. El original con `str` pelado nunca se chequea y nunca
llega a la IR, así que en la IR solo existen `str<N>` acotados: no hay centinela
(0, -1, None, 65536) que signifique «abierto» en ningún lado.

Dos llamadas con anchos distintos conviven como dos funciones distintas; la
definición fuente sigue siendo una sola.
"""
from __future__ import annotations

import copy

from . import ast as A
from .types import ContextStrT, StrT

#: CORE v0.5 §7: es un literal normativo del spec, no un límite configurable — igual que
#: `types.MAX_STR`. Cambiarlo aquí cambia el idioma, no un ajuste del toolchain.
MAX_CLONES_PER_DEFINITION = 256


def contextual_slots(fn: A.Fn) -> list[int]:
    """Posiciones de los parámetros escritos `str` sin capacidad."""
    return [i for i, (_, ty, _) in enumerate(fn.params) if isinstance(ty, ContextStrT)]


def is_contextual(fn: A.Fn) -> bool:
    """¿La firma de `fn` difiere la alguna capacidad?"""
    return bool(contextual_slots(fn)) or isinstance(fn.ret, ContextStrT)


def spec_name(name: str, widths: tuple[int, ...], ret_width: int | None) -> str:
    """Identificador interno de la especialización: inyectivo y válido como identificador.

    Se añade como segmentos extra del nombre calificado (`pad.8`, `geo.pad.8.16`,
    `pad.8.r16`), así que `backends/base.py:fn_ident` lo convierte en un nombre legal
    en C/Rust/Zig sin que ningún backend conozca V6. La codificación es inyectiva para
    una base fija: los anchos son decimales sin ceros a la izquierda y el del retorno
    empieza con `r`, así que la secuencia de segmentos se lee sola (`pad.1.23` solo
    puede salir de (pad, [1, 23])). Que la base no termine en un segmento numérico lo
    da el léxico: un identificador empieza en letra o `_`, y el prefijo de módulo
    (`geo.punto.`) nunca es el último segmento.
    """
    parts = [name] + [str(w) for w in widths]
    if ret_width is not None:
        parts.append(f"r{ret_width}")
    return ".".join(parts)


def make_clone(fn: A.Fn, name: str, widths: tuple[int, ...], ret_width: int | None) -> A.Fn:
    """Copia de `fn` con las capacidades diferidas sustituidas por las resueltas."""
    clone = copy.deepcopy(fn)
    clone.name = name
    for slot, width in zip(contextual_slots(fn), widths):
        pname, _, pat = clone.params[slot]
        clone.params[slot] = (pname, StrT(width), pat)
    if isinstance(clone.ret, ContextStrT):
        clone.ret = StrT(ret_width)
    return clone
