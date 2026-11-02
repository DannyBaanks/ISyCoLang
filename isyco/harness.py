"""Arnés: un fallo del instrumento se registra como dato, no aborta la corrida.

Vive en `isyco/` porque lo necesitan tanto `difftest.py` (el motor del diferencial) como
las herramientas de `tools/`, y `isyco/` no puede importar `tools/`. Precedente de
soporte-de-prueba dentro del paquete: `isyco/difftest.py`, `isyco/conformance.py`.

Dos códigos, y la distinción es lo que importa (hallazgo 13 de `docs/EVIDENCE_MATRIX.md`):

- `TOOLCHAIN_BUILD_FAIL` — murió el compilador del toolchain al armar el binario. El
  programa puede ser perfectamente legal: lo que falló es una pata del banco de pruebas.
- `HARNESS_INTERNAL` — el instrumento explotó por algo que este módulo no sabe clasificar.

Ninguno se parece a un resultado de backend: `intento` devuelve `(None, fila)` y el
llamador **no** compara nada, así que un crash no puede escribirse en `failures` ni en
`diffs` (spec/BACKEND.md: la semántica normativa es el intérprete de referencia).
"""
from __future__ import annotations

import time

from .backends.base import ToolchainBuildFailure
from .errors import InvalidProgram

SCHEMA = "isyco.harness/1"
CODES = ("TOOLCHAIN_BUILD_FAIL", "HARNESS_INTERNAL")
DETAIL_CHARS = 130      # el mismo presupuesto con que v05_p4_probe.py resume un fallo
EXCERPT_CHARS = 400     # el que ya usaba Backend.build() para el stderr del compilador


def detalle(texto: str) -> str:
    """La línea `error:` del mensaje, o la última no vacía: lo que hace útil un crash.

    Un fallo sin la línea del compilador no es reproducible, y el mensaje completo son
    cientos de líneas de volcado que no caben en un recibo.
    """
    lineas = [x.strip() for x in texto.splitlines() if x.strip()]
    return next((x for x in lineas if "error:" in x), lineas[-1] if lineas else "") \
        [:DETAIL_CHARS]


def fila(code: str, exc: BaseException, fase: str, contexto: dict | None = None,
         ms: float = 0.0) -> dict:
    """Forma fija de una fila: pierna, fase, código, excepción, lo que dijo y lo medido.

    `contexto` se vuelca tal cual (con `leg` como pierna) para que cada llamador deje las
    coordenadas del caso que mató la pierna — tipo, operador, entrada, hash del programa—.
    """
    contexto = dict(contexto or {})
    texto = getattr(exc, "output", None) or str(exc)
    registro = {"leg": contexto.pop("leg", ""), "phase": fase, "code": code,
                "exception": type(exc).__name__, "detail": detalle(texto),
                "excerpt": str(exc)[:EXCERPT_CHARS], "ms": round(ms, 1), **contexto}
    key = getattr(exc, "key", None)
    if key is not None:
        # El nombre del artefacto bajo `build/` (hash de backend + toolchain + banderas +
        # fuente). Sin campo propio habría que leérselo del stderr del compilador.
        registro["build_key"] = key
    return registro


def intento(f, *args, fase: str, contexto: dict | None = None, **kw):
    """`(resultado, None)` si nada explotó; `(None, fila)` si falló el instrumento.

    `InvalidProgram` **no** se captura: que el frontend rechace un programa es conducta del
    idioma y tiene que subir con su traceback, no quedarse como una fila en el recibo. Todo
    lo demás se clasifica en los dos códigos de arriba y se devuelve como dato, con el
    tiempo que llevó el intento para que el recibo no pierda la medición.
    """
    start = time.perf_counter()
    try:
        return f(*args, **kw), None
    except InvalidProgram:
        raise
    except ToolchainBuildFailure as exc:
        return None, fila("TOOLCHAIN_BUILD_FAIL", exc, fase, contexto,
                          (time.perf_counter() - start) * 1000)
    except Exception as exc:                       # noqa: BLE001 — el fallo es el dato
        return None, fila("HARNESS_INTERNAL", exc, fase, contexto,
                          (time.perf_counter() - start) * 1000)
