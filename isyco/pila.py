"""La pila que el paquete necesita la reserva el paquete, no quien lo llama (Z2-b).

Z2 nombró la cota de anidamiento (`ast.MAX_EXPR_DEPTH`) y dejó medido un hueco: el fuente del
tope legal —64 niveles— bajaba con pila limpia y moría por `RecursionError` si quien llamaba
traía 300 frames (C8 de `evidence/z2_guard/run_2026-11-04T001913Z.json`). El idioma decidía el
borde, pero el anfitrión seguía decidiendo si lo legal cabía.

El límite de recursión de Python es **absoluto**: cuenta los frames del hilo entero, también los
que ya traía el llamante. `reserva(n)` lo vuelve relativo: mide la profundidad en curso, sube el
límite a `profundidad + n` si hace falta, y lo restaura al salir. Nunca lo baja.

Dos presupuestos, dos ejes, y los dos salen de las cotas nombradas del idioma
(`ast.MAX_EXPR_DEPTH`, Z2, y `ast.MAX_STMT_DEPTH`, Z3):

* todo lo que **recorre un árbol acotado por las cotas** —parser, checker con sus clones, bajada
  a IR, validador de IR, censo de capacidades y los cinco emisores— lleva `@con_pila` y pide
  `frames_frontend()`: `FRAMES_POR_NIVEL` por cada nivel de las dos cotas. La forma legal más
  cara medida gasta menos de la mitad (`tests/test_depth.py::LoLegalCabe` lo ata);
* la **ejecución** (`interp.run`, `ir_interp.run_ir`) pide `frames_ejecucion(max_call_depth)`:
  `FRAMES_EJECUCION_POR_NIVEL` por nivel de las dos cotas **por cada llamada** del programa. El
  `50 * max_call_depth + 1000` anterior no era una cota: una llamada recursiva dentro de 60
  `if` anidados gasta 126 frames por llamada y moría dentro de `max_call_depth`.

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


#: Frames reservados por nivel de anidamiento legal **en cada llamada** del programa que corre.
FRAMES_EJECUCION_POR_NIVEL = 4


def niveles() -> int:
    """Niveles legales de anidamiento, leídos de las cotas **vivas** (un sabotaje las mueve)."""
    return A.MAX_EXPR_DEPTH + A.MAX_STMT_DEPTH


def frames_frontend() -> int:
    """Presupuesto de un recorrido de árbol: expresión al tope dentro de sentencias al tope."""
    return FRAMES_POR_NIVEL * niveles()


def frames_ejecucion(max_call_depth: int) -> int:
    """Presupuesto de la ejecución: cada llamada puede estar al fondo de las dos cotas."""
    return FRAMES_EJECUCION_POR_NIVEL * niveles() * max_call_depth + frames_frontend()


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
