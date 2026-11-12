"""La pila que el paquete necesita la reserva el paquete, no quien lo llama (Z2-b).

Z2 nombró la cota de anidamiento (`ast.MAX_EXPR_DEPTH`) y dejó medido un hueco: el fuente del
tope legal —64 niveles— bajaba con pila limpia y moría por `RecursionError` si quien llamaba
traía 300 frames (C8 de `evidence/z2_guard/run_2026-11-04T001913Z.json`). El idioma decidía el
borde, pero el anfitrión seguía decidiendo si lo legal cabía.

El límite de recursión de Python es **absoluto**: cuenta los frames del hilo entero, también los
que ya traía el llamante. `reserva(n)` lo vuelve relativo: mide la profundidad en curso, sube el
límite a `profundidad + n` si hace falta, y lo restaura al salir. Nunca lo baja.

Dos presupuestos, dos ejes:

* todo lo que **recorre un árbol acotado por la cota** —parser, checker con sus clones, bajada
  a IR, validador de IR, censo de capacidades y los cinco emisores— lleva `@con_pila` y pide
  `frames_frontend()`: `FRAMES_POR_NIVEL` por cada nivel de la cota. La forma legal más cara
  medida gasta menos de la mitad (`tests/test_depth.py::LoLegalCabe` lo ata);
* la **ejecución** (`interp.run`, `ir_interp.run_ir`) pide lo que ya pedía, ahora contado desde
  el llamante: `50 * max_call_depth + 1000`.

No captura `RecursionError`: si el presupuesto fuera falso, la excepción sube tal cual y el arnés
la registra como fallo del instrumento, igual que antes.
"""
from __future__ import annotations

import functools
import sys
from contextlib import contextmanager

from . import ast as A

#: Frames reservados por nivel de anidamiento legal. No es normativo: es holgura del anfitrión.
FRAMES_POR_NIVEL = 32


def frames_frontend() -> int:
    """Presupuesto del frontend, leído de la cota **viva** (un sabotaje de la cota lo mueve)."""
    return FRAMES_POR_NIVEL * A.MAX_EXPR_DEPTH


def profundidad() -> int:
    """Frames de Python en curso en este hilo, sin contar este."""
    frame, n = sys._getframe(1), 0
    while frame is not None:
        n += 1
        frame = frame.f_back
    return n


@contextmanager
def reserva(frames: int):
    """Garantiza `frames` de pila por debajo del llamante mientras dura el bloque."""
    antes = sys.getrecursionlimit()
    sys.setrecursionlimit(max(antes, profundidad() + frames))
    try:
        yield
    finally:
        sys.setrecursionlimit(antes)


def con_pila(fn):
    """Decorador: `fn` recorre un árbol acotado por la cota y corre con la reserva del frontend."""
    @functools.wraps(fn)
    def envuelta(*args, **kwargs):
        with reserva(frames_frontend()):
            return fn(*args, **kwargs)
    return envuelta
