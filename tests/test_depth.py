"""Z2 (CORE v0.5 §7): la cota de anidamiento de una expresión la pone el idioma, no el anfitrión.

Antes de nombrar el número se midieron las fronteras (Z2 en `docs/OPEN_QUESTIONS_P1_P4.md`):
sin guarda, la cadena de paréntesis moría por `RecursionError` en 89 pares con pila limpia y en
62 con 300 frames del llamante encima, y la cadena izquierda de `len(s)` agotaba la pila en el
`deepcopy` del clon de V6 (985 de 999 frames). En los dos casos la señal era `RecursionError`:
sin código, sin número y sin por qué, y la pagaba la referencia normativa (C6 y C8 de
`evidence/z2_guard/`, con la guarda levantada a 200 para que no estorbiera la medición).

La guarda se mide dos veces porque anidar tiene dos caras distintas:

* el **parser** cuenta los niveles que de verdad le bajan frames —paréntesis, argumentos de
  llamada, operadores prefijos—;
* el **checker** mide la cadena de nodos del AST, porque una suma izquierda de k términos se
  construye en un bucle y no hace bajar ni un frame al parser.

El `expected` de cada test está escrito sobre la regla, no copiado de una corrida.

**Z2-b (2026-11-12).** La cota decidía el borde, pero el fuente del tope legal seguía muriendo si
quien llamaba traía 300 frames (C8). `isyco/pila.py` reserva la pila del paquete contada desde el
llamante; `LoLegalCabe` fija que lo legal baja, se valida, se emite y ejecuta con 300 y 3 000
frames encima, y que es la reserva —no el anfitrión— la que lo consigue.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from isyco import ast as A                                     # noqa: E402
from isyco import pila                                         # noqa: E402
from isyco.backends import registry                            # noqa: E402
from isyco.backends.base import features_of                    # noqa: E402
from isyco.checker import expr_depth                           # noqa: E402
from isyco.errors import InvalidProgram                        # noqa: E402
from isyco.interp import run                                   # noqa: E402
from isyco.ir_interp import compile_ir, run_via_ir             # noqa: E402
from isyco.modules import load_program                         # noqa: E402

N = A.MAX_EXPR_DEPTH
KEYS = ("status", "code", "emits", "return")


def parentesis(pares: int) -> bytes:
    """`pares` anidados: el parser baja un nivel por par, el AST queda en profundidad 1."""
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'(' * pares}1{')' * pares};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def cadena(terminos: int) -> bytes:
    """Suma izquierda de k términos: k niveles de AST sin que el parser recursione."""
    return (f"isyco 0.5\n\nfn main() -> i64 !emit {{\n"
            f"    let x: i64 = {' + '.join(['1'] * terminos)};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def pelado(terminos: int) -> bytes:
    """La misma cadena sobre un `str` pelado: cota con el clon de V6 puesto."""
    return (f'isyco 0.5\n\nfn cuanto(s: str) -> i64 {{\n'
            f'    return {" + ".join(["len(s)"] * terminos)};\n}}\n\n'
            f'fn main() -> i64 !emit {{\n    emit cuanto("hola");\n'
            f'    return {4 * terminos};\n}}\n').encode()


def resultado(fuente: bytes) -> dict:
    doc, _ = run(fuente, [])
    return {k: doc[k] for k in KEYS}


#: (legal en el borde, un nivel más arriba): las tres caras de la misma cota
BORDES = ((parentesis(N - 1), parentesis(N)),
          (cadena(N), cadena(N + 1)),
          (pelado(N - 1), pelado(N)))


class CotaNombrada(unittest.TestCase):
    """El número es un literal de la spec, no una consecuencia del anfitrión."""

    def test_la_constante_es_un_literal_del_spec(self):
        self.assertEqual(A.MAX_EXPR_DEPTH, 64)

    def test_el_borde_es_exclusivo_por_debajo(self):
        """Único instrumento del off-by-one: `>` y no `>=`. Nivel N se acepta, N+1 no."""
        forlegal, fallos = zip(*BORDES)
        for fuente in forlegal:
            with self.subTest(fuente=fuente[:24]):
                self.assertEqual(resultado(fuente)["status"], "HALTED")
        for fuente in fallos:
            with self.subTest(fuente=fuente[:24]):
                visto = resultado(fuente)
                self.assertEqual(visto["status"], "INVALID_PROGRAM")
                self.assertEqual(visto["code"], "SPEC_LIMIT")
                self.assertEqual((visto["emits"], visto["return"]), ([], None))

    def test_las_tres_caras_llegan_al_mismo_nivel(self):
        """La cota es de niveles de expresión, no de una forma concreta del fuente."""
        niveles = [expr_depth(load_program(parentesis(N - 1)))[0],
                   expr_depth(load_program(cadena(N)))[0],
                   expr_depth(load_program(pelado(N - 1)))[0]]
        self.assertEqual(niveles[1:], [N, N])          # AST: 64 y 64
        self.assertEqual(niveles[0], 1)                 # paréntesis: no son nodos
        compile_ir(parentesis(N - 1))                   # y aun así la guarda del parser la frena


class LaGuardaGanaAlAnfitrion(unittest.TestCase):
    """Con la pila que traen los caminos del paquete, el rechazo es del idioma."""

    def con_frames(self, n: int, f):
        return self.con_frames(n - 1, f) if n else f()

    def test_un_llamante_hondo_sigue_obteniendo_spec_limit(self):
        # Medido (C4 de `tools/z2_guard_probe.py`): la CLI llega al frontend con 6 frames y un
        # test del paquete con 10. Aquí se prueba con 100 —diez veces el margen real— y la señal
        # sigue siendo SPEC_LIMIT.
        for _, fuente in BORDES:
            with self.subTest(fuente=fuente[:24]):
                self.assertEqual(self.con_frames(100, lambda: resultado(fuente))["code"],
                                 "SPEC_LIMIT")

    def test_la_guarda_no_agota_la_pila_que_mide(self):
        hondo = lambda: expr_depth(load_program(cadena(N)))
        self.assertEqual(hondo()[0], N)
        self.assertEqual(self.con_frames(400, hondo)[0], N)


class EsLaGuardaLoQueRechaza(unittest.TestCase):
    """Sabotaje: mover la constante mueve el borde. Si el rechazo viniera de otro lado, no."""

    def test_subir_la_cota_devuelve_la_aceptacion(self):
        with mock.patch.object(A, "MAX_EXPR_DEPTH", 200):
            for _, fuente in BORDES:
                with self.subTest(fuente=fuente[:24]):
                    self.assertEqual(resultado(fuente)["status"], "HALTED")

    def test_bajar_la_cota_rechaza_lo_que_hoy_es_legal(self):
        self.assertEqual(resultado(cadena(6))["status"], "HALTED")
        with mock.patch.object(A, "MAX_EXPR_DEPTH", 5):
            self.assertEqual(resultado(cadena(6))["code"], "SPEC_LIMIT")


def llamadas(niveles: int) -> bytes:
    """`f(f(…f(1)…))`: la cara legal más cara medida (12,2 frames por nivel en el frontend)."""
    return (f"isyco 0.5\n\nfn f(a: i64) -> i64 {{\n    return a;\n}}\n\n"
            f"fn main() -> i64 !emit {{\n"
            f"    let x: i64 = {'f(' * niveles}1{')' * niveles};\n"
            f"    emit x;\n    return x;\n}}\n").encode()


def recursivo(hondo: int) -> bytes:
    """Un programa que se llama a sí mismo `hondo` veces: gasta pila de **ejecución**."""
    return (f"isyco 0.5\n\nfn baja(n: i64) -> i64 {{\n    if n == 0 {{\n        return 0;\n    }}\n"
            f"    return 1 + baja(n - 1);\n}}\n\n"
            f"fn main() -> i64 !emit {{\n    emit baja({hondo});\n    return 0;\n}}\n").encode()


#: Las cuatro caras en su tope legal: las tres del corpus más la más cara.
TOPES = {"parentesis": parentesis(N - 1), "cadena": cadena(N), "pelado": pelado(N - 1),
         "llamadas": llamadas(N - 1)}


def con_llamante(frames: int, f):
    """Corre `f` con `frames` frames encima y un límite que deja solo 40 de aire.

    Es el llamante hostil: no llega «con pila de sobra», llega casi agotado. Lo que pase debajo
    lo decide la reserva del paquete o no lo decide nadie.
    """
    def baja(n):
        return baja(n - 1) if n else f()
    antes = sys.getrecursionlimit()
    sys.setrecursionlimit(pila.profundidad() + frames + 40)     # exacto: también puede bajarlo
    try:
        return baja(frames)
    finally:
        sys.setrecursionlimit(antes)


def todo_el_camino(fuente: bytes) -> list:
    """Baja, valida, censa, emite por cada backend que lo declara y ejecuta por las dos rutas."""
    modulo = compile_ir(fuente)
    for backend in registry().values():
        if features_of(modulo) <= set(backend.features):
            backend.emit(modulo)
    return [run(fuente, [])[0]["status"], run_via_ir(fuente, [])[0]["status"]]


class LoLegalCabe(unittest.TestCase):
    """Z2-b: la pila que trae quien llama no decide si un programa legal baja."""

    def test_el_tope_legal_recorre_todo_el_camino_con_cualquier_llamante(self):
        for frames in (0, 300, 3000):
            for cara, fuente in TOPES.items():
                with self.subTest(cara=cara, frames=frames):
                    self.assertEqual(con_llamante(frames, lambda: todo_el_camino(fuente)),
                                     ["HALTED", "HALTED"])

    def test_el_rechazo_sigue_siendo_del_idioma_con_cualquier_llamante(self):
        for frames in (300, 3000):
            for _, fuente in BORDES:
                with self.subTest(fuente=fuente[:24], frames=frames):
                    self.assertEqual(con_llamante(frames, lambda: resultado(fuente))["code"],
                                     "SPEC_LIMIT")

    def test_sin_la_reserva_vuelve_el_muro_del_anfitrion(self):
        """Sabotaje: con presupuesto 0 el tope legal muere con 300 frames, como medía C8."""
        fuente = TOPES["parentesis"]
        with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
            with self.assertRaises(RecursionError):
                con_llamante(300, lambda: compile_ir(fuente))
        self.assertEqual(con_llamante(300, lambda: compile_ir(fuente))["schema"][:6], "isy-ir")

    def test_el_validador_y_los_emisores_tambien_dependian_del_llamante(self):
        """El hueco no era solo del frontend: la IR es un árbol y sus recorridos bajan frames."""
        modulo = compile_ir(TOPES["cadena"])
        recorridos = {"features_of": lambda: features_of(modulo),
                      **{n: (lambda b=b: b.emit(modulo)) for n, b in registry().items()}}
        for nombre, recorrer in recorridos.items():
            with self.subTest(recorrido=nombre):
                with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
                    with self.assertRaises(RecursionError):
                        con_llamante(300, recorrer)
                con_llamante(300, recorrer)

    def test_el_presupuesto_dobla_el_coste_medido(self):
        """La holgura no es fe: la cara más cara gasta menos de la mitad de lo reservado."""
        def coste(fuente: bytes) -> int:
            base, lo, hi = pila.profundidad(), 5, pila.frames_frontend()
            antes = sys.getrecursionlimit()
            while lo + 1 < hi:
                medio = (lo + hi) // 2
                sys.setrecursionlimit(base + medio)
                try:
                    with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
                        todo_el_camino(fuente)
                    hi = medio
                except RecursionError:
                    lo = medio
                finally:
                    sys.setrecursionlimit(antes)
            return hi
        costes = {cara: coste(fuente) for cara, fuente in TOPES.items()}
        self.assertEqual(max(costes, key=costes.get), "llamadas", costes)
        self.assertLessEqual(2 * max(costes.values()), pila.frames_frontend(), costes)
        self.assertGreater(max(costes.values()), 700, costes)     # y no es un coste de juguete

    def test_el_limite_del_llamante_queda_como_estaba(self):
        antes = sys.getrecursionlimit()
        todo_el_camino(TOPES["llamadas"])
        self.assertEqual(sys.getrecursionlimit(), antes)
        self.assertEqual(resultado(BORDES[0][1])["code"], "SPEC_LIMIT")    # sale por excepción
        self.assertEqual(sys.getrecursionlimit(), antes)
        with mock.patch.object(pila, "FRAMES_POR_NIVEL", 0):
            with self.assertRaises(RecursionError):
                con_llamante(300, lambda: compile_ir(TOPES["parentesis"]))
        self.assertEqual(sys.getrecursionlimit(), antes)                   # y por RecursionError

    def test_la_ejecucion_tambien_cuenta_desde_el_llamante(self):
        """`50 * max_call_depth + 1000` era absoluto: un llamante más hondo que eso lo anulaba."""
        fuente, limites = recursivo(200), {"max_call_depth": 256}
        corre = lambda: run(fuente, [], limites)[0]
        self.assertEqual(corre()["emits"], ["200"])
        self.assertEqual(con_llamante(14000, corre)["emits"], ["200"])
        with mock.patch.object(pila, "profundidad", lambda: 0):           # sabotaje: absoluto
            with self.assertRaises(RecursionError):
                con_llamante(14000, corre)


class LaPoblacionQuedaDebajo(unittest.TestCase):
    """Tripwire: ningún programa del repo roza la cota; si uno la cruza, esto lo nombra."""

    FUENTES_Z2 = tuple(f"{n}_" for n in range(449, 455))   # viven en la cota: no son población

    def test_toda_fuente_del_repo_cabe_bajo_la_cota(self):
        """Se miden los programas que la spec acepta; los rechazos a propósito no tienen AST."""
        censadas, profunda, donde = 0, 0, ""
        for carpeta in ("conformance", "conformance_v0.2", "conformance_v0.3",
                        "conformance_v0.4", "conformance_v0.5", "dogfood"):
            for ruta in sorted((ROOT / "programs" / carpeta).rglob("*.isy")):
                if ruta.parent.name == "gemelos":
                    continue
                esperado = ruta.with_suffix(".expect.json")
                if esperado.exists() and not self.se_acepta(esperado):
                    continue
                try:
                    hondo, _ = expr_depth(load_program(ruta.read_bytes()))
                except InvalidProgram:
                    continue                    # rechazos a propósito: no tienen AST que medir
                censadas += 1
                self.assertLessEqual(hondo, A.MAX_EXPR_DEPTH, str(ruta))
                if not ruta.name.startswith(self.FUENTES_Z2) and hondo > profunda:
                    profunda, donde = hondo, str(ruta.relative_to(ROOT))
        self.assertGreaterEqual(censadas, 150, "la población censada cambió sin decir nada")
        self.assertLessEqual(profunda, 8, f"la población real se pasó de lo censado: {donde}")

    @staticmethod
    def se_acepta(expect: Path) -> bool:
        return json.loads(expect.read_text())["expected"]["status"] != "INVALID_PROGRAM"


if __name__ == "__main__":
    unittest.main()
